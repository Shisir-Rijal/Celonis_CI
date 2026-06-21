from pydantic import BaseModel, Field
from datetime import datetime, timezone
from typing import TypedDict, NotRequired, Annotated
import operator

# --- BaseData: provenance stamp for every interpreted insight below.
# Lighter cousin of research/state.py's BaseData (RAG-chunk metadata,
# company+url+entities+...) — that one doesn't fit here because these
# sub-classes are cross-company groupings, not per-company source chunks.
# Deliberately NOT applied to the top-level *Analysis classes: those are
# just containers, re-assembled fresh from their (independently timestamped)
# children each run, so a single blanket date on them would be misleading.

class BaseData(BaseModel):
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))


# --Shared:

class DimensionCategory(BaseData):
    """Generic category + usage-share + who-uses-it bucket, reused across every
    "how do tracked competitors break down on X" dimension (renamed from the
    image-only `ImageryDimensions` so fonts/logos/videos can reuse it too —
    mirrors the frontend's shared `DimensionCategory` type 1:1)."""
    naming: str
    percentage: float | int
    companies: list[str]


# --Color-Node:

class ColorSpectrum(BaseData):
    type: str
    color: str
    companies: list[str]
    description: str

class HueGroup(BaseModel):
    # nested fragment of one ColorDiversity insight, not a standalone finding — no BaseData
    hue_family: str
    colors: list[str]

class ColorDiversity(BaseData):
    company: str
    count: int
    hues: list[HueGroup]

class ColorAnalysis(BaseModel): # wird übergeben an VisualBrandingState
    very_common: ColorSpectrum
    common: ColorSpectrum
    occasional: ColorSpectrum
    rare: ColorSpectrum
    diversities: list[ColorDiversity]
    warm: list[str]     # Companies
    cold: list[str]
    neutral: list[str]


# --Font-Node:

class SimilarFontGroup(BaseData):
    companies: list[str]
    shared_font_family: str
    sample_font_name: str  # real Google Fonts family name, used to render a live preview
    note: str | None

class FontArchetype(BaseData):
    naming: str
    description: str
    sample_font_name: str
    companies: list[str]

class FontAnalysis(BaseModel):
    similar_fonts: list[SimilarFontGroup]
    archetypes: list[FontArchetype]
    classification: list[DimensionCategory]   # Serif / Sans-serif / Monospace / Display
    weight_emphasis: list[DimensionCategory]  # Light / Regular / Bold-heavy
    personality: list[DimensionCategory]      # Modern / Traditional / Playful / Technical


# --Logo-Node:

class LogoPlacement(BaseData):
    position: str  # "top-left" | "top-center" | "top-right" | "center" |
                    # "bottom-left" | "bottom-center" | "bottom-right" | "not-present"
    percentage: float | int
    companies: list[str]

class LogoAnalysis(BaseModel):
    type: list[DimensionCategory]          # Wordmark / Combination mark / Icon-only
    color: list[DimensionCategory]         # Colored / Monochrome
    shape_style: list[DimensionCategory]   # Rounded / Angular / Mixed
    signal_shape: list[DimensionCategory]  # Circle / Square / Abstract / None — typographic only
    placement: list[LogoPlacement]
    logo_urls: dict[str, str] = {}         # {company: logo image URL} — lets the frontend show
                                            # the actual logo behind any company name in any bucket above


# --Image-Node:

class ArchetypeAnalysis(BaseData):
    naming: str
    description: str
    sample_image: str  # representative image URL illustrating this style cluster
    companies: list[str]

class ImagerySimilarity(BaseData):
    company_a: str
    company_b: str
    similarity: float  # 0-1

class ImageUsage(BaseData):
    company: str
    count: int  # number of scraped marketing images analyzed for this company

class ImageAnalysis(BaseModel):
    archetypes: list[ArchetypeAnalysis]
    similarity: list[ImagerySimilarity]
    style: list[DimensionCategory]
    effect: list[DimensionCategory]
    subject: list[DimensionCategory]
    look_feel: list[DimensionCategory]
    color_scheme: list[DimensionCategory]
    usage: list[ImageUsage]


# --Video-Node:

class VideoArchetype(BaseData):
    naming: str
    description: str
    thumbnail: str  # representative thumbnail (or video URL) illustrating this style cluster
    companies: list[str]

class VideoUsage(BaseData):
    company: str
    count: int
    avg_duration_seconds: int | None

class VideoAnalysis(BaseModel):
    archetypes: list[VideoArchetype]
    format: list[DimensionCategory]    # Product Demo / Testimonial / Explainer / Brand Film
    effect: list[DimensionCategory]    # Emotional / Technical / Aspirational
    length: list[DimensionCategory]    # Short (<1min) / Medium / Long
    presence: list[DimensionCategory]  # Captioned / Voiceover / Silent
    usage: list[VideoUsage]


# --Trends-Node:

class ElementTrend(BaseData):
    element: str     # "Color" | "Font" | "Logo" | "Imagery" | "Video"
    direction: str   # "up" | "down" | "flat"
    summary: str

class TrendAnalysis(BaseModel):
    trends: list[ElementTrend]

# --Brand-Archetype-Node: cross-dimension synthesis, not gated on a single
# raw VisualsData field — built from every other node's persisted output.

class BrandArchetype(BaseData):
    naming: str
    keywords: list[str]       # short vibe descriptors, e.g. ["Bold", "Technical", "Disruptive"]
    vibe: str                 # one-sentence overall personality summary
    typography: str           # one-sentence summary of this cluster's typographic identity
    coloring: str              # one-sentence summary of this cluster's color identity
    sample_image: str | None  # representative image URL, or None if nothing scraped yet
    companies: list[str]      # can be a single company — not every archetype needs 2+ members
    # Per-dimension trait signature this archetype was built from (color_temp,
    # font_personality, logo_type, ...) — not shown in the UI, used only to
    # decide next run whether a company still "fits" this exact archetype
    # (see nodes/archetypes.py) rather than being reshuffled into a new one.
    signature: dict[str, str] = Field(default_factory=dict)

class BrandArchetypeAnalysis(BaseModel):
    archetypes: list[BrandArchetype]


class AlertAnalysis(BaseModel):
    color: list[str] | None
    font: list[str] | None
    logo: list[str] | None
    image: list[str] | None
    video: list[str] | None
    trend: list[str] | None



class VisualBrandingState(TypedDict):
    # Each is NotRequired: the change-detection router (graph.py) only routes
    # to nodes whose source data actually changed, so any given run's state
    # may legitimately be missing keys for nodes that were skipped.
    colors: NotRequired[ColorAnalysis]
    fonts: NotRequired[FontAnalysis]
    logos: NotRequired[LogoAnalysis]
    images: NotRequired[ImageAnalysis]
    videos: NotRequired[VideoAnalysis]
    trends: NotRequired[TrendAnalysis]
    brand_archetypes: NotRequired[BrandArchetypeAnalysis]
    alerts: NotRequired[AlertAnalysis]

    # Per-dimension change-description fragments (see alerts.py) — each is
    # written by exactly one node, so no reducer needed. build_alerts_node
    # (graph.py) collects these into the final AlertAnalysis once every
    # interpretation node has run.
    color_alerts: NotRequired[list[str]]
    font_alerts: NotRequired[list[str]]
    logo_alerts: NotRequired[list[str]]
    image_alerts: NotRequired[list[str]]
    video_alerts: NotRequired[list[str]]
    trend_alerts: NotRequired[list[str]]

    # Bookkeeping — set by detect_changes_node, read by route_changed_nodes
    changed_nodes: NotRequired[list[str]]
    # Reducers so parallel-fanned-out nodes append rather than overwrite —
    # mirrors research/state.py's ResearchState.
    errors: Annotated[list[str], operator.add]
    completed_nodes: Annotated[list[str], operator.add]
