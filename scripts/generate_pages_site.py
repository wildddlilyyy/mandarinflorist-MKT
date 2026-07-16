from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pandas as pd


DOCS = Path("docs")
REPORT_DATE = date.today().isoformat()
SITE_URL = "https://www.mandarinflorist.com.tw/"
REPORT_LABEL = "文華花苑 SEO 分析報告"
REPORTS_INDEX = DOCS / "reports.json"
REPORTS_DIR = DOCS / "reports"
REPORT_DIR = REPORTS_DIR / REPORT_DATE
SCORED_CSV = Path("output/seo_report_scored.csv")
AI_AUDIT_CSV = Path("output/ai_audit.csv")
RECOMMENDATION_SEPARATOR = "；"


def main() -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(SCORED_CSV).fillna("")
    prepare_dataframe(df)

    records = [record_from_row(row) for _, row in df.iterrows()]
    chunk_paths = write_page_chunks(records)
    summary = build_summary(df, chunk_paths)

    (REPORT_DIR / "summary.json").write_text(
        json.dumps(summary, ensure_ascii=False, separators=(",", ":")),
        encoding="utf-8",
    )
    update_reports_index(summary)

    print(DOCS / "index.html")
    print(REPORTS_INDEX)
    print(REPORT_DIR / "summary.json")
    print(f"chunks={len(chunk_paths)} rows={len(records)} ai_audit={bool(summary.get('aiAudit'))}")


def prepare_dataframe(df: pd.DataFrame) -> None:
    text_cols = [
        "url",
        "title",
        "meta_description",
        "h1_text",
        "canonical",
        "error",
        "seo_grade",
        "fix_priority",
        "recommendations",
    ]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    numeric_cols = [
        "status_code",
        "title_length",
        "meta_description_length",
        "h1_count",
        "image_count",
        "images_missing_alt",
        "images_missing_alt_ratio",
        "internal_links_count",
        "external_links_count",
        "seo_score",
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)


def record_from_row(row: pd.Series) -> dict[str, object]:
    return {
        "url": row["url"],
        "status": int(row["status_code"]),
        "score": int(row["seo_score"]),
        "grade": row["seo_grade"],
        "priority": row["fix_priority"],
        "title": row["title"],
        "titleLength": int(row["title_length"]),
        "description": row["meta_description"],
        "descriptionLength": int(row["meta_description_length"]),
        "h1Count": int(row["h1_count"]),
        "h1Text": row["h1_text"],
        "canonical": row["canonical"],
        "imageCount": int(row["image_count"]),
        "missingAlt": int(row["images_missing_alt"]),
        "missingAltRatio": round(float(row["images_missing_alt_ratio"]), 4),
        "internalLinks": int(row["internal_links_count"]),
        "externalLinks": int(row["external_links_count"]),
        "recommendations": split_recommendations(row["recommendations"]),
        "error": row["error"],
    }


def split_recommendations(value: object) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    if RECOMMENDATION_SEPARATOR in text:
        return [item.strip() for item in text.split(RECOMMENDATION_SEPARATOR) if item.strip()]
    return [item.strip() for item in text.split("|") if item.strip()] or [text]


def write_page_chunks(records: list[dict[str, object]]) -> list[str]:
    chunk_paths = []
    for idx in range(0, len(records), 25):
        chunk = records[idx : idx + 25]
        path = REPORT_DIR / f"pages-{idx // 25 + 1:02d}.json"
        path.write_text(json.dumps(chunk, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
        chunk_paths.append(path.name)
    return chunk_paths


def build_summary(df: pd.DataFrame, chunk_paths: list[str]) -> dict[str, object]:
    summary = {
        "reportDate": REPORT_DATE,
        "site": SITE_URL,
        "title": REPORT_LABEL,
        "pageCount": int(len(df)),
        "averageScore": round(float(df["seo_score"].mean()), 1) if len(df) else 0,
        "grades": df["seo_grade"].value_counts().reindex(["A", "B", "C", "D"], fill_value=0).to_dict(),
        "status": df["status_code"].astype(int).value_counts().sort_index().to_dict(),
        "issues": build_issue_counts(df),
        "chunks": chunk_paths,
    }
    ai_audit = build_ai_audit_summary()
    if ai_audit:
        summary["aiAudit"] = ai_audit
    return summary


def build_issue_counts(df: pd.DataFrame) -> dict[str, int]:
    return {
        "非 200 狀態碼頁面": int((df["status_code"] != 200).sum()),
        "缺少 title": int(df["title"].eq("").sum()),
        "title 長度需調整": int(((df["title_length"] > 0) & ~df["title_length"].between(15, 35)).sum()),
        "缺少 meta description": int(df["meta_description"].eq("").sum()),
        "meta description 長度需調整": int(
            ((df["meta_description_length"] > 0) & ~df["meta_description_length"].between(50, 160)).sum()
        ),
        "缺少 H1": int((df["h1_count"] == 0).sum()),
        "多個 H1": int((df["h1_count"] > 1).sum()),
        "缺少 canonical": int(df["canonical"].eq("").sum()),
        "圖片缺少 alt 總數": int(df["images_missing_alt"].sum()),
        "爬取錯誤頁面": int(df["error"].astype(str).str.len().gt(0).sum()),
    }


def build_ai_audit_summary() -> dict[str, object]:
    if not AI_AUDIT_CSV.exists():
        return {}

    df = pd.read_csv(AI_AUDIT_CSV).fillna("")
    if df.empty:
        return {}

    row = df.iloc[0].to_dict()
    indicators = []
    for key, label in ai_indicator_labels().items():
        indicators.append(
            {
                "key": key,
                "label": label,
                "status": str(row.get(f"{key}_status", "")),
                "score": int(float(row.get(f"{key}_score", 0) or 0)),
                "evidence": str(row.get(f"{key}_evidence", "")),
                "recommendation": str(row.get(f"{key}_recommendation", "")),
            }
        )

    return {
        "siteUrl": str(row.get("site_url", "")),
        "checkedAt": str(row.get("checked_at", "")),
        "pagesChecked": int(float(row.get("pages_checked", 0) or 0)),
        "score": int(float(row.get("ai_score", 0) or 0)),
        "grade": str(row.get("ai_grade", "")),
        "indicators": indicators,
        "overallRecommendations": str(row.get("overall_recommendations", "")),
    }


def ai_indicator_labels() -> dict[str, str]:
    return {
        "https": "HTTPS",
        "meta_title": "Meta Title",
        "meta_description": "Meta Description",
        "html_semantics": "HTML 語意結構",
        "open_graph": "Open Graph",
        "rwd": "RWD",
        "schema": "Schema",
        "robots_txt": "robots.txt",
        "sitemap": "Sitemap",
        "llms_txt": "llms.txt",
    }


def update_reports_index(summary: dict[str, object]) -> None:
    report_entry = {
        "id": summary["reportDate"],
        "label": f"{summary['reportDate']} SEO 報告",
        "reportDate": summary["reportDate"],
        "site": summary["site"],
        "path": f"reports/{summary['reportDate']}/",
        "pageCount": summary["pageCount"],
        "averageScore": summary["averageScore"],
        "grades": summary["grades"],
        "status": summary["status"],
        "issues": summary["issues"],
        "aiAudit": summary.get("aiAudit", {}),
        "isLatest": True,
    }

    if REPORTS_INDEX.exists():
        reports = json.loads(REPORTS_INDEX.read_text(encoding="utf-8"))
    else:
        reports = []

    reports = [report for report in reports if report.get("id") != report_entry["id"]]
    reports.insert(0, report_entry)
    reports.sort(key=lambda report: report.get("reportDate", ""), reverse=True)

    for idx, report in enumerate(reports):
        report["isLatest"] = idx == 0

    REPORTS_INDEX.write_text(json.dumps(reports, ensure_ascii=False, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()
