from __future__ import annotations

import time
from collections import deque
from dataclasses import asdict
from typing import Callable, Iterable
from xml.etree import ElementTree
from urllib.parse import urldefrag, urljoin, urlparse, urlunparse

import requests
from bs4 import BeautifulSoup

from .analyzer import PageAnalysis, analyze_page


DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) "
    "Chrome/126.0 Safari/537.36"
)
SITEMAP_NAMESPACE = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
SKIPPED_EXTENSIONS = {
    ".7z",
    ".avi",
    ".css",
    ".csv",
    ".doc",
    ".docx",
    ".gif",
    ".gz",
    ".ico",
    ".jpeg",
    ".jpg",
    ".js",
    ".json",
    ".mov",
    ".mp3",
    ".mp4",
    ".pdf",
    ".png",
    ".ppt",
    ".pptx",
    ".rar",
    ".svg",
    ".tar",
    ".webm",
    ".webp",
    ".xls",
    ".xlsx",
    ".xml",
    ".zip",
}


class SEOCrawler:
    def __init__(
        self,
        start_url: str,
        max_pages: int = 100,
        timeout: int = 15,
        delay_seconds: float = 0.2,
        user_agent: str = DEFAULT_USER_AGENT,
        use_sitemap: bool = False,
        sitemap_timeout: int = 5,
        progress_callback: Callable[[dict[str, object]], None] | None = None,
    ) -> None:
        self.start_url = normalize_url(start_url)
        self.max_pages = max_pages
        self.timeout = timeout
        self.delay_seconds = delay_seconds
        self.use_sitemap = use_sitemap
        self.sitemap_timeout = sitemap_timeout
        self.progress_callback = progress_callback
        self.root_domain = comparable_domain(urlparse(self.start_url).netloc)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": user_agent})

    def crawl(self) -> list[dict[str, object]]:
        seed_urls = self._seed_urls()
        queue: deque[str] = deque(seed_urls)
        queued: set[str] = set(seed_urls)
        visited: set[str] = set()
        result_urls: set[str] = set()
        results: list[PageAnalysis] = []

        while queue and len(result_urls) < self.max_pages:
            current_url = queue.popleft()
            if current_url in visited:
                continue

            visited.add(current_url)
            page_result, discovered_urls = self._fetch_and_analyze(current_url)
            report_url = normalize_url(page_result.url)
            if report_url not in result_urls:
                results.append(page_result)
                result_urls.add(report_url)
                self._emit_progress(
                    {
                        "crawled": len(results),
                        "max_pages": self.max_pages,
                        "queued": len(queue),
                        "status_code": page_result.status_code,
                        "url": page_result.url,
                    }
                )

            for discovered_url in discovered_urls:
                if len(result_urls) + len(queue) >= self.max_pages:
                    break
                if discovered_url not in visited and discovered_url not in queued:
                    queue.append(discovered_url)
                    queued.add(discovered_url)

            if self.delay_seconds > 0 and queue:
                time.sleep(self.delay_seconds)

        return [asdict(result) for result in results]

    def _seed_urls(self) -> list[str]:
        urls = [self.start_url]
        if self.use_sitemap:
            urls.extend(self._discover_sitemap_page_urls())
        return dedupe_preserve_order(urls)[: self.max_pages]

    def is_internal_url(self, url: str) -> bool:
        parsed_url = urlparse(url)
        if parsed_url.scheme not in {"http", "https"}:
            return False
        return comparable_domain(parsed_url.netloc) == self.root_domain

    def _fetch_and_analyze(self, url: str) -> tuple[PageAnalysis, list[str]]:
        try:
            response = self.session.get(url, timeout=self.timeout, allow_redirects=True)
            final_url = normalize_url(response.url)
            content_type = response.headers.get("content-type", "").lower()

            if "text/html" not in content_type:
                error = f"Non-HTML content type: {content_type or 'unknown'}"
                return analyze_page(final_url, response.status_code, "", self.is_internal_url, error), []

            html = response_text(response)
            analysis = analyze_page(final_url, response.status_code, html, self.is_internal_url)
            return analysis, list(self._extract_internal_links(final_url, html))
        except requests.RequestException as exc:
            error = f"{exc.__class__.__name__}: {exc}"
            return analyze_page(url, None, "", self.is_internal_url, error), []

    def _extract_internal_links(self, base_url: str, html: str) -> Iterable[str]:
        soup = BeautifulSoup(html or "", "lxml")
        for anchor in soup.find_all("a", href=True):
            href = anchor["href"].strip()
            candidate = normalize_url(urljoin(base_url, href))
            if self.is_internal_url(candidate) and not should_skip_url(candidate):
                yield candidate

    def _discover_sitemap_page_urls(self) -> list[str]:
        sitemap_urls = self._discover_sitemap_urls()
        page_urls: list[str] = []
        seen_sitemaps: set[str] = set()
        pending_sitemaps: deque[str] = deque(sitemap_urls)

        while pending_sitemaps and len(page_urls) < self.max_pages:
            sitemap_url = pending_sitemaps.popleft()
            if sitemap_url in seen_sitemaps:
                continue

            seen_sitemaps.add(sitemap_url)
            try:
                response = self.session.get(sitemap_url, timeout=self.sitemap_timeout)
                response.raise_for_status()
                root = ElementTree.fromstring(response.content)
            except (requests.RequestException, ElementTree.ParseError):
                continue

            if root.tag.endswith("sitemapindex"):
                for loc in root.findall(f".//{SITEMAP_NAMESPACE}loc"):
                    child_sitemap = normalize_url(loc.text or "")
                    if child_sitemap and self.is_internal_url(child_sitemap):
                        pending_sitemaps.append(child_sitemap)
            elif root.tag.endswith("urlset"):
                for loc in root.findall(f".//{SITEMAP_NAMESPACE}url/{SITEMAP_NAMESPACE}loc"):
                    page_url = normalize_url(loc.text or "")
                    if self.is_internal_url(page_url) and not should_skip_url(page_url):
                        page_urls.append(page_url)
                        if len(page_urls) >= self.max_pages:
                            break

        return dedupe_preserve_order(page_urls)

    def _discover_sitemap_urls(self) -> list[str]:
        candidates = [
            urljoin(self.start_url, "/sitemap.xml"),
            urljoin(self.start_url, "/sitemap_index.xml"),
        ]

        try:
            robots_url = urljoin(self.start_url, "/robots.txt")
            response = self.session.get(robots_url, timeout=self.sitemap_timeout)
            if response.ok:
                for line in response.text.splitlines():
                    key, separator, value = line.partition(":")
                    if separator and key.strip().lower() == "sitemap":
                        candidates.append(value.strip())
        except requests.RequestException:
            pass

        return [
            url
            for url in dedupe_preserve_order(normalize_url(candidate) for candidate in candidates if candidate)
            if self.is_internal_url(url)
        ]

    def _emit_progress(self, event: dict[str, object]) -> None:
        if self.progress_callback:
            self.progress_callback(event)


def normalize_url(url: str) -> str:
    url_without_fragment, _fragment = urldefrag(url.strip())
    parsed_url = urlparse(url_without_fragment)
    scheme = parsed_url.scheme.lower() or "https"
    netloc = parsed_url.netloc.lower()
    path = parsed_url.path or "/"

    if netloc.endswith(":80") and scheme == "http":
        netloc = netloc[:-3]
    if netloc.endswith(":443") and scheme == "https":
        netloc = netloc[:-4]

    return urlunparse((scheme, netloc, path, "", parsed_url.query, ""))


def comparable_domain(netloc: str) -> str:
    host = netloc.lower().split("@")[-1].split(":")[0]
    return host[4:] if host.startswith("www.") else host


def should_skip_url(url: str) -> bool:
    parsed_url = urlparse(url)
    if parsed_url.scheme not in {"http", "https"}:
        return True
    path = parsed_url.path.lower()
    return any(path.endswith(extension) for extension in SKIPPED_EXTENSIONS)


def response_text(response: requests.Response) -> str:
    if not response.encoding or response.encoding.lower() == "iso-8859-1":
        response.encoding = response.apparent_encoding
    return response.text


def dedupe_preserve_order(urls: Iterable[str]) -> list[str]:
    seen: set[str] = set()
    unique_urls: list[str] = []
    for url in urls:
        if url and url not in seen:
            seen.add(url)
            unique_urls.append(url)
    return unique_urls
