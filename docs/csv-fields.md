# SEO 爬蟲 CSV 欄位說明

這份 CSV 的目的，是讓業主可以逐頁檢查網站的基礎 SEO 狀態，並知道每個欄位如何協助後續分析與修正。

| 欄位 | 代表意義 | SEO 分析用途 |
| --- | --- | --- |
| `url` | 被爬取的頁面網址。 | 用來定位需要檢查或修正的頁面。 |
| `status_code` | HTTP 狀態碼，例如 200、301、404、500。 | 判斷頁面是否正常開啟，非 200 頁面通常需要優先處理。 |
| `title` | HTML `<title>` 內容。 | 影響搜尋結果標題，也是搜尋引擎理解頁面主題的重要訊號。 |
| `title_length` | title 字數。 | 判斷標題是否過短、過長或可能被搜尋結果截斷。 |
| `meta_description` | HTML `<meta name="description">` 內容。 | 通常會影響搜尋結果摘要與點擊意願。 |
| `meta_description_length` | meta description 字數。 | 判斷摘要是否過短、過長或需要重寫。 |
| `h1_count` | 頁面中的 H1 數量。 | 建議每頁有一個清楚 H1，過多 H1 可能讓主題分散。 |
| `h1_text` | 頁面中所有 H1 的文字。 | 用來檢查頁面主標題是否符合頁面內容與關鍵字方向。 |
| `canonical` | `<link rel="canonical">` 指向的主要網址。 | 避免重複內容分散 SEO 權重。 |
| `image_count` | 頁面圖片數量。 | 用來搭配 alt 缺漏狀態判斷圖片 SEO 完整度。 |
| `images_missing_alt` | 缺少 alt 或 alt 為空的圖片數。 | alt 有助於圖片 SEO 與無障礙體驗，缺漏越多越需要優先補強。 |
| `images_missing_alt_ratio` | 缺少 alt 的圖片比例。 | 比例越高，代表該頁圖片替代文字越不完整。 |
| `internal_links_count` | 該頁連到同網域頁面的連結數。 | 判斷頁面是否有足夠站內連結，避免形成孤立頁。 |
| `external_links_count` | 該頁連到外部網站的連結數。 | 協助盤點外部連結狀況。 |
| `error` | 爬取或解析時的錯誤訊息。 | 若有錯誤，需確認頁面是否可被搜尋引擎穩定讀取。 |
| `seo_score` | 基礎 SEO 分數，滿分 100。 | 快速判斷頁面的 SEO 健康度。 |
| `seo_grade` | A、B、C、D 等級。 | 方便業主快速分群檢視頁面狀態。 |
| `fix_priority` | 修正優先順序。 | 依問題嚴重度標示低、中、高、緊急。 |
| `recommendations` | 每頁建議修改方向。 | 提供後續實作修正時的具體參考。 |

## 建議分析順序

1. 先看 `status_code`，優先處理 404、500 或異常轉址。
2. 檢查 `title`、`meta_description` 是否缺漏或長度不適合。
3. 確認 `h1_count` 是否為 1，並檢查 `h1_text` 是否清楚。
4. 檢查 `canonical` 是否存在且指向正確主要頁面。
5. 依 `images_missing_alt_ratio` 補強圖片 alt。
6. 檢查 `internal_links_count`，找出站內連結不足的頁面。
7. 依 `seo_score`、`seo_grade`、`fix_priority` 排定修正順序。
