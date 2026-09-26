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

# ── 巴哈日期解析（2026-09-26 健檢新增）：列表頁是「昨天 22:16」「09-04 15:20」這類
# 相對/無年份格式，舊版只認 YYYY-MM-DD 導致 80% 巴哈文章沒有日期。純離線測試。──
import datetime as _dt
import bahamut
_T = _dt.date(2026, 9, 26)
for _s, _exp in {"昨天 22:16": "2026-09-25", "前天 23:13": "2026-09-24", "今天 08:00": "2026-09-26",
                 "09-04 15:20": "2026-09-04", "2026-08-05": "2026-08-05", "": "", "22:16": "",
                 "99-99 10:00": ""}.items():
    assert bahamut._normalize_date(_s, today=_T) == _exp, f"日期解析錯誤：{_s!r}"
assert bahamut._normalize_date("12-30 10:00", today=_dt.date(2026, 1, 2)) == "2025-12-30", "跨年推算錯誤"
print("=== 巴哈日期解析測試通過 ===")

# ── 規則式抽取重點（extract.py；Gemini 失效時的免費備援）。純離線測試。──
import extract
_BODY = """劍術士基本作業流程：
1. 循環技能 134 - 24 - 14 迅速弄出落花
2. 找她不會跑走的時間落花
白魅魔需要注意的是：
別亂吃地板的玫瑰持續傷害，那有點痛
根據我自己數個職業去挑戰並用 DPS 檢測器所測出來的數字
DPS 起碼要穩定在 40000 以上才能通關
大家好
請問這樣配符文可以嗎？
"""
_item = {"title": "劍術士白魅魔心得", "category": "副本攻略", "source": "bahamut", "region": "tw", "_body": _BODY}
_pts = extract.extract_key_points(_item)
assert _pts and len(_pts) <= 3, f"應抽到 1~3 條重點：{_pts}"
assert all(p.startswith("「") and p.endswith("」") for p in _pts), "抽取式重點要用「」標示是原句節錄"
assert not any("大家好" in p or "請問" in p or "?" in p or "？" in p for p in _pts), f"閒聊/問句不該入選：{_pts}"
assert not any(p.rstrip("」").endswith(("：", ":")) for p in _pts), "小標題（冒號結尾）不該入選"
# 問題文、活動文、太短的文章一律不抽
assert extract.extract_key_points({**_item, "title": "請問符文怎麼配", "_body": "請問各位" * 20}) == []
assert extract.extract_key_points({**_item, "category": "活動情報"}) == []
assert extract.extract_key_points({**_item, "_body": "推薦用千把劍"}) == [], "內文太短不抽"
# YouTube 章節：≥3 個章節才抽，開場/結尾等通用章節略過
_yt = {"source": "youtube", "region": "tw", "_body": "說明\n0:00 開場\n0:30 符文選擇\n3:20 技能循環\n8:05 實戰演示\n10:00 結尾\n"}
assert extract.extract_key_points(_yt) == ["0:30 符文選擇", "3:20 技能循環", "8:05 實戰演示"], extract.extract_key_points(_yt)
assert extract.extract_key_points({**_yt, "_body": "0:00 開場\n1:00 內容"}) == [], "章節不足 3 個不算有章節"
# apply()：只補 _rule_fallback 的項目；AI 處理過的（即使 key_points 為空）不用規則硬湊
_a = {**_item, "id": "a", "_rule_fallback": True, "key_points": []}
_b = {**_item, "id": "b", "key_points": []}                       # 沒有 _rule_fallback ＝ AI 處理過
_c = {**_item, "id": "c", "_rule_fallback": True, "key_points": ["既有重點"]}
extract.apply([_a, _b, _c])
assert _a["key_points"] and _b["key_points"] == [] and _c["key_points"] == ["既有重點"]
# 韓服章節：走 translate（此處已 monkeypatch），沒翻譯就不放韓文
_kr = {"id": "k", "source": "youtube", "region": "kr", "_rule_fallback": True, "key_points": [],
       "_body": "0:00 오프닝\n0:40 룬 추천\n3:10 스킬 순서\n6:00 정리 요약\n"}
extract.apply([_kr])
assert _kr["key_points"] and all("（翻譯測試）" in k for k in _kr["key_points"]), _kr["key_points"]
translate.has_translate = lambda: False
_kr2 = {**_kr, "key_points": []}
extract.apply([_kr2])
assert _kr2["key_points"] == [], "沒有翻譯金鑰時不該把韓文章節放上卡片"
# _body 只在記憶體，不能流進 guides.json 合約
assert "_body" not in schema.to_record(_item) and "_rule_fallback" not in schema.to_record(_a)
print("=== 規則式抽取重點測試通過 ===")

# ── class_digests.json（職業速答卡，人工整理版）合約檢查：鐵律「沒有依據的內容不寫」——
# 每一條都要有來源連結與證據等級，頂層 key 只能是六大職業。純離線。──
import json, re
import classify
_dpath = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "class_digests.json")
with open(_dpath, encoding="utf-8") as _f:
    _cd = json.load(_f)
assert set(_cd["digests"]) == set(classify.OFFICIAL_CLASSES), "速答卡職業必須剛好是六大職業"
for _cls, _d in _cd["digests"].items():
    assert isinstance(_d.get("guide_count"), int) and _d["guide_count"] > 0, _cls
    for _sec in ("runes", "skill_order", "faq"):
        assert _d[_sec], f"{_cls}.{_sec} 不該是空的（沒依據就整條不寫，但這三段都有依據）"
        for _i in _d[_sec]:
            assert 10 <= len(_i["text"]) <= 200, f"{_cls}.{_sec} 條目長度異常：{_i['text'][:20]}"
            assert _i["tiers"] and set(_i["tiers"]) <= {"official", "wiki", "player"}, f"{_cls} 證據等級非法：{_i['tiers']}"
            assert _i["links"], f"{_cls}.{_sec} 有條目沒有來源連結：{_i['text'][:20]}"
            for _l in _i["links"]:
                assert _l["label"] and re.match(r"^(https://[^\s]+|[a-z-]+\.html(#[\w-]+)?)$", _l["url"]), f"連結格式不合法：{_l}"
print("=== class_digests.json 合約檢查通過 ===")
