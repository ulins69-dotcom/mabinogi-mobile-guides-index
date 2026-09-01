# -*- coding: utf-8 -*-
"""
資料合約（Schema）守門員 —— v2（台韓雙軌）。
產出 guides.json 前，每筆都經 to_record() 正規化，與前端 index.html 對齊。

v2 新增：
- region："tw"（台服）/ "kr"（韓服）
- title：顯示用標題（一律中文；韓服為 AI 翻譯後）
- title_original：原始標題（韓服為韓文原文，台服同 title）
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

    return {
        "id": _s(item.get("id")),
        "title": display,
        "title_original": original,
        "author": _s(item.get("author"), "未知"),
        "category": category,
        "tags": tags,
        "url": _s(item.get("url")),
        "summary": _s(item.get("summary")),
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
    return problems


def dedupe(records: list[dict]) -> list[dict]:
    seen, out = set(), []
    for r in records:
        rid = r.get("id")
        if not rid or rid in seen:
            continue
        seen.add(rid)
        out.append(r)
    return out
