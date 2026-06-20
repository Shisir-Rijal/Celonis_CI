import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import asyncio
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


async def _get_page_contents(domain: str, num_pages: int = 5) -> list[tuple[str, str, str]]:
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)
    homepage = f"https://{domain}"

    map_result = await asyncio.to_thread(app.map_url, homepage, limit=num_pages)
    mapped_urls: list[str] = getattr(map_result, "links", None) or []

    # map_url's ordering doesn't guarantee the homepage itself is among the
    # first `num_pages` results, but it's where the primary logo, nav, and
    # hero styling usually live — always scrape it.
    urls = [homepage] + [u for u in mapped_urls if u != homepage]
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
    return False


def _url_path_lower(url: str) -> str:
    """The path+query of a URL, lowercased — deliberately excludes the
    hostname so checking "does the company's name appear in this URL" can't
    trivially match just because the image happens to be hosted on the
    company's own domain (e.g. aris.com/.../suva-logo.svg contains "aris"
    only because of the domain, not because it's ARIS's own logo)."""
    parsed = urlparse(url)
    return f"{parsed.path}?{parsed.query}".lower()


# Brandfetch's own CDN regularly serves files literally named "logo.svg" with
# no company name anywhere in the URL — trust those rather than applying the
# stricter "company name must appear" rule meant for other-domain fallback scans.
_TRUSTED_LOGO_CDN_HOSTS = {"cdn.brandfetch.io"}


def _looks_like_own_logo(url: str, company: str) -> bool:
    """Used to retroactively re-check logos already stored from a previous run
    against the (possibly newer/stricter) company-name requirement, without
    punishing legitimate Brandfetch URLs that never carry the company name."""
    host = (urlparse(url).hostname or "").lower()
    if any(host == h or host.endswith("." + h) for h in _TRUSTED_LOGO_CDN_HOSTS):
        return True
    if "logo" not in url.lower():
        return True
    return company.lower() in _url_path_lower(url)


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
        return urls

    # Fallback: scan rawHtml (not just markdown, which often strips header/nav
    # chrome out as "boilerplate") for img-like tags. The site's own logo
    # almost always lives inside <header>/<nav>, so those regions are scanned
    # first and preferred; anywhere else on the page is a fallback. Within
    # header/nav we also accept images whose URL has no "logo" in it at all
    # as long as the alt text matches the company name (many real logos are
    # served from a CDN asset hash with no descriptive filename — Microsoft's
    # own nav logo is exactly this: alt="Microsoft", no "logo" in the URL).
    #
    # Outside header/nav, "logo" in the URL is NOT enough on its own — that's
    # exactly where customer/partner logo carousels live (e.g. ARIS's
    # "suva-logo.svg" or Apromore's "Logo-One.nz.png", neither of which trips
    # any of the known third-party keyword/context heuristics). Requiring the
    # company's own name somewhere in the URL/alt there filters those out,
    # mirroring the same rule _classify_image already applies for images.
    header_urls: list[str] = []
    other_urls: list[str] = []
    company_lower = company.lower()

    def _scan_region(
        region_html: str, page_html: str, page_url: str, bucket: list[str], match_alt: bool, require_company: bool
    ) -> None:
        for tag in _candidate_asset_tags(region_html):
            url, alt = _extract_asset_from_tag(tag, page_url)
            if not url or url in seen:
                continue
            looks_like_logo = "logo" in url.lower() or (match_alt and alt and company_lower in alt.lower())
            if not looks_like_logo:
                continue
            if require_company and company_lower not in _url_path_lower(url) and company_lower not in alt.lower():
                continue
            context = _html_window_text(page_html, tag)
            if _is_third_party_logo(url, context):
                continue
            seen.add(url)
            bucket.append(url)

    for page_url, markdown, html in pages:
        header_html = "".join(re.findall(r'<header\b.*?</header>', html, re.IGNORECASE | re.DOTALL))
        header_html += "".join(re.findall(r'<nav\b.*?</nav>', html, re.IGNORECASE | re.DOTALL))
        _scan_region(header_html, html, page_url, header_urls, match_alt=True, require_company=False)
        _scan_region(html, html, page_url, other_urls, match_alt=False, require_company=True)

        for src in re.findall(r'!\[([^\]]*)\]\((https?://[^\)]+)\)', markdown):
            alt, url = src
            if (
                "logo" in url.lower()
                and url not in seen
                and (company_lower in _url_path_lower(url) or company_lower in alt.lower())
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


def _is_grayscale(hex_code: str, threshold: int = 12) -> bool:
    """True for near-black/white/grey colors (low channel spread) — these
    are almost never the "brand color" a designer picked on purpose."""
    h = hex_code.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    return max(r, g, b) - min(r, g, b) <= threshold


def _rank_css_colors(css_text: str, top_n: int = 25) -> list[tuple[str, int]]:
    """Distinct chromatic (non-grayscale) hex colors in `css_text`, ranked by
    how many separate CSS rule blocks use them. Frequency is a simple but
    effective proxy for "this is an actual brand/accent color" vs. a one-off
    illustration color — and it's why a heavily-used color like a brand
    purple won't get lost.

    Counted per rule block (not per raw literal occurrence): design-token
    systems often declare dozens of named custom properties
    (--fnd-color-text-low, --fnd-color-border-state-disabled, ...) inside a
    single block, reusing the same rarely-applied color many times over —
    that inflated unused tokens (e.g. a disabled-state blue) above real,
    widely-applied brand colors when counted literally."""
    counts: dict[str, int] = {}
    blocks = re.findall(r'\{([^{}]*)\}', css_text) or [css_text]
    for block in blocks:
        seen_in_block: set[str] = set()
        for match in _HEX_COLOR_RE.findall(block):
            hex_code = _normalize_hex(match)
            if not _is_grayscale(hex_code):
                seen_in_block.add(hex_code)
        for hex_code in seen_in_block:
            counts[hex_code] = counts.get(hex_code, 0) + 1
    return sorted(counts.items(), key=lambda kv: kv[1], reverse=True)[:top_n]


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


async def _fetch_external_stylesheets(pages: list[tuple[str, str, str]], limit: int = 6) -> list[str]:
    """Fetch the CSS of <link rel="stylesheet"> files referenced by the scraped
    pages. Most sites keep their real color palette in compiled, external
    stylesheets rather than inline <style> blocks, which inline-only parsing
    misses entirely.

    Restricted to same-site stylesheets only — third-party CSS (font loaders,
    chat widgets, cookie banners, ad/analytics scripts, ...) carries its own
    unrelated colors and was flooding the ranked list with noise (e.g. a
    random widget blue showing up as a "brand color").
    """
    hrefs: set[str] = set()
    for page_url, _, html in pages:
        raw_hrefs = re.findall(
            r'<link\b[^>]*rel=["\']stylesheet["\'][^>]*href=["\']([^"\']+)["\']', html, re.IGNORECASE
        )
        raw_hrefs += re.findall(
            r'<link\b[^>]*href=["\']([^"\']+)["\'][^>]*rel=["\']stylesheet["\']', html, re.IGNORECASE
        )
        for href in raw_hrefs:
            resolved = _resolve_asset_url(href, page_url)
            if resolved and _same_site(resolved, page_url):
                hrefs.add(resolved)

    async def _fetch(url: str) -> str:
        try:
            async with httpx.AsyncClient(follow_redirects=True, timeout=8) as client:
                resp = await client.get(url)
                if resp.status_code < 400:
                    return resp.text
        except Exception as e:
            logger.warning("stylesheet_fetch_failed", url=url, error=str(e))
        return ""

    results = await asyncio.gather(*[_fetch(h) for h in list(hrefs)[:limit]])
    return [r for r in results if r]


async def _extract_colors(
    data: dict, pages: list[tuple[str, str, str]], openai: AsyncOpenAI
) -> dict[str, list[str]]:
    # Primary: Brandfetch
    primary = [c.get("hex") for c in data.get("colors", []) if c.get("hex")]
    primary_set = {c.lower() for c in primary}

    # Secondary: the real palette usually lives in compiled CSS — inline
    # <style> blocks AND external stylesheets — ranked by frequency so a
    # heavily-used accent color (e.g. a brand purple) reliably surfaces,
    # then handed to OpenAI to pick the brand-relevant ones.
    css_parts: list[str] = []
    for _, _, html in pages[:5]:
        css_parts.extend(re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE))
    css_parts.extend(await _fetch_external_stylesheets(pages))

    scraped: list[str] = []
    css_content = " ".join(css_parts)
    ranked_colors = _rank_css_colors(css_content)
    if ranked_colors:
        color_list = ", ".join(f"{hex_code} (used {count}x)" for hex_code, count in ranked_colors)
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "These are the most frequently used non-grayscale hex colors found in a "
                    "company's website CSS, with usage counts. Pick the ones that look like "
                    "real brand/accent colors (buttons, highlights, headings, logos) rather than "
                    "incidental illustration or one-off colors. A color used many times is "
                    "likely a brand color even if it's unusual (e.g. purple, teal). "
                    'Return JSON: {"colors": ["#RRGGBB", ...]}. Max 8 colors. Empty list if none found.'
                )},
                {"role": "user", "content": color_list},
            ],
            response_format={"type": "json_object"},
        )
        scraped = json.loads(response.choices[0].message.content).get("colors", [])

    if not primary:
        # No Brandfetch data at all (missing brand, or a path-scoped domain
        # where Brandfetch is skipped entirely) — use the CSS-derived colors
        # as primary instead of silently leaving it empty.
        primary = scraped
        secondary: list[str] = []
    else:
        secondary = [c for c in scraped if c.lower() not in primary_set]

    return {"primary": primary, "secondary": secondary}


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


async def _extract_fonts(
    data: dict, pages: list[tuple[str, str, str]]
) -> list[FontInfo] | None:
    # Brandfetch zuerst
    brandfetch_fonts = data.get("fonts", [])
    if brandfetch_fonts:
        html_blob = " ".join(html for _, _, html in pages)
        result = [
            FontInfo(
                name=f["name"],
                type=f.get("type"),
                weights=[str(f["weight"])] if f.get("weight") else None,
                sizes=_extract_font_sizes(html_blob, f["name"]) or None,
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
        if name.lower() not in generic:
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
}

# Section headings that introduce rows of OTHER companies' logos, regardless of
# whether "logo" appears in the image's own URL/alt text
_THIRD_PARTY_CONTEXT_KEYWORDS = (
    "trusted by", "our customers", "our clients", "our partners", "partner ecosystem",
    "featured in", "as seen in", "backed by", "integration partners",
    "customer logos", "client logos", "partner logos", "press logos", "in the news",
    "what our customers", "loved by", "used by teams at",
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
    if "logo" in text and company.lower() not in text:
        return "logo"
    return "image"


def _html_window_text(html: str, fragment: str, window: int = 300) -> str:
    """Plain-text slice of `html` around `fragment`, tags stripped, for context checks."""
    idx = html.find(fragment)
    if idx == -1:
        return ""
    start = max(0, idx - window)
    end = min(len(html), idx + len(fragment) + window)
    return re.sub(r"<[^>]+>", " ", html[start:end])


def _extract_images(
    data: dict, pages: list[tuple[str, str, str]], company: str, domain: str
) -> tuple[list[SourcedAsset], dict[str, str]]:
    seen: set[str] = set()
    images: list[SourcedAsset] = []
    icons: dict[str, str] = {}

    def _consider(url: str, source_page: str, alt: str = "", context: str = "") -> None:
        if not url or url in seen:
            return
        seen.add(url)
        kind = _classify_image(url, alt, context, company)
        if kind == "icon":
            icons[url] = alt or "icon"
        elif kind == "logo":
            return  # third-party logo — skip, don't store as our image
        else:
            images.append(SourcedAsset(url=url, source_page=source_page))

    homepage = f"https://{domain}"

    # Brandfetch — brand-level assets, not tied to a specific scraped page
    for image in data.get("images", []):
        for fmt in image.get("formats", []):
            _consider(fmt.get("src"), homepage)

    # HTML: Markdown images (with alt text + surrounding context), <img> tags,
    # and img-like custom elements (e.g. <arc-image srcset="...">) that some
    # sites use instead of plain <img>
    for page_url, markdown, html in pages:
        for m in re.finditer(r'!\[([^\]]*)\]\((https?://[^\)]+)\)', markdown):
            alt, url = m.group(1), m.group(2)
            start, end = max(0, m.start() - 150), min(len(markdown), m.end() + 150)
            _consider(url, page_url, alt, markdown[start:end])
        for tag in _candidate_asset_tags(html):
            url, alt = _extract_asset_from_tag(tag, page_url)
            if not url:
                continue
            context = _html_window_text(html, tag)
            _consider(url, page_url, alt, context)

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


def _merge_sourced(existing: list[SourcedAsset] | None, new: list[SourcedAsset]) -> list[SourcedAsset]:
    """Merge by URL, de-duplicating on both sides; fills in a missing source_page
    from a later duplicate if the first-seen entry didn't have one."""
    by_url: dict[str, SourcedAsset] = {}
    for asset in [*(existing or []), *new]:
        prev = by_url.get(asset.url)
        if prev is None or (prev.source_page is None and asset.source_page):
            by_url[asset.url] = asset
    return list(by_url.values())


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
    company = domain.split(".")[0].capitalize()

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
        merged_images = _merge_sourced(existing.images if existing else None, images or [])
        merged_videos = _merge_sourced(existing.videos if existing else None, videos)
        # Re-validate the full merged lists so stale/404/broken entries from older snapshots are dropped too.
        # Anything smaller than 50x50px isn't a real image — demote it to icons instead.
        merged_images, demoted_icons = await _validate_images(merged_images)
        merged_videos = await _validate_videos(merged_videos)
        logger.info("images_found", domain=domain, count=len(merged_images))
        logger.info("videos_found", domain=domain, count=len(merged_videos))
        merged_icons = _merge_dict(existing.icons if existing else None, icons)
        merged_icons = _merge_dict(merged_icons, {a.url: "icon" for a in demoted_icons})

        existing_fonts = existing.fonts if existing else None
        merged_fonts = _merge_fonts(existing_fonts, fonts or []) or None

        # Colors are a fresh judgment call each run (frequency-ranked CSS +
        # an LLM picking "real brand colors" out of that list), not a
        # discovered-once-keep-forever asset like images/logos. Merging them
        # additively across runs let every off-base LLM pick from any past
        # run accumulate forever, which is why "too many / wrong colors"
        # (e.g. random blues for Celonis) kept growing over time. Replace
        # with the latest extraction instead; only fall back to the stored
        # snapshot if this run's scrape came back empty (e.g. a transient
        # failure), so a bad run can't wipe out previously good data.
        existing_colors = (existing.colors if existing else None) or {}
        merged_primary = colors.get("primary") or existing_colors.get("primary", [])
        merged_secondary = colors.get("secondary") or existing_colors.get("secondary", [])
        primary_set = set(merged_primary)
        merged_secondary = [c for c in merged_secondary if c not in primary_set]

        visuals_data = VisualsData(
            company=company,
            url=f"https://{domain}",
            title=f"Visuals: {company}",
            logo=merged_logos,
            colors={"primary": merged_primary, "secondary": merged_secondary},
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
