from __future__ import annotations

import argparse
import html
import json
from pathlib import Path
from typing import Any

import pandas as pd


DEFAULT_INPUT = "output/seo_report_scored.csv"
DEFAULT_OUTPUT = "output/seo_report.html"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Render the SEO CSV report as a responsive HTML dashboard.")
    parser.add_argument("--input", default=DEFAULT_INPUT, help=f"CSV report input path. Default: {DEFAULT_INPUT}")
    parser.add_argument("--output", default=DEFAULT_OUTPUT, help=f"HTML output path. Default: {DEFAULT_OUTPUT}")
    return parser


def render_report(input_path: str, output_path: str) -> Path:
    dataframe = pd.read_csv(input_path).fillna("")
    html_output = build_report_html(dataframe)

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_output, encoding="utf-8")
    return path


def build_report_html(dataframe: pd.DataFrame) -> str:
    rows = normalize_rows(dataframe.to_dict("records"))
    summary = summarize(rows)
    issue_cards = build_issue_cards(summary)
    grade_data = json.dumps(summary["grade_counts"], ensure_ascii=False)
    top_pages = sorted(
        rows,
        key=lambda row: (
            _number(row.get("seo_score"), 0),
            -_number(row.get("images_missing_alt"), 0),
        ),
    )[:8]

    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>SEO Report Dashboard</title>
  <style>
    :root {{
      --background: #f4f6f5;
      --surface: #ffffff;
      --surface-muted: #e5ebe7;
      --text: #201f1c;
      --muted: #68716b;
      --border: #d8ded9;
      --accent: #276c65;
      --accent-strong: #184d48;
      --warning: #b46a1b;
      --danger: #b83f3b;
      --good: #407a38;
      --shadow: 0 18px 45px rgba(43, 38, 30, 0.11);
      --radius: 8px;
    }}

    * {{
      box-sizing: border-box;
    }}

    body {{
      margin: 0;
      color: var(--text);
      background: var(--background);
      font-family: "Inter", "Noto Sans TC", "Microsoft JhengHei", system-ui, -apple-system, sans-serif;
      line-height: 1.5;
    }}

    .shell {{
      width: min(1180px, calc(100% - 32px));
      margin: 0 auto;
    }}

    .hero {{
      padding: 36px 0 24px;
      border-bottom: 1px solid var(--border);
      background: linear-gradient(180deg, #ffffff 0%, #f4f6f5 100%);
    }}

    .hero-grid {{
      display: grid;
      grid-template-columns: minmax(0, 1fr) 280px;
      gap: 28px;
      align-items: end;
    }}

    .eyebrow {{
      margin: 0 0 10px;
      color: var(--accent);
      font-size: 0.78rem;
      font-weight: 800;
      letter-spacing: 0;
      text-transform: uppercase;
    }}

    h1 {{
      max-width: 780px;
      margin: 0;
      font-size: clamp(2rem, 4vw, 4.1rem);
      line-height: 1;
      letter-spacing: 0;
    }}

    .subtitle {{
      max-width: 720px;
      margin: 16px 0 0;
      color: var(--muted);
      font-size: 1rem;
    }}

    .score-panel {{
      padding: 22px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--surface);
      box-shadow: var(--shadow);
    }}

    .score-value {{
      display: flex;
      align-items: baseline;
      gap: 8px;
      color: var(--accent-strong);
    }}

    .score-value strong {{
      font-size: 4rem;
      line-height: 0.9;
    }}

    .score-value span {{
      color: var(--muted);
      font-weight: 700;
    }}

    main {{
      padding: 28px 0 44px;
    }}

    .metric-grid {{
      display: grid;
      grid-template-columns: repeat(4, minmax(0, 1fr));
      gap: 12px;
      margin-bottom: 24px;
    }}

    .metric {{
      min-height: 112px;
      padding: 18px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--surface);
    }}

    .metric span {{
      display: block;
      color: var(--muted);
      font-size: 0.82rem;
      font-weight: 700;
    }}

    .metric strong {{
      display: block;
      margin-top: 10px;
      font-size: 2rem;
      line-height: 1;
    }}

    .content-grid {{
      display: grid;
      grid-template-columns: 1.1fr 0.9fr;
      gap: 16px;
      align-items: start;
    }}

    .section {{
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: var(--surface);
      overflow: hidden;
    }}

    .section-header {{
      display: flex;
      justify-content: space-between;
      gap: 16px;
      padding: 18px 20px;
      border-bottom: 1px solid var(--border);
    }}

    h2 {{
      margin: 0;
      font-size: 1.05rem;
      letter-spacing: 0;
    }}

    .hint {{
      color: var(--muted);
      font-size: 0.84rem;
    }}

    .issues {{
      display: grid;
      gap: 10px;
      padding: 16px;
    }}

    .issue {{
      display: grid;
      grid-template-columns: 42px 1fr auto;
      gap: 12px;
      align-items: center;
      min-height: 68px;
      padding: 12px;
      border: 1px solid var(--border);
      border-radius: var(--radius);
      background: #fbfcfb;
    }}

    .issue-badge {{
      display: grid;
      width: 42px;
      height: 42px;
      place-items: center;
      border-radius: 50%;
      color: #fff;
      background: var(--accent);
      font-weight: 800;
    }}

    .issue.danger .issue-badge {{
      background: var(--danger);
    }}

    .issue.warning .issue-badge {{
      background: var(--warning);
    }}

    .issue-title {{
      margin: 0;
      font-weight: 800;
    }}

    .issue-copy {{
      margin: 2px 0 0;
      color: var(--muted);
      font-size: 0.88rem;
    }}

    .issue-count {{
      color: var(--text);
      font-weight: 800;
      white-space: nowrap;
    }}

    .chart-wrap {{
      padding: 18px 20px 20px;
    }}

    .bars {{
      display: grid;
      gap: 12px;
    }}

    .bar-row {{
      display: grid;
      grid-template-columns: 34px 1fr 42px;
      gap: 10px;
      align-items: center;
      font-weight: 800;
    }}

    .track {{
      height: 12px;
      border-radius: 999px;
      background: var(--surface-muted);
      overflow: hidden;
    }}

    .fill {{
      height: 100%;
      min-width: 3px;
      border-radius: inherit;
      background: var(--accent);
    }}

    .fill.grade-a {{
      background: var(--good);
    }}

    .fill.grade-b {{
      background: var(--accent);
    }}

    .fill.grade-c {{
      background: var(--warning);
    }}

    .fill.grade-d {{
      background: var(--danger);
    }}

    .table-wrap {{
      overflow-x: auto;
    }}

    table {{
      width: 100%;
      border-collapse: collapse;
      min-width: 760px;
    }}

    th,
    td {{
      padding: 14px 16px;
      border-bottom: 1px solid var(--border);
      text-align: left;
      vertical-align: top;
    }}

    th {{
      color: var(--muted);
      font-size: 0.76rem;
      text-transform: uppercase;
      letter-spacing: 0;
    }}

    td {{
      font-size: 0.9rem;
    }}

    .url-cell {{
      max-width: 380px;
      color: var(--accent-strong);
      overflow-wrap: anywhere;
      font-weight: 700;
    }}

    .pill {{
      display: inline-flex;
      align-items: center;
      justify-content: center;
      min-width: 34px;
      min-height: 28px;
      padding: 4px 8px;
      border-radius: 999px;
      color: #fff;
      background: var(--accent);
      font-weight: 800;
    }}

    .pill.grade-a {{
      background: var(--good);
    }}

    .pill.grade-b {{
      background: var(--accent);
    }}

    .pill.grade-c {{
      background: var(--warning);
    }}

    .pill.grade-d {{
      background: var(--danger);
    }}

    .recommendation {{
      max-width: 360px;
      color: var(--muted);
    }}

    @media (max-width: 860px) {{
      .hero-grid,
      .content-grid {{
        grid-template-columns: 1fr;
      }}

      .score-panel {{
        max-width: none;
      }}

      .metric-grid {{
        grid-template-columns: repeat(2, minmax(0, 1fr));
      }}
    }}

    @media (max-width: 560px) {{
      .shell {{
        width: min(100% - 24px, 1180px);
      }}

      .hero {{
        padding-top: 26px;
      }}

      h1 {{
        font-size: 2.35rem;
      }}

      .metric-grid {{
        grid-template-columns: 1fr;
      }}

      .section-header,
      .issue {{
        grid-template-columns: 1fr;
      }}

      .section-header {{
        display: block;
      }}

      .hint {{
        display: block;
        margin-top: 4px;
      }}

      .issue {{
        gap: 8px;
      }}

      .issue-count {{
        white-space: normal;
      }}
    }}
  </style>
</head>
<body>
  <header class="hero">
    <div class="shell hero-grid">
      <div>
        <p class="eyebrow">Mandarin Florist SEO crawler</p>
        <h1>SEO report dashboard</h1>
        <p class="subtitle">A compact view of crawl health, score distribution, and the pages that need the most attention.</p>
      </div>
      <aside class="score-panel" aria-label="Average SEO score">
        <div class="score-value"><strong>{summary["average_score"]}</strong><span>/ 100</span></div>
        <p class="subtitle">Average across {summary["total_pages"]} crawled pages.</p>
      </aside>
    </div>
  </header>

  <main class="shell">
    <section class="metric-grid" aria-label="SEO summary metrics">
      <article class="metric"><span>Total pages</span><strong>{summary["total_pages"]}</strong></article>
      <article class="metric"><span>Healthy status</span><strong>{summary["ok_pages"]}</strong></article>
      <article class="metric"><span>Missing meta</span><strong>{summary["missing_meta"]}</strong></article>
      <article class="metric"><span>Missing alt text</span><strong>{summary["missing_alt"]}</strong></article>
    </section>

    <section class="content-grid">
      <div class="section">
        <div class="section-header">
          <h2>Priority issues</h2>
          <span class="hint">Sorted by likely impact</span>
        </div>
        <div class="issues">
          {issue_cards}
        </div>
      </div>

      <div class="section">
        <div class="section-header">
          <h2>Grade distribution</h2>
          <span class="hint">A to D score bands</span>
        </div>
        <div class="chart-wrap">
          {build_grade_bars(summary["grade_counts"], summary["total_pages"])}
        </div>
      </div>
    </section>

    <section class="section" style="margin-top: 16px;">
      <div class="section-header">
        <h2>Pages to fix first</h2>
        <span class="hint">Lowest scores from the crawl</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Page</th>
              <th>Score</th>
              <th>Grade</th>
              <th>Status</th>
              <th>Recommendation</th>
            </tr>
          </thead>
          <tbody>
            {build_rows(top_pages)}
          </tbody>
        </table>
      </div>
    </section>
  </main>
  <script type="application/json" id="grade-data">{grade_data}</script>
</body>
</html>
"""


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    total_pages = len(rows)
    score_values = [_number(row.get("seo_score"), None) for row in rows]
    score_values = [score for score in score_values if score is not None]
    status_values = [_number(row.get("status_code"), None) for row in rows]

    grade_counts = {"A": 0, "B": 0, "C": 0, "D": 0}
    for row in rows:
        grade = str(row.get("seo_grade") or "").strip().upper()
        if grade in grade_counts:
            grade_counts[grade] += 1

    return {
        "total_pages": total_pages,
        "average_score": round(sum(score_values) / len(score_values), 1) if score_values else 0,
        "ok_pages": sum(1 for status in status_values if status == 200),
        "missing_meta": sum(1 for row in rows if _number(row.get("meta_description_length"), 0) == 0),
        "missing_h1": sum(1 for row in rows if _number(row.get("h1_count"), 0) == 0),
        "missing_canonical": sum(1 for row in rows if not str(row.get("canonical") or "").strip()),
        "missing_alt": int(sum(_number(row.get("images_missing_alt"), 0) for row in rows)),
        "broken_pages": sum(1 for status in status_values if status and status >= 400),
        "grade_counts": grade_counts,
    }


def normalize_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [normalize_row(row) for row in rows]


def normalize_row(row: dict[str, Any]) -> dict[str, Any]:
    normalized = dict(row)
    if _number(normalized.get("seo_score"), None) is None:
        score = estimate_score(normalized)
        normalized["seo_score"] = score
        normalized["seo_grade"] = grade_for_score(score)
    elif not str(normalized.get("seo_grade") or "").strip():
        normalized["seo_grade"] = grade_for_score(_number(normalized.get("seo_score"), 0) or 0)

    if not str(normalized.get("recommendations") or "").strip():
        normalized["recommendations"] = build_recommendation(normalized)

    return normalized


def estimate_score(row: dict[str, Any]) -> int:
    score = 0
    status_code = _number(row.get("status_code"), 0) or 0
    title_length = _number(row.get("title_length"), 0) or 0
    description_length = _number(row.get("meta_description_length"), 0) or 0
    h1_count = _number(row.get("h1_count"), 0) or 0
    missing_alt_ratio = _number(row.get("images_missing_alt_ratio"), 0) or 0
    internal_links = _number(row.get("internal_links_count"), 0) or 0

    score += 20 if status_code == 200 else 0
    score += 15 if 10 <= title_length <= 35 else 10 if title_length else 0
    score += 15 if 40 <= description_length <= 160 else 5 if description_length else 0
    score += 15 if h1_count == 1 else 5 if h1_count > 1 else 0
    score += 10 if str(row.get("canonical") or "").strip() else 0
    score += 10 if missing_alt_ratio == 0 else 8 if missing_alt_ratio <= 0.1 else 5 if missing_alt_ratio <= 0.3 else 2
    score += 10 if internal_links > 0 else 0
    score += 5 if not str(row.get("error") or "").strip() else 0
    return score


def grade_for_score(score: float) -> str:
    if score >= 85:
        return "A"
    if score >= 70:
        return "B"
    if score >= 50:
        return "C"
    return "D"


def build_recommendation(row: dict[str, Any]) -> str:
    recommendations = []
    if (_number(row.get("status_code"), 0) or 0) != 200:
        recommendations.append("Fix the HTTP status")
    if _number(row.get("meta_description_length"), 0) == 0:
        recommendations.append("add a meta description")
    if _number(row.get("h1_count"), 0) != 1:
        recommendations.append("review H1 structure")
    if not str(row.get("canonical") or "").strip():
        recommendations.append("add a canonical URL")
    if _number(row.get("images_missing_alt"), 0) > 0:
        recommendations.append("fill missing image alt text")
    return ", ".join(recommendations).capitalize() + "." if recommendations else clean_recommendation("")


def build_issue_cards(summary: dict[str, Any]) -> str:
    issues = [
        ("broken_pages", "HTTP errors", "Resolve 4xx/5xx URLs so important pages can be indexed.", "danger"),
        ("missing_meta", "Missing meta descriptions", "Add clear search snippets for pages without descriptions.", "warning"),
        ("missing_h1", "Missing H1", "Give each page one primary heading that matches the page intent.", "warning"),
        ("missing_canonical", "Missing canonical", "Declare canonical URLs to reduce duplicate-content ambiguity.", ""),
        ("missing_alt", "Image alt gaps", "Add descriptive alt text to important product and content images.", ""),
    ]

    cards = []
    for key, title, copy, tone in issues:
        count = summary[key]
        cards.append(
            f"""<article class="issue {tone}">
              <div class="issue-badge">{html.escape(str(count))}</div>
              <div>
                <p class="issue-title">{html.escape(title)}</p>
                <p class="issue-copy">{html.escape(copy)}</p>
              </div>
              <div class="issue-count">{html.escape(str(count))} found</div>
            </article>"""
        )
    return "\n".join(cards)


def build_grade_bars(grade_counts: dict[str, int], total_pages: int) -> str:
    rows = []
    for grade in ["A", "B", "C", "D"]:
        count = grade_counts.get(grade, 0)
        width = round((count / total_pages) * 100, 1) if total_pages else 0
        rows.append(
            f"""<div class="bar-row">
              <span>{grade}</span>
              <div class="track"><div class="fill grade-{grade.lower()}" style="width: {width}%;"></div></div>
              <span>{count}</span>
            </div>"""
        )
    return f"""<div class="bars">{"".join(rows)}</div>"""


def build_rows(rows: list[dict[str, Any]]) -> str:
    table_rows = []
    for row in rows:
        grade = html.escape(str(row.get("seo_grade") or ""))
        status = html.escape(str(row.get("status_code") or ""))
        recommendation = html.escape(clean_recommendation(str(row.get("recommendations") or "")))
        table_rows.append(
            f"""<tr>
              <td class="url-cell">{html.escape(str(row.get("url") or ""))}</td>
              <td><strong>{html.escape(str(row.get("seo_score") or ""))}</strong></td>
              <td><span class="pill grade-{grade.lower()}">{grade}</span></td>
              <td>{status}</td>
              <td class="recommendation">{recommendation}</td>
            </tr>"""
        )
    return "\n".join(table_rows)


def clean_recommendation(value: str) -> str:
    value = " ".join(value.split())
    return value if value else "Review title, description, headings, canonical, and media metadata."


def _number(value: Any, default: float | None = 0) -> float | None:
    if value == "":
        return default
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def main() -> None:
    args = build_parser().parse_args()
    output_path = render_report(args.input, args.output)
    print(f"SEO dashboard saved to: {output_path}")


if __name__ == "__main__":
    main()
