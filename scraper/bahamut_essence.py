# -*- coding: utf-8 -*-
"""
巴哈姆特「瑪奇 Mobile 精華區」爬蟲（bsn=32564，G1.php 資料夾 / G2.php 文章）。

跟 bahamut.py（一般哈啦板列表）是兩條不同的路：一般板是全站閒聊，
用「近期 N 頁」抓，混雜大量無關內容；精華區是板務已經人工篩選過的
優質文章，所以這裡的策略是「相關資料夾內近乎全收」，不用關鍵字篩選。

實測確認（2026-09-01，見 scraper/sources_candidates.md）：
- 資料夾索引：https://forum.gamer.com.tw/G1.php?bsn=32564&parent={folder_id}
- 文章內頁：  https://forum.gamer.com.tw/G2.php?bsn=32564&sn={sn}，
  跟 C.php 用同一套 .c-article__content 選擇器（server-rendered）。
- 「RE:」開頭的項目實測是別人在該篇底下的簡短留言/回覆，不是內容更新
  （抓了兩個真實案例：一個是「已加入樂器與部分遺漏外觀」29 字的作者
  補充留言，一個是別人純感謝的留言），一律跳過，只收原文。
  原文本身要更新是作者直接編輯原文（標題常見「XX 已更新」字樣），
  不會另開一篇，所以不需要額外的版本合併/去重邏輯。

已知限制：G2.php 文章頁面沒有連回原始 C.php/snA 的線索，沒辦法跟
bahamut.py 抓到的一般列表做交叉比對去重。精華區文章通常比較舊，
跟一般列表「最近 N 頁」的窗口重疊機率低，這裡先不處理。
"""

from __future__ import annotations
import time
import re
from bs4 import BeautifulSoup

from bahamut import (
    BSN, REQUEST_DELAY_SEC, SUMMARY_MAX_CHARS,
    _get, _first, _normalize_date,
)

# 精華區資料夾：只收跟攻略直接相關的，同人創作/音樂演奏/圖文創作/
# 疑難排除/社群分享是閒聊或客服類，跟本站「攻略索引」定位無關，不收。
FOLDERS = {
    2: "遊戲攻略",
    77: "職業攻略",
    95: "情報分享",
    138: "副本攻略",
}


def _parse_folder_list(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for link in soup.select("a[href*='G2.php']"):
        href = link.get("href", "")
        m = re.search(r"[?&]sn=(\d+)", href)
        if not m:
            continue
        sn = m.group(1)

        title = link.get_text(strip=True)
        if not title or title.startswith("RE:"):
            continue  # RE: 是留言/回覆，不是內容更新，見檔案開頭說明

        raw_tag = ""
        tag_m = re.match(r"[\[【]([^\]】]+)[\]】]", title)
        if tag_m:
            raw_tag = tag_m.group(1)
            title = re.sub(r"^[\[【][^\]】]+[\]】]\s*", "", title)

        items.append({
            "id": f"bahamut-essence-{sn}",
            "title": title,
            "raw_tag": raw_tag,
            "author": "",
            "url": f"https://forum.gamer.com.tw/G2.php?bsn={BSN}&sn={sn}",
            "summary": "",
            "source": "bahamut",
            "region": "tw",
            "published_at": "",
            "views": 0,
            "replies": 0,
            "thumbnail": "",
            # 板務已篩選過的內容，直接視為精華，不吃瀏覽數演算法
            # （精華區抓不到瀏覽/回覆數，套演算法只會全部落選）。
            # 見 classify.mark_featured() 對這個欄位的特殊處理。
            "is_featured": True,
        })
    return items


def _fill_detail(item: dict) -> None:
    """就地補上摘要、作者、發布日期。抓不到就留預設值，單篇失敗不拖垮整批。"""
    html = _get(item["url"])
    if not html:
        return
    soup = BeautifulSoup(html, "html.parser")

    content_el = _first(soup, [".c-article__content", ".c-post__body"])
    if content_el:
        text = content_el.get_text(separator=" ", strip=True)
        text = re.sub(r"\s+", " ", text)
        if len(text) > SUMMARY_MAX_CHARS:
            text = text[:SUMMARY_MAX_CHARS] + "…"
        item["summary"] = text

    author_el = _first(soup, [".username", "a[href*='homeindex']"])
    if author_el:
        item["author"] = author_el.get_text(strip=True)

    date_el = _first(soup, [".edittime", "time"])
    if date_el:
        item["published_at"] = _normalize_date(date_el.get_text(strip=True))


def fetch() -> list[dict]:
    """抓精華區裡跟攻略相關的資料夾，資料夾內文章近乎全收（跳過 RE: 留言）。"""
    all_items = []
    for parent, name in FOLDERS.items():
        url = f"https://forum.gamer.com.tw/G1.php?bsn={BSN}&parent={parent}"
        print(f"[巴哈精華區] 讀取「{name}」：{url}")
        html = _get(url)
        if not html:
            continue
        items = _parse_folder_list(html)
        print(f"[巴哈精華區] 「{name}」共 {len(items)} 篇（已排除 RE: 留言）")
        all_items.extend(items)
        time.sleep(REQUEST_DELAY_SEC)

    print(f"[巴哈精華區] 共取得 {len(all_items)} 篇，開始逐篇補摘要...")
    for i, item in enumerate(all_items, 1):
        _fill_detail(item)
        time.sleep(REQUEST_DELAY_SEC)
        if i % 10 == 0:
            print(f"[巴哈精華區] 摘要進度 {i}/{len(all_items)}")

    return all_items
