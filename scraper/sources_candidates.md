# 候選資料來源清單

這份記錄使用者提供的、尚未接進 `main.py` 管線的候選資料來源，供之後擴充爬蟲時參考。
**這些都還沒被任何爬蟲程式使用**——記錄下來只是備查，不代表已驗證可爬、也不代表符合鐵律第五節「僅存標題/連結/摘要」的條款考量，接入前都要照 README 的「首次上線檢查表」流程重新確認。

## 官方（可信）

| 名稱 | 網址 | 語言 | 備註 |
|---|---|---|---|
| 瑪奇 Mobile 台版官網 | https://tw.nexon.com/mabinogimobile/home/ | 繁體中文 | 已用於本次職業分類查證，詳見「職業介紹」子頁 |
| 瑪奇 Mobile 全球版官網 | https://mabinogimobile.nexon.com/ | 英文 | 內容進度與台版接近，**不是**韓服 |
| 瑪奇 Mobile 韓文攻略 wiki（namu.wiki） | https://namu.wiki/w/마비노기 모바일/클래스 | 韓文 | 非官方但資料詳實，含各職業上線日期，本次用來查證韓服領先職業 |

⚠️ 使用者原提供清單中的「Nexon 韓國官網 `mabinogi.nexon.com`」**經查證是 PC 版《瑪奇》（原版 MMORPG）的官網，不是《瑪奇 Mobile》**，職業名稱完全不同（艾雷門塔騎士、暗黑法師等），已剔除、不採用。真正的瑪奇 Mobile 韓文入口目前只找到 `mabinogimobile.nexon.com`，但該網域目前導向的是英文版內容，韓服專屬網址待後續查證。

## 巴哈姆特

| 名稱 | 網址 | 備註 |
|---|---|---|
| 瑪奇 Mobile 哈啦板 | https://forum.gamer.com.tw/B.php?bsn=32564 | **已接入** `scraper/bahamut.py`（bsn=32564） |
| 精華區 | （待查證正確路徑） | 使用者提供的 `B.php`/`C.php?bsn=XXXX` 是列表頁/內文頁樣式，不是精華區專屬路徑；巴哈精華區通常需另外的網址模式，待確認 |

## YouTube（候選頻道，尚未指定頻道 ID）

| 頻道 | 備註 |
|---|---|
| 阿翊頻道 | 新手六大職業選擇、每日任務、生活技能掛機 |
| CD喜德頻道 | 開服極限開荒、副本通關、職業配裝（`scraper/youtube.py` 目前用關鍵字搜尋，已有這個頻道的影片出現在爬到的資料裡） |
| Nia尼亞頻道 | 劍術士技能符文養成 |
| 阿貝手遊 MrBay | 符文配置、副本速通、資源囤積 |
| Nexon Taiwan 官方頻道 | https://www.youtube.com/@NexonTaiwan，官方宣傳/職業介紹/活動影片 |

目前 `youtube.py` 是用關鍵字搜尋（`search.list`），不是指定頻道抓取；若要改成鎖定上述頻道，需要先查出各頻道的 Channel ID，並評估 API 配額（`search.list` 加 `channelId` 參數不影響 100 units/次的成本）。
