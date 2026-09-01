# 瑪奇 Mobile 攻略索引網站

一個唯讀、靜態、能自動更新的攻略索引站。整合巴哈姆特與 YouTube 攻略，
資料由排程代理人每週自動更新。

> 本專案的最高準則見《專案工作流與鐵律》。任何修改前先讀它。

## 目錄結構

```
.
├── index.html                     # 前端（單檔，唯讀展示）
├── guides.json                    # 資料檔（由代理人產生，勿手改）
├── scraper/                       # 資料管線代理人
│   ├── main.py                    # 總指揮
│   ├── bahamut.py                 # 巴哈爬蟲
│   ├── youtube.py                 # YouTube API 抓取
│   ├── classify.py                # ★分類/打標/評精華（可抽換：日後換 LLM 只改這檔）
│   ├── schema.py                  # 資料合約守門員
│   ├── test_pipeline.py           # 管線邏輯測試
│   └── requirements.txt
└── .github/workflows/
    └── update-guides.yml          # 每週自動跑 + 手動觸發
```

## 快速開始（本機預覽）

因為前端用 `fetch("guides.json")`，直接雙擊開檔會被瀏覽器擋。請起一個本地伺服器：

```bash
cd 專案目錄
python3 -m http.server 8000
# 瀏覽器開 http://localhost:8000
```

## 部署（GitHub Pages，全免費）

1. 把整個專案推上 GitHub。
2. Settings → Pages → Source 選 `main` 分支根目錄，儲存。
3. 幾分鐘後網站上線於 `https://<帳號>.github.io/<repo>/`。

## 讓資料自動更新（GitHub Actions）

1. 到 Google Cloud Console 申請 **YouTube Data API v3** 金鑰。
2. GitHub repo → Settings → Secrets and variables → Actions → New secret
   - 名稱：`YOUTUBE_API_KEY`
   - 值：你的金鑰
3. 完成後，`.github/workflows/update-guides.yml` 會：
   - 每週一台灣時間早上 8 點自動跑
   - 也可在 Actions 頁面按「Run workflow」手動觸發
   - 產生新的 `guides.json` 並自動 commit、觸發 Pages 重新部署

### 配額鐵則（別踩雷）
- YouTube 免費配額每天 10,000 units。
- `search.list` 一次 **100 units**，`youtube.py` 只用 3 個關鍵字（=300 units）。
- `videos.list` 一次僅 **1 unit**，批次抓詳情。
- 每週跑一次遠低於配額。想加關鍵字，注意每個 +100 units。

## ⚠️ Phase 2 首次上線檢查表（重要）

巴哈姆特有反爬蟲，且版面 class 名稱可能隨改版變動。**第一次正式跑之前**：

1. 先手動確認能抓到列表頁（帶 User-Agent）：
   ```bash
   cd scraper
   python3 main.py --no-youtube --pages 1 --out /tmp/test.json
   cat /tmp/test.json
   ```
2. 若抓到 0 筆，代表 `bahamut.py` 的 CSS 選擇器需對照當前 HTML 調整
   （用瀏覽器「檢視原始碼」核對列表列的 class 名稱，改 `_parse_list()` 內的選擇器）。
3. 遵守禮貌爬取：`REQUEST_DELAY_SEC` 已設 3 秒，勿調太快。
4. 條款考量：本專案僅存標題、連結、摘要與公開互動數，不轉載內文全文。

## 執行測試

```bash
cd scraper
python3 test_pipeline.py
```

## 日後升級成 AI 分類（可選）

目前分類與評精華是「規則 + 關鍵字」（零成本）。要升級成 LLM 判斷時，
**只需重寫 `scraper/classify.py` 的三個函式**（`classify_category` / `extract_tags` / `mark_featured`），
其餘爬蟲、部署完全不動。這是刻意的模組化設計。
