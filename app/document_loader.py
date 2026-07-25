"""Safe-ish public web document loader used by automatic RAG ingestion."""
from __future__ import annotations

from io import BytesIO
from ipaddress import ip_address
from socket import getaddrinfo
from urllib.parse import urljoin, urlparse
from urllib.robotparser import RobotFileParser

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader

from app.config import get_settings
from app.crawl_policy import canonical_url, wait_for_host


def _public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public http(s) URLs can be collected.")
    for record in getaddrinfo(parsed.hostname, None):
        address = ip_address(record[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            raise ValueError("Private network URLs cannot be collected.")


def _robots_allowed(client: httpx.Client, url: str, user_agent: str) -> bool:
    settings = get_settings()
    if not settings.crawler_respect_robots_txt:
        return True
    parsed = urlparse(url)
    robots_url = f"{parsed.scheme}://{parsed.netloc}/robots.txt"
    _public_url(robots_url)
    try:
        response = client.get(robots_url)
        if response.status_code in {401, 403}:
            return False
        if response.status_code >= 400:
            return True
        parser = RobotFileParser()
        parser.parse(response.text.splitlines())
        return parser.can_fetch(user_agent, url)
    except httpx.HTTPError:
        # A transient robots failure must not become an implicit bypass.
        return False


def load_url(url: str) -> dict[str, str]:
    settings = get_settings()
    current = canonical_url(url)
    with httpx.Client(follow_redirects=False, timeout=20, headers={"User-Agent": settings.crawler_user_agent}) as client:
        for _ in range(6):
            _public_url(current)
            wait_for_host(current, settings.crawler_request_interval_seconds)
            if not _robots_allowed(client, current, settings.crawler_user_agent):
                raise ValueError("Collection is disallowed by robots.txt.")
            response = client.get(current)
            if response.is_redirect:
                location = response.headers.get("location")
                if not location:
                    raise ValueError("Redirect response has no location.")
                current = urljoin(current, location)
                continue
            response.raise_for_status()
            break
        else:
            raise ValueError("Too many redirects while collecting URL.")
        payload = response.content[:10_000_000]
        content_type = response.headers.get("content-type", "").lower()
        metadata = {"etag": response.headers.get("etag"), "last_modified": response.headers.get("last-modified")}
    if "pdf" in content_type or str(response.url).lower().endswith(".pdf") or payload.startswith(b"%PDF-"):
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(payload)).pages)
        return {"title": str(response.url).rsplit("/", 1)[-1] or "PDF document", "url": canonical_url(str(response.url)), "content": text, "raw_content": payload, "content_type": content_type or "application/pdf", **metadata}
    soup = BeautifulSoup(payload, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        node.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else str(response.url)
    text = soup.get_text(" ", strip=True)
    return {"title": title[:500], "url": canonical_url(str(response.url)), "content": text[:200_000], "raw_content": payload, "content_type": content_type or "text/html", **metadata}
