# 文華花苑 SEO 分析報告

這是一個針對 `https://www.mandarinflorist.com.tw/` 建立的 Python SEO 爬蟲與視覺化報告專案。專案會爬取同網域頁面、輸出 CSV、產生 SEO 評分，並轉成可部署到 GitHub Pages 的報告網站。

預期 GitHub Pages 網址：

```text
https://wildddlilyyy.github.io/mandarinflorist-SEO-Report/
```

## 專案結構

- `seo_crawler/`：爬蟲、HTML 解析、CSV 輸出與簡易 dashboard。
- `scripts/score_seo_report.py`：根據爬蟲 CSV 加上 SEO 分數、等級、優先順序與建議。
- `scripts/generate_pages_site.py`：將評分後資料轉成 GitHub Pages 使用的 JSON 報告資料。
- `scripts/generate_full_report.py`：產出 Markdown / HTML 完整稽核報告。
- `docs/index.html`：業主瀏覽用的 SEO 報告中心。
- `docs/reports.json`：多期報告索引。
- `docs/reports/YYYY-MM-DD/`：每期報告資料。
- `output/`：本機爬蟲與評分輸出資料夾，不作為正式部署資料來源。

## 安裝

建議使用 Python 3.10 以上版本。

```powershell
python -m venv .venv
.\.venv\Scripts\python -m pip install -r requirements.txt
```

## 執行爬蟲

小量測試：

```powershell
.\.venv\Scripts\python -m seo_crawler.main --url https://www.mandarinflorist.com.tw/ --max-pages 10 --output output/seo_report_full.csv
```

正式報告：

```powershell
.\.venv\Scripts\python -m seo_crawler.main --url https://www.mandarinflorist.com.tw/ --max-pages 300 --output output/seo_report_full.csv
```

常用參數：

- `--url`：起始網址，預設為 `https://www.mandarinflorist.com.tw/`
- `--max-pages`：最多爬取頁數，正式報告建議 300。
- `--output`：CSV 輸出路徑。
- `--timeout`：單頁請求逾時秒數，預設 15。
- `--delay`：每次請求間隔秒數，預設 0.2。

## 產生評分 CSV

```powershell
.\.venv\Scripts\python scripts\score_seo_report.py
```

輸入：

```text
output/seo_report_full.csv
```

輸出：

```text
output/seo_report_scored.csv
```

## 產生 GitHub Pages 報告資料

```powershell
.\.venv\Scripts\python scripts\generate_pages_site.py
```

產出內容會寫入：

```text
docs/reports/YYYY-MM-DD/
docs/reports.json
```

網站首頁會自動讀取 `docs/reports.json`，預設顯示最新一期報告，也可透過日期選單切換歷史報告。

## 產出完整 HTML / Markdown 報告

```powershell
.\.venv\Scripts\python scripts\generate_full_report.py
```

輸出：

```text
output/seo_full_audit_report.md
output/seo_full_audit_report.html
```

## GitHub Pages 設定

在 GitHub repo 的 Settings > Pages 設定：

- Source：Deploy from a branch
- Branch：`main`
- Folder：`/docs`

## 爬取與分析提醒

- 第一版以靜態 HTML 為主，不處理 JavaScript 渲染後才出現的內容。
- CSV 使用 `utf-8-sig` 輸出，方便 Excel 開啟中文。
- 報告分數用於盤點優先順序，正式 SEO 策略仍需搭配關鍵字、流量、轉換與商業目標判讀。
