# -*- coding: utf-8 -*-
"""
AI 增強模組（翻譯 + 分類 + 打標）—— 用 Google Gemini。

這就是當初 classify.py 預留的「可抽換 AI 版」。設計原則：
- 有 GEMINI_API_KEY → 用 AI 翻譯韓文、判斷分類、抽標籤（品質最高）。
- 沒有金鑰或 AI 呼叫失敗 → 自動降級回 classify.py 的規則版，整條管線不會壞。
- 批次處理（一次送多筆）以節省 API 呼叫數，穩穩待在免費額度內。

金鑰放環境變數 GEMINI_API_KEY（GitHub Actions 用 Secrets）。
"""

from __future__ import annotations
import json
import os
import time
import requests

import classify  # 規則版，作為降級備援與 is_featured 計算

MODEL = "gemini-2.5-flash"  # 2.0 已從官方模型清單下架（2026-09 查證）
# 2026-09 查證：Gemini 換代成新版 Interactions API，舊的
# /v1beta/models/{MODEL}:generateContent 端點跟 contents/candidates 回應格式
# 都已經被取代。新端點固定是 /v1beta/interactions，不用把 MODEL 接在路徑裡，
# 改成放在 request body 的 "model" 欄位。見 ai.google.dev/api/interactions-api。
ENDPOINT = "https://generativelanguage.googleapis.com/v1beta/interactions"
BATCH_SIZE = 15
VALID_CATEGORIES = ["新手指南", "職業解析", "副本攻略", "活動情報"]


def _key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def has_ai() -> bool:
    return bool(_key())


def _build_prompt(batch: list[dict]) -> str:
    lines = []
    for i, it in enumerate(batch):
        lines.append(f'{i}. [{it.get("region","tw")}] {it.get("title","")}')
    items_text = "\n".join(lines)
    return f"""你是《瑪奇 Mobile》繁體中文攻略網站的內容編輯。以下是攻略標題清單，有些是韓文（韓服搶先資訊）。
請針對每一筆，輸出一個 JSON 物件，欄位如下：
- "i": 該筆的編號（整數）
- "title_zh": 繁體中文標題。若原文是韓文，翻成自然的繁體中文；若已是中文，做適度潤飾即可。
- "category": 只能是這四種之一：新手指南、職業解析、副本攻略、活動情報
- "tags": 2~4 個繁體中文關鍵標籤的字串陣列（如職業名、副本名、活動名）
- "summary_zh": 一句話繁體中文重點摘要（20字內；資訊不足就給空字串）

只輸出一個 JSON 陣列，不要加任何說明文字。

攻略清單：
{items_text}
"""


def _extract_text(data: dict) -> str | None:
    """從 Interaction 資源的 steps 裡找出模型輸出的文字（見 ModelOutputStep）。"""
    for step in reversed(data.get("steps", [])):
        if step.get("type") != "model_output":
            continue
        parts = [
            c.get("text", "") for c in step.get("content", [])
            if isinstance(c, dict) and c.get("type") == "text"
        ]
        if parts:
            return "".join(parts)
    return None


def _call_gemini(prompt: str, key: str) -> list | None:
    body = {
        "model": MODEL,
        "input": prompt,
        "response_format": {"type": "text", "mime_type": "application/json"},
    }
    try:
        r = requests.post(f"{ENDPOINT}?key={key}", json=body, timeout=60)
        if r.status_code in (401, 403):
            # 2026-09 起 Gemini 開始拒絕「標準 API 金鑰」，要求改用 AI Studio
            # 產生的「驗證金鑰」（見 ai.google.dev/gemini-api/docs/api-key）。
            # 401/403 十之八九是這個，不是程式邏輯問題，印清楚一點方便判斷。
            print(
                f"[AI] 呼叫失敗（HTTP {r.status_code}），這批降級為規則版。"
                "常見原因：GEMINI_API_KEY 是舊式「標準金鑰」被拒絕，"
                "需要去 Google AI Studio 重新產生「驗證金鑰」並更新 GitHub Secret。"
                f"原始回應：{r.text[:300]}"
            )
            return None
        r.raise_for_status()
        data = r.json()
        if data.get("status") not in (None, "completed"):
            print(f"[AI] 呼叫失敗，這批降級為規則版：status={data.get('status')} errors={data.get('errors')}")
            return None
        text = _extract_text(data)
        if text is None:
            print(f"[AI] 呼叫失敗，這批降級為規則版：回應裡找不到 model_output 文字內容")
            return None
        parsed = json.loads(text)
        return parsed if isinstance(parsed, list) else None
    except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as e:
        print(f"[AI] 呼叫失敗，這批降級為規則版：{e}")
        return None


def _apply_rule_fallback(item: dict) -> None:
    """單筆用規則版補上欄位（AI 失敗時）。"""
    item["category"] = classify.classify_category(item)
    item["tags"] = classify.extract_tags(item)
    item.setdefault("title_zh", item.get("title", ""))


def enrich(items: list[dict]) -> list[dict]:
    """
    對每筆補上 category / tags / title_zh / summary(中文)，再整批評精華。
    有金鑰用 AI，否則整批走規則版。回傳同一批（就地修改）。
    """
    key = _key()
    if not key:
        print("[AI] 未設定 GEMINI_API_KEY，全部使用規則版分類（韓文不翻譯）")
        for it in items:
            _apply_rule_fallback(it)
        classify.mark_featured(items)
        return items

    print(f"[AI] 啟用 Gemini（{MODEL}），共 {len(items)} 筆，分 {(len(items)+BATCH_SIZE-1)//BATCH_SIZE} 批")
    failed_batches = 0
    total_batches = 0
    for start in range(0, len(items), BATCH_SIZE):
        batch = items[start:start + BATCH_SIZE]
        total_batches += 1
        result = _call_gemini(_build_prompt(batch), key)
        if result is None:
            failed_batches += 1
            for it in batch:
                _apply_rule_fallback(it)
            continue
        # 把 AI 回傳依 i 對應回 batch
        by_i = {}
        for r in result:
            if isinstance(r, dict) and "i" in r:
                try:
                    by_i[int(r["i"])] = r
                except (ValueError, TypeError):
                    pass
        for idx, it in enumerate(batch):
            r = by_i.get(idx)
            if not r:
                _apply_rule_fallback(it)
                continue
            cat = r.get("category")
            it["category"] = cat if cat in VALID_CATEGORIES else classify.classify_category(it)
            tags = r.get("tags")
            it["tags"] = [str(t) for t in tags if t] if isinstance(tags, list) else classify.extract_tags(it)
            it["title_zh"] = str(r.get("title_zh") or it.get("title", ""))
            it["summary"] = str(r.get("summary_zh") or it.get("summary", ""))
        time.sleep(1)  # 禮貌節流，避開每分鐘速率上限

    if failed_batches == total_batches and total_batches > 0:
        print(
            f"[AI] 警告：{total_batches} 批全數呼叫失敗，本次 GEMINI_API_KEY 形同沒設定"
            "（金鑰本身可能沒問題，常見原因是 MODEL 常數指到的模型已下架/改名，"
            "去看上面每批印出的失敗原因）"
        )
    elif failed_batches:
        print(f"[AI] {failed_batches}/{total_batches} 批呼叫失敗，已降級為規則版")

    classify.mark_featured(items)
    return items
