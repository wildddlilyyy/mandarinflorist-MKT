from __future__ import annotations

import argparse
import csv
import html
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urljoin, urlparse
from xml.etree import ElementTree

import pandas as pd
import requests
from bs4 import BeautifulSoup

from .crawler import DEFAULT_USER_AGENT, SEOCrawler, comparable_domain, normalize_url, response_text
from .main import slugify_site_name


INDICATORS = [
    ("https", "HTTPS", "安全連線"),
    ("meta_title", "Meta Title", "頁面標題"),
    ("meta_description", "Meta Description", "頁面摘要"),
    ("html_semantics", "HTML 語意結構", "H1/H2 架構"),
    ("open_graph", "Open Graph", "社群摘要"),
    ("rwd", "RWD", "行動裝置"),
    ("schema", "Schema", "結構化資料"),
    ("robots_txt", "robots.txt", "爬蟲指引"),
    ("sitemap", "Sitemap", "頁面索引"),
    ("llms_txt", "llms.txt", "AI 讀取指引"),
]

AI_AUDIT_COLUMNS = ["site_url", "checked_at", "pages_checked", "ai_score", "ai_grade"]
for key, _name, _subtitle in INDICATORS:
    AI_AUDIT_COLUMNS.extend([f"{key}_status", f"{key}_score", f"{key}_evidence", f"{key}_recommendation"])
AI_AUDIT_COLUMNS.append("overall_recommendations")


@dataclass(frozen=True)
class IndicatorResult:
    key: str
    status: str
    score: int
    evidence: str
    recommendation: str


@dataclass
class SiteFetch:
    url: str
    status_code: int | None
    html: str
    soup: BeautifulSoup
    error: str = ""


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an AI readiness audit and export a separate CSV/HTML report.")
    parser.add_argument("--url", required=True, help="Website URL to audit.")
    parser.add_argument("--site-name", default="", help="Optional client/site name for output folder.")
    parser.add_argument("--max-pages", type=int, default=300, help="Maximum number of pages to crawl for site summary.")
    parser.add_argument("--use-sitemap", action="store_true", help="Seed the crawl queue from sitemap URLs when available.")
    parser.add_argument("--output", default="", help="CSV output path. Default: output/{site-name}/ai_audit.csv")
    parser.add_argument("--html-output", default="", help="HTML output path. Default: output/{site-name}/ai_audit.html")
    parser.add_argument("--timeout", type=int, default=20, help="Request timeout in seconds.")
    parser.add_argument("--sitemap-timeout", type=int, default=10, help="Sitemap and robots.txt timeout in seconds.")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between crawl requests in seconds.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help=f"Request User-Agent. Default: {DEFAULT_USER_AGENT}")
    parser.add_argument("--progress-every", type=int, default=10, help="Print progress every N crawled pages. Use 0 to disable.")
    return parser


def main() -> None:
    args = build_parser().parse_args()
    csv_output = resolve_ai_output_path(args.output, args.site_name, args.url, "ai_audit.csv")
    html_output = resolve_ai_output_path(args.html_output, args.site_name, args.url, "ai_audit.html")

    row = run_ai_audit(
        url=args.url,
        max_pages=args.max_pages,
        use_sitemap=args.use_sitemap,
        timeout=args.timeout,
        sitemap_timeout=args.sitemap_timeout,
        delay=args.delay,
        user_agent=args.user_agent,
        progress_every=args.progress_every,
    )
    export_ai_audit_csv(row, csv_output)
    render_ai_audit_html(csv_output, html_output)

    print(f"AI audit CSV saved to: {csv_output}")
    print(f"AI audit HTML saved to: {html_output}")
    print(f"AI score: {row['ai_score']} / 100 ({row['ai_grade']})")


def run_ai_audit(
    url: str,
    max_pages: int,
    use_sitemap: bool,
    timeout: int,
    sitemap_timeout: int,
    delay: float,
    user_agent: str,
    progress_every: int,
) -> dict[str, Any]:
    start_url = normalize_url(url)
    session = requests.Session()
    session.headers.update({"User-Agent": user_agent})

    homepage = fetch_site(session, start_url, timeout)
    site_signals = collect_site_signals(session, start_url, sitemap_timeout)
    crawl_rows = crawl_summary_rows(
        start_url=start_url,
        max_pages=max_pages,
        timeout=timeout,
        sitemap_timeout=sitemap_timeout,
        delay=delay,
        user_agent=user_agent,
        use_sitemap=use_sitemap,
        progress_every=progress_every,
    )

    results = [
        check_https(start_url),
        check_meta_title(homepage, crawl_rows),
        check_meta_description(homepage, crawl_rows),
        check_html_semantics(homepage, crawl_rows),
        check_open_graph(homepage),
        check_rwd(homepage),
        check_schema(homepage),
        check_robots(site_signals),
        check_sitemap(site_signals),
        check_llms(site_signals),
    ]

    total_score = sum(result.score for result in results)
    row: dict[str, Any] = {
        "site_url": start_url,
        "checked_at": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "pages_checked": len(crawl_rows),
        "ai_score": total_score,
        "ai_grade": grade_for_score(total_score),
    }

    recommendations = []
    for result in results:
        row[f"{result.key}_status"] = result.status
        row[f"{result.key}_score"] = result.score
        row[f"{result.key}_evidence"] = result.evidence
        row[f"{result.key}_recommendation"] = result.recommendation
        if result.status != "pass":
            recommendations.append(f"{indicator_name(result.key)}: {result.recommendation}")

    row["overall_recommendations"] = " | ".join(recommendations) if recommendations else "AI 可讀性基礎狀態良好，建議持續維護內容品質與結構化資料。"
    return row


def crawl_summary_rows(
    start_url: str,
    max_pages: int,
    timeout: int,
    sitemap_timeout: int,
    delay: float,
    user_agent: str,
    use_sitemap: bool,
    progress_every: int,
) -> list[dict[str, object]]:
    crawler = SEOCrawler(
        start_url=start_url,
        max_pages=max_pages,
        timeout=timeout,
        delay_seconds=delay,
        user_agent=user_agent,
        use_sitemap=use_sitemap,
        sitemap_timeout=sitemap_timeout,
        progress_callback=build_progress_callback(progress_every),
    )
    return crawler.crawl()


def build_progress_callback(progress_every: int):
    if progress_every <= 0:
        return None

    def progress(event: dict[str, object]) -> None:
        crawled = int(event["crawled"])
        if crawled == 1 or crawled % progress_every == 0:
            print(
                f"[ai-audit progress] {crawled}/{event['max_pages']} pages, "
                f"queued={event['queued']}, status={event['status_code']}, url={event['url']}"
            )

    return progress


def fetch_site(session: requests.Session, url: str, timeout: int) -> SiteFetch:
    try:
        response = session.get(url, timeout=timeout, allow_redirects=True)
        final_url = normalize_url(response.url)
        content_type = response.headers.get("content-type", "").lower()
        page_html = response_text(response) if "text/html" in content_type else ""
        return SiteFetch(
            url=final_url,
            status_code=response.status_code,
            html=page_html,
            soup=BeautifulSoup(page_html, "lxml"),
        )
    except requests.RequestException as exc:
        return SiteFetch(url=url, status_code=None, html="", soup=BeautifulSoup("", "lxml"), error=f"{exc.__class__.__name__}: {exc}")


def collect_site_signals(session: requests.Session, start_url: str, timeout: int) -> dict[str, Any]:
    signals: dict[str, Any] = {
        "robots_status": "fail",
        "robots_evidence": "",
        "robots_text": "",
        "sitemap_urls": [],
        "sitemap_page_count": 0,
        "llms_urls": [],
        "llms_status": "fail",
        "llms_evidence": "",
    }

    robots_url = urljoin(start_url, "/robots.txt")
    try:
        response = session.get(robots_url, timeout=timeout)
        if response.ok:
            signals["robots_status"] = "pass"
            signals["robots_text"] = response.text
            signals["robots_evidence"] = f"robots.txt 可讀：{robots_url}"
            signals["sitemap_urls"].extend(extract_robots_values(response.text, "sitemap"))
            signals["llms_urls"].extend(extract_robots_values(response.text, "llms"))
        else:
            signals["robots_evidence"] = f"robots.txt 回應狀態碼：{response.status_code}"
    except requests.RequestException as exc:
        signals["robots_evidence"] = f"robots.txt 無法讀取：{exc.__class__.__name__}"

    signals["sitemap_urls"].extend([urljoin(start_url, "/sitemap.xml"), urljoin(start_url, "/sitemap_index.xml")])
    signals["sitemap_page_count"] = count_sitemap_pages(session, start_url, signals["sitemap_urls"], timeout)

    llms_candidates = [urljoin(start_url, "/llms.txt"), urljoin(start_url, "/llms.txt/")]
    llms_candidates.extend(signals["llms_urls"])
    llms_result = fetch_first_ok(session, llms_candidates, timeout)
    if llms_result:
        signals["llms_status"] = "pass"
        signals["llms_evidence"] = f"llms.txt 可讀：{llms_result}"
    else:
        signals["llms_evidence"] = "未找到可讀取的 llms.txt 或 LLMS 宣告。"

    return signals


def extract_robots_values(robots_text: str, key: str) -> list[str]:
    values = []
    for line in robots_text.splitlines():
        name, separator, value = line.partition(":")
        if separator and name.strip().lower() == key.lower():
            values.append(value.strip())
    return values


def count_sitemap_pages(session: requests.Session, start_url: str, sitemap_urls: list[str], timeout: int) -> int:
    root_domain = comparable_domain(urlparse(start_url).netloc)
    pending = [normalize_url(url) for url in sitemap_urls if url]
    seen: set[str] = set()
    page_urls: set[str] = set()

    while pending:
        sitemap_url = pending.pop(0)
        if sitemap_url in seen or comparable_domain(urlparse(sitemap_url).netloc) != root_domain:
            continue
        seen.add(sitemap_url)

        try:
            response = session.get(sitemap_url, timeout=timeout)
            response.raise_for_status()
            root = ElementTree.fromstring(response.content)
        except (requests.RequestException, ElementTree.ParseError):
            continue

        namespace = "{http://www.sitemaps.org/schemas/sitemap/0.9}"
        if root.tag.endswith("sitemapindex"):
            pending.extend(normalize_url(loc.text or "") for loc in root.findall(f".//{namespace}loc") if loc.text)
        elif root.tag.endswith("urlset"):
            for loc in root.findall(f".//{namespace}url/{namespace}loc"):
                if loc.text:
                    page_urls.add(normalize_url(loc.text))

    return len(page_urls)


def fetch_first_ok(session: requests.Session, urls: list[str], timeout: int) -> str:
    for url in dict.fromkeys(normalize_url(candidate) for candidate in urls if candidate):
        try:
            response = session.get(url, timeout=timeout)
            if response.ok and response.text.strip():
                return url
        except requests.RequestException:
            continue
    return ""


def check_https(url: str) -> IndicatorResult:
    if urlparse(url).scheme == "https":
        return indicator("https", "pass", f"網站使用 HTTPS：{url}", "維持 HTTPS 與有效憑證。")
    return indicator("https", "fail", f"網站未使用 HTTPS：{url}", "啟用 HTTPS，並將 HTTP 301 轉址到 HTTPS。")


def check_meta_title(homepage: SiteFetch, rows: list[dict[str, object]]) -> IndicatorResult:
    total = len(rows)
    missing = sum(1 for row in rows if not str(row.get("title") or "").strip())
    homepage_title = homepage.soup.title.get_text(strip=True) if homepage.soup.title else ""
    if homepage_title and missing == 0:
        return indicator("meta_title", "pass", f"首頁 title 存在；抽查 {total} 頁皆有 title。", "維持每頁唯一且清楚的 title。")
    if homepage_title:
        return indicator("meta_title", "partial", f"首頁 title 存在；抽查 {total} 頁，有 {missing} 頁缺 title。", "補齊缺少 title 的頁面，並避免多頁使用相同標題。")
    return indicator("meta_title", "fail", "首頁缺少 title。", "補上首頁 title，並檢查全站重要頁面。")


def check_meta_description(homepage: SiteFetch, rows: list[dict[str, object]]) -> IndicatorResult:
    total = len(rows)
    missing = sum(1 for row in rows if not str(row.get("meta_description") or "").strip())
    homepage_description = homepage.soup.find("meta", attrs={"name": lambda value: value and value.lower() == "description"})
    if homepage_description and missing == 0:
        return indicator("meta_description", "pass", f"首頁 description 存在；抽查 {total} 頁皆有 description。", "維持每頁清楚摘要。")
    if homepage_description:
        return indicator("meta_description", "partial", f"首頁 description 存在；抽查 {total} 頁，有 {missing} 頁缺 description。", "補齊缺少 description 的頁面。")
    return indicator("meta_description", "fail", "首頁缺少 meta description。", "補上首頁與重要頁面的 meta description。")


def check_html_semantics(homepage: SiteFetch, rows: list[dict[str, object]]) -> IndicatorResult:
    h1_count = len(homepage.soup.find_all("h1"))
    h2_count = len(homepage.soup.find_all("h2"))
    missing_h1 = sum(1 for row in rows if int(row.get("h1_count") or 0) == 0)
    if h1_count == 1 and h2_count > 0 and missing_h1 == 0:
        return indicator("html_semantics", "pass", f"首頁有 1 個 H1、{h2_count} 個 H2；抽查頁面皆有 H1。", "維持清楚的 H1/H2 標題層級。")
    if h1_count > 0:
        return indicator("html_semantics", "partial", f"首頁 H1={h1_count}、H2={h2_count}；抽查有 {missing_h1} 頁缺 H1。", "調整標題層級，讓每頁有清楚主題。")
    return indicator("html_semantics", "fail", f"首頁缺少 H1；H2={h2_count}。", "補上首頁 H1，並建立 H2 區塊架構。")


def check_open_graph(homepage: SiteFetch) -> IndicatorResult:
    required = ["og:title", "og:description", "og:image", "og:url"]
    found = [prop for prop in required if homepage.soup.find("meta", property=prop)]
    if len(found) == len(required):
        return indicator("open_graph", "pass", "首頁 Open Graph 欄位完整。", "維持 og:title、og:description、og:image、og:url。")
    if found:
        missing = ", ".join(prop for prop in required if prop not in found)
        return indicator("open_graph", "partial", f"已找到 {len(found)}/4 個 OG 欄位；缺少 {missing}。", "補齊缺少的 Open Graph 欄位。")
    return indicator("open_graph", "fail", "首頁未找到 Open Graph meta。", "新增 og:title、og:description、og:image、og:url。")


def check_rwd(homepage: SiteFetch) -> IndicatorResult:
    viewport = homepage.soup.find("meta", attrs={"name": lambda value: value and value.lower() == "viewport"})
    if viewport:
        return indicator("rwd", "pass", f"找到 viewport meta：{viewport.get('content', '')}", "維持行動裝置 viewport 設定，並定期做手機版檢查。")
    return indicator("rwd", "fail", "未找到 viewport meta。", "新增 viewport meta，確保 RWD 基礎設定。")


def check_schema(homepage: SiteFetch) -> IndicatorResult:
    json_ld = homepage.soup.find_all("script", attrs={"type": lambda value: value and value.lower() == "application/ld+json"})
    microdata = homepage.soup.find_all(attrs={"itemscope": True})
    if json_ld or microdata:
        return indicator("schema", "pass", f"找到 JSON-LD {len(json_ld)} 組、microdata {len(microdata)} 組。", "維持 Organization、WebSite、Product 或 Breadcrumb 等 Schema。")
    return indicator("schema", "fail", "首頁未找到 JSON-LD 或 microdata。", "新增結構化資料，協助 AI 與搜尋引擎理解品牌與內容。")


def check_robots(signals: dict[str, Any]) -> IndicatorResult:
    if signals["robots_status"] == "pass":
        return indicator("robots_txt", "pass", signals["robots_evidence"], "維持 robots.txt 可讀，並確認重要頁面未被封鎖。")
    return indicator("robots_txt", "fail", signals["robots_evidence"], "建立可讀取的 robots.txt，並宣告 sitemap。")


def check_sitemap(signals: dict[str, Any]) -> IndicatorResult:
    page_count = int(signals.get("sitemap_page_count") or 0)
    if page_count > 0:
        return indicator("sitemap", "pass", f"可解析 sitemap，找到 {page_count} 個 URL。", "維持 sitemap 更新，讓搜尋引擎快速找到頁面。")
    return indicator("sitemap", "fail", "未找到可解析且含 URL 的 sitemap。", "建立 sitemap.xml，或在 robots.txt 宣告 Sitemap。")


def check_llms(signals: dict[str, Any]) -> IndicatorResult:
    if signals["llms_status"] == "pass":
        return indicator("llms_txt", "pass", signals["llms_evidence"], "維持 llms.txt，提供 AI 系統可讀的品牌與重點內容。")
    return indicator("llms_txt", "fail", signals["llms_evidence"], "新增 /llms.txt，提供 AI 系統可讀的網站摘要與重點連結。")


def indicator(key: str, status: str, evidence: str, recommendation: str) -> IndicatorResult:
    score_by_status = {"pass": 10, "partial": 5, "fail": 0}
    return IndicatorResult(key=key, status=status, score=score_by_status[status], evidence=evidence, recommendation=recommendation)


def indicator_name(key: str) -> str:
    for indicator_key, name, _subtitle in INDICATORS:
        if indicator_key == key:
            return name
    return key


def grade_for_score(score: int) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def resolve_ai_output_path(output: str, site_name: str, url: str, filename: str) -> Path:
    if output:
        return Path(output)
    folder_name = slugify_site_name(site_name) if site_name else slugify_site_name(comparable_domain(urlparse(url).netloc))
    return Path("output") / folder_name / filename


def export_ai_audit_csv(row: dict[str, Any], output_path: Path) -> Path:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with output_path.open("w", newline="", encoding="utf-8-sig") as csv_file:
        writer = csv.DictWriter(csv_file, fieldnames=AI_AUDIT_COLUMNS)
        writer.writeheader()
        writer.writerow({column: row.get(column, "") for column in AI_AUDIT_COLUMNS})
    return output_path


def render_ai_audit_html(input_path: Path, output_path: Path) -> Path:
    dataframe = pd.read_csv(input_path).fillna("")
    row = dataframe.to_dict("records")[0] if len(dataframe) else {}
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(build_ai_audit_html(row), encoding="utf-8")
    return output_path


def build_ai_audit_html(row: dict[str, Any]) -> str:
    cards = "\n".join(build_indicator_card(row, key, name, subtitle) for key, name, subtitle in INDICATORS)
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>AI Readiness Audit</title>
  <style>
    body {{ margin: 0; background: #f7f7f8; color: #26262a; font-family: "Noto Sans TC", "Microsoft JhengHei", Arial, sans-serif; }}
    .shell {{ width: min(1120px, calc(100% - 32px)); margin: 0 auto; padding: 34px 0 44px; }}
    .eyebrow {{ margin: 0 0 8px; color: #8d4e2c; font-size: 13px; font-weight: 800; letter-spacing: 0; text-transform: uppercase; text-align: center; }}
    h1 {{ margin: 0; text-align: center; font-size: 32px; line-height: 1.2; }}
    .sub {{ margin: 12px auto 26px; max-width: 760px; color: #6b7280; text-align: center; line-height: 1.7; }}
    .score {{ margin: 0 auto 24px; width: fit-content; padding: 12px 18px; border: 1px solid #dedfe4; border-radius: 8px; background: white; font-weight: 800; }}
    .grid {{ display: grid; grid-template-columns: repeat(5, minmax(0, 1fr)); gap: 14px; }}
    .card {{ min-height: 132px; padding: 16px; border: 1px solid #dedfe4; border-radius: 8px; background: white; }}
    .card h2 {{ margin: 0; font-size: 17px; text-align: center; }}
    .card .label {{ margin: 4px 0 12px; color: #8b8f99; text-align: center; }}
    .status {{ display: inline-block; padding: 3px 8px; border-radius: 999px; color: white; font-size: 12px; font-weight: 800; }}
    .pass {{ background: #2e7d32; }}
    .partial {{ background: #bf7b16; }}
    .fail {{ background: #ba3d34; }}
    .evidence {{ margin: 10px 0 0; color: #555963; font-size: 13px; line-height: 1.45; }}
    .recommendation {{ margin: 8px 0 0; color: #25262b; font-size: 13px; line-height: 1.45; }}
    .overall {{ margin-top: 18px; padding: 16px; border: 1px solid #dedfe4; border-radius: 8px; background: white; color: #555963; line-height: 1.6; }}
    @media (max-width: 980px) {{ .grid {{ grid-template-columns: repeat(2, minmax(0, 1fr)); }} }}
    @media (max-width: 560px) {{ .grid {{ grid-template-columns: 1fr; }} h1 {{ font-size: 26px; }} }}
  </style>
</head>
<body>
  <main class="shell">
    <p class="eyebrow">AI Readiness</p>
    <h1>AI 搜尋可讀性十項指標</h1>
    <p class="sub">檢查網站是否具備 ChatGPT、Perplexity、Google AI Overview 等 AI 搜尋情境中，較容易被理解、引用與摘要的基礎訊號。</p>
    <div class="score">AI Score：{html.escape(str(row.get("ai_score", "")))} / 100（{html.escape(str(row.get("ai_grade", "")))}）｜檢查頁數：{html.escape(str(row.get("pages_checked", "")))}</div>
    <section class="grid">{cards}</section>
    <section class="overall"><strong>整體建議：</strong>{html.escape(str(row.get("overall_recommendations", "")))}</section>
  </main>
</body>
</html>
"""


def build_indicator_card(row: dict[str, Any], key: str, name: str, subtitle: str) -> str:
    status = str(row.get(f"{key}_status", "fail"))
    score = str(row.get(f"{key}_score", "0"))
    evidence = str(row.get(f"{key}_evidence", ""))
    recommendation = str(row.get(f"{key}_recommendation", ""))
    return f"""<article class="card">
      <h2>{html.escape(name)}</h2>
      <p class="label">{html.escape(subtitle)}</p>
      <span class="status {html.escape(status)}">{html.escape(status)} · {html.escape(score)}/10</span>
      <p class="evidence">{html.escape(evidence)}</p>
      <p class="recommendation">{html.escape(recommendation)}</p>
    </article>"""


if __name__ == "__main__":
    main()
