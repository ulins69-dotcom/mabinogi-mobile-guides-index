# -*- coding: utf-8 -*-
"""
把聊天 AI 回覆的「編號｜口訣」匯入 mnemonics.json（流程見 export_for_chat.py 開頭說明）。

聊天 AI 的回覆格式常常不乾淨（多了清單符號、方括號、程式碼區塊、說明文字），
這裡盡量寬鬆地解析，但有三道把關，寧可少匯也不要匯錯：
  - 編號必須真的存在於目前的 guides.json（防止 AI 打錯或編造編號）
  - 「略」或空白的不匯入
  - 長度要在 MIN_LEN～MAX_LEN 字之間，太長通常是 AI 在寫說明，不是口訣

用法：
    python import_mnemonics.py 回覆.txt [回覆2.txt ...]
    python import_mnemonics.py < 回覆.txt
"""

from __future__ import annotations
import datetime
import json
import os
import re
import sys

ROOT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..")
PATH = os.path.join(ROOT, "mnemonics.json")
MIN_LEN, MAX_LEN = 4, 30  # 指示要求 7～20 字；留一點標點空白的餘裕，再長通常是 AI 在寫說明
TW = datetime.timezone(datetime.timedelta(hours=8))

_LINE = re.compile(
    r"^\s*(?:[-*•>]|\d+[.、)])?\s*[\[【]?\s*"
    r"((?:bahamut(?:-essence)?-\d+)|(?:youtube-[A-Za-z0-9_-]{11})|(?:inven-(?:news|tip)-\d+))"
    r"\s*[\]】]?\s*[|｜:：\t]\s*(.+?)\s*$"
)
_SKIP = re.compile(r"^[（(]?\s*(?:略|無|N/?A|none|-+)\s*[)）]?[。.]?$", re.IGNORECASE)
_QUOTES = "「」『』\"'“”‘’`"


def parse_reply(text: str) -> list[tuple[str, str]]:
    """回傳 [(編號, 口訣)]；「略」與格式不合的行直接略過。"""
    out = []
    for line in text.splitlines():
        m = _LINE.match(line)
        if not m:
            continue
        gid, body = m.group(1), m.group(2).strip().strip(_QUOTES).strip()
        if not body or _SKIP.match(body):
            continue
        out.append((gid, body))
    return out


def load() -> dict:
    if os.path.exists(PATH):
        with open(PATH, encoding="utf-8") as f:
            return json.load(f)
    return {"updated_at": "", "note": "攻略口訣：站長把攻略匯出給聊天 AI 生成後匯入（見 scraper/export_for_chat.py）。", "items": {}}


def merge(data: dict, pairs: list[tuple[str, str]], valid_ids: set[str], today: str) -> dict:
    stats = {"added": 0, "updated": 0, "unknown_id": [], "bad_length": []}
    items = data.setdefault("items", {})
    for gid, text in pairs:
        if gid not in valid_ids:
            stats["unknown_id"].append(gid)
            continue
        if not (MIN_LEN <= len(text) <= MAX_LEN):
            stats["bad_length"].append(f"{gid}｜{text[:30]}")
            continue
        stats["updated" if gid in items else "added"] += 1
        items[gid] = {"text": text, "added": today}
    data["updated_at"] = today
    return stats


def main():
    texts = []
    if len(sys.argv) > 1:
        for p in sys.argv[1:]:
            with open(p, encoding="utf-8-sig") as f:
                texts.append(f.read())
    else:
        texts.append(sys.stdin.read())
    pairs = [pr for t in texts for pr in parse_reply(t)]

    with open(os.path.join(ROOT, "guides.json"), encoding="utf-8") as f:
        valid_ids = {g["id"] for g in json.load(f).get("guides", [])}

    data = load()
    stats = merge(data, pairs, valid_ids, datetime.datetime.now(TW).date().isoformat())
    with open(PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

    print(f"[口訣] 讀到 {len(pairs)} 條（「略」已略過）｜新增 {stats['added']}｜更新 {stats['updated']}｜目前共 {len(data['items'])} 條")
    if stats["unknown_id"]:
        print(f"[口訣] 編號不在 guides.json，沒有匯入（{len(stats['unknown_id'])}）：{', '.join(stats['unknown_id'][:10])}")
    if stats["bad_length"]:
        print(f"[口訣] 長度不在 {MIN_LEN}～{MAX_LEN} 字，沒有匯入（{len(stats['bad_length'])}）：")
        for s in stats["bad_length"][:10]:
            print("   ", s)


if __name__ == "__main__":
    main()
