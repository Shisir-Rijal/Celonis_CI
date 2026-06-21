"""backend/app/api/visualbranding.py

Visual Branding Agent API router.

GET /branding/color-insights
    Latest cross-competitor ColorAnalysis, shaped for the frontend's
    ColorInsights type (frontend/src/lib/branding/types.ts).

GET /branding/font-insights
    Latest cross-competitor FontAnalysis, shaped for the frontend's
    FontInsights type.

GET /branding/logo-dimensions, /branding/logo-placement
    Latest cross-competitor LogoAnalysis, split into the frontend's
    LogoDimensionBreakdown and LogoPlacement shapes.

GET /branding/imagery-archetypes, /branding/imagery-dimensions, /branding/imagery-similarity
    Latest cross-competitor ImageAnalysis, split into the frontend's
    ImageryArchetypes, ImageryDimensionBreakdown, and ImagerySimilarity shapes.

GET /branding/video-insights
    Latest cross-competitor VideoAnalysis. No dedicated frontend component
    consumes this yet — exposed for parity/persistence so it's ready to wire
    up once one exists.

GET /branding/visual-trends
    Latest cross-competitor TrendAnalysis, shaped for the frontend's
    VisualTrends type.

GET /branding/archetypes
    Latest cross-dimension BrandArchetypeAnalysis (nodes/archetypes.py) — one
    holistic brand archetype per company or company group, synthesized from
    every other node's latest analysis.

GET /branding/alerts
    Latest AlertAnalysis — what changed since each node's previous run.

Each endpoint reads the latest row in visualbranding_snapshots for its node
and adapts the backend's snake_case Pydantic shape into the exact camelCase
shape the frontend types already define, so the frontend's existing
components (which were built against dummy data matching that shape) work
unchanged once the queryFn in hooks.ts points here instead.

Requires a valid JWT via Authorization: Bearer <token>.
"""

from typing import Any

import structlog
from fastapi import APIRouter, Depends

from app.auth.dependencies import require_auth
from app.rag.supabase_client import get_supabase

logger = structlog.get_logger(__name__)

router = APIRouter(prefix="/branding", tags=["branding"])

TABLE = "visualbranding_snapshots"

_USAGE_LABELS = {
    "very_common": "Very common",
    "common": "Common",
    "occasional": "Occasional",
    "rare": "Rare",
}


def _latest_snapshot(node: str) -> dict | None:
    db = get_supabase()
    result = (
        db.table(TABLE)
        .select("data")
        .eq("node", node)
        .order("run_at", desc=True)
        .limit(1)
        .execute()
    )
    rows = result.data or []
    return rows[0]["data"] if rows else None


def _pct(count: int, total: int) -> float:
    return round(count / total * 100, 1) if total else 0.0


# ---------------------------------------------------------------------------
# Colors
# ---------------------------------------------------------------------------

def _build_company_hex_lookup(diversities: list[dict]) -> dict[tuple[str, str], str]:
    """{(company, hue_family): that company's own hex in this family} — so the
    color spectrum's company chips can show each competitor's actual shade
    (e.g. their specific blue) instead of one shared representative swatch
    for the whole family."""
    lookup: dict[tuple[str, str], str] = {}
    for d in diversities or []:
        company = d.get("company")
        for h in d.get("hues", []):
            colors = h.get("colors") or []
            if company and colors:
                lookup[(company, h.get("hue_family"))] = colors[0]
    return lookup


def _adapt_color_spectrum_entry(
    bucket_key: str, bucket: dict, company_hex: dict[tuple[str, str], str]
) -> dict[str, Any]:
    companies: list[str] = bucket.get("companies", [])
    family = bucket.get("type")
    hex_code = bucket.get("color")
    return {
        "colorFamily": family,
        "representativeHex": hex_code,
        "usageLabel": _USAGE_LABELS[bucket_key],
        "usageCount": len(companies),
        "usedBy": [
            {"company": c, "hex": company_hex.get((c, family), hex_code), "colorType": "primary"}
            for c in companies
        ],
        "association": bucket.get("description"),
    }


def adapt_color_analysis(data: dict) -> dict[str, Any]:
    company_hex = _build_company_hex_lookup(data.get("diversities", []))
    spectrum = [
        _adapt_color_spectrum_entry(key, data[key], company_hex)
        for key in ("very_common", "common", "occasional", "rare")
        if data.get(key)
    ]
    diversity = [
        {
            "company": d["company"],
            "hues": [{"hueFamily": h["hue_family"], "colors": h["colors"]} for h in d.get("hues", [])],
        }
        for d in data.get("diversities", [])
    ]
    warm, cold, neutral = data.get("warm", []), data.get("cold", []), data.get("neutral", [])
    total = len(warm) + len(cold) + len(neutral)
    return {
        "spectrum": spectrum,
        "diversity": diversity,
        "warmCoolSplit": {
            "warmPct": _pct(len(warm), total),
            "coolPct": _pct(len(cold), total),
            "neutralPct": _pct(len(neutral), total),
            "warmCompanies": warm,
            "coolCompanies": cold,
            "neutralCompanies": neutral,
        },
        "generatedAt": (data.get("very_common") or {}).get("generated_at"),
    }


@router.get("/color-insights")
async def get_color_insights(_: None = Depends(require_auth)) -> dict[str, Any]:
    data = _latest_snapshot("colors")
    if not data:
        return {"spectrum": [], "diversity": [], "warmCoolSplit": {
            "warmPct": 0, "coolPct": 0, "neutralPct": 0,
            "warmCompanies": [], "coolCompanies": [], "neutralCompanies": [],
        }, "generatedAt": None}
    return adapt_color_analysis(data)


# ---------------------------------------------------------------------------
# Fonts
# ---------------------------------------------------------------------------

_FONT_DIMENSION_LABELS = {
    "classification": "Classification",
    "weight_emphasis": "Weight Emphasis",
    "personality": "Personality",
}


def _adapt_dimension_category(category: dict) -> dict[str, Any]:
    return {
        "category": category.get("naming"),
        "pct": category.get("percentage"),
        "companies": category.get("companies", []),
    }


def adapt_font_analysis(data: dict) -> dict[str, Any]:
    similar = data.get("similar_fonts", [])
    archetypes = data.get("archetypes", [])
    generated_at = None
    if similar:
        generated_at = similar[0].get("generated_at")
    elif archetypes:
        generated_at = archetypes[0].get("generated_at")

    return {
        "similarFonts": [
            {
                "companies": s.get("companies", []),
                "sharedFontFamily": s.get("shared_font_family"),
                "sampleFontName": s.get("sample_font_name"),
                "note": s.get("note"),
            }
            for s in similar
        ],
        "archetypes": [
            {
                "name": a.get("naming"),
                "description": a.get("description"),
                "sampleFontName": a.get("sample_font_name"),
                "companies": a.get("companies", []),
            }
            for a in archetypes
        ],
        "dimensions": [
            {
                "key": key,
                "label": _FONT_DIMENSION_LABELS[key],
                "categories": [_adapt_dimension_category(c) for c in data.get(key, [])],
            }
            for key in ("classification", "weight_emphasis", "personality")
        ],
        "generatedAt": generated_at,
    }


@router.get("/font-insights")
async def get_font_insights(_: None = Depends(require_auth)) -> dict[str, Any]:
    data = _latest_snapshot("fonts")
    if not data:
        return {"similarFonts": [], "archetypes": [], "dimensions": [], "generatedAt": None}
    return adapt_font_analysis(data)


# ---------------------------------------------------------------------------
# Logos
# ---------------------------------------------------------------------------

_LOGO_DIMENSION_LABELS = {
    "type": "Type",
    "color": "Color",
    "shape_style": "Shape Style",
    "signal_shape": "Signal Shape",
}


def adapt_logo_dimensions(data: dict) -> dict[str, Any]:
    any_category = next(
        (c for key in _LOGO_DIMENSION_LABELS for c in data.get(key, [])), None
    )
    return {
        "dimensions": [
            {
                "key": {"shape_style": "shapeStyle", "signal_shape": "signalShape"}.get(key, key),
                "label": label,
                "categories": [_adapt_dimension_category(c) for c in data.get(key, [])],
            }
            for key, label in _LOGO_DIMENSION_LABELS.items()
        ],
        "logoUrls": data.get("logo_urls", {}),
        "generatedAt": any_category.get("generated_at") if any_category else None,
    }


def adapt_logo_placement(data: dict) -> dict[str, Any]:
    placement = data.get("placement", [])
    return {
        "positions": [
            {
                "position": p.get("position"),
                "pct": p.get("percentage"),
                "companies": p.get("companies", []),
            }
            for p in placement
        ],
        "logoUrls": data.get("logo_urls", {}),
        "generatedAt": placement[0].get("generated_at") if placement else None,
    }


@router.get("/logo-dimensions")
async def get_logo_dimensions(_: None = Depends(require_auth)) -> dict[str, Any]:
    data = _latest_snapshot("logos")
    if not data:
        return {"dimensions": [], "logoUrls": {}, "generatedAt": None}
    return adapt_logo_dimensions(data)


@router.get("/logo-placement")
async def get_logo_placement(_: None = Depends(require_auth)) -> dict[str, Any]:
    data = _latest_snapshot("logos")
    if not data:
        return {"positions": [], "logoUrls": {}, "generatedAt": None}
    return adapt_logo_placement(data)


# ---------------------------------------------------------------------------
# Imagery
# ---------------------------------------------------------------------------

_IMAGERY_DIMENSION_LABELS = {
    "style": "Style",
    "effect": "Effect",
    "subject": "Subject Matter",
    "look_feel": "Look & Feel",
    "color_scheme": "Color Scheme",
}


def adapt_imagery_archetypes(data: dict) -> dict[str, Any]:
    archetypes = data.get("archetypes", [])
    return {
        "archetypes": [
            {
                "name": a.get("naming"),
                "description": a.get("description"),
                "image": a.get("sample_image"),
                "companies": a.get("companies", []),
            }
            for a in archetypes
        ],
        "generatedAt": archetypes[0].get("generated_at") if archetypes else None,
    }


def adapt_imagery_dimensions(data: dict) -> dict[str, Any]:
    any_category = next(
        (c for key in _IMAGERY_DIMENSION_LABELS for c in data.get(key, [])), None
    )
    return {
        "dimensions": [
            {
                "key": {"look_feel": "lookFeel", "color_scheme": "colorScheme"}.get(key, key),
                "label": label,
                "categories": [_adapt_dimension_category(c) for c in data.get(key, [])],
            }
            for key, label in _IMAGERY_DIMENSION_LABELS.items()
        ],
        "generatedAt": any_category.get("generated_at") if any_category else None,
    }


def adapt_imagery_similarity(data: dict) -> dict[str, Any]:
    usage = data.get("usage", [])
    similarity = data.get("similarity", [])
    return {
        "nodes": [{"company": u.get("company"), "imageCount": u.get("count")} for u in usage],
        "links": [
            {
                "source": s.get("company_a"),
                "target": s.get("company_b"),
                "similarity": s.get("similarity"),
            }
            for s in similarity
        ],
        "generatedAt": usage[0].get("generated_at") if usage else None,
    }


@router.get("/imagery-archetypes")
async def get_imagery_archetypes(_: None = Depends(require_auth)) -> dict[str, Any]:
    data = _latest_snapshot("images")
    if not data:
        return {"archetypes": [], "generatedAt": None}
    return adapt_imagery_archetypes(data)


@router.get("/imagery-dimensions")
async def get_imagery_dimensions(_: None = Depends(require_auth)) -> dict[str, Any]:
    data = _latest_snapshot("images")
    if not data:
        return {"dimensions": [], "generatedAt": None}
    return adapt_imagery_dimensions(data)


@router.get("/imagery-similarity")
async def get_imagery_similarity(_: None = Depends(require_auth)) -> dict[str, Any]:
    data = _latest_snapshot("images")
    if not data:
        return {"nodes": [], "links": [], "generatedAt": None}
    return adapt_imagery_similarity(data)


# ---------------------------------------------------------------------------
# Video
# ---------------------------------------------------------------------------

_VIDEO_DIMENSION_LABELS = {
    "format": "Format",
    "effect": "Effect",
    "length": "Length",
    "presence": "Presence",
}


def adapt_video_insights(data: dict) -> dict[str, Any]:
    archetypes = data.get("archetypes", [])
    usage = data.get("usage", [])
    any_category = next(
        (c for key in _VIDEO_DIMENSION_LABELS for c in data.get(key, [])), None
    )
    return {
        "archetypes": [
            {
                "name": a.get("naming"),
                "description": a.get("description"),
                "thumbnail": a.get("thumbnail"),
                "companies": a.get("companies", []),
            }
            for a in archetypes
        ],
        "dimensions": [
            {
                "key": key,
                "label": label,
                "categories": [_adapt_dimension_category(c) for c in data.get(key, [])],
            }
            for key, label in _VIDEO_DIMENSION_LABELS.items()
        ],
        "usage": [
            {
                "company": u.get("company"),
                "count": u.get("count"),
                "avgDurationSeconds": u.get("avg_duration_seconds"),
            }
            for u in usage
        ],
        "generatedAt": any_category.get("generated_at") if any_category else None,
    }


@router.get("/video-insights")
async def get_video_insights(_: None = Depends(require_auth)) -> dict[str, Any]:
    data = _latest_snapshot("videos")
    if not data:
        return {"archetypes": [], "dimensions": [], "usage": [], "generatedAt": None}
    return adapt_video_insights(data)


# ---------------------------------------------------------------------------
# Trends
# ---------------------------------------------------------------------------

def adapt_visual_trends(data: dict) -> dict[str, Any]:
    trends = data.get("trends", [])
    return {
        "trends": [
            {
                "element": t.get("element"),
                "direction": t.get("direction"),
                "summary": t.get("summary"),
            }
            for t in trends
        ],
        "generatedAt": trends[0].get("generated_at") if trends else None,
    }


@router.get("/visual-trends")
async def get_visual_trends(_: None = Depends(require_auth)) -> dict[str, Any]:
    data = _latest_snapshot("trends")
    if not data:
        return {"trends": [], "generatedAt": None}
    return adapt_visual_trends(data)


# ---------------------------------------------------------------------------
# Brand archetypes (cross-dimension synthesis — nodes/archetypes.py)
# ---------------------------------------------------------------------------

def adapt_brand_archetypes(data: dict) -> dict[str, Any]:
    archetypes = data.get("archetypes", [])
    return {
        "archetypes": [
            {
                "name": a.get("naming"),
                "keywords": a.get("keywords", []),
                "vibe": a.get("vibe"),
                "typography": a.get("typography"),
                "coloring": a.get("coloring"),
                "image": a.get("sample_image"),
                "companies": a.get("companies", []),
            }
            for a in archetypes
        ],
        "generatedAt": archetypes[0].get("generated_at") if archetypes else None,
    }


@router.get("/archetypes")
async def get_brand_archetypes(_: None = Depends(require_auth)) -> dict[str, Any]:
    data = _latest_snapshot("brand_archetypes")
    if not data:
        return {"archetypes": [], "generatedAt": None}
    return adapt_brand_archetypes(data)


# ---------------------------------------------------------------------------
# Alerts
# ---------------------------------------------------------------------------

@router.get("/alerts")
async def get_alerts(_: None = Depends(require_auth)) -> dict[str, Any]:
    data = _latest_snapshot("alerts")
    if not data:
        return {"color": None, "font": None, "logo": None, "image": None, "video": None, "trend": None}
    return data
