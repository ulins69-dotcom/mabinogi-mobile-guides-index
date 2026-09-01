# -*- coding: utf-8 -*-
"""
巴哈姆特 瑪奇 Mobile 哈啦板爬蟲（bsn=32564）。

【Phase 0 已知事項】
- 列表頁：https://forum.gamer.com.tw/B.php?bsn=32564
- 內文頁：https://forum.gamer.com.tw/C.php?bsn=32564&snA={snA}
- snA 為天然唯一鍵 → id = "bahamut-{snA}"
- 站方有反爬蟲：必帶 User-Agent、放慢頻率、遵守 robots.txt。
- 條款考量：僅存標題/連結/摘要與公開互動數，不轉載內文全文。

【重要】gamer.com.tw 版面 class 名稱可能隨改版變動。
本檔用「多重選擇器 + 保底」策略；首次正式執行時，
請先人工抓一頁 HTML 核對選擇器（見 README 的 Phase 2 上線檢查表）。

【內文摘要】原本只抓列表頁標題，summary 永遠是空字串，導致職業分類
（scraper/classify.py）只能靠標題判斷，很多不把職業寫進標題的深度攻略
會被漏分類。2026-09 起改為每篇額外進一篇內文頁（C.php），
用 `.c-article__content`（實測 2026-09-01 確認，server-rendered，
requests 抓得到不用跑 JS）擷取前 SUMMARY_MAX_CHARS 字當摘要——
只取片段，不存全文，符合鐵律「僅存標題/連結/摘要」的條款考量。
代價是請求量翻倍（列表+內文各一次），一樣遵守 REQUEST_DELAY_SEC 禮貌爬取。
"""

from __future__ import annotations
import time
import re
import requests
from bs4 import BeautifulSoup

BSN = 32564
LIST_URL = f"https://forum.gamer.com.tw/B.php?bsn={BSN}"
BASE = "https://forum.gamer.com.tw/"

HEADERS = {
    # 帶正常瀏覽器 UA，降低被 403 機率；請勿偽造來源做惡意用途。
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"
    ),
    "Accept-Language": "zh-TW,zh;q=0.9",
}

REQUEST_DELAY_SEC = 3  # 每次請求間隔，禮貌爬取
SUMMARY_MAX_CHARS = 150  # 內文摘要最長字數，只取片段不存全文


def _get(url: str) -> str | None:
    try:
        resp = requests.get(url, headers=HEADERS, timeout=15)
        resp.raise_for_status()
        # gamer.com.tw 全站固定 UTF-8。原本用 resp.apparent_encoding（chardet
        # 猜編碼）偶爾會把 UTF-8 的中文誤判成西里爾字母系編碼，抓出一整篇亂碼
        # 標題（實測抓到過，見 2026-09-02 除錯記錄）。直接寫死不用猜。
        resp.encoding = "utf-8"
        return resp.text
    except requests.RequestException as e:
        print(f"[巴哈] 取得失敗 {url}: {e}")
        return None


def _first(el, selectors):
    """依序嘗試多個 CSS 選擇器，回傳第一個命中的元素。"""
    for sel in selectors:
        found = el.select_one(sel)
        if found:
            return found
    return None


def _parse_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []

    # 多重選擇器：涵蓋常見的 gamer 列表列結構
    rows = soup.select("tr.b-list__row") or soup.select(".b-list__row") or soup.select("table.b-list tr")

    for row in rows:
        link = _first(row, [
            "a.b-list__main__title",
            ".b-list__main a",
            "a[href*='C.php']",
        ])
        if not link or not link.get("href"):
            continue

        href = link["href"]
        m = re.search(r"snA=(\d+)", href)
        if not m:
            continue
        sn = m.group(1)

        title = link.get_text(strip=True)

        # 分類前綴標籤，如【攻略】【情報】
        raw_tag = ""
        tag_m = re.match(r"[\[【]([^\]】]+)[\]】]", title)
        if tag_m:
            raw_tag = tag_m.group(1)
            title = re.sub(r"^[\[【][^\]】]+[\]】]\s*", "", title)

        author_el = _first(row, [".b-list__count__user", ".username", "a[href*='homeindex']"])
        author = author_el.get_text(strip=True) if author_el else ""

        # 互動數（GP / 回覆）盡量抓，抓不到給 0
        gp_el = _first(row, [".b-list__summary__gp", ".gp"])
        reply_el = _first(row, [".b-list__count__number", ".b-list__count"])
        views = _to_int(gp_el.get_text() if gp_el else "0")
        replies = _to_int(reply_el.get_text() if reply_el else "0")

        date_el = _first(row, [".b-list__time__edittime", ".edittime", "time"])
        published_at = _normalize_date(date_el.get_text(strip=True) if date_el else "")

        items.append({
            "id": f"bahamut-{sn}",
            "title": title,
            "raw_tag": raw_tag,
            "author": author,
            "url": f"https://forum.gamer.com.tw/C.php?bsn={BSN}&snA={sn}",
            "summary": "",
            "source": "bahamut",
            "region": "tw",
            "published_at": published_at,
            "views": views,
            "replies": replies,
            "thumbnail": "",
        })
    return items


def _to_int(s: str) -> int:
    s = re.sub(r"[^\d]", "", str(s))
    return int(s) if s else 0


def _normalize_date(s: str) -> str:
    # 巴哈常見格式 2026-08-05 或 08/05；統一成 YYYY-MM-DD，失敗留空
    m = re.search(r"(\d{4})[-/](\d{1,2})[-/](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def _fetch_summary(url: str) -> str:
    """進文章內頁抓一小段內文當摘要。抓不到就回傳空字串，不拖垮整批。"""
    html = _get(url)
    if not html:
        return ""
    soup = BeautifulSoup(html, "html.parser")
    el = _first(soup, [".c-article__content", ".c-post__body"])
    if not el:
        return ""
    text = el.get_text(separator=" ", strip=True)
    text = re.sub(r"\s+", " ", text)
    if len(text) > SUMMARY_MAX_CHARS:
        text = text[:SUMMARY_MAX_CHARS] + "…"
    return text


def fetch(pages: int = 1) -> list[dict]:
    """抓取列表前 pages 頁的貼文，並各自進內文頁補摘要。回傳未分類的原始 item 清單。"""
    all_items = []
    for p in range(1, pages + 1):
        url = LIST_URL if p == 1 else f"{LIST_URL}&page={p}"
        print(f"[巴哈] 讀取列表 第 {p} 頁：{url}")
        html = _get(url)
        if not html:
            continue
        all_items.extend(_parse_list(html))
        time.sleep(REQUEST_DELAY_SEC)

    print(f"[巴哈] 共取得 {len(all_items)} 筆，開始逐篇補摘要...")
    for i, item in enumerate(all_items, 1):
        item["summary"] = _fetch_summary(item["url"])
        time.sleep(REQUEST_DELAY_SEC)
        if i % 10 == 0:
            print(f"[巴哈] 摘要進度 {i}/{len(all_items)}")

    return all_items
