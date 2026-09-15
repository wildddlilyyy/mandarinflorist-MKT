# 文華花苑 SEO 分析報告

本 Repository 只保存 https://www.mandarinflorist.com.tw/ 的 SEO 爬蟲結果，首頁提供 Dashboard，並連結到頁面設計 demo 與 SEO report；本 repo 不包含爬蟲程式。

公開網址：

https://wildddlilyyy.github.io/mandarinflorist-MKT/

## 報告結構

- `docs/index.html`：Dashboard 首頁
- `docs/seo-report.html`：SEO 報告頁
- `docs/reports.json`：歷史報告索引
- `docs/reports/YYYY-MM-DD/`：各日期的 HTML、JSON 與頁面資料

## 更新報告

爬蟲程式位於獨立的 `C:\Users\User\Documents\SEO\seo-crawler` 專案。在爬蟲專案執行：

```powershell
python scripts/run_report.py --config config/mandarinflorist.json
```

產出結果會寫入本 repo 的 `docs/reports/YYYY-MM-DD/`。確認報告後，只需在本 repo Commit／Push 報告檔案。

GitHub Pages 請設定為 `main` branch 的 `/docs` 資料夾。
