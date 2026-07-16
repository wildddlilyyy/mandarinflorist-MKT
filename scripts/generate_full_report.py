from __future__ import annotations

import html
from datetime import date
from pathlib import Path

import pandas as pd


BASE = Path("output")
SCORED_CSV = BASE / "seo_report_scored.csv"
REPORT_MD = BASE / "seo_full_audit_report.md"
REPORT_HTML = BASE / "seo_full_audit_report.html"
REPORT_DATE = date.today().isoformat()
SITE_URL = "https://www.mandarinflorist.com.tw/"
REPORT_TITLE = "文華花苑 SEO 完整稽核報告"


def main() -> None:
    BASE.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(SCORED_CSV).fillna("")
    prepare_dataframe(df)

    avg_score = df["seo_score"].mean() if len(df) else 0
    grade_counts = df["seo_grade"].value_counts().reindex(["A", "B", "C", "D"], fill_value=0)
    status_counts = df["status_code"].astype(int).value_counts().sort_index()
    issue_counts = build_issue_counts(df)
    priority_pages = build_priority_pages(df)

    markdown = build_markdown_report(df, avg_score, grade_counts, status_counts, issue_counts, priority_pages)
    REPORT_MD.write_text(markdown, encoding="utf-8")
    REPORT_HTML.write_text(build_html_report(markdown), encoding="utf-8")

    print(REPORT_MD)
    print(REPORT_HTML)
    print(f"rows={len(df)} avg_score={avg_score:.1f}")
    print(f"A={grade_counts['A']} B={grade_counts['B']} C={grade_counts['C']} D={grade_counts['D']}")


def prepare_dataframe(df: pd.DataFrame) -> None:
    text_cols = ["url", "title", "meta_description", "h1_text", "canonical", "error", "recommendations", "seo_grade", "fix_priority"]
    for col in text_cols:
        if col in df.columns:
            df[col] = df[col].fillna("").astype(str)

    numeric_cols = ["status_code", "title_length", "meta_description_length", "h1_count", "image_count", "images_missing_alt", "images_missing_alt_ratio", "internal_links_count", "external_links_count", "seo_score"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)


def build_issue_counts(df: pd.DataFrame) -> dict[str, int]:
    return {
        "非 200 狀態碼頁面": int((df["status_code"] != 200).sum()),
        "缺少 title": int(df["title"].eq("").sum()),
        "title 長度需調整": int(((df["title_length"] > 0) & ~df["title_length"].between(15, 35)).sum()),
        "缺少 meta description": int(df["meta_description"].eq("").sum()),
        "meta description 長度需調整": int(((df["meta_description_length"] > 0) & ~df["meta_description_length"].between(50, 160)).sum()),
        "缺少 H1": int((df["h1_count"] == 0).sum()),
        "多個 H1": int((df["h1_count"] > 1).sum()),
        "缺少 canonical": int(df["canonical"].eq("").sum()),
        "圖片缺少 alt 總數": int(df["images_missing_alt"].sum()),
        "爬取錯誤頁面": int(df["error"].astype(str).str.len().gt(0).sum()),
    }


def build_priority_pages(df: pd.DataFrame) -> pd.DataFrame:
    priority_order = {"緊急": 0, "高": 1, "中": 2, "低": 3}
    sortable = df.copy()
    sortable["_priority_order"] = sortable["fix_priority"].map(priority_order).fillna(9)
    return sortable.sort_values(["_priority_order", "seo_score", "images_missing_alt"], ascending=[True, True, False]).head(20)


def build_markdown_report(
    df: pd.DataFrame,
    avg_score: float,
    grade_counts: pd.Series,
    status_counts: pd.Series,
    issue_counts: dict[str, int],
    priority_pages: pd.DataFrame,
) -> str:
    return f"""# {REPORT_TITLE}

分析網站：<{SITE_URL}>  
SEO 報告日期：{REPORT_DATE}  
分析頁數：{len(df)}  
資料來源：`{SCORED_CSV.as_posix()}`

## 1. 整體摘要

- 平均 SEO 分數：{avg_score:.1f} / 100
- A 級頁數：{grade_counts["A"]}
- B 級頁數：{grade_counts["B"]}
- C 級頁數：{grade_counts["C"]}
- D 級頁數：{grade_counts["D"]}

## 2. HTTP 狀態碼分布

{md_table(["狀態碼", "頁數"], [(int(k), int(v)) for k, v in status_counts.items()])}

## 3. 問題統計

{md_table(["問題項目", "數量"], issue_counts.items())}

## 4. 評分方式

{md_table(["評分項目", "權重", "判讀方式"], score_rows())}

## 5. 優先處理頁面 Top 20

{md_table(["URL", "分數", "等級", "優先順序", "建議修改方向"], priority_rows(priority_pages))}

## 6. 逐頁完整 SEO 爬蟲內容

{md_table(page_headers(), page_rows(df))}

## 7. 建議修改方向

1. 優先處理非 200 頁面，修正 404、伺服器錯誤或不必要的轉址。
2. 補齊缺少的 title 與 meta description，讓搜尋結果摘要更完整。
3. 確認每頁有清楚且唯一的 H1，並檢查 canonical 是否正確。
4. 為重要圖片補上具描述性的 alt 文字。
5. 增加內容相關頁面的內部連結。
6. 分數較低或優先順序為「緊急／高」的頁面，建議先列入第一波修正清單。
"""


def build_html_report(markdown: str) -> str:
    escaped = html.escape(markdown)
    return f"""<!doctype html>
<html lang="zh-Hant">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{html.escape(REPORT_TITLE)}</title>
<style>
body{{font-family:-apple-system,BlinkMacSystemFont,"Segoe UI","Noto Sans TC",Arial,sans-serif;margin:0;background:#f6f7f9;color:#172026}}
main{{max-width:1180px;margin:0 auto;padding:32px 24px 56px}}
pre{{white-space:pre-wrap;overflow-wrap:anywhere;background:#fff;border:1px solid #d9e2ec;border-radius:8px;padding:20px;line-height:1.65}}
</style>
</head>
<body><main><pre>{escaped}</pre></main></body>
</html>"""


def score_rows() -> list[tuple[str, str, str]]:
    return [
        ("HTTP 狀態碼", "20", "200 為滿分；轉址給部分分數；404、500 或請求失敗為 0。"),
        ("Title", "15", "檢查是否存在，以及長度是否足以表達主題且不易被截斷。"),
        ("Meta description", "15", "檢查是否存在，以及是否能作為搜尋結果摘要。"),
        ("H1", "15", "每頁建議有一個清楚 H1；缺少或過多都會扣分。"),
        ("Canonical", "10", "檢查是否設定主要網址，避免重複內容分散權重。"),
        ("圖片 alt", "10", "依缺少 alt 的圖片比例扣分。"),
        ("內部連結", "10", "檢查頁面是否有足夠站內連結。"),
        ("爬取錯誤", "5", "若爬取發生錯誤則扣分。"),
    ]


def priority_rows(priority_pages: pd.DataFrame) -> list[tuple[object, ...]]:
    return [
        (Link(row["url"]), int(row["seo_score"]), row["seo_grade"], row["fix_priority"], split_recommendations(row["recommendations"]))
        for _, row in priority_pages.iterrows()
    ]


def page_headers() -> list[str]:
    return ["#", "URL", "狀態碼", "分數", "等級", "優先順序", "Title", "Title 長度", "Meta Description", "Description 長度", "H1 數量", "H1 文字", "Canonical", "圖片數", "缺少 alt 圖片數", "缺少 alt 比例", "站內連結數", "外部連結數", "建議修改方向", "錯誤"]


def page_rows(df: pd.DataFrame) -> list[tuple[object, ...]]:
    rows = []
    for idx, row in df.iterrows():
        rows.append(
            (
                idx + 1,
                Link(row["url"]),
                int(row["status_code"]),
                int(row["seo_score"]),
                row["seo_grade"],
                row["fix_priority"],
                row["title"],
                int(row["title_length"]),
                row["meta_description"],
                int(row["meta_description_length"]),
                int(row["h1_count"]),
                row["h1_text"],
                Link(row["canonical"]) if row["canonical"] else "",
                int(row["image_count"]),
                int(row["images_missing_alt"]),
                row["images_missing_alt_ratio"],
                int(row["internal_links_count"]),
                int(row["external_links_count"]),
                split_recommendations(row["recommendations"]),
                row["error"],
            )
        )
    return rows


def split_recommendations(value: object) -> list[str]:
    text = str(value or "").strip()
    if not text:
        return []
    if "；" in text:
        return [part.strip() for part in text.split("；") if part.strip()]
    return [text]


def md_table(headers: list[str], rows) -> str:
    output = ["| " + " | ".join(headers) + " |", "| " + " | ".join(["---"] * len(headers)) + " |"]
    for row in rows:
        output.append("| " + " | ".join(md_cell(cell) for cell in row) + " |")
    return "\n".join(output)


def md_cell(value: object) -> str:
    if isinstance(value, Link):
        return f"[{value.text}]({value.href})"
    if isinstance(value, list):
        return "<br>".join(f"- {str(item).replace('|', '\\|')}" for item in value)
    return str(value).replace("|", "\\|").replace("\n", "<br>")


class Link:
    def __init__(self, href: str, text: str | None = None) -> None:
        self.href = href
        self.text = text or href


if __name__ == "__main__":
    main()
