# -*- coding: utf-8 -*-
"""
YouTube Data API v3 攻略影片抓取（台服中文 + 韓服韓文）。

【配額鐵則】每日免費 10,000 units。search.list=100/次（貴），videos.list=1/次（便宜）。
策略：少數關鍵字 search.list 拿 videoId → 合併去重 → 批次 videos.list 抓詳情。
台服 3 個關鍵字 + 韓服 2 個 = 5 次搜尋 = 500 units，遠在免費額度內。

金鑰放環境變數 YOUTUBE_API_KEY。
"""

from __future__ import annotations
import os
import requests

API_BASE = "https://www.googleapis.com/youtube/v3"

# 依地區分組：region 會標在每筆資料上，韓文影片交給 ai_enrich 翻譯
QUERIES = {
    "tw": (["瑪奇 Mobile 攻略", "瑪奇 Mobile 新手", "瑪奇 Mobile 活動"], "zh-Hant"),
    "kr": (["마비노기 모바일 공략", "마비노기 모바일 업데이트"], "ko"),
}
MAX_PER_QUERY = 50  # YouTube API 上限；search.list 每次固定收 100 units，跟 maxResults 無關，拉滿不加錢


def _key() -> str:
    key = os.environ.get("YOUTUBE_API_KEY", "").strip()
    if not key:
        raise RuntimeError("環境變數 YOUTUBE_API_KEY 未設定")
    return key


def _search_ids(query: str, lang: str, key: str) -> list[str]:
    params = {"part": "snippet", "q": query, "type": "video",
              "maxResults": MAX_PER_QUERY, "relevanceLanguage": lang,
              "order": "relevance", "key": key}
    r = requests.get(f"{API_BASE}/search", params=params, timeout=15)
    r.raise_for_status()
    return [it["id"]["videoId"] for it in r.json().get("items", [])
            if it.get("id", {}).get("videoId")]


def _video_details(video_ids: list[str], region: str, key: str) -> list[dict]:
    out = []
    for i in range(0, len(video_ids), 50):
        batch = video_ids[i:i + 50]
        params = {"part": "snippet,statistics", "id": ",".join(batch), "key": key}
        r = requests.get(f"{API_BASE}/videos", params=params, timeout=15)
        r.raise_for_status()
        for it in r.json().get("items", []):
            sn, st, vid = it.get("snippet", {}), it.get("statistics", {}), it.get("id", "")
            thumbs = sn.get("thumbnails", {})
            thumb = (thumbs.get("high") or thumbs.get("medium") or thumbs.get("default") or {}).get("url", "")
            out.append({
                "id": f"youtube-{vid}", "title": sn.get("title", ""), "raw_tag": "",
                "author": sn.get("channelTitle", ""),
                "url": f"https://www.youtube.com/watch?v={vid}",
                "summary": (sn.get("description", "") or "")[:120],
                "source": "youtube", "region": region,
                "published_at": (sn.get("publishedAt", "") or "")[:10],
                "views": int(st.get("viewCount", 0) or 0),
                "replies": int(st.get("commentCount", 0) or 0),
                "thumbnail": thumb,
            })
    return out


def fetch() -> list[dict]:
    key = _key()
    all_items = []
    for region, (queries, lang) in QUERIES.items():
        ids = []
        for q in queries:
            print(f"[YT/{region}] 搜尋：{q}")
            try:
                ids.extend(_search_ids(q, lang, key))
            except requests.RequestException as e:
                print(f"[YT/{region}] 搜尋失敗 {q}: {e}")
        ids = list(dict.fromkeys(ids))
        if ids:
            all_items.extend(_video_details(ids, region, key))
    print(f"[YT] 共取得 {len(all_items)} 筆")
    return all_items
