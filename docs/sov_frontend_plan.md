# Share-of-Voice Frontend — Implementierungsplan

Vollständige Spezifikation für das SoV-Dashboard im Frontend des Celonis-CI-Projekts. Eigenständig lesbar — kann in einem neuen Chat als Implementierungsgrundlage verwendet werden.

**Voraussetzung:** Das Backend-Pendant ist in [docs/sov_agent_plan.md](sov_agent_plan.md) beschrieben. Bitte beide Dokumente lesen.

---

## 1. Zweck

Das SoV-Dashboard zeigt die klassifizierten Mentions aus `sov_mentions` als interaktives Dashboard mit Filtern, Charts und einer Detail-Liste. Es **erzeugt keine Daten** — es liest den fertigen Bestand aus dem Backend-Endpoint `GET /sov` und aggregiert clientseitig.

**Ausgangsfrage:** „Welche Wettbewerber bekommen wieviel Aufmerksamkeit, in welchen Themen, welchen Regionen, und wie verändert sich das über die Zeit?"

---

## 2. Architektur-Entscheidungen (alle getroffenen)

| Entscheidung | Wert | Begründung |
|---|---|---|
| Datenquelle | **Ein einziger Endpoint** `GET /sov`, lädt alle Mentions in einem Schwung | Konsistent zu `/events`. Bei 500–2000 Mentions kein Performance-Problem |
| Aggregation | **Clientseitig** in `lib/sov/analysis.ts` | Reaktive Filter ohne neuen API-Call |
| State-Management | **Lokal mit `useState`** in `page.tsx`, kein Context/Redux | Reicht für einen Page-Scope |
| Filter-Persistenz | **Nur im Page-Lifecycle**, kein URL-State | Konsistent zu `/events` |
| React Query | **Ja**, mit 5 Min Stale-Time | Konvention im Projekt |
| Headline-Visualisierung | **Donut-Chart** für SoV-Anteile | Klassisch SoV, kompakt |
| Themen-Breakdown | **Gestapelter Balken**, eine Zeile pro Thema | Direkter ablesbar als Heatmap |
| Trend-Chart-Default-Filter | **„News only"** | SEO-Daten würden Spikes an Run-Tagen erzeugen |
| Regionen-Filter SEO | SEO-Mentions sind immer `Global` (Backend-seitig festgelegt) | Im Dashboard transparent dokumentiert |
| Rising/Declining-Berechnung | **Vergleich aktueller vs. vorheriger Monat**, pro Thema | Einfach, reproduzierbar |
| Zonen-Anzahl | **7 Zonen + Detail-Liste** | Genug für Aussagekraft, nicht überfrachtet |
| Farben pro Wettbewerber | Helper [getCompetitorColor()](../frontend/src/lib/competitors/colors.ts) — kombiniert echte Brand-Farben aus `/competitors/colors` mit Fallback-Palette | Existierender Mechanismus aus dem Events-Pattern |

---

## 3. Modulstruktur

```
frontend/src/app/(main)/sov/
└── page.tsx                            ← die Seite

frontend/src/lib/sov/
├── types.ts                            ← Backend-Spiegel + Filter-Typen
├── hooks.ts                            ← useSov() React Query Hook
└── analysis.ts                         ← Filter & Aggregations-Helper

frontend/components/sov/
├── SovFilters.tsx                      ← globale Filterleiste
├── SovKpis.tsx                         ← 4 KPI-Tiles
├── SovShareDonut.tsx                   ← Headline-Donut
├── SovTrendChart.tsx                   ← Linienchart über Zeit
├── SovThemeBreakdown.tsx               ← Themen × Companies (stacked bar)
├── SovRegionChart.tsx                  ← Regionen-Aufteilung
├── SovTrendingAlerts.tsx               ← Rising / Declining Themes
└── SovOverview.tsx                     ← Mention-Liste mit eigenen Sub-Filtern
```

Geteilte Komponenten, die wir wiederverwenden (existieren bereits):

| Komponente | Pfad |
|---|---|
| `PageToolbar` | [frontend/components/geo/PageToolbar.tsx](../frontend/components/geo/PageToolbar.tsx) |
| `SectionHeader` | [frontend/components/geo/SectionHeader.tsx](../frontend/components/geo/SectionHeader.tsx) |
| `DashboardCard` | [frontend/components/geo/DashboardCard.tsx](../frontend/components/geo/DashboardCard.tsx) |
| `AlertCard` | [frontend/components/geo/AlertCard.tsx](../frontend/components/geo/AlertCard.tsx) |
| `ZoneSkeleton` / `ZoneError` / `ZoneEmpty` | `frontend/components/geo/Zone*.tsx` |
| `getCompetitorColor` | [frontend/src/lib/competitors/colors.ts](../frontend/src/lib/competitors/colors.ts) |
| `useCompetitorColors` | [frontend/src/lib/competitors/hooks.ts](../frontend/src/lib/competitors/hooks.ts) |
| `apiFetch` | [frontend/src/lib/api.ts](../frontend/src/lib/api.ts) |

---

## 4. Datenfluss

```
GET /sov   ← backend, returns full mentions list
   ↓
useSov()  ← React Query, cached 5 min
   ↓
page.tsx  ← receives data + manages filter state
   ↓
applyFilters(mentions, filters)   ← analysis.ts, runs in useMemo
   ↓
filteredMentions
   ↓
   ├──► aggregateByCompany()  → SovKpis, SovShareDonut
   ├──► aggregateByMonth()    → SovTrendChart
   ├──► aggregateByTheme()    → SovThemeBreakdown
   ├──► aggregateByRegion()   → SovRegionChart
   ├──► computeRisingFalling()→ SovTrendingAlerts
   └──► (direct list)         → SovOverview
```

Sämtliche Aggregations-Funktionen sind reine TypeScript-Funktionen ohne React-Abhängigkeit und liegen in `analysis.ts`. Komponenten erhalten nur fertig aggregierte Props plus `getColor`-Callback.

---

## 5. Typen (in `types.ts`)

```typescript
export type SovSourceType = "news" | "seo";
export type SovRegion = "DACH" | "Europe" | "NA" | "APAC" | "Global";

export type SovMention = {
  id: string;
  run_at: string;
  company: string;
  source_type: SovSourceType;
  source: string;
  title: string;
  content: string | null;
  date: string;            // YYYY-MM-DD
  month_bucket: string;    // YYYY-MM
  url: string;
  language: string | null;
  themes: string[];
  region: SovRegion | null;
  is_relevant: boolean;
  reasoning: string | null;
};

export type SovListResponse = {
  mentions: SovMention[];
  total: number;
  latest_run_at: string | null;
  companies: string[];
};

export type SovPeriod = "1m" | "3m" | "6m" | "ytd" | "all";
export type SovSourceFilter = "news" | "seo" | "both";

export type SovFilters = {
  period: SovPeriod;
  themes: string[];       // empty = all
  regions: SovRegion[];   // empty = all
  source: SovSourceFilter;
};

export const DEFAULT_SOV_FILTERS: SovFilters = {
  period: "3m",
  themes: [],
  regions: [],
  source: "news",
};
```

---

## 6. Filterleiste (Phase 3)

**Layout:** horizontal, sticky beim Scrollen, vier Elemente nebeneinander.

| Filter | UI-Element | Werte |
|---|---|---|
| Period | Dropdown | `1m`, `3m`, `6m`, `ytd`, `all` |
| Themes | Multi-Select Chips | 9 Themen + „All" |
| Regions | Multi-Select Chips | DACH, Europe, NA, APAC, Global, „All" |
| Source | Toggle | News, SEO, Both |

State liegt in `page.tsx`:

```typescript
const [filters, setFilters] = useState<SovFilters>(DEFAULT_SOV_FILTERS);
const filtered = useMemo(
  () => applyFilters(data?.mentions ?? [], filters),
  [data, filters]
);
```

---

## 7. Aggregations-Funktionen (in `analysis.ts`)

```typescript
applyFilters(mentions: SovMention[], filters: SovFilters): SovMention[]

aggregateByCompany(mentions: SovMention[]): Array<{
  company: string;
  count: number;
  share: number;            // 0..1 of total
}>

aggregateByMonth(mentions: SovMention[], companies: string[]): Array<{
  month: string;            // 'YYYY-MM'
  counts: Record<string, number>;   // company → count
}>

aggregateByTheme(mentions: SovMention[]): Array<{
  theme: string;
  total: number;
  byCompany: Record<string, number>;
}>

aggregateByRegion(mentions: SovMention[]): Array<{
  region: string;
  total: number;
  byCompany: Record<string, number>;
}>

computeRisingFalling(mentions: SovMention[], topN: number = 3): {
  rising: Array<{ theme: string; deltaPct: number; current: number; previous: number }>;
  declining: Array<{ theme: string; deltaPct: number; current: number; previous: number }>;
}
```

### Period-Filter-Logik

```typescript
function periodCutoff(period: SovPeriod): Date | null {
  const now = new Date();
  switch (period) {
    case "1m":  return new Date(now.getFullYear(), now.getMonth() - 1, now.getDate());
    case "3m":  return new Date(now.getFullYear(), now.getMonth() - 3, now.getDate());
    case "6m":  return new Date(now.getFullYear(), now.getMonth() - 6, now.getDate());
    case "ytd": return new Date(now.getFullYear(), 0, 1);
    case "all": return null;
  }
}
```

### Rising/Declining-Logik

```
Für jedes Thema:
  currentCount  = Mentions im aktuellen Monat
  previousCount = Mentions im Vormonat
  deltaPct      = (currentCount - previousCount) / max(previousCount, 1)
top N nach deltaPct → rising
bottom N nach deltaPct (mit previousCount > 0) → declining
```

---

## 8. Visualisierungs-Konzept (7 Zonen + Detail-Liste)

### Header (immer sichtbar)
Title „Share of Voice", Subtitle mit Live-Status (`${total} classified mentions across ${companies.length} competitors`), rechts `PageToolbar` mit `latest_run_at`.

### Zone 1 — Globale Filterleiste
`SovFilters.tsx`. Sticky beim Scrollen.

### Zone 2 — KPI-Tiles
`SovKpis.tsx`, vier `DashboardCard`s:

| Kachel | Inhalt |
|---|---|
| **Total Mentions** | gesamte Zahl in gefilterten Mentions |
| **Leading Company** | Company mit höchstem SoV + Prozent |
| **Dominant Theme** | meistgenanntes Thema + Häufigkeit |
| **Tracked Competitors** | Anzahl Companies mit ≥1 Mention im Zeitraum |

### Zone 3 — Share of Voice Donut
`SovShareDonut.tsx`. Recharts `<PieChart>` mit `<Pie innerRadius=…>`. Farben aus `getCompetitorColor()`. Legende rechts mit Prozenten.

### Zone 4 — Trend über Zeit
`SovTrendChart.tsx`. Recharts `<LineChart>` mit `<Line>` je Company. X-Achse = `month_bucket`, Y-Achse = Mentions-Anzahl. Legende klickbar zum Ein-/Ausblenden.

**Wichtig:** standardmäßig Filter `source: "news"`. SEO-Mentions würden Spikes an Run-Tagen erzeugen.

### Zone 5 — Themen-Breakdown
`SovThemeBreakdown.tsx`. Horizontal gestapelter Bar-Chart: eine Zeile pro Thema (9 Stück), Segmente innerhalb der Zeile sind Companies, Breite = Anzahl.

### Zone 6 — Regionale Verteilung
`SovRegionChart.tsx`. Bar Chart pro Region. Optional zweite Variante mit Stack pro Company.

**Caveat in der Beschreibung:** „SEO mentions are always classified as Global."

### Zone 7 — Rising / Declining Themes
`SovTrendingAlerts.tsx`. Zwei `AlertCard`s nebeneinander:
- Oben: 📈 Top 3 steigende Themen mit Delta-Prozent
- Unten: 📉 Top 3 fallende Themen

Wenn weniger als 2 Monate Daten vorhanden sind, Empty-State zeigen.

### Zone 8 — Mention-Detail-Liste
`SovOverview.tsx`. Card-Liste analog `EventsOverview.tsx`. Eine Card pro Mention:
- Company-Farbe als Akzent
- Title
- Themes als Chips
- Region-Tag
- Datum
- Source-Tag
- Aufklappbar: Reasoning + URL

Eigene Sub-Filter über der Liste (Search, Sort by date, Company filter).

---

## 9. Phasenplan

### Phase 1 — Endpoint + Types + Hook ✓
- `GET /sov` in `backend/app/api/sov.py`
- `lib/sov/types.ts`
- `lib/sov/hooks.ts`

### Phase 2 — Page-Skelett + Navigation ✓
- `app/(main)/sov/page.tsx` mit Header, Hook-Verkabelung, Platzhalter-Sections
- Nav-Eintrag in `Navbar.tsx` und `MobileMenu.tsx`

### Phase 3 — Globale Filterleiste + analysis.ts
**Dateien:**
- `components/sov/SovFilters.tsx`
- `lib/sov/analysis.ts`

**Aufgaben:**
- Filter-State in `page.tsx` aufnehmen, an `SovFilters` als props durchreichen
- `applyFilters()` implementieren — die Aggregations-Helfer kommen schrittweise dazu, wenn die jeweiligen Charts gebraucht werden
- Filter wirken auf nichts sichtbares außer dem KPI-„Total Mentions" — die Phase 4 wird beide Zonen erst befüllen

### Phase 4 — KPIs + Donut
**Dateien:**
- `components/sov/SovKpis.tsx`
- `components/sov/SovShareDonut.tsx`
- `lib/sov/analysis.ts` ergänzt um `aggregateByCompany()`

**Aufgaben:**
- Vier KPI-Tiles aus `aggregateByCompany()` + Themen-Mode-Berechnung
- Donut mit Recharts, Farben über `useCompetitorColors()` + `getCompetitorColor()`

### Phase 5 — Trend + Themen + Region
**Dateien:**
- `components/sov/SovTrendChart.tsx`
- `components/sov/SovThemeBreakdown.tsx`
- `components/sov/SovRegionChart.tsx`
- `lib/sov/analysis.ts` ergänzt um `aggregateByMonth()`, `aggregateByTheme()`, `aggregateByRegion()`

### Phase 6 — Rising/Declining + Detail-Liste
**Dateien:**
- `components/sov/SovTrendingAlerts.tsx`
- `components/sov/SovOverview.tsx`
- `lib/sov/analysis.ts` ergänzt um `computeRisingFalling()`

---

## 10. Patterns vom Events-Pattern (Copy-Vorlagen)

| Pattern | Quelle |
|---|---|
| Page-Struktur mit Header + Sections | [frontend/src/app/(main)/events/page.tsx](../frontend/src/app/(main)/events/page.tsx) |
| `useQuery` Hook | [frontend/src/lib/events/hooks.ts](../frontend/src/lib/events/hooks.ts) |
| Backend-Spiegel-Types | [frontend/src/lib/events/types.ts](../frontend/src/lib/events/types.ts) |
| Filter-State mit useState/useMemo | [frontend/components/events/EventsOverview.tsx](../frontend/components/events/EventsOverview.tsx) |
| Recharts BarChart | [frontend/components/events/EventsCharts.tsx](../frontend/components/events/EventsCharts.tsx) |
| `getCompetitorColor` Verwendung | dort ebenfalls referenziert |

---

## 11. Tailwind / Theme-Konventionen

| Farbe | CSS-Klasse |
|---|---|
| Primary Black | `bg-primary-black` |
| Primary White | `text-primary-white` |
| Secondary Green (Celonis) | `bg-secondary-green` |
| Neutral Grey 30 (border) | `border-neutral-grey-30` |
| Neutral Grey 20 (muted text) | `text-neutral-grey-20` |
| Neutral Grey 10 (lighter text) | `text-neutral-grey-10` |
| Error | `text-error` |
| Warning | `text-warning` |

**Standard-Spacing:** `gap-24` zwischen Sections, `px-16 py-22` für Page-Padding (durch `PageWrapper`), `rounded-sm` für kleine Cards.

**Chart-Farben aus dem Events-Pattern:**
```typescript
const CELONIS_GREEN = "#5CFE50";
const GRID_COLOR = "rgba(255,255,255,0.08)";
const LABEL_COLOR = "#CBCBCB";
```

---

## 12. Wichtige Hinweise / Edge Cases

### SEO-Mentions sind immer „Global"
Bei der Region-Klassifikation hat das Backend SEO hart auf `Global` gesetzt, weil Google-Rankings nicht regional sind. Im Frontend in der Regionen-Zone transparent dokumentieren. Im Trend-Chart standardmäßig auf `source: "news"` filtern.

### Trend braucht ≥ 2 Monate Daten
Rising/Declining kann erst berechnet werden, wenn der Vormonat Mentions enthält. Wenn nicht, Empty-State mit Hinweis „Need more data history to compute trends".

### Companies ohne Mentions im Zeitraum
In `aggregateByCompany()` mit 0 Mentions ausblenden, nicht als 0%-Slice zeigen.

### Realistische Datenmengen
Aktuell ~500 Mentions pro Run, monatlich +200. Nach einem halben Jahr ~2000 Zeilen — alles unkritisch für clientseitige Aggregation.

### Color-Stabilität
Die Companies-Liste im `SovListResponse` ist alphabetisch sortiert und stabil. `getCompetitorColor()` indiziert darauf — solange die Liste stabil bleibt, bleiben die Farben pro Company stabil.

### Build-Fehler auf dem Branch
Es gibt einen vor-bestehenden Build-Fehler im `share-of-voice-agent` Branch: in `Navbar.tsx:34` ist ein Link auf `/chatbot`, aber die Page existiert nicht (kommt von einem unsauberen Merge). Für die Entwicklung mit `npm run dev` arbeiten, das ist permissiver. Für Build den Chatbot-Link entfernen oder eine Stub-Page anlegen.

---

## 13. Was NICHT im MVP enthalten ist

- Drill-Down per Klick auf Charts → Detail-View
- Export-/Download-Funktion
- URL-State für Filter (Sharing)
- Echte Weltkarte für Regionen
- Dynamische SEO-Region-Lokalisierung
- Sentiment / Tonalität
- „Re-Run"-Knopf, der POST /sov/run aufruft

Alle Punkte können später ergänzt werden, ohne bestehende Komponenten umzuschreiben.

---

## 14. Quick-Start für neuen Chat

Falls du in einem neuen Chat weiterarbeiten musst, paste diesen Block als Erstes:

> Ich arbeite am Share-of-Voice-Frontend für das Celonis-CI-Projekt. Die vollständige Spezifikation liegt in `docs/sov_frontend_plan.md`, die Backend-Pendant-Spezifikation in `docs/sov_agent_plan.md`. Bitte lies beide vollständig und halte dich strikt an die getroffenen Entscheidungen. Wir orientieren uns am Events-Pattern (`frontend/src/app/(main)/events/page.tsx`) als Vorlage. Datenquelle ist ausschließlich `GET /sov` aus dem Backend. Wir bauen in 6 Phasen, gerade arbeite ich an Phase [X]. Folgendes ist bereits umgesetzt: [Liste der fertigen Phasen].

---

## 15. Fortschritts-Tracking

- [x] **Phase 1 — Endpoint + Types + Hook**
  - [x] `GET /sov` in `backend/app/api/sov.py`
  - [x] `frontend/src/lib/sov/types.ts`
  - [x] `frontend/src/lib/sov/hooks.ts`
- [x] **Phase 2 — Page-Skelett + Navigation**
  - [x] `frontend/src/app/(main)/sov/page.tsx` mit Header + Hook + Platzhalter-Sections
  - [x] Nav-Eintrag in `Navbar.tsx`
  - [x] Nav-Eintrag in `MobileMenu.tsx`
- [ ] **Phase 3 — Globale Filterleiste + analysis.ts**
  - [ ] `lib/sov/analysis.ts` mit `applyFilters()` und `periodCutoff()`
  - [ ] `components/sov/SovFilters.tsx`
  - [ ] Filter-State in `page.tsx` integriert
- [ ] **Phase 4 — KPIs + Donut**
  - [ ] `aggregateByCompany()` in `analysis.ts`
  - [ ] `components/sov/SovKpis.tsx`
  - [ ] `components/sov/SovShareDonut.tsx`
- [ ] **Phase 5 — Trend + Themen + Region**
  - [ ] `aggregateByMonth()`, `aggregateByTheme()`, `aggregateByRegion()` in `analysis.ts`
  - [ ] `components/sov/SovTrendChart.tsx`
  - [ ] `components/sov/SovThemeBreakdown.tsx`
  - [ ] `components/sov/SovRegionChart.tsx`
- [ ] **Phase 6 — Rising/Declining + Detail-Liste**
  - [ ] `computeRisingFalling()` in `analysis.ts`
  - [ ] `components/sov/SovTrendingAlerts.tsx`
  - [ ] `components/sov/SovOverview.tsx`
  - [ ] Platzhalter-Sections und `PhasePlaceholder`-Komponente aus `page.tsx` entfernen
