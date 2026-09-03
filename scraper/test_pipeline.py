# -*- coding: utf-8 -*-
"""管線邏輯測試（v2 台韓雙軌 + AI 降級）。不呼叫真實網路/AI。"""
import os
os.environ.pop("GEMINI_API_KEY", None)  # 確保走規則版降級路徑
os.environ.pop("GOOGLE_TRANSLATE_API_KEY", None)

import ai_enrich, schema, translate

raw = [
  {"id": "bahamut-1", "title": "新手前七天該做什麼", "raw_tag": "攻略", "author": "A",
   "url": "https://forum.gamer.com.tw/C.php?bsn=32564&snA=1", "source": "bahamut",
   "region": "tw", "published_at": "2026-08-10", "views": 50, "replies": 5},
  {"id": "bahamut-2", "title": "法師轉職技能配點解析", "raw_tag": "攻略", "author": "B",
   "url": "https://forum.gamer.com.tw/C.php?bsn=32564&snA=2", "source": "bahamut",
   "region": "tw", "published_at": "2026-08-12", "views": 900, "replies": 80},
  {"id": "inven-100", "title": "신규 던전 공략 심층분석", "author": "인벤",
   "url": "https://mabimo.inven.co.kr/webzine/news/?idx=100", "source": "inven",
   "region": "kr", "published_at": "2026-08-15", "views": 3000, "replies": 40},
  {"id": "nexon-200", "title": "8월 업데이트 안내", "author": "Nexon 官方",
   "url": "https://mabinogimobile.nexon.com/News/NoticeView?id=200", "source": "nexon",
   "region": "kr", "published_at": "2026-08-20", "views": 0, "replies": 0},
  {"id": "youtube-x", "title": "마비노기 모바일 신규 직업 공개", "author": "채널",
   "url": "https://www.youtube.com/watch?v=x", "source": "youtube",
   "region": "kr", "published_at": "2026-08-21", "views": 12000, "replies": 300},
  {"id": "bahamut-2", "title": "重複id應被去除", "author": "D",
   "url": "https://forum.gamer.com.tw/C.php?bsn=32564&snA=2", "source": "bahamut", "region": "tw"},
]

ai_enrich.enrich(raw)  # 無金鑰 → 規則版降級
recs = schema.dedupe([schema.to_record(it) for it in raw])
valid = [r for r in recs if not schema.validate(r)]

print("結果：")
for r in valid:
    print("  {:12s} [{}] {:6s} 精華={} 原文={}".format(
        r["id"], r["region"], r["category"], r["is_featured"], r["title_original"][:12]))

print()
print("去重後筆數(原6筆,重複1應剩5):", len(valid))
tw = [r for r in valid if r["region"] == "tw"]
kr = [r for r in valid if r["region"] == "kr"]
print("台服:", len(tw), "｜韓服:", len(kr))

assert len(valid) == 5, "去重錯誤"
assert len(kr) == 3, "韓服筆數錯誤"
assert all(r["region"] in schema.VALID_REGIONS for r in valid)
assert all(r["source"] in schema.VALID_SOURCES for r in valid)
# 韓服項目保留原文
kr_item = next(r for r in valid if r["id"] == "inven-100")
assert kr_item["title_original"] == "신규 던전 공략 심층분석"
# 降級版：無 AI 翻譯時 title 回退為原文
assert kr_item["title"] == kr_item["title_original"], "降級時 title 應等於原文"
print()
print("=== v2 管線邏輯全部通過（AI 降級路徑）===")

# ── 翻譯安全網測試：沒有 Gemini，但有 GOOGLE_TRANSLATE_API_KEY 時，
# 韓服標題應該被 Cloud Translation 打底翻譯，不維持原文（monkeypatch，不打真實網路）──
translate.has_translate = lambda: True
translate.translate_batch = lambda texts, target="zh-TW": [t + "（翻譯測試）" for t in texts]

raw2 = [
  {"id": "inven-999", "title": "신규 던전 공략", "author": "인벤",
   "url": "https://mabimo.inven.co.kr/webzine/news/?idx=999", "source": "inven",
   "region": "kr", "published_at": "2026-08-16", "views": 10, "replies": 1},
]
ai_enrich.enrich(raw2)  # 仍無 GEMINI_API_KEY → 規則版，但翻譯安全網應該生效
rec2 = schema.to_record(raw2[0])
assert rec2["title"] == "신규 던전 공략（翻譯測試）", f"翻譯安全網未生效：{rec2['title']!r}"
assert rec2["title_original"] == "신규 던전 공략"
print("=== 翻譯安全網（Cloud Translation 降級路徑）測試通過 ===")
