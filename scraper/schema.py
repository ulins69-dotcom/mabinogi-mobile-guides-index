# -*- coding: utf-8 -*-
"""
資料合約（Schema）守門員 —— v2（台韓雙軌）。
產出 guides.json 前，每筆都經 to_record() 正規化，與前端 index.html 對齊。

v2 新增：
- region："tw"（台服）/ "kr"（韓服）
- title：顯示用標題（一律中文；韓服為 AI 翻譯後）
- title_original：原始標題（韓服為韓文原文，台服同 title）

2026-09 新增：
- key_points：AI 從內文摘要抽出的 0~3 條具體重點（string[]）。沒有 AI
  或抽不出東西一律為 []，前端卡片沒有重點時退回顯示 summary，不開天窗。
"""

from __future__ import annotations

VALID_CATEGORIES = {"新手指南", "職業解析", "副本攻略", "活動情報"}
VALID_SOURCES = {"bahamut", "youtube", "inven", "nexon", "official"}
VALID_REGIONS = {"tw", "kr"}


def _s(v, fallback="") -> str:
    return v if isinstance(v, str) and v else fallback


def to_record(item: dict) -> dict:
    category = _s(item.get("category"), "新手指南")
    if category not in VALID_CATEGORIES:
        category = "新手指南"

    source = _s(item.get("source"), "bahamut")
    if source not in VALID_SOURCES:
        source = "bahamut"

    region = _s(item.get("region"), "tw")
    if region not in VALID_REGIONS:
        region = "tw"

    original = _s(item.get("title"), "（無標題）")
    display = _s(item.get("title_zh"), original)   # 有中譯用中譯，否則用原文

    tags = item.get("tags") or []
    tags = [t for t in tags if isinstance(t, str) and t]

    key_points = item.get("key_points") or []
    key_points = [str(k) for k in key_points if isinstance(k, str) and k][:3]

    return {
        "id": _s(item.get("id")),
        "title": display,
        "title_original": original,
        "author": _s(item.get("author"), "未知"),
        "category": category,
        "tags": tags,
        "url": _s(item.get("url")),
        "summary": _s(item.get("summary")),
        "key_points": key_points,
        "source": source,
        "region": region,
        "published_at": _s(item.get("published_at")),
        "is_featured": item.get("is_featured") is True,
        "thumbnail": _s(item.get("thumbnail")),
    }


def validate(record: dict) -> list[str]:
    problems = []
    if not record.get("id"):
        problems.append("缺少 id")
    if not record.get("url"):
        problems.append("缺少 url")
    if record.get("category") not in VALID_CATEGORIES:
        problems.append(f"category 非法：{record.get('category')}")
    if record.get("source") not in VALID_SOURCES:
        problems.append(f"source 非法：{record.get('source')}")
    if record.get("region") not in VALID_REGIONS:
        problems.append(f"region 非法：{record.get('region')}")
    if not isinstance(record.get("tags"), list):
        problems.append("tags 非陣列")
    if not isinstance(record.get("key_points"), list):
        problems.append("key_points 非陣列")
    return problems


def dedupe(records: list[dict]) -> list[dict]:
    """先照 id 去重，再補一層「摘要開頭幾乎一樣」的內容去重。

    這是為了處理巴哈一般列表（bahamut.py）跟精華區（bahamut_essence.py）
    抓到同一篇文章的情況——兩邊各自有自己的一套 id（snA vs sn），精華區
    文章頁面又沒有連回原文 snA 的線索（見 bahamut_essence.py 開頭說明），
    id 比對抓不到這種重複，只能靠內容比對（2026-09-02 實測抓到過真實案例）。
    不比對作者：實測發現兩邊的作者選擇器有時會抓到不同東西（例如精華區
    那次抓到貼文裡提到的暱稱而非真正樓主），比對作者反而會漏抓真正的重複。
    摘要開頭取 80 字，一般文章不太可能剛好開頭 80 字完全相同卻是不同篇。
    同一組重複裡優先留精華區那筆（board-curated，預設會是精華）。
    """
    seen_ids, out = set(), []
    for r in records:
        rid = r.get("id")
        if not rid or rid in seen_ids:
            continue
        seen_ids.add(rid)
        out.append(r)

    def content_key(r: dict) -> str | None:
        summary = (r.get("summary") or "").strip()[:80]
        return summary if len(summary) >= 20 else None  # 太短的摘要不夠獨特，不比對

    groups: dict[str, list[dict]] = {}
    passthrough = []
    for r in out:
        key = content_key(r)
        if key is None:
            passthrough.append(r)
        else:
            groups.setdefault(key, []).append(r)

    deduped = list(passthrough)
    for records_in_group in groups.values():
        if len(records_in_group) == 1:
            deduped.append(records_in_group[0])
            continue
        essence = next((r for r in records_in_group if str(r.get("id", "")).startswith("bahamut-essence-")), None)
        deduped.append(essence or records_in_group[0])

    return deduped
