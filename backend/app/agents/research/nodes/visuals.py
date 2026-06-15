import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import asyncio
import json
import re
from datetime import date, datetime, timezone
from firecrawl import V1FirecrawlApp as FirecrawlApp
from openai import AsyncOpenAI
from app.agents.research.state import ResearchState, VisualsData
from app.agents.research.repositories.research_repository import insert_research_snapshot
import structlog
from app.config import get_settings
from app.agents.shared.utils.brandfetch import _get_brand_data



logger = structlog.get_logger(__name__)
today = date.today().strftime("%Y-%m-%d")


# --- Website: Unterseiten einmal scrapen, dann für alle Extraktionen nutzen ---

async def _get_page_contents(domain: str, num_pages: int = 5) -> list[tuple[str, str, str]]:
    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)

    map_result = await asyncio.to_thread(app.map_url, f"https://{domain}", limit=num_pages)
    urls: list[str] = (getattr(map_result, "links", None) or [])[:num_pages]
    logger.info("map_urls_found", count=len(urls), domain=domain)

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
    pages = [r for r in results if r is not None]
    logger.info("pages_ready", count=len(pages))
    return pages


# --- Brandfetch: Logo, Colors, Fonts ---


def _extract_logos(data: dict, pages: list[tuple[str, str]]) -> list[str]:
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

    # Fallback: Bild-URLs mit "logo" im Pfad aus gescrapten Seiten
    for _, markdown, _ in pages:
        for src in re.findall(r'!\[.*?\]\((https?://[^\)]+)\)', markdown):
            if "logo" in src.lower() and src not in seen:
                seen.add(src)
                urls.append(src)
    return urls


async def _extract_colors(
    data: dict, pages: list[tuple[str, str, str]], openai: AsyncOpenAI
) -> dict[str, list[str]]:
    # Primary: Brandfetch
    primary = [c.get("hex") for c in data.get("colors", []) if c.get("hex")]
    primary_set = {c.lower() for c in primary}

    # Secondary: CSS aus <style>-Blöcken extrahieren → OpenAI filtert Markenwerte heraus
    css_parts: list[str] = []
    for _, _, html in pages[:5]:
        css_parts.extend(re.findall(r'<style[^>]*>(.*?)</style>', html, re.DOTALL | re.IGNORECASE))

    secondary: list[str] = []
    css_content = " ".join(css_parts)
    if css_content:
        response = await openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "From this CSS, extract the main brand colors (not grey, white, or black). "
                    "Focus on distinctive colors used for branding, buttons, highlights, or headings. "
                    'Return JSON: {"colors": ["#RRGGBB", ...]}. Max 8 colors. Empty list if none found.'
                )},
                {"role": "user", "content": css_content[:5000]},
            ],
            response_format={"type": "json_object"},
        )
        scraped = json.loads(response.choices[0].message.content).get("colors", [])
        secondary = [c for c in scraped if c.lower() not in primary_set]

    return {"primary": primary, "secondary": secondary}


async def _extract_fonts(
    data: dict, pages: list[tuple[str, str, str]]
) -> list[str] | None:
    # Brandfetch zuerst
    fonts = data.get("fonts", [])
    parts = [
        f"{f.get('type', '')}: {f['name']}" if f.get("type") else f["name"]
        for f in fonts if f.get("name")
    ]
    if parts:
        return parts

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

    found: set[str] = set()
    generic = {"sans-serif", "serif", "monospace", "inherit", "initial", "unset", "cursive", "fantasy"}

    # Google Fonts
    for match in re.findall(r'fonts\.googleapis\.com/css[^"\']*[?&]family=([^"\'&]+)', html):
        for name in match.replace("+", " ").split("|"):
            found.add(name.split(":")[0].strip())

    # Adobe Fonts / Typekit
    for match in re.findall(r'use\.typekit\.net/([a-z]+)\.css', html):
        found.add(f"Adobe Fonts ({match})")

    # CSS font-family declarations
    for match in re.findall(r"font-family\s*:\s*['\"]?([A-Za-z][\w\s-]+?)['\"]?\s*[,;]", html):
        name = match.strip()
        if name.lower() not in generic:
            found.add(name)

    if found:
        return sorted(found)

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
    return ai_fonts if ai_fonts else None


def _extract_images(data: dict, pages: list[tuple[str, str, str]]) -> list[str]:
    seen: set[str] = set()
    result: list[str] = []

    # Brandfetch
    for image in data.get("images", []):
        for fmt in image.get("formats", []):
            src = fmt.get("src")
            if src and src not in seen:
                seen.add(src)
                result.append(src)

    # HTML: Markdown-Bilder und <img src/data-src> Tags
    for _, markdown, html in pages:
        for url in re.findall(r'!\[.*?\]\((https?://[^\)]+)\)', markdown):
            if url not in seen:
                seen.add(url)
                result.append(url)
        for url in re.findall(r'<img[^>]+?(?:src|data-src)=["\']([^"\']+)["\']', html, re.IGNORECASE):
            if url.startswith("http") and url not in seen:
                seen.add(url)
                result.append(url)

    return result

def _extract_videos(pages: list[tuple[str, str, str]]) -> list[str]:
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
    videos: list[str] = []

    for _, markdown, html in pages:
        for pattern in md_patterns:
            for url in re.findall(pattern, markdown):
                if url not in seen:
                    seen.add(url)
                    videos.append(url)
        for pattern in html_patterns:
            for url in re.findall(pattern, html, re.IGNORECASE):
                if url and url not in seen:
                    seen.add(url)
                    videos.append(url)

    return videos



# --- run ---

async def run(state: ResearchState) -> dict:
    logger.info("Run Visuals")
    domain = state["competitor_domain"]
    company = domain.split(".")[0].capitalize()

    try:
        openai = AsyncOpenAI(api_key=get_settings().OPENAI_API_KEY)

        data = await _get_brand_data(domain)
        pages = await _get_page_contents(domain)

        logos = _extract_logos(data, pages)
        colors = await _extract_colors(data, pages, openai)
        fonts = await _extract_fonts(data, pages)
        images = _extract_images(data, pages)
        videos = _extract_videos(pages)


        visuals_data = VisualsData(
            company=company,
            url=f"https://{domain}",
            title=f"Visuals: {company}",
            logo=logos,
            colors=colors,
            fonts=fonts,
            images=images if images else None,
            videos=videos,
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
