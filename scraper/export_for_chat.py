# -*- coding: utf-8 -*-
"""
把網站首頁實際會列出的攻略匯出成文字檔，給站長手動丟進聊天 AI 生成「口訣」。

背景（2026-09-26 站長決定）：這個站無法變現、以不花錢為主，攻略也不是即時需求，
所以口訣不在管線裡呼叫付費 AI，而是：
  1. 跑這支程式 → exports/口訣_日期_第N段.txt（每段開頭已附好給聊天 AI 的指示）
  2. 站長把檔案丟給聊天 AI，拿回「編號｜口訣」格式的回覆
  3. 用 import_mnemonics.py 把回覆匯入 mnemonics.json → 網站卡片顯示口訣

匯出範圍＝首頁實際顯示的攻略（跟 index.html 的分頁規則一致）：
  - 最近 FRESH_DAYS 天（台灣時間）發布的台版／韓版攻略
  - 更早或沒有日期、但被評為精華的攻略（「精選」分頁）
預設只匯出「還沒有口訣、也還沒匯出過」的攻略（匯出過的編號記在 exports/已匯出編號.txt），
所以站長還沒把上一批回覆貼回來之前再跑一次，也不會重複拿到同一篇。檔名帶日期，不覆蓋舊檔。

用法：
    python export_for_chat.py              # 只匯出新的（沒口訣、也沒匯出過）
    python export_for_chat.py --all        # 全部重匯（忽略已匯出紀錄與既有口訣）
    python export_for_chat.py --per-file 40
"""

from __future__ import annotations
import argparse
import datetime
import json
import os
import re

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
FRESH_DAYS = 21  # 必須跟 index.html 的 FRESH_DAYS 一致
TW = datetime.timezone(datetime.timedelta(hours=8))

PROMPT = """你是《瑪奇 Mobile》繁體中文攻略網站的編輯。下面有 {n} 篇攻略，每篇有編號（方括號內）、標題、分類和內文摘要。
請為每一篇寫一句「口訣」，讓玩家一眼記住這篇攻略的重點：
- 繁體中文，7～20 字；可以用對仗、押韻或數字口訣。
- 只能用下面提供的文字裡真的有的資訊（符文名、數值、步驟、結論），不要補充你自己知道的遊戲知識，不要誇大。
- 摘要太短、看不出具體重點（例如只是提問、閒聊、活動宣傳）的，就寫「略」。
- 不要加表情符號、引號或說明。

輸出格式（很重要，網站程式要自動讀取）：
每篇一行，格式是「編號｜口訣」，共 {n} 行；不要加任何其他文字、不要編號清單、不要表格、不要程式碼區塊。
範例：
bahamut-3026｜落花慢熱別亂出，DPS 四萬才過關
youtube-AbCdEfGhIjK｜略

以下是攻略：
"""


def taiwan_today() -> datetime.date:
    return datetime.datetime.now(TW).date()


def age_days(date_str: str, today: datetime.date) -> int | None:
    try:
        return (today - datetime.date.fromisoformat(date_str)).days
    except (TypeError, ValueError):
        return None


def tab_of(g: dict, today: datetime.date) -> str | None:
    """跟 index.html 的 tabOf() 同一套規則：新文章依地區分台版／韓版，舊文章是精華才進精選。"""
    age = age_days(g.get("published_at", ""), today)
    if age is not None and age <= FRESH_DAYS:
        return "kr" if g.get("region") == "kr" else "tw"
    return "featured" if g.get("is_featured") else None


def load_json(name: str, default):
    path = os.path.join(ROOT, name)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def describe(g: dict, tab: str) -> str:
    tab_label = {"tw": "台版", "kr": "韓版", "featured": "精選"}[tab]
    lines = [f"[{g['id']}] {g.get('title', '')}"]
    if g.get("region") == "kr" and g.get("title_original") and g["title_original"] != g.get("title"):
        lines.append(f"原文標題：{g['title_original']}")
    lines.append(f"分類：{g.get('category', '')}｜{tab_label}｜{g.get('published_at') or '日期不明'}｜作者：{g.get('author', '')}")
    if g.get("key_points"):
        lines.append("重點：" + " / ".join(g["key_points"]))
    if g.get("summary"):
        lines.append("摘要：" + g["summary"])
    return "\n".join(lines)


MANIFEST_NAME = "已匯出編號.txt"
_ID_LINE = re.compile(r"^\[([A-Za-z0-9_-]+)\] ")


def load_exported(out_dir: str) -> set[str]:
    """已匯出過的編號。第一次用（還沒有紀錄檔）時，從資料夾裡既有的分段檔回推。"""
    path = os.path.join(out_dir, MANIFEST_NAME)
    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return {ln.strip() for ln in f if ln.strip()}
    ids = set()
    if os.path.isdir(out_dir):
        for name in os.listdir(out_dir):
            if name.startswith("口訣_") and name.endswith(".txt"):
                with open(os.path.join(out_dir, name), encoding="utf-8") as f:
                    ids.update(m.group(1) for m in map(_ID_LINE.match, f) if m)
    return ids


def select(guides: list[dict], have: set[str], include_all: bool, today: datetime.date) -> list[tuple[dict, str]]:
    out = []
    for g in guides:
        tab = tab_of(g, today)
        if tab is None:
            continue
        if not include_all and g.get("id") in have:
            continue
        out.append((g, tab))
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--all", action="store_true", help="連已經有口訣的也一起匯出")
    ap.add_argument("--per-file", type=int, default=50, help="每個檔案幾篇（太多聊天 AI 會漏）")
    ap.add_argument("--out", default=os.path.join(ROOT, "exports"))
    args = ap.parse_args()

    guides = load_json("guides.json", {"guides": []}).get("guides", [])
    have = set(load_json("mnemonics.json", {"items": {}}).get("items", {}))
    exported = load_exported(args.out)
    today = taiwan_today()
    picked = select(guides, have | exported, args.all, today)
    if not picked:
        print("[匯出] 沒有新的攻略需要生成口訣（都已經有口訣或匯出過了）。要全部重匯請加 --all")
        return

    os.makedirs(args.out, exist_ok=True)
    stamp = today.isoformat()
    for old in os.listdir(args.out):  # 同一天重跑才清掉當天的分段檔；舊日期的檔案保留
        if old.startswith(f"口訣_{stamp}_") and old.endswith(".txt"):
            os.remove(os.path.join(args.out, old))

    parts = [picked[i:i + args.per_file] for i in range(0, len(picked), args.per_file)]
    for n, part in enumerate(parts, 1):
        body = "\n\n".join(describe(g, tab) for g, tab in part)
        path = os.path.join(args.out, f"口訣_{stamp}_第{n}段（共{len(parts)}段）.txt")
        with open(path, "w", encoding="utf-8") as f:
            f.write(PROMPT.format(n=len(part)) + "\n" + body + "\n")
        print(f"[匯出] {path}（{len(part)} 篇）")
    with open(os.path.join(args.out, MANIFEST_NAME), "w", encoding="utf-8") as f:
        f.write("\n".join(sorted(exported | {g["id"] for g, _ in picked})) + "\n")
    print(f"[匯出] 共 {len(picked)} 篇，分 {len(parts)} 段（略過先前已匯出的 {len(exported)} 篇）")


if __name__ == "__main__":
    main()
