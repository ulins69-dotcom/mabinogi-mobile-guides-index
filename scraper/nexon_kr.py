# -*- coding: utf-8 -*-
"""
韓國 Nexon 官方《마비노기 모바일》公告/情報爬蟲。
官網：https://mabinogimobile.nexon.com/News/Notice

region = "kr"，source = "nexon"。這是「預測未來」價值最高的來源——
官方改版與活動公告，等於台服未來一年多會依序拿到的內容時間表。

【重要：首次上線需驗證】Nexon 官網多為 JavaScript 動態渲染，
純 requests 可能抓不到內容。本檔採兩段策略：
  1) 先試官網常見的 JSON 資料端點（多數 Nexon 站以 API 回傳清單）。
  2) 再退回解析 HTML。
若兩者都取到 0 筆，第一次上線時需用瀏覽器「開發者工具 → Network」找出真正的
公告 JSON 端點，把網址填進 API_ENDPOINTS。這一步我會在你部署後協助定位。
"""

from __future__ import annotations
import re
import time
import requests
from bs4 import BeautifulSoup

BASE = "https://mabinogimobile.nexon.com"
NOTICE_PAGE = f"{BASE}/News/Notice"
# 可能的 JSON 端點（首次上線核對後填入正確者）
API_ENDPOINTS = [
    f"{BASE}/api/news/notice?page=1",
    f"{BASE}/News/NoticeList?page=1",
]
HEADERS = {
    "User-Agent": ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
                   "(KHTML, like Gecko) Chrome/124.0 Safari/537.36"),
    "Accept-Language": "ko-KR,ko;q=0.9",
    "X-Requested-With": "XMLHttpRequest",
}
REQUEST_DELAY_SEC = 3


def _norm_date(s: str) -> str:
    m = re.search(r"(\d{4})[-.\/](\d{1,2})[-.\/](\d{1,2})", str(s))
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def _try_json() -> list[dict]:
    items = []
    for url in API_ENDPOINTS:
        try:
            r = requests.get(url, headers=HEADERS, timeout=15)
            if r.status_code != 200:
                continue
            data = r.json()
            rows = data if isinstance(data, list) else (data.get("list") or data.get("data") or [])
            for row in rows:
                if not isinstance(row, dict):
                    continue
                nid = str(row.get("id") or row.get("boardId") or row.get("seq") or "")
                title = row.get("title") or row.get("subject") or ""
                if not nid or not title:
                    continue
                items.append({
                    "id": f"nexon-{nid}",
                    "title": title, "raw_tag": "", "author": "Nexon 官方",
                    "url": f"{BASE}/News/NoticeView?id={nid}",
                    "summary": "", "source": "nexon", "region": "kr",
                    "published_at": _norm_date(row.get("date") or row.get("regDate") or ""),
                    "views": 0, "replies": 0, "thumbnail": "",
                })
            if items:
                print(f"[NexonKR] JSON 端點成功：{url}（{len(items)} 筆）")
                return items
        except (requests.RequestException, ValueError):
            continue
    return items


def _try_html() -> list[dict]:
    items = []
    try:
        r = requests.get(NOTICE_PAGE, headers=HEADERS, timeout=15)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "html.parser")
        for a in soup.select("a[href*='NoticeView'], a[href*='id=']"):
            href = a.get("href", "")
            m = re.search(r"id=(\d+)", href)
            title = a.get_text(strip=True)
            if not m or not title or len(title) < 4:
                continue
            url = href if href.startswith("http") else BASE + href
            items.append({
                "id": f"nexon-{m.group(1)}", "title": title, "raw_tag": "",
                "author": "Nexon 官方", "url": url, "summary": "",
                "source": "nexon", "region": "kr", "published_at": "",
                "views": 0, "replies": 0, "thumbnail": "",
            })
    except requests.RequestException as e:
        print(f"[NexonKR] HTML 取得失敗：{e}")
    return items


def fetch() -> list[dict]:
    items = _try_json()
    if not items:
        items = _try_html()
    # 去重
    seen, out = set(), []
    for it in items:
        if it["id"] not in seen:
            seen.add(it["id"]); out.append(it)
    if not out:
        print("[NexonKR] 取得 0 筆 —— 官網可能為動態渲染，需於首次上線定位 JSON 端點")
    else:
        print(f"[NexonKR] 共取得 {len(out)} 筆")
    time.sleep(REQUEST_DELAY_SEC)
    return out
