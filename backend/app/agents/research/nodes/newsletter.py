import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[4]))

import asyncio
import base64
import json
from datetime import date, datetime
from urllib.parse import urlparse

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import httpx
import structlog
from bs4 import BeautifulSoup
from firecrawl import V1FirecrawlApp as FirecrawlApp

from app.agents.research.state import ResearchState, NewsletterData
from app.config import get_settings

logger = structlog.get_logger(__name__)
today = date.today().strftime("%Y-%m-%d")

NEWSLETTER_EMAIL = "celonisdashboard@gmail.com"
SUBSCRIPTIONS_FILE = Path(__file__).parents[4] / "data" / "newsletter_subscriptions.json"


# --- Subscription tracking ---

def _load_subscriptions() -> dict:
    if SUBSCRIPTIONS_FILE.exists():
        return json.loads(SUBSCRIPTIONS_FILE.read_text())
    return {}


def _save_subscriptions(data: dict) -> None:
    SUBSCRIPTIONS_FILE.parent.mkdir(parents=True, exist_ok=True)
    SUBSCRIPTIONS_FILE.write_text(json.dumps(data, indent=2))


# --- Subscribe via website form ---

async def _subscribe_to_newsletter(domain: str) -> bool:
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://google.serper.dev/search",
            headers={"X-API-KEY": get_settings().SERPER_API_KEY},
            json={"q": f"site:{domain} newsletter subscribe signup email", "num": 3},
            timeout=10,
        )
    results = resp.json().get("organic", [])
    if not results:
        return False

    app = FirecrawlApp(api_key=get_settings().FIRECRAWL_API_KEY)

    for result in results[:3]:
        url = result["link"]
        try:
            scraped = await asyncio.to_thread(app.scrape_url, url, formats=["rawHtml"])
            html = getattr(scraped, "rawHtml", "") or ""
            if not html:
                continue

            soup = BeautifulSoup(html, "html.parser")

            for form in soup.find_all("form"):
                # Find email input
                email_input = (
                    form.find("input", {"type": "email"})
                    or form.find("input", {"name": lambda n: n and "email" in n.lower()})
                    or form.find("input", {"placeholder": lambda p: p and "email" in p.lower()})
                )
                if not email_input:
                    continue

                action = form.get("action") or url
                method = form.get("method", "post").lower()

                # Resolve relative action URL
                if action.startswith("/"):
                    parsed = urlparse(url)
                    action = f"{parsed.scheme}://{parsed.netloc}{action}"
                elif not action.startswith("http"):
                    action = url

                # Build form data
                form_data: dict = {}
                for inp in form.find_all(["input", "textarea", "select"]):
                    name = inp.get("name")
                    if not name:
                        continue
                    if inp.get("type", "").lower() in ("submit", "button", "reset", "image"):
                        continue
                    if name == email_input.get("name"):
                        form_data[name] = NEWSLETTER_EMAIL
                    else:
                        form_data[name] = inp.get("value", "")

                try:
                    async with httpx.AsyncClient(follow_redirects=True, timeout=15) as http:
                        r = await (http.post(action, data=form_data) if method == "post"
                                   else http.get(action, params=form_data))
                        if r.status_code < 400:
                            logger.info("newsletter_subscribed", domain=domain, url=url)
                            return True
                except Exception as e:
                    logger.warning("newsletter_submit_failed", action=action, error=str(e))

        except Exception as e:
            logger.warning("newsletter_scrape_failed", url=url, error=str(e))

    return False


# --- Read newsletters from Gmail via IMAP ---

GMAIL_TOKEN_FILE = Path(__file__).parents[4] / "data" / "gmail_token.json"
GMAIL_SCOPES = ["https://www.googleapis.com/auth/gmail.readonly"]


def _get_gmail_service():
    if not GMAIL_TOKEN_FILE.exists():
        logger.warning("gmail_token_not_found", path=str(GMAIL_TOKEN_FILE))
        return None
    creds = Credentials.from_authorized_user_file(str(GMAIL_TOKEN_FILE), GMAIL_SCOPES)
    if creds.expired and creds.refresh_token:
        creds.refresh(Request())
        GMAIL_TOKEN_FILE.write_text(creds.to_json())
    return build("gmail", "v1", credentials=creds)


def _extract_body(payload: dict) -> str:
    mime = payload.get("mimeType", "")
    if mime in ("text/plain", "text/html"):
        data = payload.get("body", {}).get("data", "")
        return base64.urlsafe_b64decode(data + "==").decode(errors="replace") if data else ""
    html_fallback = ""
    for part in payload.get("parts", []):
        if part.get("mimeType") == "text/plain":
            data = part.get("body", {}).get("data", "")
            return base64.urlsafe_b64decode(data + "==").decode(errors="replace") if data else ""
        if part.get("mimeType") == "text/html" and not html_fallback:
            data = part.get("body", {}).get("data", "")
            html_fallback = base64.urlsafe_b64decode(data + "==").decode(errors="replace") if data else ""
        if part.get("mimeType", "").startswith("multipart/"):
            result = _extract_body(part)
            if result:
                return result
    return html_fallback


def _fetch_newsletters_from_gmail(domain: str, since: str | None = None) -> list[dict]:
    service = _get_gmail_service()
    if not service:
        return []

    try:
        query = f"from:@{domain}"
        if since:
            try:
                after = datetime.strptime(since, "%Y-%m-%d").strftime("%Y/%m/%d")
                query += f" after:{after}"
            except ValueError:
                pass

        result = service.users().messages().list(userId="me", q=query, maxResults=10).execute()
        messages = result.get("messages", [])

        newsletters = []
        for ref in messages:
            msg = service.users().messages().get(userId="me", id=ref["id"], format="full").execute()
            headers = {h["name"]: h["value"] for h in msg["payload"].get("headers", [])}
            newsletters.append({
                "subject": headers.get("Subject", ""),
                "from": headers.get("From", ""),
                "date": headers.get("Date", ""),
                "body": _extract_body(msg["payload"])[:8000],
            })

        return newsletters

    except Exception as e:
        logger.warning("gmail_fetch_failed", domain=domain, error=str(e))
        return []


# --- Node entry point ---

async def run(state: ResearchState) -> dict:
    domain = state["competitor_domain"]
    try:
        subscriptions = _load_subscriptions()
        sub_info = subscriptions.get(domain)

        if sub_info is None:
            logger.info("newsletter_not_yet_subscribed", domain=domain)
            success = await _subscribe_to_newsletter(domain)
            sub_info = {"subscribed": success, "subscribed_at": today, "last_checked": None}
            subscriptions[domain] = sub_info
            _save_subscriptions(subscriptions)
            logger.info("newsletter_subscription_result", domain=domain, success=success)

        last_checked = sub_info.get("last_checked")
        newsletters = await asyncio.to_thread(_fetch_newsletters_from_gmail, domain, last_checked)

        subscriptions[domain]["last_checked"] = today
        _save_subscriptions(subscriptions)

        return {
            "newsletter": NewsletterData(
                newsletter={"subscribed": sub_info.get("subscribed", False), "items": newsletters},
                source="gmail",
            ),
            "completed_nodes": ["newsletter"],
        }
    except Exception as e:
        logger.error("node_failed", node="newsletter", error=str(e))
        return {"errors": [f"newsletter: {e}"]}


if __name__ == "__main__":
    import asyncio
    structlog.configure(processors=[structlog.dev.ConsoleRenderer()])

    async def main():
        from app.agents.research.state import (
            VisualsData, PositioningData, FinancialData, SocialData,
            SeoGeoData, NewsData, EventsData,
        )
        state = ResearchState(
            competitor_domain="celonis.com",
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
            print(result["newsletter"].model_dump_json(indent=2))

    asyncio.run(main())
