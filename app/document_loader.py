"""Safe-ish public web document loader used by automatic RAG ingestion."""
from __future__ import annotations

from io import BytesIO
from ipaddress import ip_address
from socket import getaddrinfo
from urllib.parse import urljoin, urlparse

import httpx
from bs4 import BeautifulSoup
from pypdf import PdfReader


def _public_url(url: str) -> None:
    parsed = urlparse(url)
    if parsed.scheme not in {"http", "https"} or not parsed.hostname:
        raise ValueError("Only public http(s) URLs can be collected.")
    for record in getaddrinfo(parsed.hostname, None):
        address = ip_address(record[4][0])
        if address.is_private or address.is_loopback or address.is_link_local or address.is_reserved:
            raise ValueError("Private network URLs cannot be collected.")


def load_url(url: str) -> dict[str, str]:
    current = url
    with httpx.Client(follow_redirects=False, timeout=20, headers={"User-Agent": "ProofGraphResearch/1.0 (+research indexing)"}) as client:
        for _ in range(6):
            _public_url(current)
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
    if "pdf" in content_type or str(response.url).lower().endswith(".pdf"):
        text = "\n".join(page.extract_text() or "" for page in PdfReader(BytesIO(payload)).pages)
        return {"title": str(response.url).rsplit("/", 1)[-1] or "PDF document", "url": str(response.url), "content": text}
    soup = BeautifulSoup(payload, "html.parser")
    for node in soup(["script", "style", "nav", "footer", "header", "aside", "noscript"]):
        node.decompose()
    title = soup.title.get_text(" ", strip=True) if soup.title else str(response.url)
    text = soup.get_text(" ", strip=True)
    return {"title": title[:500], "url": str(response.url), "content": text[:200_000]}
