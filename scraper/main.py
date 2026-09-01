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
import youtube
import inven
import nexon_kr
import ai_enrich
import schema


def build(no_youtube=False, no_kr=False, pages=2) -> dict:
    raw = []

    # 台服
    raw.extend(bahamut.fetch(pages=pages))

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
