# -*- coding: utf-8 -*-
"""
分類 / 打標 / 評精華 —— 全案唯一「智慧」所在，設計為可抽換模組。

【鐵律】想升級成 LLM 版本時，只需重寫本檔的三個函式：
    classify_category(item) -> str
    extract_tags(item)      -> list[str]
    mark_featured(items)    -> None (就地修改 is_featured)
其他檔案（爬蟲、部署）完全不需更動。這就是模組化的意義。

目前為「規則 + 關鍵字」實作：零成本、可離線、可預測，
代價是界線模糊的貼文偶爾會分錯，精華只看硬指標（觀看/推文數）。

2026-09-03 補充：韓服關鍵字。實測發現 AI（ai_enrich.py）失敗降級時，
韓文原文標題完全比對不到本檔原本只有中文的關鍵字表，導致全部 75 篇
韓服文章清一色落在保底分類「新手指南」、tags 全空——職業選單因此在
韓服分頁完全是空的（見鐵律11：這不是等 AI 就能忽視的體驗斷點，AI
降級鐵則要求規則版本身也要「堪用」，不能整批放棄分類）。這裡補上
韓文關鍵字，讓規則版對韓文也有基本判斷力；標題翻譯仍然只有 AI 做得到，
不在此範圍內。
"""

from __future__ import annotations

# ── 分類關鍵字表（由上而下比對，先命中者為準）────────────────
CATEGORY_RULES = [
    ("新手指南", [
        "新手", "入門", "前期", "萌新", "零課", "練等", "練功", "路線", "配裝入門", "該做什麼",
        "뉴비", "초보", "초반", "입문", "복귀",  # 新人/初期/回歸玩家
    ]),
    ("副本攻略", [
        "副本", "地城", "深淵", "王", "boss", "首領", "機制", "打法", "團隊", "攻堅", "討伐",
        "레이드", "보스", "던전", "어비스", "패턴",  # 團隊本/首領/地城/深淵/機制
    ]),
    ("職業解析", [
        "職業", "轉職", "技能", "配點", "天賦", "加點", "輸出手法", "流派",
        "法師", "冰霜術士", "火焰術士", "電擊術士",
        "戰士", "大劍戰士", "劍術士", "騎士",
        "弓手", "弓箭", "弩手", "長弓兵",
        "治癒師", "祭司", "修道士", "暗黑術士",
        "吟遊詩人", "樂師", "舞者",
        "盜賊", "格鬥家", "雙刀客", "刺客",
        # 韓文：轉職/技能通用詞 + 六大系列官方韓文名稱（見下方 CLASS_ALIASES 出處）
        "전직", "스킬", "클래스", "세팅",
        "전사", "대검전사", "검술사",
        "궁수", "석궁사수", "장궁병",
        "마법사", "화염술사", "빙결술사",
        "힐러", "사제", "수도사",
        "음유시인", "댄서", "악사",
        "도적", "격투가", "듀얼 블레이드",
    ]),
    ("活動情報", [
        "活動", "改版", "更新", "版本", "獎勵", "情報", "公告", "限時", "簽到", "抽獎", "禮包", "序號",
        "업데이트", "이벤트", "패치", "콜라보", "신규",  # 更新/活動/改版/聯名/新增
    ]),
]
DEFAULT_CATEGORY = "新手指南"  # 都沒命中時的保底分類

# 標題若帶巴哈前綴，優先採用其暗示
PREFIX_HINT = {
    "攻略": None,      # 攻略是通用前綴，交給關鍵字判斷
    "情報": "活動情報",
    "心得": None,
    "討論": None,
}

# 官方六大職業系列（見 tw.nexon.com/mabinogimobile/home/info/class 官網角色頁，
# 每系列點開後底部分頁會顯示：見習OO（起始）→ 三個轉職）。
# 前端「職業」選單只認這六個官方名稱（見 index.html CLASS_TAGS，須與此同步）。
OFFICIAL_CLASSES = ["戰士", "弓手", "魔法師", "治癒師", "吟遊詩人", "盜賊"]

# 官方轉職名稱 → 對應官方系列（實測台版官網 tw.nexon.com 確認過，非猜測）：
#   戰士系列：戰士／大劍戰士／劍術士
#   弓手系列：弓手／弩手／長弓兵
#   魔法師系列：魔法師／火焰術士／冰霜術士
#   治癒師系列：治癒師／祭司／修道士
#   吟遊詩人系列：吟遊詩人／舞者／樂師
#   盜賊系列：盜賊／格鬥家／雙刀客
# 「法師」是社群慣用的「魔法師」簡稱，一併歸類。
#
# 韓文對照（2026-09-03 WebSearch 查證，來源 bluestacks.com 攻略頁 + namu.wiki，
# 非猜測）：韓服官方系列基礎職業叫「힐러」（Healer），中文對應「治癒師」，
# 底下兩個轉職才叫「사제」（祭司）／「수도사」（修道士）——跟中文「治癒師」
# 系列的命名邏輯剛好錯開，容易誤植，特別註記。
#   전사(戰士)／대검전사(大劍戰士)／검술사(劍術士)
#   궁수(弓手)／석궁사수(弩手)／장궁병(長弓兵)
#   마법사(魔法師)／화염술사(火焰術士)／빙결술사(冰霜術士)
#   힐러(治癒師)／사제(祭司)／수도사(修道士)
#   음유시인(吟遊詩人)／댄서(舞者)／악사(樂師)
#   도적(盜賊)／격투가(格鬥家)／듀얼 블레이드(雙刀客)
# 加這份是因為 AI 翻譯失敗時（ai_enrich.py 降級），規則版要靠這份表格
# 直接比對韓文原文，否則韓服文章的職業/分類全部比對不到（見本檔開頭說明）。
CLASS_ALIASES = {
    "法師": "魔法師", "冰霜術士": "魔法師", "火焰術士": "魔法師",
    "大劍戰士": "戰士", "劍術士": "戰士",
    "弩手": "弓手", "長弓兵": "弓手",
    "祭司": "治癒師", "修道士": "治癒師",
    "樂師": "吟遊詩人", "舞者": "吟遊詩人",
    "格鬥家": "盜賊", "雙刀客": "盜賊",
    # 韓文
    "전사": "戰士", "대검전사": "戰士", "검술사": "戰士",
    "궁수": "弓手", "석궁사수": "弓手", "장궁병": "弓手",
    "마법사": "魔法師", "화염술사": "魔法師", "빙결술사": "魔法師",
    "힐러": "治癒師", "사제": "治癒師", "수도사": "治癒師",
    "음유시인": "吟遊詩人", "댄서": "吟遊詩人", "악사": "吟遊詩人",
    "도적": "盜賊", "격투가": "盜賊", "듀얼 블레이드": "盜賊",
}

# 韓服已上線、但台版官網（tw.nexon.com「公告」「更新」頁，2026-09-01 查證時
# 均顯示「目前尚無相關內容」）尚未公布任何時間的第 4 轉職。
# 來源：namu.wiki「마비노기 모바일/클래스」（韓文攻略 wiki，2026-08-19 版本）：
#   魔法師系列＋電擊術士（전격술사，韓服 2025-06-19 上線）
#   戰士系列＋騎士（기사，韓服 2026-04-23 上線）
#   治癒師系列＋暗黑術士（암흑술사，韓服 2025-10-16 上線）
# 一旦台版官網公告確切日期，把對應項目從這裡移到 CLASS_ALIASES，
# 並把下面 extract_tags() 補上的狀態標籤從「尚未開放」改成「即將登場」。
#
# 韓文原文一併列進來：韓服文章原文就是用這些韓文字，AI 翻譯失敗降級時
# 規則版要能直接比對韓文，否則這幾個職業在韓服分頁完全比對不到。
UPCOMING_CLASSES = {
    "電擊術士": "魔法師", "電擊魔法師": "魔法師", "전격술사": "魔法師",
    "騎士": "戰士", "기사": "戰士",
    "暗黑術士": "治癒師", "암흑술사": "治癒師",
}

# ── 標籤字典：出現在標題就抽出來當標籤 ─────────────────────
# 這份是一般描述性標籤（含官方轉職名稱與非官方叫法），跟上面的官方職業歸類分開處理。
TAG_DICT = [
    # 職業（官方轉職名稱 + 社群慣用叫法 + 韓服已上線但台版未開放的職業）
    "法師", "冰霜術士", "火焰術士", "電擊術士", "電擊魔法師",
    "戰士", "大劍戰士", "劍術士", "騎士",
    "弓手", "弩手", "長弓兵",
    "治癒師", "祭司", "修道士", "暗黑術士",
    "吟遊詩人", "樂師", "舞者",
    "盜賊", "格鬥家", "雙刀客", "刺客",
    "轉職", "技能", "配點", "天賦",
    # 副本/戰鬥
    "副本", "深淵", "王機制", "站位", "打法",
    # 新手
    "新手", "零課金", "練等", "路線", "規劃",
    # 活動
    "活動", "改版", "獎勵", "課金", "抽卡",
    # 裝備／符文／寶石（原本沒被挑出來的一群）
    "裝備", "強化", "符文", "寶石", "催化劑", "刻印",
    # 生活技能（製作、練等以外的日常培養）
    "生活技能", "製作", "打造", "採集",
    "寵物",
]


def _text_of(item: dict) -> str:
    """把可供比對的文字欄位串起來（標題權重最高）。"""
    return " ".join(
        str(item.get(k, "")) for k in ("title", "summary", "raw_tag")
    ).lower()


def classify_category(item: dict) -> str:
    """回傳四大分類之一。"""
    raw_tag = str(item.get("raw_tag", "")).strip("【】[]")
    if raw_tag in PREFIX_HINT and PREFIX_HINT[raw_tag]:
        return PREFIX_HINT[raw_tag]

    text = _text_of(item)
    for category, keywords in CATEGORY_RULES:
        if any(kw.lower() in text for kw in keywords):
            return category
    return DEFAULT_CATEGORY


def extract_tags(item: dict) -> list[str]:
    """從標題/摘要抽出已知標籤，去重並保留順序。"""
    text = _text_of(item)
    tags = []
    for tag in TAG_DICT:
        if tag.lower() in text and tag not in tags:
            tags.append(tag)
    # 官方職業歸類：命中官方名稱或其別名，一律補上官方名稱標籤，
    # 讓前端職業選單能用官方名稱篩到（同一篇可能同時有「法師」跟「魔法師」兩個標籤）。
    for official in OFFICIAL_CLASSES:
        if official.lower() in text and official not in tags:
            tags.append(official)
    for alias, official in CLASS_ALIASES.items():
        if alias.lower() in text and official not in tags:
            tags.append(official)
    # 韓服已上線、台版尚無公告日期的職業：歸進對應系列，並補上狀態標籤，
    # 讓玩家看得出這是「參考韓服，台版暫時玩不到」的內容。
    for alias, official in UPCOMING_CLASSES.items():
        if alias.lower() in text:
            if official not in tags:
                tags.append(official)
            if "尚未開放" not in tags:
                tags.append("尚未開放")
    return tags


def mark_featured(items: list[dict], top_ratio: float = 0.2) -> None:
    """
    就地標記精華：以互動分數排序，取前 top_ratio（至少 1 篇）為精華。
    互動分數 = 正規化(觀看/GP) + 正規化(回覆/留言)。
    用「相對排名」而非絕對門檻，避免因資料量或熱度基準變動而全有或全無。

    來源已經幫忙人工篩選過的資料（如巴哈精華區，見 scraper/bahamut_essence.py）
    會在產出時就把 is_featured 預先設成 True；這種「已知精華」不吃瀏覽數演算法
    （精華區文章本來就抓不到瀏覽/回覆數，套演算法只會全部落選），
    直接保留，只對其餘沒有預先標記的項目做正常排名。
    """
    if not items:
        return

    curated = [it for it in items if it.get("is_featured") is True]
    rest = [it for it in items if it.get("is_featured") is not True]

    def engagement(it: dict) -> float:
        views = float(it.get("views", 0) or 0)      # YouTube viewCount / 巴哈 GP
        replies = float(it.get("replies", 0) or 0)  # 回覆數 / 留言數
        # 取對數壓縮長尾，避免單一爆量影片吃掉所有名額
        import math
        return math.log1p(views) * 1.0 + math.log1p(replies) * 1.5

    ranked = sorted(rest, key=engagement, reverse=True)
    n_featured = max(1, round(len(rest) * top_ratio)) if rest else 0
    featured_ids = {id(it) for it in ranked[:n_featured]}
    for it in rest:
        it["is_featured"] = id(it) in featured_ids
    for it in curated:
        it["is_featured"] = True


def enrich(items: list[dict]) -> list[dict]:
    """對每筆資料補上 category / tags，再整批評精華。回傳同一批（就地）。"""
    for it in items:
        it["category"] = classify_category(it)
        it["tags"] = extract_tags(it)
    mark_featured(items)
    return items
