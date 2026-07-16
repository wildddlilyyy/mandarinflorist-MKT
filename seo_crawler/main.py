from __future__ import annotations

import argparse
import re
from pathlib import Path

from .crawler import DEFAULT_USER_AGENT, SEOCrawler
from .exporter import export_csv
from .ui import render_report


DEFAULT_URL = "https://www.mandarinflorist.com.tw/"
DEFAULT_OUTPUT = "output/seo_report.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl a website and export a basic SEO CSV report.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Start URL. Default: {DEFAULT_URL}")
    parser.add_argument("--site-name", default="", help="Optional client/site name for output folder, such as client-a.")
    parser.add_argument("--max-pages", type=int, default=300, help="Maximum number of pages to crawl.")
    parser.add_argument("--output", default="", help=f"CSV output path. Default: {DEFAULT_OUTPUT}")
    parser.add_argument("--html-output", default="", help="Optional HTML dashboard output path.")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds.")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between requests in seconds.")
    parser.add_argument("--user-agent", default=DEFAULT_USER_AGENT, help=f"Request User-Agent. Default: {DEFAULT_USER_AGENT}")
    parser.add_argument("--use-sitemap", action="store_true", help="Seed the crawl queue from sitemap URLs when available.")
    parser.add_argument("--sitemap-timeout", type=int, default=5, help="Sitemap and robots.txt timeout in seconds.")
    parser.add_argument("--progress-every", type=int, default=10, help="Print progress every N crawled pages. Use 0 to disable.")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    crawler = SEOCrawler(
        start_url=args.url,
        max_pages=args.max_pages,
        timeout=args.timeout,
        delay_seconds=args.delay,
        user_agent=args.user_agent,
        use_sitemap=args.use_sitemap,
        sitemap_timeout=args.sitemap_timeout,
        progress_callback=build_progress_callback(args.progress_every),
    )
    rows = crawler.crawl()
    output_path = export_csv(rows, resolve_output_path(args.output, args.site_name))

    print(f"Crawled {len(rows)} page(s).")
    print(f"SEO report saved to: {output_path}")
    print_summary(rows)

    if args.html_output:
        html_output_path = render_report(str(output_path), args.html_output)
        print(f"SEO dashboard saved to: {html_output_path}")


def resolve_output_path(output: str, site_name: str) -> str:
    if output:
        return output
    if site_name:
        return str(Path("output") / slugify_site_name(site_name) / "seo_report.csv")
    return DEFAULT_OUTPUT


def slugify_site_name(site_name: str) -> str:
    slug = re.sub(r"[^\w.-]+", "-", site_name.strip()).strip("-._")
    return slug.lower() or "site"


def build_progress_callback(progress_every: int):
    if progress_every <= 0:
        return None

    def progress(event: dict[str, object]) -> None:
        crawled = int(event["crawled"])
        if crawled == 1 or crawled % progress_every == 0:
            print(
                f"[progress] {crawled}/{event['max_pages']} pages, "
                f"queued={event['queued']}, status={event['status_code']}, url={event['url']}"
            )

    return progress


def print_summary(rows: list[dict[str, object]]) -> None:
    if not rows:
        print("Summary: no pages crawled.")
        return

    status_counts: dict[object, int] = {}
    for row in rows:
        status_code = row.get("status_code") or "unknown"
        status_counts[status_code] = status_counts.get(status_code, 0) + 1

    missing_title = sum(1 for row in rows if not str(row.get("title") or "").strip())
    missing_description = sum(1 for row in rows if not str(row.get("meta_description") or "").strip())
    missing_h1 = sum(1 for row in rows if int(row.get("h1_count") or 0) == 0)
    missing_alt_total = sum(int(row.get("images_missing_alt") or 0) for row in rows)
    errors = sum(1 for row in rows if str(row.get("error") or "").strip())

    print("Summary:")
    print(f"- status codes: {format_status_counts(status_counts)}")
    print(f"- errors: {errors}")
    print(f"- missing title: {missing_title}")
    print(f"- missing meta description: {missing_description}")
    print(f"- missing H1: {missing_h1}")
    print(f"- missing image alt total: {missing_alt_total}")


def format_status_counts(status_counts: dict[object, int]) -> str:
    return ", ".join(
        f"{status}={count}" for status, count in sorted(status_counts.items(), key=lambda item: str(item[0]))
    )


if __name__ == "__main__":
    main()
