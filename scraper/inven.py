# -*- coding: utf-8 -*-
"""
韓國 인벤(Inven) 瑪奇 Mobile 來源。region = "kr"，source = "inven"。

2026-09-27 重寫：舊網址 mabimo.inven.co.kr/webzine/news/ 已 404（從上線起就沒抓到過）。
實測後改抓兩個仍然有效的地方（robots.txt 允許，只存標題／連結／摘要片段，不轉載全文）：

1) 인벤 게임뉴스（瑪奇 Mobile 分類）：https://www.inven.co.kr/webzine/news/?site=mabimo
   記者寫的改版／活動新聞，列表本身就有標題、摘要、完整日期，不用進內頁。量少（約每月 1～3 篇）。
2) 팁과 노하우 게시판的「공략」分類：https://www.inven.co.kr/board/mabimo/6366?category=공략
   韓服玩家的深度攻略（例：서큐버스／어비스／타바르타스），多數是台服即將拿到的內容，
   適合放進「精選」。列表日期沒有年份（「06-28」），而且文章編號跟日期不同步，
   不能用推的——所以逐篇進內頁拿完整日期與內文片段，只取最新 DETAIL_LIMIT 篇。
   2026-09-27 觀察：這個板活躍度很低（最新一篇 06-28），所以它對「最近 21 天」分頁幫助不大。

抓到的是韓文，標題與摘要交給 translate.py（Cloud Translation）翻成中文。
"""

from __future__ import annotations
import re
import time
import requests
from bs4 import BeautifulSoup

NEWS_URL = "https://www.inven.co.kr/webzine/news/?site=mabimo"
TIPS_URL = "https://www.inven.co.kr/board/mabimo/6366?category=%EA%B3%B5%EB%9E%B5"  # category=공략
DETAIL_LIMIT = 25  # 攻略板每次最多進幾篇內頁（禮貌爬取）
SUMMARY_MAX_CHARS = 150
BODY_MAX_CHARS = 2500  # 只在記憶體（item["_body"]），不寫進 guides.json

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
        r.encoding = "utf-8"  # 全站 UTF-8，不用猜（猜錯會整篇亂碼，見 bahamut.py 同樣的教訓）
        return r.text
    except requests.RequestException as e:
        print(f"[Inven] 取得失敗 {url}: {e}")
        return None


def _to_int(s: str) -> int:
    s = re.sub(r"[^\d]", "", str(s))
    return int(s) if s else 0


def _full_date(s: str) -> str:
    m = re.search(r"(20\d{2})[-.](\d{1,2})[-.](\d{1,2})", s or "")
    return f"{m.group(1)}-{int(m.group(2)):02d}-{int(m.group(3)):02d}" if m else ""


def _clip(text: str) -> str:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text[:SUMMARY_MAX_CHARS] + "…" if len(text) > SUMMARY_MAX_CHARS else text


def _parse_news(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for row in soup.select("div.webzineNewsList tr"):
        a = row.select_one("a[href*='news=']")
        title_el = row.select_one(".cols.title")
        if not a or not title_el:
            continue
        m = re.search(r"news=(\d+)", a["href"])
        if not m:
            continue
        cmt = title_el.select_one(".cmtnum")
        replies = _to_int(cmt.get_text()) if cmt else 0
        if cmt:
            cmt.extract()
        title = title_el.get_text(" ", strip=True)
        summary_el = row.select_one(".cols.summary")
        info = row.select_one(".info")
        items.append({
            "id": f"inven-news-{m.group(1)}",
            "title": title,
            "raw_tag": "",
            "author": "인벤 뉴스",  # 列表的 info 欄含記者 email，不存
            "url": f"https://www.inven.co.kr/webzine/news/?news={m.group(1)}&site=mabimo",
            "summary": _clip(summary_el.get_text(" ", strip=True) if summary_el else ""),
            "source": "inven",
            "region": "kr",
            "published_at": _full_date(info.get_text(" ", strip=True) if info else ""),
            "views": 0,
            "replies": replies,
            "thumbnail": "",
        })
    return items


def _parse_tips(html: str) -> list[dict]:
    soup = BeautifulSoup(html, "html.parser")
    items = []
    for row in soup.select("table tbody tr"):
        a = row.select_one("a.subject-link")
        if not a or not a.get("href"):
            continue
        m = re.search(r"/board/mabimo/6366/(\d+)", a["href"])
        if not m:
            continue
        cat = a.select_one(".category")
        if cat:
            cat.extract()
        title = a.get_text(" ", strip=True)
        if len(title) < 4:
            continue
        author = row.select_one(".layerNickName")
        comment = row.select_one(".con-comment")
        items.append({
            "id": f"inven-tip-{m.group(1)}",
            "title": title,
            "raw_tag": "공략",
            "author": author.get_text(strip=True) if author else "인벤",
            "url": f"https://www.inven.co.kr/board/mabimo/6366/{m.group(1)}",
            "summary": "",
            "source": "inven",
            "region": "kr",
            "published_at": "",  # 列表沒有年份，進內頁補
            "views": _to_int(row.select_one("td.view").get_text() if row.select_one("td.view") else "0"),
            "replies": _to_int(comment.get_text() if comment else "0"),
            "thumbnail": "",
        })
    # 列表依文章編號排，編號越大越新
    items.sort(key=lambda it: int(it["id"].rsplit("-", 1)[1]), reverse=True)
    return items


def _parse_detail(html: str) -> tuple[str, str, str]:
    """(完整日期, 摘要片段, 內文前段)。"""
    soup = BeautifulSoup(html, "html.parser")
    date_el = soup.select_one(".articleDate")
    body_el = soup.select_one("#powerbbsContent") or soup.select_one(".contentBody")
    body = body_el.get_text("\n", strip=True) if body_el else ""
    return (_full_date(date_el.get_text(strip=True) if date_el else ""),
            _clip(body), body[:BODY_MAX_CHARS])


def fetch() -> list[dict]:
    items: list[dict] = []

    print(f"[Inven] 讀取新聞：{NEWS_URL}")
    html = _get(NEWS_URL)
    if html:
        news = _parse_news(html)
        print(f"[Inven] 新聞 {len(news)} 筆")
        items.extend(news)
    time.sleep(REQUEST_DELAY_SEC)

    print(f"[Inven] 讀取攻略板：{TIPS_URL}")
    html = _get(TIPS_URL)
    tips = _parse_tips(html)[:DETAIL_LIMIT] if html else []
    kept = 0
    for it in tips:
        time.sleep(REQUEST_DELAY_SEC)
        page = _get(it["url"])
        if not page:
            continue
        it["published_at"], it["summary"], it["_body"] = _parse_detail(page)
        if it["published_at"]:  # 拿不到日期就不放，避免沒日期的舊文被當成新文
            items.append(it)
            kept += 1
    print(f"[Inven] 攻略 {kept}/{len(tips)} 筆（有完整日期才收）｜共取得 {len(items)} 筆")
    return items
