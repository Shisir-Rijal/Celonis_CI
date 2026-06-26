import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import asyncio
import html as html_lib  # aliased — this module uses `html` as a loop variable name (raw page HTML)
import io
import json
import re
import httpx
from datetime import date, datetime, timezone
from typing import Any
from urllib.parse import urljoin, urlparse
from firecrawl import V1FirecrawlApp as FirecrawlApp
from openai import AsyncOpenAI
from PIL import Image, UnidentifiedImageError
from app.agents.research.state import ResearchState, VisualsData, FontInfo, SourcedAsset
from app.agents.research.repositories.research_repository import insert_research_snapshot, snapshot_exists, get_latest_snapshot
import structlog
from app.config import get_settings
from app.agents.shared.utils.brandfetch import _get_brand_data
from app.agents.shared.competitors import get_competitor_names



logger = structlog.get_logger(__name__)
today = date.today().strftime("%Y-%m-%d")


# --- Website: Unterseiten einmal scrapen, dann für alle Extraktionen nutzen ---

async def _scrape_urls(urls: list[str]) -> list[tuple[str, str, str]]:
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)

    async def _scrape_one(url: str) -> tuple[str, str, str] | None:
        try:
            result = await asyncio.to_thread(app.scrape_url, url, formats=["markdown", "rawHtml"])
            markdown = getattr(result, "markdown", None) or ""
            html = getattr(result, "rawHtml", None) or getattr(result, "html", None) or ""
            if markdown:
                return (url, markdown, html)
        except Exception as e:
            logger.warning("page_scrape_failed", url=url, error=str(e))
        return None

    results = await asyncio.gather(*[_scrape_one(u) for u in urls])
    return [r for r in results if r is not None]


def _www_normalized_host(url: str) -> str:
    h = (urlparse(url).hostname or "").lower()
    return h[4:] if h.startswith("www.") else h


async def _get_page_contents(domain: str, num_pages: int = 5) -> list[tuple[str, str, str]]:
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    homepage = f"https://{domain}"

    # map_url frequently returns pages on unrelated subdomains (e.g. an
    # academy/LMS or docs subdomain running a completely different design
    # system) — over-fetch a larger candidate pool so that after filtering
    # those out, num_pages worth of genuine main-site pages still remain.
    map_result = await asyncio.to_thread(app.map_url, homepage, limit=num_pages * 4)
    mapped_urls: list[str] = getattr(map_result, "links", None) or []

    home_host = _www_normalized_host(homepage)
    same_site = [u for u in mapped_urls if _www_normalized_host(u) == home_host]

    # map_url's ordering doesn't guarantee the homepage itself is among the
    # first results, but it's where the primary logo, nav, and hero styling
    # usually live — always scrape it. Fall back to the unfiltered pool if
    # filtering to the main host would leave too few pages to work with.
    pool = same_site if len(same_site) >= num_pages else mapped_urls
    urls = [homepage] + [u for u in pool if u != homepage]
    urls = urls[:num_pages]
    logger.info("map_urls_found", count=len(urls), domain=domain)

    pages = await _scrape_urls(urls)
    logger.info("pages_ready", count=len(pages))
    return pages


# --- Videos: zusätzliche Kandidatenseiten finden + tote Links aussortieren ---

async def _discover_video_pages(domain: str, exclude: set[str]) -> list[str]:
    """Find extra pages likely to host demo/product videos (not always among the
    first homepage-linked pages already scraped for colors/fonts/images)."""
    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                "https://google.serper.dev/search",
                headers={"X-API-KEY": get_settings().SERPER_API_KEY},
                json={"q": f'site:{domain} video OR demo OR webinar OR "watch now"', "num": 5},
            )
        results = resp.json().get("organic", [])
        return [r["link"] for r in results if r.get("link") and r["link"] not in exclude]
    except Exception as e:
        logger.warning("video_page_discovery_failed", domain=domain, error=str(e))
        return []


async def _validate_videos(videos: list[SourcedAsset]) -> list[SourcedAsset]:
    """Drop videos that 404 or are otherwise unreachable/removed."""

    async def _check(asset: SourcedAsset) -> SourcedAsset | None:
        url = asset.url
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=6) as client:
                if "youtube.com" in url or "youtu.be" in url:
                    resp = await client.get(
                        "https://www.youtube.com/oembed",
                        params={"url": url, "format": "json"},
                    )
                elif "vimeo.com" in url:
                    resp = await client.get(
                        "https://vimeo.com/api/oembed.json",
                        params={"url": url},
                    )
                else:
                    resp = await client.head(url)
                if resp.status_code < 400:
                    return asset
        except Exception:
            pass
        return None

    results = await asyncio.gather(*[_check(v) for v in videos])
    return [v for v in results if v]


MIN_IMAGE_DIMENSION = 50  # px — smaller than this reads as an icon/UI asset, not a real image
MAX_IMAGE_DOWNLOAD_BYTES = 15 * 1024 * 1024  # safety cap, real web images never approach this

# Some asset CDNs (Akamai, etc.) block plain httpx requests with a 403 or by
# dropping the connection outright, even for perfectly real, public images —
# Firecrawl's headless browser already rendered the page successfully, so a
# generic browser UA + Accept header at least clears the simpler WAF checks.
_BROWSER_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    ),
    "Accept": "image/avif,image/webp,image/apng,image/*,*/*;q=0.8",
}


async def _validate_images(images: list[SourcedAsset]) -> tuple[list[SourcedAsset], list[SourcedAsset]]:
    """Drop images that confirmed-404, or don't resolve to real image content;
    route anything smaller than MIN_IMAGE_DIMENSION on either axis to icons
    instead of dropping it outright (it's still a valid asset, just icon-sized).

    Network-level failures and non-404 error responses (timeouts, connection
    resets, 403, 429, ...) are NOT treated as proof the image is dead — bot
    protection on the CDN blocking our direct request looks identical to a
    broken link, but punishing a real image for that would just recreate the
    bug we're trying to fix. Only a clean 404 is trusted as "actually gone".

    Returns (kept_images, demoted_to_icons).
    """

    async def _check(asset: SourcedAsset) -> tuple[str, SourcedAsset]:
        url = asset.url
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=10, headers=_BROWSER_HEADERS) as client:
                resp = await client.get(url)
        except Exception:
            return "image", asset  # likely blocked, not actually missing — keep it

        if resp.status_code == 404:
            return "drop", asset
        if resp.status_code >= 400:
            return "image", asset  # probably blocked (403/429/etc.), not missing
        content_type = resp.headers.get("content-type", "")
        if content_type and not content_type.startswith("image/"):
            return "drop", asset
        content_length = resp.headers.get("content-length")
        if content_length and int(content_length) > MAX_IMAGE_DOWNLOAD_BYTES:
            return "drop", asset
        try:
            with Image.open(io.BytesIO(resp.content)) as img:
                width, height = img.size
        except (UnidentifiedImageError, OSError):
            return "drop", asset
        if width < MIN_IMAGE_DIMENSION or height < MIN_IMAGE_DIMENSION:
            return "icon", asset
        return "image", asset

    results = await asyncio.gather(*[_check(i) for i in images])
    kept = [asset for kind, asset in results if kind == "image"]
    demoted = [asset for kind, asset in results if kind == "icon"]
    return kept, demoted


# --- Brandfetch: Logo, Colors, Fonts ---


def _resolve_asset_url(raw: str | None, page_url: str) -> str | None:
    """Resolve a possibly relative or protocol-relative URL against the page
    it was found on. Returns None if it still doesn't end up absolute http(s)."""
    if not raw:
        return None
    raw = raw.strip()
    if not raw:
        return None
    if raw.startswith("//"):
        raw = "https:" + raw
    resolved = urljoin(page_url, raw)
    return resolved if resolved.startswith("http") else None


def _first_srcset_url(srcset: str) -> str | None:
    """A `srcset`/`data-srcset` value is a comma-separated list of "url descriptor"
    candidates (e.g. "a.png 1x, b.png 2x" or "a.png 480w, b.png 800w") — take
    the first one when there's no plain `src`/`data-src` to fall back to."""
    first = srcset.split(",")[0].strip()
    return first.split()[0] if first else None


# Many modern sites render images through custom elements (e.g. ServiceNow's
# <arc-image srcset="...">) instead of plain <img> tags. Matching on the
# srcset/data-srcset/data-src attribute name — rather than the tag name —
# catches those too. Plain `src` is deliberately excluded here (handled
# separately, scoped to <img>) since <script src=...>/<iframe src=...> would
# otherwise also match.
_RESPONSIVE_ASSET_TAG_RE = re.compile(
    r'<[a-zA-Z][\w-]*\b[^>]*?(?:srcset|data-srcset|data-src)\s*=\s*["\'][^"\']*["\'][^>]*>',
    re.IGNORECASE,
)


def _candidate_asset_tags(html: str) -> set[str]:
    """All <img> tags plus any other tag carrying a responsive-image attribute."""
    tags = set(re.findall(r'<img\b[^>]*>', html, re.IGNORECASE))
    tags.update(_RESPONSIVE_ASSET_TAG_RE.findall(html))
    return tags


def _extract_asset_from_tag(tag: str, page_url: str) -> tuple[str | None, str]:
    """Resolved asset URL + alt text from an <img> or img-like custom-element tag,
    preferring `src`, then `data-src`, then the first `srcset`/`data-srcset` candidate."""
    src_match = re.search(r'\bsrc\s*=\s*["\']([^"\']+)["\']', tag, re.IGNORECASE)
    raw_src = src_match.group(1) if src_match else None
    if not raw_src:
        data_src_match = re.search(r'\bdata-src\s*=\s*["\']([^"\']+)["\']', tag, re.IGNORECASE)
        raw_src = data_src_match.group(1) if data_src_match else None
    if not raw_src:
        srcset_match = re.search(r'\b(?:srcset|data-srcset)\s*=\s*["\']([^"\']*)["\']', tag, re.IGNORECASE)
        raw_src = _first_srcset_url(srcset_match.group(1)) if srcset_match else None
    # HTML attributes legitimately spell "&" as "&amp;" — without unescaping,
    # a URL like "...&amp;w=3840&amp;q=75" gets stored with the literal
    # entity still in it, which most CDNs (Next.js image API included) 400
    # on, since "amp;w" isn't a recognized query param. That produced a
    # broken-image render for every page using this pattern.
    raw_src = html_lib.unescape(raw_src) if raw_src else raw_src
    url = _resolve_asset_url(raw_src, page_url)
    alt_match = re.search(r'\balt\s*=\s*["\']([^"\']*)["\']', tag, re.IGNORECASE)
    return url, (alt_match.group(1) if alt_match else "")


# Catches "customer stories" testimonial-carousel logos like
# "1031661-customerstories-logos-03" or "Customer-stories-02-Logo-160x68" —
# variants _THIRD_PARTY_PATH_KEYWORDS' plain "customer-logo" substring check
# misses because "stories"/a numeric slide id sits between the two words.
# Deliberately scoped to logo detection only (requires "logo" nearby) so it
# can't catch unrelated, legitimate "customer story" content images that
# don't mention "logo" at all (e.g. a hero photo at /customer-story/...).
_THIRD_PARTY_LOGO_CONTEXT_RE = re.compile(r'customer.{0,3}stor(?:y|ies).{0,20}logo', re.IGNORECASE)

# Social-share/follow buttons are often filenamed "<platform>-logo" — that's
# the platform's logo, never the scraped company's own.
_SOCIAL_PLATFORM_NAMES = {
    "twitter", "facebook", "linkedin", "instagram", "youtube", "tiktok",
    "github", "pinterest", "reddit", "whatsapp", "telegram", "mastodon",
    "threads", "bluesky", "vimeo", "slack", "snapchat",
}


def _is_third_party_logo(url: str, context: str) -> bool:
    low_url = url.lower()
    if any(kw in low_url for kw in _THIRD_PARTY_PATH_KEYWORDS):
        return True
    if any(kw in context.lower() for kw in _THIRD_PARTY_CONTEXT_KEYWORDS):
        return True
    if _THIRD_PARTY_LOGO_CONTEXT_RE.search(url):
        return True
    if any(name in low_url for name in _SOCIAL_PLATFORM_NAMES):
        return True
    if any(name in low_url for name in _THIRD_PARTY_BRAND_KEYWORDS):
        return True
    return False


def _url_path_lower(url: str) -> str:
    """The path+query of a URL, lowercased — deliberately excludes the
    hostname so checking "does the company's name appear in this URL" can't
    trivially match just because the image happens to be hosted on the
    company's own domain (e.g. aris.com/.../suva-logo.svg contains "aris"
    only because of the domain, not because it's ARIS's own logo)."""
    parsed = urlparse(url)
    return f"{parsed.path}?{parsed.query}".lower()


def _company_name_in_path(url: str, company_lower: str) -> bool:
    """Whether `company_lower` genuinely identifies this URL as the
    company's own asset — not just a coincidental match inside a generic
    CDN bucket-name segment. Many sites file every asset (including OTHER
    brands' customer/partner logos) under a path like
    ".../servicenow-assets/.../logo-siemens-white.svg" — the bare substring
    check would call that "ServiceNow's own" purely because of the bucket
    name, even though the actual logo in it is Siemens'. Scrubbing that one
    well-known noisy pattern before checking removes the false signal
    without touching genuine matches (e.g. ".../logo-white_<hash>.svg"
    sitting under an "Apromore_March_2024" folder still matches)."""
    path = _url_path_lower(url)
    scrubbed = re.sub(rf"{re.escape(company_lower)}[-_]?assets", "", path)
    return company_lower in scrubbed


# Brandfetch's own CDN regularly serves files literally named "logo.svg" with
# no company name anywhere in the URL — trust those rather than applying the
# stricter "company name must appear" rule meant for other-domain fallback scans.
_TRUSTED_LOGO_CDN_HOSTS = {"cdn.brandfetch.io"}


def _looks_like_own_logo(url: str, company: str) -> bool:
    """Used to retroactively re-check logos already stored from a previous run
    against the (possibly newer/stricter) company-name requirement, without
    punishing legitimate Brandfetch URLs that never carry the company name.

    Requires the company's own name in the URL path for everything else —
    including URLs with no "logo" in them at all. That used to auto-pass,
    on the theory that a real logo can be served from a hash-named CDN path
    with no descriptive filename — but the same permissiveness let plain
    content images that slipped into `logo` via a loose alt-text match
    (no "logo" in their URL either) survive re-validation forever, since
    no alt/context text is available retroactively to catch them any other
    way (e.g. Palantir's "Adobe_Express_-_file.png", UiPath's
    "latest_thumb_AgenticSolutions.png")."""
    host = (urlparse(url).hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in _TRUSTED_LOGO_CDN_HOSTS):
        return True
    return _company_name_in_path(url, company.lower())


_RASTER_LOGO_EXTENSIONS = ("png", "webp", "jpg", "jpeg")


_LOGO_DIMENSION_SEGMENT_RE = re.compile(r"/w/\d+/h/\d+")


def _logo_asset_key(url: str) -> str:
    """Identity for "the same logo artwork, any file format" — query string,
    extension, AND any `/w/<width>/h/<height>/` sizing segment stripped.
    Brandfetch inserts that sizing segment only for raster formats (vector
    SVGs don't need one), so e.g. ".../theme/dark/logo.svg" and
    ".../w/800/h/319/theme/dark/logo.png" must both reduce to
    ".../theme/dark/logo" to be recognized as the same artwork."""
    path = _LOGO_DIMENSION_SEGMENT_RE.sub("", url.split("?", 1)[0])
    return path.rsplit(".", 1)[0] if "." in path.rsplit("/", 1)[-1] else path


def _dedupe_logo_formats(urls: list[str]) -> list[str]:
    """One URL per distinct logo artwork, preferring a raster format over
    SVG. Brandfetch's SVG logos have proven unreliable to render here: some
    ship with no fill at all (defaulting to black per the SVG spec), others
    bake in a fixed light/dark color that goes invisible against whichever
    UI surface doesn't match — a raster format always renders its own
    pixels regardless of background, so it wins whenever both exist for the
    same artwork. Order-preserving and safe to re-run on an already-merged
    list (e.g. to retroactively drop an SVG twin a previous run stored)."""
    by_asset: dict[str, str] = {}
    for url in urls:
        key = _logo_asset_key(url)
        ext = url.split("?", 1)[0].rsplit(".", 1)[-1].lower()
        current = by_asset.get(key)
        if current is None:
            by_asset[key] = url
            continue
        current_ext = current.split("?", 1)[0].rsplit(".", 1)[-1].lower()
        if current_ext not in _RASTER_LOGO_EXTENSIONS and ext in _RASTER_LOGO_EXTENSIONS:
            by_asset[key] = url
    return list(by_asset.values())


def _extract_logos(data: dict, pages: list[tuple[str, str, str]], company: str) -> list[str]:
    # Brandfetch zuerst
    seen: set[str] = set()
    urls: list[str] = []
    for logo in data.get("logos", []):
        for fmt in logo.get("formats", []):
            src = fmt.get("src")
            if src and src not in seen:
                seen.add(src)
                urls.append(src)
    if urls:
        return _dedupe_logo_formats(urls)

    # Fallback: scan rawHtml (not just markdown, which often strips header/nav
    # chrome out as "boilerplate") for img-like tags. The site's own logo
    # almost always lives inside <header>/<nav>, so those regions are scanned
    # first and preferred; anywhere else on the page is a fallback.
    #
    # "logo" in the URL is NEVER enough on its own, in EITHER region — that's
    # exactly where customer/partner logo carousels live (e.g. ARIS's
    # "suva-logo.svg", Apromore's "Logo-One.nz.png", or ServiceNow's
    # "logo-siemens-white.svg"/"logo-fedex-white.svg" sitting inside an
    # oversized <nav> that turned out to also contain a customer-logo strip).
    # The company's own name must also appear somewhere in the URL/alt,
    # mirroring the same rule _classify_image already applies for images.
    #
    # Within header/nav we additionally accept images with NO "logo" in the
    # URL at all, purely by alt text (many real logos are served from a CDN
    # asset hash with no descriptive filename — Microsoft's own nav logo is
    # exactly this: alt="Microsoft", no "logo" in the URL) — but that alt
    # text must be essentially JUST the company name, not merely contain it
    # somewhere; a loose substring match let unrelated content images
    # through whenever their caption happened to mention the company (e.g.
    # Palantir's "Adobe_Express_-_file.png" captioned with a Palantir
    # customer-story headline, or UiPath's marketing thumbnails captioned
    # "UiPath Agentic Solutions...").
    header_urls: list[str] = []
    other_urls: list[str] = []
    company_lower = company.lower()

    def _alt_is_just_company_name(alt: str) -> bool:
        stripped = re.sub(r"\b(logo|icon)\b", "", alt.lower()).strip()
        return stripped == company_lower

    def _scan_region(
        region_html: str, page_html: str, page_url: str, bucket: list[str], allow_alt_only_match: bool
    ) -> None:
        for tag in _candidate_asset_tags(region_html):
            url, alt = _extract_asset_from_tag(tag, page_url)
            if not url or url in seen:
                continue
            url_has_logo = "logo" in url.lower()
            alt_only_match = allow_alt_only_match and not url_has_logo and _alt_is_just_company_name(alt)
            if not url_has_logo and not alt_only_match:
                continue
            if url_has_logo and not _company_name_in_path(url, company_lower) and company_lower not in alt.lower():
                continue
            context = _html_window_text(page_html, tag)
            if _is_third_party_logo(url, context):
                continue
            seen.add(url)
            bucket.append(url)

    for page_url, markdown, html in pages:
        header_html = "".join(re.findall(r'<header\b.*?</header>', html, re.IGNORECASE | re.DOTALL))
        header_html += "".join(re.findall(r'<nav\b.*?</nav>', html, re.IGNORECASE | re.DOTALL))
        _scan_region(header_html, html, page_url, header_urls, allow_alt_only_match=True)
        _scan_region(html, html, page_url, other_urls, allow_alt_only_match=False)

        for src in re.findall(r'!\[([^\]]*)\]\((https?://[^\)]+)\)', markdown):
            alt, url = src
            if (
                "logo" in url.lower()
                and url not in seen
                and (_company_name_in_path(url, company_lower) or company_lower in alt.lower())
                and not _is_third_party_logo(url, "")
            ):
                seen.add(url)
                other_urls.append(url)

    return header_urls + other_urls


_HEX_COLOR_RE = re.compile(r'#([0-9A-Fa-f]{6}|[0-9A-Fa-f]{3})\b')


def _normalize_hex(raw: str) -> str:
    if len(raw) == 3:
        raw = "".join(c * 2 for c in raw)
    return f"#{raw.upper()}"


def _saturation(hex_color: str) -> int:
    """Rough saturation proxy (0-255): max channel - min channel. Higher
    means more vivid/colorful; near 0 means grayscale."""
    h = hex_color.lstrip("#").strip()
    if len(h) == 3:
        h = "".join(c * 2 for c in h)
    if len(h) != 6:
        return 0
    try:
        r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    except ValueError:
        return 0
    return max(r, g, b) - min(r, g, b)


def _is_grayscale(hex_color: str) -> bool:
    """True for black/white/grey — R, G, B channels all close to equal.
    Catches near-black/near-white tones (e.g. "#161616", "#F4F4F4"), not
    just exact "#000000"/"#FFFFFF"."""
    return _saturation(hex_color) <= 12


# Design-token systems name their status/utility colors after what they
# mean (e.g. `--fnd-color-semantic-border-success: #0b9e23`), not after any
# real brand identity — checked in order, first match wins. Kept broader than
# what's actually reported (see _REPORTED_SEMANTIC_LABELS below) so e.g. a
# "disabled"-state grey-blue is still excluded from primary/secondary
# candidates even though it's not itself surfaced as a semantic color.
_SEMANTIC_KEYWORD_LABELS: list[tuple[str, str]] = [
    ("disabled", "disabled"),
    ("success", "success"),
    ("positive", "success"),
    ("danger", "error"),
    ("error", "error"),
    ("negative", "error"),
    ("critical", "error"),
    ("destructive", "error"),
    ("warning", "warning"),
    ("warn", "warning"),
    ("caution", "warning"),
    ("info", "info"),
]

# Only these are reported as "semantic colors" to the user — error/warning/
# success cover what's actually meaningful as a status color; "disabled"/
# "info" stay excluded from primary/secondary above but aren't themselves
# interesting enough to surface.
_REPORTED_SEMANTIC_LABELS = {"success", "warning", "error"}

# Default color-palette swatches that ship with common CMS/editor stacks
# regardless of whether the site's content actually uses them — e.g.
# WordPress's Gutenberg block editor injects these 9 preset colors into
# every theme's compiled CSS, so on WP sites they show up as "used" in the
# stylesheet even when nothing on the page is actually styled with them.
_FRAMEWORK_DEFAULT_COLORS = {
    "#F78DA7", "#CF2E2E", "#FF6900", "#FCB900", "#7BDCB5",
    "#00D084", "#8ED1FC", "#0693E3", "#9B51E0",
}

# The browser's own built-in default link colors (UA stylesheet / legacy
# HTML spec) — show up incidentally wherever a reset/normalize stylesheet
# or un-styled <a> still carries one of these, never a deliberate brand
# choice. Worth excluding specifically (unlike other incidental colors)
# because they're maximally saturated, so the saturation-weighted primary
# pick below would otherwise favor one of these over a less-saturated but
# genuinely deliberate accent color (e.g. Anthropic's actual orange #D97757
# losing to the default link blue #0000EE purely on vividness).
_BROWSER_DEFAULT_LINK_COLORS = {"#0000EE", "#0000FF", "#551A8B"}

# A color used in only one CSS rule block reads as a one-off illustration/
# icon fill, not a deliberate brand choice — never worth storing.
_MIN_COLOR_USAGE_COUNT = 2


def _css_property_name_at(css_text: str, pos: int) -> str:
    """The property name of the CSS declaration whose value starts at `pos`
    (e.g. "background-color" in "background-color: #fff;").

    Scoped to exactly the current declaration (from the last `;`/`{` up to
    the `:` right before this value) rather than a fixed-size character
    window — a blind window bleeds into the *previous* declaration's name
    (e.g. matching "success" from the prior line while the actual property
    for this value is "...-danger") once enough short declarations are
    packed together, as a real design-token block often does."""
    stmt_start = max(css_text.rfind(";", 0, pos), css_text.rfind("{", 0, pos)) + 1
    colon_idx = css_text.rfind(":", stmt_start, pos)
    return css_text[stmt_start:colon_idx].strip().lower() if colon_idx != -1 else ""


def _extract_semantic_colors(css_text: str) -> dict[str, str]:
    """Hex colors whose CSS property/custom-property name (e.g.
    `--fnd-color-semantic-border-success:`) suggests a semantic/status
    meaning rather than an intentional brand color. These are genuinely used
    somewhere on the site (forms, alerts, badges) — just not as part of the
    brand palette — so they're kept out of primary/secondary and reported
    separately instead (see _REPORTED_SEMANTIC_LABELS for which labels
    actually surface to the user)."""
    semantic: dict[str, str] = {}
    for match in _HEX_COLOR_RE.finditer(css_text):
        hex_code = _normalize_hex(match.group(1))
        property_name = _css_property_name_at(css_text, match.start())
        for keyword, label in _SEMANTIC_KEYWORD_LABELS:
            if keyword in property_name:
                semantic[hex_code] = label
                break
    return semantic


# Property names that carry a color but aren't "the section's background" or
# "the text's font color" — these would otherwise slip through a naive
# "-color" suffix check and pollute the secondary-color pool with decorative
# accents that were never the actual ask. NOT "accent" as a bare substring:
# design-token systems name their actual brand/accent colors things like
# "--fnd-color-background-accent-green", which legitimately is a background
# color — only the literal CSS `accent-color` property (the decorative ring
# around checkboxes/radios) should be excluded, handled separately below.
_DECORATIVE_COLOR_PROPERTY_HINTS = (
    "border", "outline", "shadow", "decoration", "caret",
    "fill", "stroke", "placeholder", "scrollbar", "ring",
)


def _is_section_or_text_color_property(property_name: str) -> bool:
    if property_name == "accent-color" or property_name.endswith("-accent-color"):
        return False
    if any(hint in property_name for hint in _DECORATIVE_COLOR_PROPERTY_HINTS):
        return False
    return "background" in property_name or property_name == "color" or property_name.endswith("-color")


_RGB_FUNC_RE = re.compile(r'rgba?\(\s*([\d.]+)[,\s]+([\d.]+)[,\s]+([\d.]+)', re.IGNORECASE)
_RGB_TRIPLET_RE = re.compile(r'^\s*([\d.]+)\s*[,\s]\s*([\d.]+)\s*[,\s]\s*([\d.]+)\s*$')


def _channels_to_hex(r: str, g: str, b: str) -> str | None:
    try:
        ri, gi, bi = round(float(r)), round(float(g)), round(float(b))
    except ValueError:
        return None
    if not all(0 <= x <= 255 for x in (ri, gi, bi)):
        return None
    return f"#{ri:02X}{gi:02X}{bi:02X}"


_CUSTOM_PROPERTY_RE = re.compile(r'(--[\w-]+)\s*:\s*([^;]+);')
_VAR_REF_RE = re.compile(r'var\(\s*(--[\w-]+)')


def _build_custom_property_map(css_text: str) -> dict[str, str]:
    """{--design-token-name: hex} for every color-valued CSS custom property
    declared anywhere in the stylesheet — as a literal hex (`--foo: #hex`),
    an rgb()/rgba() function (`--foo: rgb(1,2,3)`), or a bare R, G, B channel
    triplet (`--foo-rgb: 1, 2, 3`, used elsewhere as `rgba(var(--foo-rgb),.5)`
    — a common Tailwind-style opacity-aware color pattern). Design-token
    systems (like Celonis's, IBM's, OpenAI's, ...) define their real brand
    colors once like this and reference them everywhere else via var(...) —
    without resolving these, a declaration like
    `background-color:var(--fnd-color-background-inverse)` looks colorless
    to a regex scan that only matches literal hex codes."""
    props: dict[str, str] = {}
    for name, raw_value in _CUSTOM_PROPERTY_RE.findall(css_text):
        value = raw_value.strip()
        hex_match = _HEX_COLOR_RE.search(value)
        if hex_match:
            props[name] = _normalize_hex(hex_match.group(1))
            continue
        rgb_match = _RGB_FUNC_RE.search(value) or _RGB_TRIPLET_RE.match(value)
        if rgb_match:
            hex_code = _channels_to_hex(*rgb_match.groups())
            if hex_code:
                props[name] = hex_code
    return props


def _resolve_block_colors(block: str, custom_props: dict[str, str]) -> set[str]:
    """Hex colors actually painted as a background/text color within one CSS
    rule block — resolving var(--token) references (via custom_props,
    chained up to 3 levels deep) and rgb()/rgba() function values, not just
    literal hex codes. Design-token systems declare their real colors once
    via custom properties and apply them everywhere through var(...); a scan
    that only matched literal "#RRGGBB" text in the block itself missed the
    overwhelming majority of a modern site's actual color usage (e.g.
    OpenAI's CSS has 900+ literal hex codes but barely any on a
    background/text property directly — almost everything goes through a
    custom property)."""

    def _resolve_var(token: str, depth: int = 3) -> str | None:
        value = custom_props.get(token)
        for _ in range(depth):
            if value is None:
                return None
            chain_match = _VAR_REF_RE.match(value.strip())
            if not chain_match:
                return value
            value = custom_props.get(chain_match.group(1))
        return None

    found: set[str] = set()
    for decl in re.finditer(r'([\w-]+)\s*:\s*([^;{}]+)', block):
        prop, value = decl.group(1).strip().lower(), decl.group(2)
        if not _is_section_or_text_color_property(prop):
            continue
        hex_match = _HEX_COLOR_RE.search(value)
        if hex_match:
            found.add(_normalize_hex(hex_match.group(1)))
            continue
        rgb_match = _RGB_FUNC_RE.search(value)
        if rgb_match:
            hex_code = _channels_to_hex(*rgb_match.groups())
            if hex_code:
                found.add(hex_code)
            continue
        var_match = _VAR_REF_RE.search(value)
        if var_match:
            resolved = _resolve_var(var_match.group(1))
            if resolved:
                found.add(resolved)
    return found


def _rank_section_colors(
    css_text: str, custom_props: dict[str, str], top_n: int = 40
) -> list[tuple[str, int]]:
    """Hex colors declared specifically as a `background`/`background-color`
    (a section's own background) or a `color`/`*-color` font/text color —
    never border/outline/shadow/etc — ranked by how many separate rule
    blocks use them this way (resolving var(--token)/rgb() values via
    _resolve_block_colors). Secondary brand colors should be colors actually
    painted onto the page as a section background or text color, not just
    any hex that happens to appear somewhere in the CSS.

    Grayscale is NOT excluded here — a genuinely deliberate neutral grey
    (e.g. a muted secondary-text or card-background grey) is a real, common
    secondary color choice. When Brandfetch has primary data, the LLM step
    that picks the final secondary colors is relied on to still tell a plain
    white-page-background or black-body-text default apart from an
    intentional grey accent; in the no-Brandfetch fallback (_extract_colors),
    this same pool also supplies primary candidates, where button-color
    promotion (_pick_fallback_primary) does the equivalent job of telling a
    deliberate black/white brand identity apart from incidental usage."""
    counts: dict[str, int] = {}
    for block_match in re.finditer(r'\{([^{}]*)\}', css_text):
        for hex_code in _resolve_block_colors(block_match.group(1), custom_props):
            counts[hex_code] = counts.get(hex_code, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top_n]


# Selectors that mark a rule block as styling an actual clickable
# button/CTA — a button's own background is the single strongest "this is
# our primary brand color" signal a website gives off, stronger than mere
# section-background frequency.
_BUTTON_SELECTOR_RE = re.compile(
    r'(?:^|[\s,>+~.])(?:button|\.btn\b|\.button\b|\.cta\b|'
    r'\[type=["\']?(?:submit|button)["\']?\]|input\[type=["\']?(?:submit|button)["\']?\])',
    re.IGNORECASE,
)


def _rank_button_colors(
    css_text: str, custom_props: dict[str, str], top_n: int = 10
) -> list[tuple[str, int]]:
    """Background/text colors declared on button-like selectors (button,
    .btn, .button, .cta, [type=submit], ...), ranked by how many separate
    rule blocks use them this way — resolving var(--token)/rgb() values via
    _resolve_block_colors, not just literal hex codes, since design-token
    systems style buttons through CSS variables almost exclusively."""
    counts: dict[str, int] = {}
    for block_match in re.finditer(r'([^{}]+)\{([^{}]*)\}', css_text):
        selector, block = block_match.group(1), block_match.group(2)
        if not _BUTTON_SELECTOR_RE.search(selector):
            continue
        for hex_code in _resolve_block_colors(block, custom_props):
            counts[hex_code] = counts.get(hex_code, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top_n]


def _pick_fallback_primary(
    candidates: list[tuple[str, int]], button_colors: list[tuple[str, int]], limit: int = 3
) -> list[str]:
    """Top `limit` colors by combined section/text frequency + button-usage
    count — with the single best chromatic (non grey/white/black) candidate
    guaranteed one slot if any exists. A button's own color is a strong
    "this is our primary brand color" signal, so it's added as a boost on
    top of the regular frequency score — not used to override frequency
    outright, which would let a rarely-used secondary/link button color
    crowd out the actual palette (e.g. a one-off blue "Sign up" link button
    outranking the brand's actual green just for appearing in its own single
    rule block).

    The chromatic guarantee exists because plain frequency alone
    systematically buries a brand's actual accent color: base text/section
    styling (black, white, grey) is painted on far more rule blocks
    site-wide than any one accent ever is, so without this, sites with a
    minimal black/white aesthetic plus a signature accent color (Anthropic's
    orange, ARIS's red/green, SAP Signavio's blue) would always end up with
    an all-grayscale primary despite a real accent existing in the data.
    That guaranteed slot goes to the candidate maximizing usage x
    saturation, not just usage alone — picking by usage alone tends to
    surface a merely-frequent dark/muted near-grayscale tone (e.g. a dark
    navy footer background) over a less-frequent but unmistakably "the
    brand color" vivid hue (e.g. SAP Signavio's saturated blue #0070F2).
    Grayscale isn't excluded from `candidates` itself, so a genuinely
    black/white-only brand identity (no chromatic candidate at all) still
    fills every slot, just like it would via Brandfetch."""
    scores: dict[str, int] = dict(candidates)
    for hex_code, count in button_colors:
        scores[hex_code] = scores.get(hex_code, 0) + count
    ranked = [h for h, _ in sorted(scores.items(), key=lambda kv: kv[1], reverse=True)]

    chromatic_candidates = [h for h in ranked if not _is_grayscale(h)]
    if not chromatic_candidates:
        return ranked[:limit]
    chromatic = max(chromatic_candidates, key=lambda h: scores[h] * _saturation(h))
    rest = [h for h in ranked if h != chromatic][: limit - 1]
    return [chromatic, *rest]


def _base_domain(hostname: str) -> str:
    parts = hostname.lower().split(".")
    return ".".join(parts[-2:]) if len(parts) >= 2 else hostname.lower()


def _same_site(url_a: str, url_b: str) -> bool:
    """Loose same-site check (ignores subdomain) so e.g. static.example.com
    and www.example.com both count as "the company's own", while excluding
    third-party domains entirely."""
    host_a = urlparse(url_a).hostname or ""
    host_b = urlparse(url_b).hostname or ""
    if not host_a or not host_b:
        return False
    return _base_domain(host_a) == _base_domain(host_b)


async def _fetch_external_stylesheets(pages: list[tuple[str, str, str]], limit: int = 12) -> list[str]:
    """Fetch the CSS of <link rel="stylesheet"> files referenced by the scraped
    pages. Most sites keep their real color palette in compiled, external
    stylesheets rather than inline <style> blocks, which inline-only parsing
    misses entirely.

    Restricted to same-site stylesheets only — third-party CSS (font loaders,
    chat widgets, cookie banners, ad/analytics scripts, ...) carries its own
    unrelated colors and was flooding the ranked list with noise (e.g. a
    random widget blue showing up as a "brand color").
    """
    hrefs: list[str] = []
    seen: set[str] = set()
    for page_url, _, html in pages:
        raw_hrefs = re.findall(
            r'<link\b[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE
        )
        raw_hrefs += re.findall(
            r'<link\b[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']stylesheet["\']', html, re.IGNORECASE
        )
        for href in raw_hrefs:
            resolved = _resolve_asset_url(href, page_url)
            # Dedup while preserving discovery order — a plain `set` would
            # iterate in a hash-randomized order, making which stylesheets
            # get fetched (and thus which colors get found) non-deterministic
            # across runs once truncated to `limit`.
            if resolved and resolved not in seen and _same_site(resolved, page_url):
                seen.add(resolved)
                hrefs.append(resolved)

    async def _fetch(url: str) -> str:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
                resp = await client.get(url)
                if resp.status_code < 400:
                    return resp.text
        except Exception as e:
            logger.warning("stylesheet_fetch_failed", url=url, error=str(e))
        return ""

    results = await asyncio.gather(*[_fetch(h) for h in hrefs[:limit]])
    return [r for r in results if r]


def _brandfetch_primary_colors(data: dict, limit: int = 3) -> list[str]:
    """Brandfetch's own brand-color API, taken as-is for primary — it's
    curated by Brandfetch specifically as "the official brand colors",
    including legitimate black/white ones a CSS-frequency scan would
    otherwise discard as grayscale noise. Only used as a fallback source for
    *primary*; secondary/semantic always come from the company's own CSS."""
    seen: set[str] = set()
    colors: list[str] = []
    for c in data.get("colors", []):
        hex_code = c.get("hex")
        if not hex_code:
            continue
        normalized = _normalize_hex(hex_code.lstrip("#"))
        if normalized not in seen:
            seen.add(normalized)
            colors.append(normalized)
    return colors[:limit]


async def _extract_colors(
    data: dict, pages: list[tuple[str, str, str]], openai: AsyncOpenAI
) -> dict[str, Any]:
    """Primary tries Brandfetch first (see _brandfetch_primary_colors). Only
    when Brandfetch has nothing does this fall back to a fully deterministic
    read of the site's own CSS: every section/text color in active use
    (_rank_section_colors — grayscale included, since we're no longer
    relying on Brandfetch to supply a legitimate black/white identity),
    ranked by frequency with button-background usage added as a boost on
    top (see _pick_fallback_primary) — a button is the single strongest
    "this is our primary brand color" signal a site gives off. In that same
    fallback, secondary becomes the next 8 most-used colors after primary
    (no LLM judgment call, just frequency rank — once primary and semantic
    are carved out). Semantic always comes exclusively from the company's
    own compiled CSS — inline <style> blocks AND external stylesheets —
    never from Brandfetch, which can derive "accent colors" from logo/image
    analysis rather than the site's actual design tokens."""
    brandfetch_primary = _brandfetch_primary_colors(data)

    # _get_page_contents already prefers same-host pages, but filter again
    # defensively in case its fallback kicked in — an unrelated subdomain's
    # CSS (different design system entirely) would otherwise drown out the
    # actual marketing site's own colors. `pages[0]` is always the homepage.
    homepage_host = _www_normalized_host(pages[0][0]) if pages else ""
    own_pages = [p for p in pages if _www_normalized_host(p[0]) == homepage_host] if homepage_host else pages
    own_pages = own_pages or pages

    css_parts: list[str] = []
    for _, _, html in own_pages[:5]:
        css_parts.extend(re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE))
    css_parts.extend(await _fetch_external_stylesheets(own_pages))

    css_content = " ".join(css_parts)

    # Status/utility design-tokens (success, error, warning, ...) are
    # genuinely used somewhere on the site but aren't intentional brand
    # colors — pull them out before ranking so they can't be picked as a
    # "secondary" brand color. Only error/warning/success are actually
    # reported back; "disabled"/"info" stay excluded from the candidate
    # pools below without being surfaced as their own thing.
    all_semantic_colors = _extract_semantic_colors(css_content)
    reported_semantic_colors = {
        h: label for h, label in all_semantic_colors.items() if label in _REPORTED_SEMANTIC_LABELS
    }

    def _eligible(hex_code: str, count: int) -> bool:
        return (
            hex_code not in all_semantic_colors
            and hex_code not in _FRAMEWORK_DEFAULT_COLORS
            and hex_code not in _BROWSER_DEFAULT_LINK_COLORS
            and count >= _MIN_COLOR_USAGE_COUNT
        )

    # Built once and reused for both section and button ranking below — see
    # _build_custom_property_map / _resolve_block_colors for why this
    # matters: most of a modern site's actual color usage goes through
    # var(--token) rather than a literal hex on the declaration itself.
    custom_props = _build_custom_property_map(css_content)

    # Section/text colors actually painted onto the page — not just any hex
    # that shows up somewhere in the stylesheet (e.g. a border or shadow
    # tint nobody would call a brand color). Used as the candidate pool for
    # secondary always, and for primary too in the no-Brandfetch fallback.
    section_candidates = [
        (h, c) for h, c in _rank_section_colors(css_content, custom_props) if _eligible(h, c)
    ]

    def _format(colors: list[tuple[str, int]]) -> str:
        return ", ".join(f"{hex_code} (used {count}x)" for hex_code, count in colors) or "(none)"

    if brandfetch_primary:
        primary = brandfetch_primary
        primary_set = {c.lower() for c in primary}
        if not section_candidates:
            return {"primary": primary, "secondary": [], "semantic": reported_semantic_colors}

        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "These are hex colors declared as a section background or font/text color "
                    "in a company's own website CSS, each with how many separate CSS rule blocks "
                    "use it. Pick clearly intentional secondary/accent colors — used for "
                    "highlights but not the main identity — up to 8. A deliberate neutral grey "
                    "(e.g. muted secondary text, a card/section background) is a perfectly valid "
                    "secondary color — don't reject it just for being grayscale. But leave out the "
                    "page's generic plain white background or plain black body text (the "
                    "universal base style every page has, not a brand choice), anything that "
                    "looks like a generic UI-framework/CMS default swatch, or a one-off "
                    "illustration color.\n"
                    'Return JSON: {"secondary": ["#RRGGBB", ...]}. Empty list if nothing qualifies.'
                )},
                {"role": "user", "content": _format(section_candidates)},
            ],
            response_format={"type": "json_object"},
        )
        picked = json.loads(response.choices[0].message.content)
        secondary = [c for c in picked.get("secondary", [])[:8] if c.lower() not in primary_set]
        return {"primary": primary, "secondary": secondary, "semantic": reported_semantic_colors}

    # No Brandfetch data at all — fully deterministic fallback, no LLM call.
    # Primary: top 3 by section/text frequency, boosted by button usage
    # (grayscale included — see docstring). Button colors skip the
    # >=2-rule-block usage floor `_eligible` applies —
    # a site typically has far fewer button rule blocks than section ones,
    # so a real button color can legitimately appear in just one.
    def _button_eligible(hex_code: str) -> bool:
        return (
            hex_code not in all_semantic_colors
            and hex_code not in _FRAMEWORK_DEFAULT_COLORS
            and hex_code not in _BROWSER_DEFAULT_LINK_COLORS
        )

    button_candidates = [
        (h, c) for h, c in _rank_button_colors(css_content, custom_props) if _button_eligible(h)
    ]
    primary = _pick_fallback_primary(section_candidates, button_candidates, limit=3)
    # Secondary: the next 8 most-used colors after primary — no LLM judgment
    # call, just frequency rank.
    primary_set = {c.lower() for c in primary}
    secondary = sorted(
        (h for h, _ in section_candidates if h.lower() not in primary_set),
        key=lambda h: dict(section_candidates)[h],
        reverse=True,
    )[:8]
    return {"primary": primary, "secondary": secondary, "semantic": reported_semantic_colors}


_GOOGLE_FONTS_RE = re.compile(r'fonts\.googleapis\.com/css[^"\']*[?&]family=([^"\'&]+)', re.IGNORECASE)


def _parse_google_font_param(raw: str) -> list[tuple[str, list[str]]]:
    """Parse a Google Fonts `family=` query value into [(name, weights), ...].

    Handles both legacy syntax (`Open+Sans:400,700`) and css2 syntax
    (`Inter:wght@400;700`), and multiple families separated by `|`.
    """
    results: list[tuple[str, list[str]]] = []
    for family in raw.split("|"):
        name_part, weights = family, []
        if ":wght@" in family:
            name_part, weight_part = family.split(":wght@", 1)
            weights = [w.strip() for w in weight_part.replace("+", " ").split(";") if w.strip()]
        elif ":" in family:
            name_part, weight_part = family.split(":", 1)
            weights = [w.strip() for w in weight_part.split(",") if w.strip().isdigit()]
        name = name_part.replace("+", " ").strip()
        if name:
            results.append((name, weights))
    return results


def _extract_font_sizes(html: str, name: str) -> list[str]:
    """Best-effort: font-size values declared in the same CSS rule block as a
    font-family reference to `name`. CSS isn't reliably regex-parseable, so this
    only catches simple cases where font-family and font-size share one rule."""
    sizes: set[str] = set()
    for block in re.findall(r'\{([^{}]*)\}', html):
        if name.lower() not in block.lower() or "font-family" not in block.lower():
            continue
        for s in re.findall(r'font-size\s*:\s*([\d.]+(?:px|rem|em|pt))', block, re.IGNORECASE):
            sizes.add(s.lower())
    return sorted(sizes)


_FONT_WEIGHT_KEYWORDS = {"bold": "700", "normal": "400", "lighter": "300", "bolder": "700"}


def _extract_general_font_signal(html: str) -> tuple[list[str], list[str]]:
    """Site-wide fallback for font-size/font-weight when the per-name match in
    `_extract_font_sizes` finds nothing — which is the common case for a
    Brandfetch-sourced font name (e.g. "Anthropic Sans"), since Brandfetch's
    display name rarely matches the literal CSS identifier a stylesheet
    actually uses (e.g. "AnthropicSans", a CSS variable, or a Tailwind/atomic
    utility class where `font-family` and `font-size`/`font-weight` are each
    their own single-property rule and never share a block at all).

    Collects every font-size/font-weight value declared *anywhere* in the
    page's CSS, with no name or co-occurrence requirement. Much less precise
    than the per-name match, but turns a hard zero into at least some signal
    — and the interpretation layer (visualbranding/nodes/fonts.py) already
    aggregates by dominant bucket per company, not per exact font, so
    attributing a site's general type-scale to all of its fonts is an
    acceptable trade for actually having data to classify on."""
    sizes: set[str] = set()
    weights: set[str] = set()
    for s in re.findall(r'font-size\s*:\s*([\d.]+(?:px|rem|em|pt))', html, re.IGNORECASE):
        sizes.add(s.lower())
    for w in re.findall(r'font-weight\s*:\s*(\d{3}|bold|normal|lighter|bolder)\b', html, re.IGNORECASE):
        weights.add(_FONT_WEIGHT_KEYWORDS.get(w.lower(), w.lower()))
    return sorted(sizes), sorted(weights)


async def _extract_fonts(
    data: dict, pages: list[tuple[str, str, str]]
) -> list[FontInfo] | None:
    # Brandfetch zuerst
    brandfetch_fonts = data.get("fonts", [])
    if brandfetch_fonts:
        html_blob = " ".join(html for _, _, html in pages)
        general_sizes, general_weights = _extract_general_font_signal(html_blob)
        result = [
            FontInfo(
                name=f["name"],
                type=f.get("type"),
                # Per-name match first; site-wide fallback fills the gap when
                # Brandfetch's display name doesn't literally appear in the
                # site's CSS (see _extract_general_font_signal docstring).
                weights=sorted(
                    set([str(f["weight"])] if f.get("weight") else []) | set(general_weights)
                ) or None,
                sizes=sorted(set(_extract_font_sizes(html_blob, f["name"])) | set(general_sizes)) or None,
            )
            for f in brandfetch_fonts if f.get("name")
        ]
        if result:
            return result

    # Fallback: rawHtml der Homepage scrapen und Font-Deklarationen extrahieren
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    domain = pages[0][0].split("/")[2] if pages else None
    if not domain:
        return None

    result = await asyncio.to_thread(
        app.scrape_url, f"https://{domain}", formats=["rawHtml"]
    )
    html = getattr(result, "rawHtml", "") or ""
    if not html:
        return None

    found: dict[str, list[str]] = {}  # name -> weights
    generic = {"sans-serif", "serif", "monospace", "inherit", "initial", "unset", "cursive", "fantasy"}
    # Universal OS/browser default fonts — without a real CSS parser, the
    # regex below can't tell a font a company *deliberately* chose from one
    # that's merely the 2nd/3rd item in some unrelated third-party widget's
    # fallback stack (e.g. `font-family: Arial, sans-serif` in an embedded
    # script). These render on virtually every site that loads no custom
    # font at all, so they're the *absence* of a brand choice, not a signal.
    system_fallback = {
        "arial", "arial black", "helvetica", "helvetica neue", "times new roman",
        "times", "verdana", "tahoma", "trebuchet ms", "georgia", "courier new",
        "courier", "calibri", "segoe ui", "segoe ui symbol", "comic sans ms",
        "impact", "lucida console", "lucida sans unicode", "ms sans serif",
        "ms serif", "geneva", "consolas",
    }

    # Google Fonts — captures weights straight from the URL when present
    for match in _GOOGLE_FONTS_RE.findall(html):
        for name, weights in _parse_google_font_param(match):
            existing_weights = found.setdefault(name, [])
            for w in weights:
                if w not in existing_weights:
                    existing_weights.append(w)

    # Adobe Fonts / Typekit
    for match in re.findall(r'use\.typekit\.net/([a-z]+)\.css', html):
        found.setdefault(f"Adobe Fonts ({match})", [])

    # CSS font-family declarations
    for match in re.findall(r"font-family\s*:\s*['\"]?([A-Za-z][\w\s-]+?)['\"]?\s*[,;]", html):
        name = match.strip()
        if name.lower() not in generic and name.lower() not in system_fallback:
            found.setdefault(name, [])

    if found:
        return [
            FontInfo(name=name, weights=weights or None, sizes=_extract_font_sizes(html, name) or None)
            for name, weights in sorted(found.items())
        ]

    # Letzter Fallback: OpenAI analysiert den HTML-Inhalt
    openai_client = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)
    response = await openai_client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": (
                "Find font names used on this website from the HTML. "
                "Look for font-family, Google/Adobe Fonts links, @font-face, or font loader scripts. "
                'Return JSON: {"fonts": ["FontName1", "FontName2"]}. Empty list if none found.'
            )},
            {"role": "user", "content": html[:6000]},
        ],
        response_format={"type": "json_object"},
    )
    ai_fonts = json.loads(response.choices[0].message.content).get("fonts", [])
    return [FontInfo(name=f) for f in ai_fonts] if ai_fonts else None


_ICON_KEYWORDS = {"icon", "favicon", "apple-touch", "sprite", "social-icon"}

# URL path segments that almost always indicate a partner/client/press logo grid
_THIRD_PARTY_PATH_KEYWORDS = {
    "partner", "partners", "client", "clients", "customer-logo", "customer-logos",
    "trusted-by", "trustedby", "press-logo", "press-logos", "brand-logo", "brand-logos",
    # Some CMSes name the asset with "logo" first, the audience second (e.g.
    # Appian's AEM exports "logo-customer-pwc.svg", "logo-customer-aon.svg") —
    # the word-order-reversed counterpart of "customer-logo" above.
    "logo-customer", "logo-client", "logo-partner",
}

# Section headings that introduce rows of OTHER companies' logos, regardless of
# whether "logo" appears in the image's own URL/alt text
_THIRD_PARTY_CONTEXT_KEYWORDS = (
    "trusted by", "our customers", "our clients", "our partners", "partner ecosystem",
    "featured in", "as seen in", "backed by", "integration partners",
    "customer logos", "client logos", "partner logos", "press logos", "in the news",
    "what our customers", "loved by", "used by teams at",
)

# Analyst-firm and review-site names that show up in "award badge" images
# (e.g. "gartner-blue.png", "forrester-black.png", "idc-blue.png") — these
# are always someone else's logo, regardless of whether "logo" itself
# appears anywhere in the URL/alt text.
_THIRD_PARTY_BRAND_KEYWORDS = (
    "gartner", "forrester", "idc", "g2crowd", "g2-crowd", "capterra", "trustradius",
    "peerspot", "softwarereviews", "everest-group", "everestgroup", "nucleus-research",
    "kuppingercole", "getapp", "softwareadvice",
)


def _classify_image(url: str, alt: str, context: str, company: str) -> str:
    """Classify a scraped image as 'icon', 'logo' (skipped from images), or 'image' (keep).

    Icons (favicons, social/UI icons) are routed to the icons field instead of
    images. Any image whose URL mentions "logo" — our own logo or a
    third-party one (partner/client/press grids, "Trusted by" sections, etc.)
    — is excluded from images; logos already have their own dedicated field.
    """
    text = f"{url} {alt}".lower()
    if any(kw in text for kw in _ICON_KEYWORDS):
        return "icon"
    if "logo" in url.lower():
        return "logo"
    if any(kw in url.lower() for kw in _THIRD_PARTY_PATH_KEYWORDS):
        return "logo"
    if any(kw in context.lower() for kw in _THIRD_PARTY_CONTEXT_KEYWORDS):
        return "logo"
    if any(kw in text for kw in _THIRD_PARTY_BRAND_KEYWORDS):
        return "logo"
    if "logo" in text and company.lower() not in text:
        return "logo"
    return "image"


def _reclassify_images(images: list[SourcedAsset], company: str) -> tuple[list[SourcedAsset], dict[str, str]]:
    """Re-run `_classify_image`'s URL-based heuristics over an already-merged
    images list, dropping/demoting anything that should never have counted
    as a real "image" in the first place. `_merge_sourced` only adds new
    entries — without this, an entry stored by an older, looser version of
    `_classify_image` (e.g. a third-party "Gartner-Logo.png" customer-logo
    image, predating today's unconditional "logo" in url check) would
    persist in `images` forever. No alt/context text is available
    retroactively, but the URL-substring checks alone already catch every
    case seen in practice (filenames literally containing "logo")."""
    kept: list[SourcedAsset] = []
    icons: dict[str, str] = {}
    for asset in images:
        kind = _classify_image(asset.url, "", "", company)
        if kind == "icon":
            icons[asset.url] = "icon"
        elif kind != "logo":
            kept.append(asset)
    return kept, icons


_IMAGE_CATEGORIES = ("diagram", "screenshot", "photo", "illustration", "other")
# Formats GPT-4o-mini's vision input genuinely can't read at all.
_VISION_INCOMPATIBLE_EXTENSIONS = {"svg", "pdf", "ico", "bmp", "tiff", "avif"}
_CATEGORIZE_BATCH_SIZE = 16  # keeps each vision call's prompt small/cheap


def _is_vision_compatible(url: str) -> bool:
    """Many image CDNs (Adobe Scene7, Next.js's image proxy, Kaltura
    thumbnails, ...) serve raster images through extensionless URLs — the
    real format lives in a query param or isn't exposed at all. Defaulting
    to "compatible" unless the path explicitly names a format vision can't
    read catches those, instead of a whitelist that excludes them outright."""
    path = url.split("?", 1)[0].rsplit("/", 1)[-1]
    ext = path.rsplit(".", 1)[-1].lower() if "." in path else ""
    return ext not in _VISION_INCOMPATIBLE_EXTENSIONS


async def _categorize_images_batch(urls: list[str], openai: AsyncOpenAI) -> dict[str, str]:
    """One vision call classifying every url in this batch. `detail: low` keeps
    per-image cost roughly fixed (~85 tokens) regardless of resolution — plenty
    for a coarse style call like this, not a content-reading one."""
    content: list[dict] = [
        {
            "type": "text",
            "text": (
                "Each image below is a marketing image scraped from a company website, "
                "labeled by index. Classify each one as exactly one of:\n"
                f"{list(_IMAGE_CATEGORIES)}\n"
                "- diagram: process flows, charts, infographics, architecture diagrams\n"
                "- screenshot: a product/app/dashboard UI screenshot\n"
                "- photo: real photography (people, offices, events, products)\n"
                "- illustration: stylized/vector or 3D-rendered graphic art, not a screenshot or diagram\n"
                "- other: anything that doesn't clearly fit the above\n"
                'Return JSON: {"<index>": "<category>", ...} for every index given.'
            ),
        }
    ]
    for i, url in enumerate(urls):
        content.append({"type": "text", "text": f"Index {i}"})
        content.append({"type": "image_url", "image_url": {"url": url, "detail": "low"}})

    response = await openai.chat.completions.create(
        model="gpt-4o-mini",
        messages=[{"role": "user", "content": content}],
        response_format={"type": "json_object"},
    )
    raw = json.loads(response.choices[0].message.content)
    return {
        urls[int(i)]: v
        for i, v in raw.items()
        if i.isdigit() and int(i) < len(urls) and v in _IMAGE_CATEGORIES
    }


async def _categorize_with_retry(urls: list[str], openai: AsyncOpenAI) -> dict[str, str]:
    """Classify `urls` in one vision call; on failure (e.g. one unreachable
    image in the batch — OpenAI fails the *entire* call if it can't download
    even one image_url), split the batch in half and retry each half
    independently instead of losing every other image to one bad apple.
    Bottoms out at single-image calls in the worst case."""
    try:
        return await _categorize_images_batch(urls, openai)
    except Exception as exc:
        if len(urls) == 1:
            logger.warning("image_categorization_failed", url=urls[0], error=str(exc))
            return {}
        mid = len(urls) // 2
        left, right = await asyncio.gather(
            _categorize_with_retry(urls[:mid], openai),
            _categorize_with_retry(urls[mid:], openai),
        )
        return {**left, **right}


async def _categorize_images(images: list[SourcedAsset], openai: AsyncOpenAI) -> dict[str, str]:
    """{url: category} for every image still missing one. Scoped to only the
    uncategorized subset (not the full merged list) so a repeat run doesn't
    re-pay for classifying the same hundreds of images every time — once an
    image has a category it keeps it forever, same as logo/icon classification."""
    candidates = [img.url for img in images if img.category is None and _is_vision_compatible(img.url)]
    if not candidates:
        return {}
    batches = [candidates[i : i + _CATEGORIZE_BATCH_SIZE] for i in range(0, len(candidates), _CATEGORIZE_BATCH_SIZE)]
    results = await asyncio.gather(*[_categorize_with_retry(b, openai) for b in batches])
    merged: dict[str, str] = {}
    for r in results:
        merged.update(r)
    return merged


def _html_window_text(html: str, fragment: str, window: int = 300) -> str:
    """Plain-text slice of `html` around `fragment`, tags stripped, for context checks."""
    idx = html.find(fragment)
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(html), idx + len(fragment) + window)
    return re.sub(r"<[^>]+>", " ", html[start:end])


# Adobe Experience Manager asset-delivery URLs (used by many enterprise
# marketing sites, e.g. Celonis) embed a stable urn:aaid:aem:<uuid> asset ID
# in the path — the SAME image gets requested at many different
# widths/formats (width=750&format=jpg vs width=2000&format=webply, ...) for
# responsive <picture>/srcset markup, which otherwise looks like dozens of
# different "duplicate" images for what is visually one photo/illustration.
_AEM_ASSET_ID_RE = re.compile(r"urn:aaid:aem:[0-9a-fA-F-]+")


def _asset_identity_key(url: str) -> str:
    """Identity for "the same asset, any size/format/query variant" — the
    AEM asset ID when present, otherwise the URL with query string and
    HTML-entity differences stripped."""
    normalized = html_lib.unescape(url).strip()
    aem_match = _AEM_ASSET_ID_RE.search(normalized)
    if aem_match:
        return aem_match.group(0)
    return normalized.split("?", 1)[0]


def _extract_images(
    data: dict, pages: list[tuple[str, str, str]], company: str, domain: str
) -> tuple[list[SourcedAsset], dict[str, str]]:
    seen: set[str] = set()
    images: list[SourcedAsset] = []
    icons: dict[str, str] = {}

    def _consider(url: str, source_page: str, alt: str = "", context: str = "") -> None:
        if not url:
            return
        key = _asset_identity_key(url)
        if key in seen:
            return
        seen.add(key)
        kind = _classify_image(url, alt, context, company)
        if kind == "icon":
            icons[url] = alt or "icon"
        elif kind == "logo":
            return  # third-party logo — skip, don't store as our image
        else:
            images.append(SourcedAsset(url=url, source_page=source_page))

    homepage = f"https://{domain}"

    # HTML first: Markdown images (with alt text + surrounding context), <img>
    # tags, and img-like custom elements (e.g. <arc-image srcset="...">) that
    # some sites use instead of plain <img>. Scanned before Brandfetch below
    # so that when the same asset shows up in both sources, `_consider`'s
    # `seen` guard keeps the genuine page it was actually found on instead of
    # Brandfetch's generic homepage placeholder overwriting it.
    for page_url, markdown, html in pages:
        for m in re.finditer(r'!\[([^\]]*)\]\((https?://[^\)]+)\)', markdown):
            alt, url = m.group(1), html_lib.unescape(m.group(2))
            start, end = max(0, m.start() - 150), min(len(markdown), m.end() + 150)
            _consider(url, page_url, alt, markdown[start:end])
        for tag in _candidate_asset_tags(html):
            url, alt = _extract_asset_from_tag(tag, page_url)
            if not url:
                continue
            context = _html_window_text(html, tag)
            _consider(url, page_url, alt, context)

    # Brandfetch — brand-level assets, not tied to a specific scraped page.
    # Only adds entries for assets that weren't already found above with a
    # real page attached.
    for image in data.get("images", []):
        for fmt in image.get("formats", []):
            _consider(fmt.get("src"), homepage)

    return images, icons

def _extract_videos(pages: list[tuple[str, str, str]]) -> list[SourcedAsset]:
    md_patterns = [
        r'https?://(?:www\.)?youtube\.com/watch\?[^\s\)\]"\']+',
        r'https?://youtu\.be/[^\s\)\]"\']+',
        r'https?://(?:www\.)?youtube\.com/embed/[^\s\)\]"\']+',
        r'https?://(?:www\.)?vimeo\.com/\d+[^\s\)\]"\']*',
        r'https?://[^\s\)\]"\']+\.(?:mp4|webm|mov|avi)',
    ]
    html_patterns = [
        r'<iframe[^>]+?(?:src|data-src)=["\']([^"\']*(?:youtube\.com/embed|youtube-nocookie\.com/embed)[^"\']*)["\']',
        r'<iframe[^>]+?(?:src|data-src)=["\']([^"\']*vimeo\.com/(?:video/)?\d+[^"\']*)["\']',
        r'<(?:video|source)[^>]+?(?:src|data-src)=["\']([^"\']+\.(?:mp4|webm|mov|ogg))["\']',
    ]
    seen: set[str] = set()
    videos: list[SourcedAsset] = []

    for page_url, markdown, html in pages:
        for pattern in md_patterns:
            for url in re.findall(pattern, markdown):
                if url not in seen:
                    seen.add(url)
                    videos.append(SourcedAsset(url=url, source_page=page_url))
        for pattern in html_patterns:
            for url in re.findall(pattern, html, re.IGNORECASE):
                if url and url not in seen:
                    seen.add(url)
                    videos.append(SourcedAsset(url=url, source_page=page_url))

    return videos



# --- Deduplication across runs ---

def _merge_unique(existing: list[str] | None, new: list[str]) -> list[str]:
    """Merge `new` into `existing`, de-duplicating (exact match) on both sides.

    De-duplicating `existing` too (not just guarding against re-adding `new`
    items) cleans up any duplicates a prior run may have already stored.
    """
    merged: list[str] = []
    seen: set[str] = set()
    for item in [*(existing or []), *new]:
        if item not in seen:
            seen.add(item)
            merged.append(item)
    return merged


def _merge_dict(existing: dict[str, Any] | None, new: dict[str, Any]) -> dict[str, Any]:
    """Add keys from `new` to `existing` that aren't already present."""
    merged = dict(existing or {})
    for k, v in new.items():
        if k not in merged:
            merged[k] = v
    return merged


def _merge_sourced(
    existing: list[SourcedAsset] | None, new: list[SourcedAsset], generic_pages: set[str] = frozenset()
) -> list[SourcedAsset]:
    """Merge by asset identity (see _asset_identity_key), de-duplicating on
    both sides; fills in a missing source_page or category from a later
    duplicate if the first-seen entry didn't have one.

    Deduplicating by _asset_identity_key rather than the raw URL collapses:
    (a) the same AEM-delivered image requested at different
    widths/formats — "...width=750&format=jpg" and
    "...width=2000&format=webply" are the same photo, just different
    responsive variants pulled from different <picture>/srcset markup; and
    (b) an old snapshot's HTML-entity-escaped "...&amp;w=3840" against a
    freshly-scraped "...&w=3840" for the same image.
    The first-seen URL variant is kept as the representative `.url`.

    `generic_pages` (e.g. {homepage}) lets an already-stored entry whose
    source_page is just that generic placeholder — from an older run that
    only found the asset via Brandfetch, never on an actual scraped page —
    get upgraded to a real page once one is found, instead of the
    placeholder winning forever just for being first-seen.

    Field-by-field merging (not whole-object replacement) matters here: a
    freshly re-extracted entry never has a `category` yet (that's filled in
    separately, after merging, only for images still missing one) — wholesale
    replacement would silently throw away a category an older snapshot
    already paid an LLM call to determine."""
    by_key: dict[str, SourcedAsset] = {}
    for asset in [*(existing or []), *new]:
        key = _asset_identity_key(asset.url)
        prev = by_key.get(key)
        if prev is None:
            by_key[key] = asset.model_copy(update={"url": html_lib.unescape(asset.url).strip()})
            continue
        prev_page_is_generic = prev.source_page in generic_pages
        new_page_is_specific = asset.source_page and asset.source_page not in generic_pages
        source_page = asset.source_page if (prev_page_is_generic and new_page_is_specific) else (
            prev.source_page or asset.source_page
        )
        by_key[key] = SourcedAsset(
            url=prev.url,
            source_page=source_page,
            category=prev.category or asset.category,
        )
    return list(by_key.values())


def _merge_fonts(existing: list[FontInfo] | None, new: list[FontInfo]) -> list[FontInfo]:
    """Merge by font name, unioning weights/sizes when a font reappears."""
    by_name: dict[str, FontInfo] = {f.name: f for f in (existing or [])}
    for f in new:
        prev = by_name.get(f.name)
        if prev is None:
            by_name[f.name] = f
            continue
        weights = sorted(set((prev.weights or []) + (f.weights or []))) or None
        sizes = sorted(set((prev.sizes or []) + (f.sizes or []))) or None
        by_name[f.name] = FontInfo(name=f.name, type=prev.type or f.type, weights=weights, sizes=sizes)
    return list(by_name.values())


def _load_existing_visuals(domain: str) -> VisualsData | None:
    data = get_latest_snapshot(domain, "visuals")
    if not data:
        return None
    try:
        return VisualsData.model_validate(data)
    except Exception:
        # Likely an older snapshot with legacy field shapes (flat string lists
        # for fonts/images/videos instead of structured objects) — drop those
        # fields and keep the rest so other merged fields aren't lost; they'll
        # simply be re-scraped fresh.
        try:
            return VisualsData.model_validate({**data, "fonts": None, "images": None, "videos": []})
        except Exception:
            return None


# --- run ---

async def run(state: ResearchState) -> dict:
    logger.info("Run Visuals")
    domain = state["competitor_domain"]
    if snapshot_exists(domain, "visuals"):
        logger.info("node_skipped_cached", node="visuals", domain=domain)
        return {"completed_nodes": ["visuals"]}
    competitor_names = await get_competitor_names()
    company = competitor_names.get(domain) or domain.split(".")[0].capitalize()

    try:
        openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)

        existing = await asyncio.to_thread(_load_existing_visuals, domain)

        data = await _get_brand_data(domain)
        pages = await _get_page_contents(domain)

        logos = _extract_logos(data, pages, company)
        colors = await _extract_colors(data, pages, openai)
        fonts = await _extract_fonts(data, pages)
        images, icons = _extract_images(data, pages, company, domain)

        # Broaden video discovery beyond the homepage-linked pages already scraped above
        video_page_urls = await _discover_video_pages(domain, exclude={p[0] for p in pages})
        video_pages = await _scrape_urls(video_page_urls) if video_page_urls else []
        videos = _extract_videos(pages + video_pages)

        # Merge with the previous snapshot so already-stored items are never duplicated
        merged_logos = _merge_unique(existing.logo if existing else None, logos)
        # Re-check the full merged list against the (possibly newer/stricter)
        # third-party heuristics — without this, a logo wrongly stored by an
        # older version of this classification logic would persist forever,
        # since _merge_unique only adds new entries, it never re-validates old ones.
        merged_logos = [
            l for l in merged_logos
            if not _is_third_party_logo(l, "") and _looks_like_own_logo(l, company)
        ]
        # Re-dedupe the full merged list too — an SVG twin stored by a run
        # before _dedupe_logo_formats existed would otherwise persist
        # forever, since _merge_unique only adds new entries.
        merged_logos = _dedupe_logo_formats(merged_logos)
        merged_images = _merge_sourced(
            existing.images if existing else None, images or [], generic_pages={f"https://{domain}"}
        )
        merged_videos = _merge_sourced(existing.videos if existing else None, videos)
        # Re-check the full merged list against the (possibly newer/stricter)
        # logo/icon heuristics — same reasoning as the merged_logos re-check
        # above. _merge_sourced only adds new entries; without this, a
        # third-party customer logo (e.g. "Gartner-Logo.png") stored by an
        # older scrape — before "logo" in the URL was enough to exclude it —
        # would persist in `images` forever.
        merged_images, reclassified_icons = _reclassify_images(merged_images, company)
        # Re-validate the full merged lists so stale/404/broken entries from older snapshots are dropped too.
        # Anything smaller than 50x50px isn't a real image — demote it to icons instead.
        merged_images, demoted_icons = await _validate_images(merged_images)
        # Vision-classify only images that don't have a category yet (new
        # this run, or scraped before this feature existed) — see
        # _categorize_images for why this is scoped, not run on everything.
        new_categories = await _categorize_images(merged_images, openai)
        if new_categories:
            merged_images = [
                img.model_copy(update={"category": new_categories.get(img.url, img.category)})
                for img in merged_images
            ]
        merged_videos = await _validate_videos(merged_videos)
        logger.info("images_found", domain=domain, count=len(merged_images))
        logger.info("videos_found", domain=domain, count=len(merged_videos))
        merged_icons = _merge_dict(existing.icons if existing else None, icons)
        merged_icons = _merge_dict(merged_icons, {a.url: "icon" for a in demoted_icons})
        merged_icons = _merge_dict(merged_icons, reclassified_icons)

        existing_fonts = existing.fonts if existing else None
        merged_fonts = _merge_fonts(existing_fonts, fonts or []) or None

        # Colors are a fresh judgment call each run (frequency-ranked CSS +
        # an LLM picking "real brand colors" out of that list), not a
        # discovered-once-keep-forever asset like images/logos. Always
        # replace with the latest extraction — including when it's smaller
        # or empty. _extract_colors only returns successfully with a result
        # (possibly empty lists, which is a legitimate "found nothing that
        # qualifies", not a failure); an actual scrape failure raises and is
        # caught by the outer try/except below, which never reaches this
        # line at all, so old data is naturally preserved on real failures.
        # A previous version used `colors.get(...) or existing...`, which
        # treated a legitimately-empty/stricter new result as "transient
        # failure" and silently kept stale colors forever (e.g. red/pink
        # tones for Celonis that no longer exist anywhere in its CSS).
        merged_primary = colors["primary"]
        merged_secondary = colors["secondary"]
        merged_semantic = colors["semantic"]

        visuals_data = VisualsData(
            company=company,
            url=f"https://{domain}",
            title=f"Visuals: {company}",
            logo=merged_logos,
            colors={"primary": merged_primary, "secondary": merged_secondary, "semantic": merged_semantic},
            fonts=merged_fonts,
            images=merged_images if merged_images else None,
            videos=merged_videos,
            icons=merged_icons or None,
        )
        try:
            insert_research_snapshot(domain, datetime.now(timezone.utc), "visuals", visuals_data)
        except Exception as db_err:
            logger.warning("snapshot_write_failed", node="visuals", error=str(db_err))
        return {
            "visuals": visuals_data,
            "completed_nodes": ["visuals"],
        }
    except Exception as e:
        logger.error("node_failed", node="visuals", error=str(e))
        return {"errors": [f"visuals: {e}"]}



if __name__ == "__main__":
    import asyncio
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main():
        from app.agents.research.state import PositioningData, FinancialData, SocialData, SeoGeoData, NewsData, EventsData, NewsletterData

        state = ResearchState(
            competitor_domain="ibm.com",
            visuals=VisualsData(),
            positioning=PositioningData(),
            financials=FinancialData(),
            socials=SocialData(),
            seogeo=SeoGeoData(),
            news=NewsData(),
            events=EventsData(),
            newsletter=NewsletterData(),
            errors=[],
            completed_nodes=[],
        )
        result = await run(state)
        if result.get("errors"):
            print("Errors:", result["errors"])
        else:
            print(result["visuals"].model_dump_json(indent=2))

    asyncio.run(main())
