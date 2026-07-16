from __future__ import annotations

from dataclasses import dataclass
from typing import Callable
from urllib.parse import urljoin

from bs4 import BeautifulSoup


@dataclass(frozen=True)
class PageAnalysis:
    url: str
    status_code: int | None
    title: str
    title_length: int
    meta_description: str
    meta_description_length: int
    h1_count: int
    h1_text: str
    canonical: str
    image_count: int
    images_missing_alt: int
    images_missing_alt_ratio: float
    internal_links_count: int
    external_links_count: int
    error: str


def analyze_page(
    url: str,
    status_code: int | None,
    html: str,
    is_internal_url: Callable[[str], bool],
    error: str = "",
) -> PageAnalysis:
    soup = BeautifulSoup(html or "", "lxml")

    title = _clean_text(soup.title.get_text()) if soup.title else ""
    meta_description_tag = soup.find("meta", attrs={"name": lambda value: value and value.lower() == "description"})
    meta_description = ""
    if meta_description_tag:
        meta_description = _clean_text(meta_description_tag.get("content", ""))

    h1_values = [_clean_text(h1.get_text(" ", strip=True)) for h1 in soup.find_all("h1")]
    h1_values = [value for value in h1_values if value]

    canonical_tag = soup.find("link", rel=lambda value: value and "canonical" in value)
    canonical = ""
    if canonical_tag:
        canonical = urljoin(url, canonical_tag.get("href", "").strip())

    images = soup.find_all("img")
    images_missing_alt = sum(
        1 for image in images if not image.has_attr("alt") or not image.get("alt", "").strip()
    )

    internal_links_count = 0
    external_links_count = 0
    for anchor in soup.find_all("a", href=True):
        absolute_url = urljoin(url, anchor["href"].strip())
        if absolute_url.startswith(("http://", "https://")):
            if is_internal_url(absolute_url):
                internal_links_count += 1
            else:
                external_links_count += 1

    image_count = len(images)
    missing_alt_ratio = round(images_missing_alt / image_count, 4) if image_count else 0.0

    return PageAnalysis(
        url=url,
        status_code=status_code,
        title=title,
        title_length=len(title),
        meta_description=meta_description,
        meta_description_length=len(meta_description),
        h1_count=len(h1_values),
        h1_text=" | ".join(h1_values),
        canonical=canonical,
        image_count=image_count,
        images_missing_alt=images_missing_alt,
        images_missing_alt_ratio=missing_alt_ratio,
        internal_links_count=internal_links_count,
        external_links_count=external_links_count,
        error=error,
    )


def _clean_text(value: str) -> str:
    return " ".join(value.split())

