# Share-of-Voice Agent — Implementierungsplan

Stand: vor Implementierung. Dieses Dokument ist die vollständige Spezifikation für den SoV-Agent im Celonis-CI-Projekt und kann eigenständig (z.B. in einem neuen Chat) als Implementierungsgrundlage verwendet werden.

---

## 1. Zweck des Agents

Der Share-of-Voice-Agent berechnet, **welchen Aufmerksamkeitsanteil jeder getrackte Wettbewerber** im Vergleich zu den anderen erhält. Er recherchiert dafür **keine neuen Daten**, sondern nutzt die bereits gescrapten Research-Daten und reichert sie um Themen-, Regions- und Relevanz-Klassifikationen an.

**Ausgangsfrage:** „Welche Unternehmen erhalten in welchen Themen und Regionen wie viel Sichtbarkeit, und wie verändert sich das über die Zeit?"

**Output:** Eine Tabelle `sov_mentions` mit klassifizierten Mentions. Aus dieser wird das Dashboard via SQL-Aggregation versorgt (kein eigener Aggregat-Speicher im MVP).

---

## 2. Architektur-Entscheidungen (alle getroffenen)

| Entscheidung | Wert | Begründung |
|---|---|---|
| Architektur | Eigenständiger Agent außerhalb von `BrandPipelineState` | SoV ist eine relative Metrik über alle Wettbewerber, nicht pro Brand |
| Datenquellen MVP | **News + SEO** | Beide liefern komplementäre Signale ohne Überlappung zum Geo-Agent |
| Wettbewerberliste | Aus DB-Tabelle `competitors` (13 Einträge) | Single Source of Truth, identisch zum Research-Scheduler |
| Themen | 9 Themen (siehe Abschnitt 5) | Klein genug für saubere Klassifikation, an GEO-Begriffen orientiert |
| Region | DACH / Europe / NA / APAC / Global | Standard-Cluster |
| Region-Filter | Nur für News sinnvoll; SEO ist „Global" | SEO-Rankings sind im Code nicht lokalisiert |
| Zeit-Buckets | Monat (`YYYY-MM`) | Reicht für MVP-Trends, später erweiterbar |
| Tabellen | Nur `sov_mentions`, kein `sov_aggregates` | Aggregate via SQL on-the-fly bei realistischem Volumen ausreichend schnell |
| Duplikat-Schutz | `UNIQUE (company, source_type, url)` + `ON CONFLICT DO NOTHING` | Erlaubt überlappende Runs ohne Doppelzählung |
| Klassifikation | Nur neue (noch nicht gespeicherte) URLs an das LLM | Spart Tokens bei wiederholten Runs |
| Relevanz | Binär (`is_relevant: bool`) | Statt 4-Stufen-Skala wie beim Geo-Agent |
| LLM | `gpt-4o-mini`, `temperature=0.0`, `with_structured_output(strict=True)` | Identisch zum Geo-Agent Phase 2 |
| Parallelisierung | `asyncio.Semaphore(5)` | Identisch zum Geo-Agent |
| Synthese-Narrative | Weggelassen | MVP braucht keinen LLM-generierten Briefing-Text |
| Multi-LLM-Klassifikation | Weggelassen | Nur ein Modell |
| 3-Tier-Keywords | Weggelassen | Flache Themenliste reicht |
| Eigenständiger Dedupe-Knoten | Weggelassen | URL-Vergleich beim Laden reicht |
| Trigger | Manueller API-Call | Scheduler/Auto-Trigger später |

---

## 3. Datenquellen (Quellen-Code im Projekt)

### News
- **Loader-Node:** [backend/app/agents/research/nodes/news.py](backend/app/agents/research/nodes/news.py)
- **DB-Tabelle:** `research_snapshots` mit `node='news'`
- **Pro Artikel verfügbar:** `company`, `url`, `title`, `text`, `summary`, `published_date`, `source_type` (finnhub / serper / firecrawl), `image`, `author`
- **Typisches Volumen:** 20–100 Artikel pro Wettbewerber pro Run

### SEO
- **Loader-Node:** [backend/app/agents/research/nodes/seogeo.py](backend/app/agents/research/nodes/seogeo.py)
- **DB-Tabelle:** `research_snapshots` mit `node='seogeo'`, Sub-Feld `seo`
- **Keyword-Liste:** 28 Begriffe in [seogeo.py:18-47](backend/app/agents/research/nodes/seogeo.py#L18-L47)
- **Pro Sighting verfügbar:** `company`, `keyword`, `company_mentioned`, `position` (Rank 1–50), `link`, `url`
- **Filter:** Nur Sightings mit `company_mentioned=true` werden Mentions
- **Datum:** Es gibt kein Veröffentlichungsdatum → wir verwenden `run_at` des Research-Snapshots

### Nicht verwendete Quellen (im MVP)
- **GEO** (`brand_geo_sightings`): wird vom dedizierten Geo-Intelligence-Agent abgedeckt, würde dasselbe Signal nochmal zeigen
- **Events** (`research_snapshots` node='events'): später möglich, hat schon ein `event_topic`-Feld
- **YouTube** (`research_snapshots` node='youtube'): später möglich

---

## 4. Wettbewerberliste

Die Liste liegt **in der DB**, nicht im Code:
- **Migration:** [backend/scripts/migrations/009_competitors.sql](backend/scripts/migrations/009_competitors.sql)
- **Tabelle:** `competitors` mit Feldern `domain`, `name`, `active`
- **Helper:** [backend/app/agents/shared/competitors.py](backend/app/agents/shared/competitors.py) — `get_competitor_domains()` und `get_competitor_names()`
- **Aktuelle 13 Einträge:** Celonis, Anthropic, OpenAI, Databricks, SAP Signavio, Palantir, ServiceNow, ARIS, IBM, UiPath, Appian, Apromore, Microsoft Fabric

Der SoV-Agent ruft `get_competitor_domains()` beim Start auf und iteriert über die zurückgegebenen Domains.

---

## 5. Themenliste

```
1. Process Mining
2. Process Intelligence
3. AI & GenAI
4. Agentic AI
5. Automation
6. Digital Transformation
7. Supply Chain
8. ERP & SAP
9. Other
```

Diese Liste muss **identisch** an drei Stellen vorkommen:
1. `backend/app/agents/sov/themes.py` (Python-Konstante)
2. `backend/app/prompts/sov/classification.py` (Pydantic-Schema, `Literal[...]`)
3. Im LLM-Prompt-Text (damit das Modell die Liste sieht)

---

## 6. Pipeline-Schritte

Ein Run durchläuft drei Schritte (vereinfacht ggü. Geo-Agent):

```
Schritt 1: load_mentions
  └─ liest research_snapshots für alle 13 Wettbewerber × {news, seogeo}
  └─ baut Mention-Objekte (Pydantic) im State
  └─ filtert URLs raus, die bereits in sov_mentions existieren

Schritt 2: classify
  └─ heuristisches Pre-Filter (Sprache → Region, SEO-Keyword → Theme-Kandidat)
  └─ pro Mention: LLM-Call mit SovClassificationOutput-Schema
  └─ ergänzt themes, region, is_relevant im State

Schritt 3: persist
  └─ bulk-insert aller neuen Mentions in sov_mentions
  └─ ON CONFLICT (company, source_type, url) DO NOTHING
```

Kein Aggregations-Knoten. Aggregate werden später vom API-Endpoint via SQL berechnet.

---

## 7. Modulstruktur

```
backend/app/agents/sov/
├── __init__.py
├── state.py                          ← SovPipelineState (TypedDict)
├── themes.py                         ← THEMES = [...] und THEMES_LITERAL
├── graph.py                          ← LangGraph: load → classify → persist
├── nodes/
│   ├── __init__.py
│   ├── load_mentions.py              ← Reader für News + SEO
│   ├── classify.py                   ← LLM-Klassifikation
│   └── persist.py                    ← Bulk-Insert
└── repositories/
    ├── __init__.py
    └── sov_repository.py             ← insert_sov_mentions(rows)

backend/app/prompts/sov/
├── __init__.py
└── classification.py                 ← SovClassificationOutput + Prompt-Builder

backend/scripts/migrations/
└── 0XX_sov_mentions.sql              ← die einzige neue Migration

backend/app/api/
└── sov.py                            ← POST /sov/run (MVP), Lese-Endpoints später

backend/tests/unit/
├── test_sov_load_mentions.py
├── test_sov_classify.py
└── test_sov_persist.py
```

---

## 8. Datenmodell

### Tabelle `sov_mentions`

```sql
CREATE TABLE sov_mentions (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    run_at          timestamptz NOT NULL,           -- wann der Agent gelaufen ist
    company         text NOT NULL,                  -- z.B. 'celonis.com'
    source_type     text NOT NULL,                  -- 'news' | 'seo'
    source          text NOT NULL,                  -- 'finnhub' | 'serper' | 'firecrawl' | 'google_serp'
    title           text NOT NULL,
    content         text,
    date            date NOT NULL,                  -- Veröffentlichungsdatum
    month_bucket    text NOT NULL,                  -- 'YYYY-MM', abgeleitet aus date
    url             text NOT NULL,
    language        text,
    themes          jsonb NOT NULL DEFAULT '[]'::jsonb,   -- z.B. ["Agentic AI", "AI & GenAI"]
    region          text,                                  -- DACH | Europe | NA | APAC | Global
    is_relevant     boolean NOT NULL DEFAULT true,
    reasoning       text,                                  -- ein-Satz-Begründung des LLM
    created_at      timestamptz NOT NULL DEFAULT now(),
    
    CONSTRAINT sov_mentions_natural_key UNIQUE (company, source_type, url)
);

CREATE INDEX sov_mentions_company_idx       ON sov_mentions (company);
CREATE INDEX sov_mentions_month_bucket_idx  ON sov_mentions (month_bucket);
CREATE INDEX sov_mentions_run_at_idx        ON sov_mentions (run_at DESC);
CREATE INDEX sov_mentions_themes_gin        ON sov_mentions USING gin (themes);
```

### Pydantic-Modell `Mention` (im State)

```python
class Mention(BaseModel):
    company: str
    source_type: Literal["news", "seo"]
    source: str
    title: str
    content: str | None
    date: date
    month_bucket: str            # YYYY-MM
    url: str
    language: str | None
    # erst nach classify gefüllt:
    themes: list[str] = []
    region: str | None = None
    is_relevant: bool | None = None
    reasoning: str | None = None
```

### Pydantic-Modell `SovClassificationOutput` (LLM-Schema)

```python
class SovClassificationOutput(BaseModel):
    themes: list[Literal[
        "Process Mining", "Process Intelligence", "AI & GenAI",
        "Agentic AI", "Automation", "Digital Transformation",
        "Supply Chain", "ERP & SAP", "Other"
    ]]
    region: Literal["DACH", "Europe", "NA", "APAC", "Global"]
    is_relevant: bool
    reasoning: str           # ein Satz
```

### State `SovPipelineState`

```python
class SovPipelineState(TypedDict):
    run_at: datetime
    companies: list[str]                          # aus competitors-Tabelle
    candidate_mentions: list[Mention]             # nach Schritt 1
    classified_mentions: list[Mention]            # nach Schritt 2
    persisted_count: int                          # nach Schritt 3
    errors: Annotated[list[str], operator.add]
```

---

## 9. Phasenplan

### Phase 1 — Datenmodell & Skelett

**Dateien:**
- `backend/scripts/migrations/0XX_sov_mentions.sql` (Nummer per `ls migrations` ermitteln)
- `backend/app/agents/sov/__init__.py` (leer)
- `backend/app/agents/sov/themes.py`
- `backend/app/agents/sov/state.py`

**Inhalte:** Siehe Abschnitte 5, 7, 8.

**Validierung:** Migration anwenden in Supabase Studio, prüfen ob Tabelle existiert.

### Phase 2 — Mention-Loader

**Dateien:**
- `backend/app/agents/sov/nodes/__init__.py`
- `backend/app/agents/sov/nodes/load_mentions.py`

**Funktionen:**
- `async def load_mentions_node(state: SovPipelineState) -> dict` (LangGraph-Knoten)
- `async def _load_news(company: str, since: date) -> list[Mention]`
- `async def _load_seo(company: str, since: date) -> list[Mention]`
- `async def _filter_already_persisted(mentions: list[Mention]) -> list[Mention]` (URL-Lookup in `sov_mentions`)

**Logik:**
- Liest `research_snapshots` per `client.table("research_snapshots").select(...).eq("node", "news").eq("domain", company)`
- Konvertiert JSON-Payload zu `Mention`-Objekten
- `month_bucket` aus `date.strftime("%Y-%m")`
- Wirft Quellen mit `is_relevant=False` noch nicht raus (kommt in classify)

**Test:** Snapshot-Fixture mit 3 News-Items → 3 Mentions raus.

### Phase 3 — Klassifikation

**Dateien:**
- `backend/app/prompts/sov/__init__.py`
- `backend/app/prompts/sov/classification.py`
- `backend/app/agents/sov/nodes/classify.py`

**Funktionen:**
- `def build_classification_messages(mention: Mention) -> list[dict]` (System- + User-Prompt)
- `async def _classify_one(mention: Mention, structured_llm) -> Mention`
- `async def classify_node(state: SovPipelineState) -> dict`

**Logik:**
- `ChatOpenAI(model="gpt-4o-mini", temperature=0.0).with_structured_output(SovClassificationOutput, method="json_schema", strict=True)`
- `asyncio.Semaphore(5)` für Parallelität
- Heuristisches Pre-Filter:
  - Wenn `mention.language == "de"` → Region-Hint „DACH" in den Prompt geben
  - Wenn `source_type == "seo"` → das SEO-Keyword als Theme-Hint in den Prompt
- LLM-Output ins `Mention`-Objekt mergen

**Prompt-Pattern (analog Geo):**
- System: „Du bist ein Brand-Analyst. Klassifiziere die folgende Mention nach Thema, Region und Relevanz. Halte dich strikt an die vorgegebene Liste."
- User: Die Mention als JSON, plus Hints aus Heuristik.

**Test:** Mock-LLM, fixierte Mention, prüfen ob Felder korrekt gesetzt sind.

### Phase 4 — Persistenz

**Dateien:**
- `backend/app/agents/sov/repositories/__init__.py`
- `backend/app/agents/sov/repositories/sov_repository.py`
- `backend/app/agents/sov/nodes/persist.py`

**Funktionen:**
- `def insert_sov_mentions(rows: list[SovMentionRow], client=None) -> int` (Bulk-Insert mit `on_conflict="company,source_type,url"`)
- `async def persist_node(state: SovPipelineState) -> dict`

**Dataclass:**
```python
@dataclass
class SovMentionRow:
    company: str
    run_at: datetime
    source_type: str
    source: str
    title: str
    content: str | None
    date: date
    month_bucket: str
    url: str
    language: str | None
    themes: list[str]
    region: str | None
    is_relevant: bool
    reasoning: str | None
```

**Pattern aus Geo übernehmen:** [backend/app/agents/brand/repositories/geo_repository.py:105-134](backend/app/agents/brand/repositories/geo_repository.py#L105-L134) (Bulk-Insert)

**Test:** Mock-Supabase-Client, prüfen ob die richtige `insert()`-Payload gebaut wird.

### Phase 5 — Graph

**Datei:** `backend/app/agents/sov/graph.py`

**Logik:**
```python
from langgraph.graph import StateGraph, START, END

def build_sov_graph():
    graph = StateGraph(SovPipelineState)
    graph.add_node("load_mentions", load_mentions_node)
    graph.add_node("classify", classify_node)
    graph.add_node("persist", persist_node)
    graph.add_edge(START, "load_mentions")
    graph.add_edge("load_mentions", "classify")
    graph.add_edge("classify", "persist")
    graph.add_edge("persist", END)
    return graph.compile()
```

**Test:** Integrationstest mit gemockten LLM-Calls, komplette Pipeline durchspielen.

### Phase 6 — API-Trigger

**Datei:** `backend/app/api/sov.py`

**Endpoint:**
```python
@router.post("/sov/run")
async def trigger_sov_run(user = Depends(get_current_user)):
    state = {
        "run_at": datetime.now(timezone.utc),
        "companies": await get_competitor_domains(),
        "candidate_mentions": [],
        "classified_mentions": [],
        "persisted_count": 0,
        "errors": [],
    }
    graph = build_sov_graph()
    result = await graph.ainvoke(state)
    return {
        "persisted": result["persisted_count"],
        "errors": result["errors"],
        "run_at": result["run_at"],
    }
```

**Auth-Pattern:** Aus [backend/app/api/geo.py](backend/app/api/geo.py) übernehmen.

**Router-Registrierung:** Im FastAPI-Hauptmodul registrieren (analog zu den anderen Routern).

---

## 10. Patterns vom Geo-Agent (Copy-Vorlagen)

| Pattern | Quelle | Verwendung im SoV |
|---|---|---|
| `_build_llm(model, temperature)` | [geo_intelligence.py:57-65](backend/app/agents/brand/nodes/geo_intelligence.py#L57-L65) | In `classify.py` |
| `with_structured_output(..., strict=True)` | [geo_intelligence.py:201-205](backend/app/agents/brand/nodes/geo_intelligence.py#L201-L205) | In `classify.py` |
| `asyncio.Semaphore(5)` für parallele LLM-Calls | [geo_intelligence.py:174-195](backend/app/agents/brand/nodes/geo_intelligence.py#L174-L195) | In `classify.py` |
| Bulk-Insert mit Supabase Client | [geo_repository.py:105-134](backend/app/agents/brand/repositories/geo_repository.py#L105-L134) | In `sov_repository.py` |
| Test-Setup mit AsyncMock | [backend/tests/unit/test_geo_intelligence_node.py](backend/tests/unit/test_geo_intelligence_node.py) | In `tests/unit/test_sov_*.py` |
| Auth-Dependency in FastAPI-Router | [backend/app/api/geo.py](backend/app/api/geo.py) | In `sov.py` |
| Structlog-Logging | überall im Geo-Code | überall im SoV-Code |
| LangGraph-State als TypedDict + `Annotated[list, operator.add]` für errors | [backend/app/agents/brand/state.py](backend/app/agents/brand/state.py) | In `state.py` |

---

## 11. Wichtige Hinweise

### Trends kommen vom Artikel-Datum, nicht vom Run-Zeitpunkt
Für Trend-Analysen wird `date` und `month_bucket` aggregiert, **nicht** `run_at`. Eine Mention bleibt im Mai-Bucket, egal wann der Agent sie verarbeitet hat. `run_at` ist nur Metadatum für Debugging und „Wann wurde das ins System aufgenommen?".

### Wiederholte Runs sind günstig
Durch URL-Pre-Filter werden bereits klassifizierte Mentions **nicht** erneut ans LLM geschickt. Ein zweiter Run am selben Tag schreibt fast nichts und kostet fast keine Tokens. Tägliche Runs sind problemlos möglich.

### `co_mentioned_companies` aus GEO werden ignoriert
SoV vergleicht **nur** die Wettbewerber aus der `competitors`-Tabelle. Erwähnungen anderer Unternehmen in News oder LLM-Antworten werden nicht als virtuelle Mentions interpretiert.

### Keine Region-Filterung bei SEO
SEO-Mentions bekommen pauschal `region = "Global"`. Im Dashboard transparent dokumentieren oder SEO bei Region-View ausblenden.

### Verhalten bei Reklassifikations-Bedarf
`ON CONFLICT DO NOTHING` behält die alte Klassifikation. Wenn jemand eine neue Themenliste einführen will und alte Mentions neu klassifizieren möchte: die betroffenen Zeilen manuell aus `sov_mentions` löschen, dann läuft der nächste Run sie automatisch wieder durch das LLM.

### Datumsfeld bei SEO
SEO-Sightings haben kein Veröffentlichungsdatum. Wir verwenden den `run_at`-Zeitstempel des Research-Snapshots als `date`. Konsequenz: SEO-Trends bewegen sich nur in Schrittweite der Research-Runs (typisch wöchentlich).

---

## 12. Was NICHT im MVP enthalten ist

- Eigene Aggregat-Tabelle (`sov_aggregates`) — Aggregation läuft on-the-fly via SQL
- Synthese-Narrative (kein LLM-generierter Briefing-Text)
- Mehrere LLM-Modelle pro Klassifikation
- 3-Tier-Keyword-Struktur
- Dedupe via Volltext-Similarity (nur URL-basiert)
- `recommendation_strength`-Gewichtung für GEO
- Events- und YouTube-Quellen
- GEO-Quelle (wird vom Geo-Agent abgedeckt)
- Region-Filterung für SEO
- Scheduler-Auto-Trigger (nur manuell)
- Lese-Endpoints fürs Dashboard (kommen mit dem Frontend-Schritt)

Alle diese Punkte können später **ohne breaking Change** ergänzt werden.

---

## 13. Spätere Erweiterungen (Roadmap-Ideen)

| Erweiterung | Aufwand | Trigger für Aufnahme |
|---|---|---|
| Events als Quelle | klein | sobald Events-Volumen relevant |
| YouTube als Quelle | mittel | sobald YouTube-Daten in Research stabil |
| Scheduler-Auto-Trigger | klein | sobald MVP läuft |
| `sov_aggregates`-Tabelle | mittel | wenn API-Latenz > 500ms |
| Volltext-Dedupe | mittel | wenn Quote ähnlicher Artikel über 10% |
| Synthese-Briefing | groß | wenn Dashboard mehr Storytelling braucht |
| Mehrsprachige Region-Heuristik | klein | wenn nicht-englische Quellen wichtiger werden |

---

## 14. Quick-Start für neuen Chat (Wenn diese Konversation verloren geht)

Falls du in einem neuen Chat weiterarbeiten musst, paste diesen Block als Erstes:

> Ich arbeite am Share-of-Voice-Agent für das Celonis-CI-Projekt. Die vollständige Spezifikation liegt in `docs/sov_agent_plan.md`. Bitte lies sie vollständig und halte dich strikt an die dort getroffenen Entscheidungen. Wir orientieren uns am Geo-Intelligence-Agent als Code-Vorlage (Pfade siehe Abschnitt 10 im Plan). Datenquellen sind ausschließlich News und SEO aus der bestehenden `research_snapshots`-Tabelle. Wir bauen in 6 Phasen, gerade arbeite ich an Phase [X]. Folgendes ist bereits umgesetzt: [Liste der fertigen Phasen].

---

## 15. Fortschritts-Tracking

Hier kann der Fortschritt mit Checkboxen aktualisiert werden:

- [ ] Phase 1 — Datenmodell & Skelett
  - [ ] Migration `sov_mentions.sql` geschrieben
  - [ ] Migration in Supabase angewendet
  - [ ] `themes.py` erstellt
  - [ ] `state.py` erstellt
- [ ] Phase 2 — Mention-Loader
  - [ ] News-Loader
  - [ ] SEO-Loader
  - [ ] URL-Pre-Filter
  - [ ] Unit-Test
- [ ] Phase 3 — Klassifikation
  - [ ] `SovClassificationOutput`-Schema
  - [ ] Prompt-Builder
  - [ ] Heuristisches Pre-Filter
  - [ ] LLM-Call mit Semaphore
  - [ ] Unit-Test
- [ ] Phase 4 — Persistenz
  - [ ] `SovMentionRow`-Dataclass
  - [ ] `insert_sov_mentions()` mit ON CONFLICT
  - [ ] `persist_node`
  - [ ] Unit-Test
- [ ] Phase 5 — Graph
  - [ ] `build_sov_graph()`
  - [ ] Integrationstest
- [ ] Phase 6 — API
  - [ ] `POST /sov/run`
  - [ ] Router-Registrierung
  - [ ] End-to-End manueller Test
