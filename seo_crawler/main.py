from __future__ import annotations

import argparse

from .crawler import SEOCrawler
from .exporter import export_csv
from .ui import render_report


DEFAULT_URL = "https://www.mandarinflorist.com.tw/"
DEFAULT_OUTPUT = "output/seo_report.csv"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Crawl a website and export a basic SEO CSV report.")
    parser.add_argument("--url", default=DEFAULT_URL, help=f"Start URL. Default: {DEFAULT_URL}")
    parser.add_argument("--max-pages", type=int, default=100, help="Maximum number of pages to crawl.")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"CSV output path. Default: {DEFAULT_OUTPUT}")
    parser.add_argument("--html-output", default="", help="Optional HTML dashboard output path.")
    parser.add_argument("--timeout", type=int, default=15, help="Request timeout in seconds.")
    parser.add_argument("--delay", type=float, default=0.2, help="Delay between requests in seconds.")
    return parser


def main() -> None:
    args = build_parser().parse_args()

    crawler = SEOCrawler(
        start_url=args.url,
        max_pages=args.max_pages,
        timeout=args.timeout,
        delay_seconds=args.delay,
    )
    rows = crawler.crawl()
    output_path = export_csv(rows, args.output)

    print(f"Crawled {len(rows)} page(s).")
    print(f"SEO report saved to: {output_path}")

    if args.html_output:
        html_output_path = render_report(str(output_path), args.html_output)
        print(f"SEO dashboard saved to: {html_output_path}")


if __name__ == "__main__":
    main()
