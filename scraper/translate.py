# -*- coding: utf-8 -*-
"""
純翻譯專用：Google Cloud Translation API（Basic v2）。

2026-09-03 討論後決定跟 ai_enrich.py（Gemini）刻意拆開、獨立配額：
Gemini 專心做「需要理解力」的工作（分類／標籤／抽 key_points），這裡
只做機械式的韓翻中標題打底。目的是保證就算 Gemini 當日配額燒光，
韓服標題也不會維持原文——這兩個服務是不同產品線、配額互不影響。

金鑰放環境變數 GOOGLE_TRANSLATE_API_KEY。
【注意】這是一把新申請的 Cloud Translation API 金鑰，跟 GEMINI_API_KEY
不同、不能共用；申請時要在 Google Cloud Console（不是 AI Studio）開一個
有掛帳單的專案、啟用 Cloud Translation API，才能建立這把金鑰。

【降級】沒有這把金鑰、或呼叫失敗，本模組回傳 None，呼叫端（ai_enrich.py）
自動維持原本的行為（title_zh_mt 不會被設定），不會讓整條管線中斷。
"""

from __future__ import annotations
import os
import requests

ENDPOINT = "https://translation.googleapis.com/language/translate/v2"
BATCH_SIZE = 50  # 官方單次上限 128，抓保守值避免單次 payload 太大或超時


def _key() -> str:
    return os.environ.get("GOOGLE_TRANSLATE_API_KEY", "").strip()


def has_translate() -> bool:
    return bool(_key())


def translate_batch(texts: list[str], target: str = "zh-TW") -> list[str] | None:
    """翻譯一批文字，保持原順序回傳；沒有金鑰或呼叫失敗回傳 None。"""
    key = _key()
    if not key or not texts:
        return None
    try:
        out = []
        for i in range(0, len(texts), BATCH_SIZE):
            batch = texts[i:i + BATCH_SIZE]
            r = requests.post(
                ENDPOINT,
                params={"key": key},
                json={"q": batch, "target": target, "format": "text"},
                timeout=30,
            )
            if r.status_code != 200:
                print(f"[翻譯] Cloud Translation API 失敗（HTTP {r.status_code}）：{r.text[:300]}")
                return None
            translations = r.json().get("data", {}).get("translations", [])
            if len(translations) != len(batch):
                print("[翻譯] Cloud Translation API 回傳筆數與送出筆數對不上，放棄這批")
                return None
            out.extend(t.get("translatedText", "") for t in translations)
        return out
    except requests.RequestException as e:
        print(f"[翻譯] Cloud Translation API 呼叫失敗：{e}")
        return None
