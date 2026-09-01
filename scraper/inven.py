# -*- coding: utf-8 -*-
"""
韓國 인벤(Inven) 瑪奇 Mobile 攻略爬蟲。
站點：https://mabimo.inven.co.kr/  （韓國最大遊戲站的瑪奇手機版專區）

region = "kr"，source = "inven"。抓到的是韓文，交給 ai_enrich 翻成中文。

【首次上線需驗證】Inven 版面 class 名稱可能與此不同。第一次跑若抓到 0 筆，
請人工開一次列表頁核對選擇器（見 README 上線檢查表），調整 _parse() 內選擇器即可。
禮貌爬取：每次請求間隔數秒；僅存標題/連結/日期，不轉載全文。
"""

from __future__ import annotations
import re
import time
import requests
from bs4 import BeautifulSoup

# Inven 瑪奇 Mobile 的攻略/情報列表（webzine 新聞列表較穩定、公開可讀）
LIST_URLS = [
    "https://mabimo.inven.co.kr/webzine/news/",       # 新聞/情報
    "https://mabimo.inven.co.kr/webzine/news/?category=tip",  # 攻略類（若分類存在）
]
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9",
}
REQUEST_DELAY_SEC = 3


def _get(url: str) -> str | None:
    try:
        r = requests.get(url, headers=HEADERS, timeout=15)
        r.raise_for_status()
        r.encoding = r.apparent_encoding or "utf-8"
        return r.text
    except requests.RequestException as e:
        print(f"[Inven] 取得失敗 {url}: {e}")
        return None


def _first(el, selectors):
    for s in selectors:
        f = el.select_one(s)
        if f:
            return f
    return None


def _to_int(s: str) -> int:
    s = re.sub(r"[^\d]", "", str(s))
    return int(s) if s else 0


def _norm_date(s: str) -> str:
    m = re.search(r"(\d{4})[-.\/](\d{1,2})[-.\/](\d{1,2})", s)
    if m:
        return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}"
    return ""


def _parse(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    rows = (soup.select("table.webzineList tbody tr") or soup.select(".article-list li")
            or soup.select("tr") )
    for row in rows:
        link = _first(row, ["a.subject-link", "td.tit a", "a[href*='idx=']", "a[href*='inven.co.kr']"])
        if not link or not link.get("href"):
            continue
        href = link["href"]
        if href.startswith("//"):
            href = "https:" + href
        elif href.startswith("/"):
            href = "https://mabimo.inven.co.kr" + href
        m = re.search(r"idx=(\d+)", href) or re.search(r"/(\d+)(?:\?|$)", href)
        if not m:
            continue
        aid = m.group(1)
        title = link.get_text(strip=True)
        if not title or len(title) < 4:
            continue
        date_el = _first(row, ["td.date", ".date", "span.time", "time"])
        views_el = _first(row, ["td.view", ".view", ".hit"])
        items.append({
            "id": f"inven-{aid}",
            "title": title,
            "raw_tag": "",
            "author": "인벤",
            "url": href,
            "summary": "",
            "source": "inven",
            "region": "kr",
            "published_at": _norm_date(date_el.get_text(strip=True) if date_el else ""),
            "views": _to_int(views_el.get_text() if views_el else "0"),
            "replies": 0,
            "thumbnail": "",
        })
    return items


def fetch() -> list[dict]:
    all_items, seen = [], set()
    for url in LIST_URLS:
        print(f"[Inven] 讀取：{url}")
        html = _get(url)
        if html:
            for it in _parse(html):
                if it["id"] not in seen:
                    seen.add(it["id"])
                    all_items.append(it)
        time.sleep(REQUEST_DELAY_SEC)
    print(f"[Inven] 共取得 {len(all_items)} 筆")
    return all_items
