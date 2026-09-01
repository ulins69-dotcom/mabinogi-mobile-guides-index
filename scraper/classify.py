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
"""

from __future__ import annotations

# ── 分類關鍵字表（由上而下比對，先命中者為準）────────────────
CATEGORY_RULES = [
    ("新手指南", ["新手", "入門", "前期", "萌新", "零課", "練等", "練功", "路線", "配裝入門", "該做什麼"]),
    ("副本攻略", ["副本", "地城", "深淵", "王", "boss", "首領", "機制", "打法", "團隊", "攻堅", "討伐"]),
    ("職業解析", ["職業", "轉職", "法師", "戰士", "弓手", "弓箭", "刺客", "牧師", "技能", "配點", "天賦", "加點", "輸出手法", "流派"]),
    ("活動情報", ["活動", "改版", "更新", "版本", "獎勵", "情報", "公告", "限時", "簽到", "抽獎", "禮包", "序號"]),
]
DEFAULT_CATEGORY = "新手指南"  # 都沒命中時的保底分類

# 標題若帶巴哈前綴，優先採用其暗示
PREFIX_HINT = {
    "攻略": None,      # 攻略是通用前綴，交給關鍵字判斷
    "情報": "活動情報",
    "心得": None,
    "討論": None,
}

# 官方六大職業系列（見 tw.nexon.com/mabinogimobile/home/info/class）。
# 前端「職業」選單只認這六個官方名稱（見 index.html CLASS_TAGS，須與此同步）。
OFFICIAL_CLASSES = ["戰士", "弓手", "魔法師", "治癒師", "吟遊詩人", "盜賊"]

# 社群慣用的非官方叫法 → 對應官方系列。只收錄有把握的對應，
# 不確定屬於哪個官方系列的字眼（如「刺客」「雙刀客」「格鬥家」）
# 一律不歸類，留在下面 TAG_DICT 當一般標籤就好，不硬塞進職業選單。
CLASS_ALIASES = {
    "法師": "魔法師", "冰霜術士": "魔法師", "電擊術士": "魔法師",
    "樂師": "吟遊詩人",
    "弩手": "弓手",
}

# ── 標籤字典：出現在標題就抽出來當標籤 ─────────────────────
# 這份是一般描述性標籤（含非官方職業叫法），跟上面的官方職業歸類分開處理。
TAG_DICT = [
    # 職業
    "法師", "冰霜術士", "電擊術士", "戰士", "大劍戰士", "弓手", "弩手",
    "刺客", "雙刀客", "牧師", "治癒師", "樂師", "格鬥家",
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
    return tags


def mark_featured(items: list[dict], top_ratio: float = 0.2) -> None:
    """
    就地標記精華：以互動分數排序，取前 top_ratio（至少 1 篇）為精華。
    互動分數 = 正規化(觀看/GP) + 正規化(回覆/留言)。
    用「相對排名」而非絕對門檻，避免因資料量或熱度基準變動而全有或全無。
    """
    if not items:
        return

    def engagement(it: dict) -> float:
        views = float(it.get("views", 0) or 0)      # YouTube viewCount / 巴哈 GP
        replies = float(it.get("replies", 0) or 0)  # 回覆數 / 留言數
        # 取對數壓縮長尾，避免單一爆量影片吃掉所有名額
        import math
        return math.log1p(views) * 1.0 + math.log1p(replies) * 1.5

    ranked = sorted(items, key=engagement, reverse=True)
    n_featured = max(1, round(len(ranked) * top_ratio))
    featured_ids = {id(it) for it in ranked[:n_featured]}
    for it in items:
        it["is_featured"] = id(it) in featured_ids


def enrich(items: list[dict]) -> list[dict]:
    """對每筆資料補上 category / tags，再整批評精華。回傳同一批（就地）。"""
    for it in items:
        it["category"] = classify_category(it)
        it["tags"] = extract_tags(it)
    mark_featured(items)
    return items
