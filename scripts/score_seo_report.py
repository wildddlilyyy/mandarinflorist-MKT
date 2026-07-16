from __future__ import annotations

from pathlib import Path

import pandas as pd


INPUT_PATH = Path("output/seo_report_full.csv")
OUTPUT_PATH = Path("output/seo_report_scored.csv")
RECOMMENDATION_SEPARATOR = "；"


def main() -> None:
    df = pd.read_csv(INPUT_PATH)
    prepare_dataframe(df)

    score_rows = [score_row(row) for _, row in df.iterrows()]
    output = pd.concat([df, pd.DataFrame(score_rows)], axis=1)
    output.to_csv(OUTPUT_PATH, index=False, encoding="utf-8-sig")

    print(OUTPUT_PATH)
    print(f"rows={len(output)} avg_score={output['seo_score'].mean():.1f}")


def prepare_dataframe(df: pd.DataFrame) -> None:
    text_cols = ["title", "meta_description", "h1_text", "canonical", "error"]
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
    ]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0)


def score_row(row: pd.Series) -> dict[str, object]:
    parts: dict[str, int] = {}
    recommendations: list[str] = []

    status_code = int(number(row["status_code"]))
    title_length = int(number(row["title_length"]))
    description_length = int(number(row["meta_description_length"]))
    h1_count = int(number(row["h1_count"]))
    image_count = int(number(row["image_count"]))
    images_missing_alt = int(number(row["images_missing_alt"]))
    internal_links_count = int(number(row["internal_links_count"]))

    if status_code == 200:
        parts["status_score"] = 20
    elif 300 <= status_code < 400:
        parts["status_score"] = 10
        recommendations.append("確認轉址是否為預期路徑，避免不必要的轉址消耗搜尋引擎爬取資源。")
    else:
        parts["status_score"] = 0
        recommendations.append("優先修正非 200 狀態碼頁面，避免錯誤頁被收錄或浪費爬取資源。")

    if title_length == 0:
        parts["title_score"] = 0
        recommendations.append("補上頁面 title，讓搜尋結果能清楚呈現頁面主題。")
    elif 15 <= title_length <= 35:
        parts["title_score"] = 15
    elif 10 <= title_length < 15 or 36 <= title_length <= 45:
        parts["title_score"] = 10
        recommendations.append("調整 title 長度，讓標題更完整且避免搜尋結果截斷。")
    else:
        parts["title_score"] = 5
        recommendations.append("重寫 title，避免過短、過長或主題不明確。")

    if description_length == 0:
        parts["description_score"] = 0
        recommendations.append("補上 meta description，提升搜尋結果摘要品質與點擊率。")
    elif 50 <= description_length <= 160:
        parts["description_score"] = 15
    elif 30 <= description_length < 50 or 161 <= description_length <= 200:
        parts["description_score"] = 10
        recommendations.append("優化 meta description 長度與內容，聚焦頁面賣點。")
    else:
        parts["description_score"] = 5
        recommendations.append("重寫 meta description，避免過短、過長或不具吸引力。")

    if h1_count == 1:
        parts["h1_score"] = 15
    elif h1_count == 0:
        parts["h1_score"] = 0
        recommendations.append("補上唯一且清楚的 H1，讓頁面主題更明確。")
    elif h1_count <= 3:
        parts["h1_score"] = 8
        recommendations.append("檢查多個 H1 是否造成主題分散，建議保留主要標題為 H1。")
    else:
        parts["h1_score"] = 5
        recommendations.append("整理頁面標題層級，避免過多 H1 稀釋頁面主題。")

    if str(row["canonical"]).strip():
        parts["canonical_score"] = 10
    else:
        parts["canonical_score"] = 0
        recommendations.append("補上 canonical，避免重複內容分散 SEO 權重。")

    if image_count == 0:
        parts["image_alt_score"] = 10
    else:
        ratio = images_missing_alt / image_count
        if ratio == 0:
            parts["image_alt_score"] = 10
        elif ratio <= 0.1:
            parts["image_alt_score"] = 8
            recommendations.append("補齊少數缺少 alt 的圖片，強化圖片 SEO 與無障礙體驗。")
        elif ratio <= 0.3:
            parts["image_alt_score"] = 5
            recommendations.append("優先補齊重點圖片 alt，讓搜尋引擎理解圖片內容。")
        else:
            parts["image_alt_score"] = 2
            recommendations.append("大量圖片缺少 alt，建議建立圖片替代文字規則並批次補強。")

    if internal_links_count >= 5:
        parts["internal_links_score"] = 10
    elif internal_links_count >= 1:
        parts["internal_links_score"] = 6
        recommendations.append("增加相關頁面的內部連結，提升內容關聯與爬取效率。")
    else:
        parts["internal_links_score"] = 0
        recommendations.append("補上內部連結，避免頁面成為孤立頁。")

    if str(row["error"]).strip():
        parts["error_score"] = 0
        recommendations.append("檢查爬取錯誤原因，確認頁面是否可被搜尋引擎正常讀取。")
    else:
        parts["error_score"] = 5

    total = sum(parts.values())
    if total >= 85:
        grade = "A"
        priority = "低"
    elif total >= 70:
        grade = "B"
        priority = "中"
    elif total >= 50:
        grade = "C"
        priority = "高"
    else:
        grade = "D"
        priority = "緊急"

    unique_recommendations = list(dict.fromkeys(recommendations))
    if not unique_recommendations:
        unique_recommendations = ["目前基礎 SEO 狀態良好，建議持續觀察排名、流量與轉換表現。"]

    return {
        **parts,
        "seo_score": total,
        "seo_grade": grade,
        "fix_priority": priority,
        "recommendations": RECOMMENDATION_SEPARATOR.join(unique_recommendations),
    }


def number(value: object) -> float:
    try:
        if pd.isna(value):
            return 0
        return float(value)
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    main()
