# -*- coding: utf-8 -*-
"""
AI 增強模組（翻譯 + 分類 + 打標）—— 用 Google Gemini。

這就是當初 classify.py 預留的「可抽換 AI 版」。設計原則：
- 有 GEMINI_API_KEY → 用 AI 翻譯韓文、判斷分類、抽標籤（品質最高）。
- 沒有金鑰或 AI 呼叫失敗 → 自動降級回 classify.py 的規則版，整條管線不會壞。
- 批次處理（一次送多筆）以節省 API 呼叫數，穩穩待在免費額度內。

2026-09 新增 key_points（重點條列）：prompt 現在會把 bahamut.py 抓到的
內文摘要一併送給 AI，讓它從實際內容抽 0~3 條具體重點，而不是只看標題
腦補一句話。沒有內文片段（或 AI 抽不出東西）就給空陣列，前端卡片會
自動退回顯示原始摘要，不會開天窗。

2026-09-03 新增翻譯安全網：韓服標題翻譯改交給 translate.py（Cloud
Translation API，獨立配額），在 Gemini 開始跑之前先幫每篇韓服標題打底
翻譯（寫入 item["title_zh_mt"]）。原因：Gemini 配額燒光時，原本韓服
標題會整批維持韓文原文——翻譯其實不需要 Gemini 等級的理解力，拆給
一個穩定、免費額度更寬裕的獨立服務，Gemini 專心做分類/標籤/key_points
這些真正需要理解力的事。Gemini 若成功，仍以 Gemini 的翻譯結果為準
（品質通常更好）；Gemini 失敗或沒有金鑰時，才退回這裡打底的翻譯，
兩者都沒有時才維持原文——三層降級，缺一層都還能動。

金鑰放環境變數 GEMINI_API_KEY（GitHub Actions 用 Secrets）。
翻譯安全網另外需要 GOOGLE_TRANSLATE_API_KEY，見 translate.py 說明。
"""

from __future__ import annotations
import json
import os
import time
import requests

import classify  # 規則版，作為降級備援與 is_featured 計算
import translate  # 翻譯安全網（Cloud Translation API，獨立於 Gemini 配額）

MODEL = "gemini-3.6-flash"  # 2026-09 實測：2.0 已下架；2.5 對「新用戶」金鑰回 404
# ("This model models/gemini-2.5-flash is no longer available to new
# users. Please update your code to use models/gemini-3.6-flash" ——
# Google API 錯誤訊息原文，直接點名這個模型，不是用猜的)
# 2026-09 查證：Google 力推新版 Interactions API（/v1beta/interactions），
# 但實測這個專案的金鑰打下去是 404（見 GitHub Actions log），這個新端點
# 標示為「實驗性 API」，很可能還沒對這個帳號/專案開放。
# 舊版 /v1beta/models/{MODEL}:generateContent 端點實測仍然是活的（用假金鑰
# 測試回 400 缺金鑰，不是 404 路徑不存在），改回用這個，只換模型名稱，
# 不要一次連新端點都換，降低風險。
ENDPOINT = f"https://generativelanguage.googleapis.com/v1beta/models/{MODEL}:generateContent"
BATCH_SIZE = 15
VALID_CATEGORIES = ["新手指南", "職業解析", "副本攻略", "活動情報"]
BATCH_DELAY_SEC = 4  # 批次間固定延遲，降低撞到每分鐘速率上限的機率
RATE_LIMIT_RETRIES = 2
RATE_LIMIT_BACKOFF_SEC = 20  # 429/503 是暫時性的，等一下再試大機率會過


def _key() -> str:
    return os.environ.get("GEMINI_API_KEY", "").strip()


def has_ai() -> bool:
    return bool(_key())


EXCERPT_MAX_CHARS = 200  # 送給 AI 的內文片段長度上限，避免單批 token 太多


def _build_prompt(batch: list[dict]) -> str:
    lines = []
    for i, it in enumerate(batch):
        title = it.get("title", "")
        excerpt = (it.get("summary") or "").strip()[:EXCERPT_MAX_CHARS]
        line = f'{i}. [{it.get("region","tw")}] 標題：{title}'
        if excerpt:
            line += f"\n   內文片段：{excerpt}"
        lines.append(line)
    items_text = "\n".join(lines)
    return f"""你是《瑪奇 Mobile》繁體中文攻略網站的編輯。以下每筆攻略給你標題，部分附「內文片段」
（韓文的請看內文片段抓重點，不要只靠標題腦補）。請針對每一筆，輸出一個 JSON 物件，欄位如下：
- "i": 該筆的編號（整數）
- "title_zh": 繁體中文標題。若原文是韓文，翻成自然的繁體中文；若已是中文，做適度潤飾即可。
- "category": 只能是這四種之一：新手指南、職業解析、副本攻略、活動情報
- "tags": 2~4 個繁體中文關鍵標籤的字串陣列（如職業名、副本名、活動名）
- "key_points": 陣列，從「內文片段」抽出 0~3 條具體、有用的重點，每條 12~18 字繁體中文。
  只抽讀者會想知道的具體資訊（數值、符文/裝備名、步驟、結論），不要重複標題文字，
  不要「內容豐富」「值得參考」這種沒有實際資訊量的空話。
  沒有內文片段、或片段裡真的抽不出實質內容，就給空陣列 []，不要硬湊。
- "summary_zh": 一句話繁體中文摘要（20字內，是內文片段的翻譯／整理；沒有片段就給空字串）

只輸出一個 JSON 陣列，不要加任何說明文字。

攻略清單：
{items_text}
"""


def _call_gemini(prompt: str, key: str) -> list | None:
    body = {
        "contents": [{"parts": [{"text": prompt}]}],
        "generationConfig": {"temperature": 0.2, "responseMimeType": "application/json"},
    }
    for attempt in range(RATE_LIMIT_RETRIES + 1):
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
            if r.status_code == 404:
                # 通常是 MODEL 常數指到的模型名稱下架/打錯，不是金鑰問題。
                print(f"[AI] 呼叫失敗（HTTP 404，模型 {MODEL} 可能已下架/名稱錯誤），這批降級為規則版：{r.text[:300]}")
                return None
            if r.status_code in (429, 503):
                # 暫時性錯誤（速率限制/伺服器忙），不是設定問題，等一下重試。
                if attempt < RATE_LIMIT_RETRIES:
                    print(f"[AI] HTTP {r.status_code}（暫時性，疑似碰到速率限制），{RATE_LIMIT_BACKOFF_SEC}秒後重試（第 {attempt+1}/{RATE_LIMIT_RETRIES} 次）")
                    time.sleep(RATE_LIMIT_BACKOFF_SEC)
                    continue
                print(f"[AI] 呼叫失敗（HTTP {r.status_code}，重試 {RATE_LIMIT_RETRIES} 次仍失敗），這批降級為規則版")
                return None
            r.raise_for_status()
            data = r.json()
            text = data["candidates"][0]["content"]["parts"][0]["text"]
            parsed = json.loads(text)
            return parsed if isinstance(parsed, list) else None
        except (requests.RequestException, KeyError, IndexError, json.JSONDecodeError) as e:
            print(f"[AI] 呼叫失敗，這批降級為規則版：{e}")
            return None
    return None


def _pretranslate_kr_titles(items: list[dict]) -> None:
    """韓服標題先用 Cloud Translation 打底翻譯，寫入 item["title_zh_mt"]。
    跑在 Gemini 之前、獨立配額——Gemini 失敗時的翻譯安全網（見本檔開頭說明）。
    沒有 GOOGLE_TRANSLATE_API_KEY 或呼叫失敗就整批跳過，不影響後續流程。"""
    kr_items = [it for it in items if it.get("region") == "kr" and it.get("title")]
    if not kr_items or not translate.has_translate():
        return
    translated = translate.translate_batch([it["title"] for it in kr_items])
    if translated is None:
        print("[翻譯] Cloud Translation 這次沒有結果，韓服標題翻譯安全網先跳過（Gemini 若成功仍不受影響）")
        return
    done = 0
    for it, t in zip(kr_items, translated):
        if t:
            it["title_zh_mt"] = t
            done += 1
    print(f"[翻譯] Cloud Translation 已為 {done}/{len(kr_items)} 篇韓服標題打底翻譯")


def _apply_rule_fallback(item: dict) -> None:
    """單筆用規則版補上欄位（AI 失敗時）。key_points 是 AI 專屬能力，
    規則版抽不出重點，給空陣列——前端會自動退回顯示原始摘要，不會空白。
    title_zh 優先用翻譯安全網打底的版本，兩者都沒有才維持原文。"""
    item["category"] = classify.classify_category(item)
    item["tags"] = classify.extract_tags(item)
    item.setdefault("title_zh", item.get("title_zh_mt") or item.get("title", ""))
    item.setdefault("key_points", [])


def enrich(items: list[dict]) -> list[dict]:
    """
    對每筆補上 category / tags / title_zh / summary(中文)，再整批評精華。
    有金鑰用 AI，否則整批走規則版。回傳同一批（就地修改）。
    """
    _pretranslate_kr_titles(items)  # 翻譯安全網，跑在 Gemini 之前、獨立配額

    key = _key()
    if not key:
        print("[AI] 未設定 GEMINI_API_KEY，全部使用規則版分類（韓文翻譯交給翻譯安全網，沒設定就維持原文）")
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
        else:
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
                it["title_zh"] = str(r.get("title_zh") or it.get("title_zh_mt") or it.get("title", ""))
                it["summary"] = str(r.get("summary_zh") or it.get("summary", ""))
                kp = r.get("key_points")
                it["key_points"] = (
                    [str(k).strip() for k in kp if isinstance(k, str) and k.strip()][:3]
                    if isinstance(kp, list) else []
                )
        # 不管這批成功或失敗都要延遲，避免失敗批次雪崩式越打越快、越打越容易被限流
        # （之前的 bug：失敗時用 continue 跳過了這行，緊接著下一批立刻打過去）。
        time.sleep(BATCH_DELAY_SEC)

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
