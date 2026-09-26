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

# 章節標題含零寬字元、或只是「開始／章節」這類通用標籤時要略過（2026-09-26 正式管線實測出現）
_yt2 = {"source": "youtube", "region": "tw",
        "_body": "00:00 ​​ 章節\n00:19 開始\n00:59 商城套組\n01:39 迎接月光活動\n02:30 符文交換\n"}
assert extract.extract_key_points(_yt2) == ["00:59 商城套組", "01:39 迎接月光活動", "02:30 符文交換"], extract.extract_key_points(_yt2)
print("=== 章節通用標籤過濾測試通過 ===")


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

# ── 口訣匯出／匯入（export_for_chat.py、import_mnemonics.py）。純離線。──
import export_for_chat, import_mnemonics
_today = _dt.date(2026, 9, 26)
assert export_for_chat.tab_of({"published_at": "2026-09-05", "region": "tw"}, _today) == "tw"      # 剛好 21 天
assert export_for_chat.tab_of({"published_at": "2026-09-04", "region": "tw"}, _today) is None      # 22 天、非精華 → 不列
assert export_for_chat.tab_of({"published_at": "2026-09-04", "is_featured": True}, _today) == "featured"
assert export_for_chat.tab_of({"published_at": "", "is_featured": True}, _today) == "featured"      # 沒日期的精華 → 精選
assert export_for_chat.tab_of({"published_at": "2026-09-20", "region": "kr"}, _today) == "kr"
_reply = """好的，以下是口訣：
```
bahamut-3026｜落花慢熱別亂出，DPS 四萬才過關
- [youtube-AbCdEfGhIjK] | 「章節看完再配符文」
3. bahamut-essence-101：略
bahamut-999999｜編號不存在的要擋掉
bahamut-2979｜這一條實在寫得太長了已經不像口訣而是在寫一整段說明文字了這樣不行喔真的太長
```"""
_pairs = import_mnemonics.parse_reply(_reply)
assert ("bahamut-3026", "落花慢熱別亂出，DPS 四萬才過關") in _pairs, _pairs
assert ("youtube-AbCdEfGhIjK", "章節看完再配符文") in _pairs, "清單符號、方括號、引號要能容忍"
assert all(g != "bahamut-essence-101" for g, _ in _pairs), "「略」不匯入"
_data = {"items": {}}
_st = import_mnemonics.merge(_data, _pairs, {"bahamut-3026", "youtube-AbCdEfGhIjK", "bahamut-2979"}, "2026-09-26")
assert set(_data["items"]) == {"bahamut-3026", "youtube-AbCdEfGhIjK"}, _data["items"]
assert _st["unknown_id"] == ["bahamut-999999"] and len(_st["bad_length"]) == 1
# mnemonics.json（若已存在）合約：每條都是 {text, added}、長度合規
_mp = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "mnemonics.json")
if os.path.exists(_mp):
    with open(_mp, encoding="utf-8") as _f:
        for _gid, _v in json.load(_f)["items"].items():
            assert re.match(r"^(bahamut(-essence)?-\d+|youtube-[A-Za-z0-9_-]{11}|inven-(news|tip)-\d+)$", _gid), _gid
            assert import_mnemonics.MIN_LEN <= len(_v["text"]) <= import_mnemonics.MAX_LEN, _gid
print("=== 口訣匯出／匯入測試通過 ===")

# ── 巴哈列表標題（2026-09-27 修正）：有縮圖的列標題是 <p class="b-list__main__title">、整塊包在 <a> 裡，
# 舊版會把「精華」標記、頁碼、內文預覽全黏進標題。純離線，用實際抓到的 HTML 結構。──
_list_html = """<table><tr class="b-list__row"><td class="b-list__main"><a href="C.php?bsn=32564&amp;snA=973&amp;tnum=414">
<div class="imglist-text"><div class="b-list__tile"><div class="b-list__summary__mark b-mark b-mark--feature">精華</div>
<p class="b-list__main__title">【心得】蓋個外觀分享樓</p><span class="b-list__main__pages"><span>19</span><span>20</span></span></div>
<p class="b-list__brief">染色劑隨機染色真的很難抓</p></div></a></td></tr>
<tr class="b-list__row"><td class="b-list__main"><div class="b-list__tile">
<a class="b-list__main__title" href="C.php?bsn=32564&amp;snA=810&amp;tnum=2">【問題】好友送禮的問題</a></div></td></tr></table>"""
_rows = bahamut._parse_list(_list_html)
assert [r["title"] for r in _rows] == ["蓋個外觀分享樓", "好友送禮的問題"], [r["title"] for r in _rows]
assert [r["raw_tag"] for r in _rows] == ["心得", "問題"]
assert _rows[0].get("is_featured") is True and "is_featured" not in _rows[1], "版主精華標記要帶出來"
print("=== 巴哈列表標題解析測試通過 ===")

# ── YouTube 每個關鍵字要搜兩次：不限時間（長青、給精選）＋最近 21 天（給台版／韓版分頁）。monkeypatch，不打網路。──
import youtube
_calls = []
youtube._key = lambda: "fake"
youtube._search_ids = lambda q, lang, key, published_after=None: (_calls.append((q, published_after)) or [q + ("-new" if published_after else "-old")])
youtube._video_details = lambda ids, region, key: [{"id": i, "region": region} for i in ids]
_yt_items = youtube.fetch()
_n_q = sum(len(qs) for qs, _ in youtube.QUERIES.values())
assert len(_calls) == 2 * _n_q, _calls
assert sum(1 for _, a in _calls if a) == _n_q and all(re.match(r"^\d{4}-\d{2}-\d{2}T00:00:00Z$", a) for _, a in _calls if a)
assert len(_yt_items) == 2 * _n_q
print("=== YouTube 近期搜尋測試通過 ===")

# ── Inven（2026-09-27 重寫）：新聞列表與攻略板解析，用實測的 HTML 結構。純離線。──
import inven
_news_html = """<div class="webzineNewsList tableType2"><table><tr><td><div class="content">
<a href="https://www.inven.co.kr/webzine/news/?news=320623&amp;site=mabimo"><span class="cols title">"AI, 양털 20개만 깎아줘" 마비노기 모바일 <span class="cmtnum">[25]</span></span>
<span class="cols summary">넥슨은 9일 '마비노기 모바일'에 외부 AI를 연결해</span></a>
<span class="info"><span class="category">게임뉴스</span> 김규만 기자 (Frann@inven.co.kr) | 2026-09-09 19:10 </span></div></td></tr></table></div>"""
_n = inven._parse_news(_news_html)
assert len(_n) == 1 and _n[0]["id"] == "inven-news-320623" and _n[0]["published_at"] == "2026-09-09"
assert _n[0]["replies"] == 25 and "[25]" not in _n[0]["title"] and "@" not in _n[0]["author"], _n[0]
_tips_html = """<table><tbody>
<tr><td class="tit"><a class="subject-link" href="https://www.inven.co.kr/board/mabimo/6366/605"><span class="category">[공략]</span> 타바르타스 레이드 간단 공략 및 후기 </a>
<span class="con-comment">[2]</span></td><td class="user"><span class="layerNickName">작성자</span></td><td class="date">11-13</td><td class="view">14,367</td></tr>
<tr><td class="tit"><a class="subject-link" href="https://www.inven.co.kr/board/mabimo/6366/622"><span class="category">[공략]</span> 한눈에 비교하는 소울스트림 </a></td>
<td class="date">06-28</td><td class="view">16,075</td></tr></tbody></table>"""
_t = inven._parse_tips(_tips_html)
assert [x["id"] for x in _t] == ["inven-tip-622", "inven-tip-605"], "要依文章編號新到舊"
assert _t[1]["title"] == "타바르타스 레이드 간단 공략 및 후기" and _t[1]["views"] == 14367 and _t[1]["replies"] == 2
assert all(x["published_at"] == "" for x in _t), "列表沒有年份，不能猜，要進內頁補"
_d = inven._parse_detail('<div class="articleDate">2026-06-28 07:24</div><div id="powerbbsContent">오랜만에 공략 올립니다.</div>')
assert _d[0] == "2026-06-28" and _d[1] == "오랜만에 공략 올립니다."
assert import_mnemonics.parse_reply("inven-tip-622｜소울스트림 한눈에") == [("inven-tip-622", "소울스트림 한눈에")]
print("=== Inven 解析測試通過 ===")

# ── 韓服摘要翻譯：只翻最近 21 天＋Inven，且有字數上限（成本原則）。monkeypatch，不打網路。──
translate.has_translate = lambda: True
_sent = []
translate.translate_batch = lambda texts, target="zh-TW": (_sent.extend(texts) or ["中：" + t for t in texts])
_kr_items = [
    {"region": "kr", "source": "youtube", "published_at": "2026-09-20", "summary": "최신 영상"},
    {"region": "kr", "source": "youtube", "published_at": "2026-05-01", "summary": "오래된 영상"},
    {"region": "kr", "source": "inven", "published_at": "2025-11-13", "summary": "인벤 공략"},
    {"region": "tw", "source": "bahamut", "published_at": "2026-09-20", "summary": "台服不用翻"},
]
ai_enrich._pretranslate_kr_summaries(_kr_items, today=_dt.date(2026, 9, 27))
assert _sent == ["최신 영상", "인벤 공략"], _sent
ai_enrich._apply_rule_fallback(_kr_items[0])
assert _kr_items[0]["summary"] == "中：최신 영상"
_sent.clear()
_big = [{"region": "kr", "source": "inven", "published_at": "", "summary": "가" * 5000} for _ in range(3)]
ai_enrich._pretranslate_kr_summaries(_big, today=_dt.date(2026, 9, 27))
assert sum(len(t) for t in _sent) <= ai_enrich.SUMMARY_CHAR_BUDGET, "超過每次字數上限"
print("=== 韓服摘要翻譯（範圍與字數上限）測試通過 ===")
