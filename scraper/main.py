# -*- coding: utf-8 -*-
"""
資料管線代理人 —— 總指揮（v2 台韓雙軌）。
流程：爬取(台服:巴哈+YT台 / 韓服:Inven+Nexon+YT韓) → AI 翻譯/分類/打標/評精華
      → 去重 → schema 驗證 → 產出 guides.json

用法：
    python main.py                 # 完整跑（需 YOUTUBE_API_KEY；有 GEMINI_API_KEY 則啟用 AI）
    python main.py --no-youtube    # 略過 YouTube
    python main.py --no-kr         # 只跑台服
    python main.py --out ../guides.json
"""

from __future__ import annotations
import argparse
import datetime
import json
import sys

import bahamut
import bahamut_essence
import youtube
import inven
import nexon_kr
import ai_enrich
import schema

# 韓服搶先報的「活動情報」類是時效性內容（版本/活動預告），超過這個天數
# 就從輸出濾掉，避免舊情報一直佔著版面。「職業解析」「副本攻略」這種玩法
# 教學不算時效性內容，不受此限制。
# 見 2026-09-02 討論：使用者提出「搶先報用最近三個月資料，攻略型/職業介紹
# 可以在沒更新前用現有狀態」。
KR_NEWS_MAX_AGE_DAYS = 90


def _is_stale_kr_news(record: dict, today: datetime.date) -> bool:
    if record["region"] != "kr" or record["category"] != "活動情報":
        return False
    if not record["published_at"]:
        return False  # 沒日期就不篩，保守起見留著讓人判斷
    try:
        published = datetime.date.fromisoformat(record["published_at"])
    except ValueError:
        return False
    return (today - published).days > KR_NEWS_MAX_AGE_DAYS


def build(no_youtube=False, no_kr=False, pages=2) -> dict:
    raw = []

    # 台服
    raw.extend(bahamut.fetch(pages=pages))
    try:
        raw.extend(bahamut_essence.fetch())
    except Exception as e:
        print(f"[主控] 巴哈精華區 略過（{e}）", file=sys.stderr)

    # 韓服
    if not no_kr:
        try:
            raw.extend(inven.fetch())
        except Exception as e:
            print(f"[主控] Inven 略過（{e}）", file=sys.stderr)
        try:
            raw.extend(nexon_kr.fetch())
        except Exception as e:
            print(f"[主控] NexonKR 略過（{e}）", file=sys.stderr)

    # YouTube（台+韓）
    if not no_youtube:
        try:
            raw.extend(youtube.fetch())
        except Exception as e:
            print(f"[主控] YouTube 略過（{e}）", file=sys.stderr)

    if not raw:
        print("[主控] 警告：未取得任何資料")

    # AI 翻譯 + 分類 + 打標 + 評精華（無金鑰自動降級規則版）
    ai_enrich.enrich(raw)

    # 轉合約 → 去重 → 驗證
    records = schema.dedupe([schema.to_record(it) for it in raw])
    valid, dropped = [], 0
    for r in records:
        problems = schema.validate(r)
        if problems:
            dropped += 1
            print(f"[主控] 丟棄 {r.get('id')}: {problems}")
        else:
            valid.append(r)

    today = datetime.date.today()
    stale = sum(1 for r in valid if _is_stale_kr_news(r, today))
    if stale:
        valid = [r for r in valid if not _is_stale_kr_news(r, today)]
        print(f"[主控] 濾掉 {stale} 筆超過 {KR_NEWS_MAX_AGE_DAYS} 天的韓服活動情報（時效性內容）")

    valid.sort(key=lambda r: r.get("published_at", ""), reverse=True)

    tw = sum(1 for r in valid if r["region"] == "tw")
    kr = sum(1 for r in valid if r["region"] == "kr")
    feat = sum(1 for r in valid if r["is_featured"])
    print(f"[主控] 有效 {len(valid)} 筆（台服 {tw} / 韓服 {kr}）｜丟棄 {dropped}｜精華 {feat}｜AI={'開' if ai_enrich.has_ai() else '關(規則版)'}")
    return {"updated_at": datetime.date.today().isoformat(), "guides": valid}


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--no-youtube", action="store_true")
    ap.add_argument("--no-kr", action="store_true")
    ap.add_argument("--pages", type=int, default=2)
    ap.add_argument("--out", default="guides.json")
    args = ap.parse_args()
    result = build(no_youtube=args.no_youtube, no_kr=args.no_kr, pages=args.pages)
    with open(args.out, "w", encoding="utf-8") as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"[主控] 已寫出 {args.out}")


if __name__ == "__main__":
    main()
