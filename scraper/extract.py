# -*- coding: utf-8 -*-
"""
規則式「抽取式重點」—— Gemini 失效時的免費備援（不呼叫任何 AI）。

背景：ai_enrich 走規則版降級時，key_points 一律是空陣列，卡片只剩一行 150 字
的開頭摘要（常常是「大家好」「如題」）。這個模組直接從內文挑出資訊量高的句子
當重點，讓 AI 掛掉時卡片仍然有東西可掃。

做法（全部是確定性規則，可重現、可測試）：
- 巴哈：把內文（bahamut.py 存在 item["_body"]，只在記憶體、不寫進 guides.json）
  拆成句子，依「有沒有數值、建議／必選／不要這類判斷詞、遊戲名詞」打分，挑最多
  3 句，維持原文順序。問題文、閒聊、活動文、太短的文章一律不抽（寧缺勿濫，
  抽不出來就留空陣列，前端會退回顯示原本的摘要）。
- YouTube：影片說明欄有時間章節（0:00 開場／3:20 符文選擇…）就抽章節標題，
  這是作者自己下的結構，比任何摘要都準。韓文章節標題交給 translate.py 翻成中文，
  翻不出來就不放（不顯示韓文）。

抽出來的句子是內文的「原句節錄」，前端不會假裝是改寫過的摘要——每條都用「」
包起來，讀者一眼看得出是原文片段；長度上限 MAX_POINT_CHARS，只存片段不存全文，
和 bahamut.py 的摘要一樣符合鐵律「僅存標題／連結／摘要」。
"""

from __future__ import annotations
import re

import translate

MAX_POINTS = 3
MIN_POINT_CHARS = 14
MAX_POINT_CHARS = 60
MIN_BODY_CHARS = 150      # 內文短於這個字數，通常是提問或閒聊，不抽
MIN_SCORE = 3             # 句子得分門檻；達不到就不放，寧缺勿濫

_URL = re.compile(r"https?://\S+")
_BULLET = re.compile(r"^\s*(?:[（(]?\d{1,2}[）).、．]|[•・▲■●◆◇★☆▶►\-\*])\s*")
_SEPARATOR = re.compile(r"^[\s\-=~＿_—─━*＊.·•]{3,}$")
# 巴哈玩家習慣用半形句點 "." 當句號；但「2.9W」「1.5 倍」這種小數不能切
_SENT_SPLIT = re.compile(r"[。！!？?；;]|(?<!\d)\.(?!\d)|\.(?=\D)")

# 問句／閒聊／求助——這類句子不是「重點」
_NOISE = re.compile(
    r"請問|請教|求教|求解|想問|想請|懇請|求助|有人知道|有沒有人|請益|"
    r"感謝|謝謝|大家好|各位|如題|哈哈|XD|orz|Orz|抱歉|不好意思|廢文|"
    r"文長|施工|待補|編輯中|更新[:：]|推推|GP|BP|訂閱|按讚|頻道"
)
_QUESTION = re.compile(r"[?？]|嗎$|呢$|吧$")
_DIRECTIVE = re.compile(
    r"推薦|建議|必選|必備|必拿|固定|優先|首選|核心|主力|不要|別|千萬|注意|小心|"
    r"盡量|最好|務必|重點|結論|順序|不划算|不需要|只要|才能|否則|適合|不適合|需要"
)
_ENTITY = re.compile(
    r"符文|裝備|技能|強化|刻印|寶石|副本|深淵|地獄|魅魔|破防|暴擊|冷卻|傷害|"
    r"戰力|徽章|飾品|防具|武器|職業|屬性|詞條|催化劑|機率|成功率|等級"
)
_QUESTION_TITLE = re.compile(r"請問|請教|求教|求解|想問|求助|問題|是不是|有人")

# YouTube 章節：0:00 / 00:00 / 1:02:03，前後可有括號或符號
_CHAPTER = re.compile(r"^\s*[\(\[（【]?\s*((?:\d{1,2}:)?\d{1,2}:\d{2})\s*[\)\]）】]?\s*[-–—:：|｜]?\s*(.+?)\s*$")
_CHAPTER_GENERIC = re.compile(
    r"^(?:開場|開頭|片頭|前言|序|序章|介紹|結尾|結語|片尾|感謝|總結|"
    r"intro|introduction|opening|ending|outro|end|thanks|"
    r"오프닝|인트로|프롤로그|엔딩|마무리|아웃트로|시작|끝)[\s!！。.]*$",
    re.IGNORECASE,
)


def _clean(s: str) -> str:
    s = _URL.sub("", s)
    s = _BULLET.sub("", s)
    return re.sub(r"\s+", " ", s).strip(" 　,，:：、-")


def _units(body: str) -> list[str]:
    """巴哈內文被作者硬斷行。實測「把短行併成一段」會把小標題黏到下一句
    （例：「白魅魔需要注意的是」＋「別亂吃地板…」），所以以「一行一單位」為主，
    只有上一行明確以逗號／頓號結尾（句子還沒講完）才併到下一行。
    以冒號結尾的行是小標題，不當重點。"""
    units: list[str] = []
    carry = ""
    for raw in body.splitlines():
        line = raw.strip()
        if not line or _SEPARATOR.match(line):
            if carry:
                units.append(carry)
                carry = ""
            continue
        if carry and not _BULLET.match(line):
            line = carry + line
            carry = ""
        if re.search(r"[，,、]$", line) and len(line) < 60:
            carry = line
            continue
        units.append(line)
    if carry:
        units.append(carry)
    return [u for u in units if not re.search(r"[:：]$", u)]


_DANGLING = re.compile(r"^[)）\]】,，、.。\-]|^(?:但|而且|所以|因為|然後|另外|還有|以及|或是|並且|不過|就是)")


def _score(sentence: str, title: str) -> int:
    if _NOISE.search(sentence) or _QUESTION.search(sentence):
        return -99
    n = len(sentence)
    if n < MIN_POINT_CHARS or n > MAX_POINT_CHARS:
        return -99
    # 殘句：以連接詞／右括號開頭，或括號不成對（被斷行切壞的句子）
    if _DANGLING.match(sentence):
        return -99
    for l, r in (("(", ")"), ("（", "）"), ("「", "」"), ("[", "]")):
        if sentence.count(l) != sentence.count(r):
            return -99
    # 跟標題重複的句子沒有新資訊
    if title and (sentence in title or title in sentence):
        return -99
    # 純英數／符號堆疊、幾乎沒有中文的句子（表格殘渣）不要
    if len(re.findall(r"[一-鿿]", sentence)) < n * 0.4:
        return -99

    has_num = bool(re.search(r"\d+\s*[%％×xX倍]|\d{2,}", sentence))
    has_directive = bool(_DIRECTIVE.search(sentence))
    has_entity = bool(_ENTITY.search(sentence))
    # 沒有判斷詞、也不是「數值＋遊戲名詞」的句子，不算重點
    if not (has_directive or (has_num and has_entity)):
        return -99
    return (2 if has_num else 0) + (2 if has_directive else 0) + (1 if has_entity else 0) + (1 if re.search(r"\d", sentence) else 0)


def _bahamut_points(item: dict) -> list[str]:
    body = item.get("_body") or ""
    if item.get("category") == "活動情報" or len(body) < MIN_BODY_CHARS:
        return []
    title = item.get("title") or ""
    if _QUESTION_TITLE.search(title) and len(body) < 600:
        return []  # 短篇提問文，內文多半是問題，不是答案

    scored: list[tuple[int, int, str]] = []
    seen: set[str] = set()
    pos = 0
    for unit in _units(body):
        for part in _SENT_SPLIT.split(unit):
            sent = _clean(part)
            if not sent:
                continue
            pos += 1
            key = re.sub(r"\W", "", sent)[:20]
            # 同一句被作者重複貼（或只差括號標點）不重複放
            if any(k.startswith(key) or key.startswith(k) for k in seen):
                continue
            seen.add(key)
            sc = _score(sent, title)
            if sc >= MIN_SCORE:
                scored.append((sc, pos, sent))
    if not scored:
        return []
    top = sorted(scored, key=lambda t: (-t[0], t[1]))[:MAX_POINTS]
    return [f"「{s}」" for _, _, s in sorted(top, key=lambda t: t[1])]


def _chapters(item: dict) -> list[str]:
    """回傳影片章節標題（不含時間），至少 3 個章節才算「有章節的影片」。"""
    out: list[tuple[str, str]] = []
    for line in (item.get("_body") or "").splitlines():
        m = _CHAPTER.match(line)
        if m:
            out.append((m.group(1), _clean(m.group(2))))
    if len(out) < 3:
        return []
    picked = [f"{t} {name}" for t, name in out
              if name and not _CHAPTER_GENERIC.match(name)
              and 2 <= len(name) <= MAX_POINT_CHARS]
    return picked


def extract_key_points(item: dict) -> list[str]:
    """單筆抽取（不含韓文翻譯）。韓服 YouTube 章節在 apply() 統一批次翻譯。"""
    if item.get("source") == "youtube":
        return _chapters(item)[:MAX_POINTS]
    if item.get("source") == "bahamut" and item.get("region") == "tw":
        return _bahamut_points(item)
    return []


def apply(items: list[dict]) -> int:
    """對「AI 沒有處理到、key_points 仍為空」的項目補上抽取式重點。回傳補到幾筆。
    只動 _rule_fallback 標記的項目：AI 有跑而且判斷「沒有值得抽的」的項目，不要用規則硬湊。"""
    todo = [it for it in items if it.get("_rule_fallback") and not it.get("key_points")]
    filled = 0
    kr: list[tuple[dict, list[str]]] = []
    for it in todo:
        pts = extract_key_points(it)
        if not pts:
            continue
        if it.get("region") == "kr":
            kr.append((it, pts))
        else:
            it["key_points"] = pts
            filled += 1

    if kr and translate.has_translate():
        flat = [p for _, pts in kr for p in pts]
        translated = translate.translate_batch(flat)
        if translated and len(translated) == len(flat):
            i = 0
            for it, pts in kr:
                got = [t.strip() for t in translated[i:i + len(pts)] if t and t.strip()]
                i += len(pts)
                if got:
                    it["key_points"] = got
                    filled += 1
        else:
            print("[重點] 韓服章節翻譯沒有結果，這次不放韓文章節")
    elif kr:
        print("[重點] 未設定 GOOGLE_TRANSLATE_API_KEY，韓服影片章節不放（不顯示未翻譯的韓文）")

    print(f"[重點] 規則式抽取：{len(todo)} 筆候選，補上 {filled} 筆重點")
    return filled
