# -*- coding: utf-8 -*-
"""
Sky Companion - 先祖与动作知识库
"""

SPIRITS = {
    "引导先知": {
        "map": "晨岛", "emote": "指路", "type": "普通", "season": "常驻",
        "cost": {"蜡烛": 5, "爱心": 3},
    },
    "鼓掌农夫": {
        "map": "云野", "emote": "鼓掌", "type": "普通", "season": "常驻",
        "cost": {"蜡烛": 5, "爱心": 3},
    },
    "笑脸矿工": {
        "map": "云野", "emote": "笑脸", "type": "普通", "season": "常驻",
        "cost": {"蜡烛": 3, "爱心": 2},
    },
    "挥手旅人": {
        "map": "云野", "emote": "挥手", "type": "普通", "season": "常驻",
        "cost": {"蜡烛": 5, "爱心": 3},
    },
    "发怒矿工": {
        "map": "雨林", "emote": "发怒", "type": "普通", "season": "常驻",
        "cost": {"蜡烛": 5, "爱心": 3},
    },
    "哭泣矿工": {
        "map": "雨林", "emote": "哭泣", "type": "普通", "season": "常驻",
        "cost": {"蜡烛": 5, "爱心": 3},
    },
    "鞠躬旅人": {
        "map": "霞谷", "emote": "鞠躬", "type": "普通", "season": "常驻",
        "cost": {"蜡烛": 5, "爱心": 3},
    },
    "恐惧矿工": {
        "map": "墓土", "emote": "恐惧", "type": "普通", "season": "常驻",
        "cost": {"蜡烛": 5, "爱心": 3},
    },
    "托举工匠": {
        "map": "禁阁", "emote": "托举", "type": "普通", "season": "常驻",
        "cost": {"蜡烛": 5, "爱心": 3},
    },
}

EMOTE_MAP = {
    "指路": "引导先知", "鼓掌": "鼓掌农夫", "笑脸": "笑脸矿工",
    "挥手": "挥手旅人", "发怒": "发怒矿工", "哭泣": "哭泣矿工",
    "鞠躬": "鞠躬旅人", "恐惧": "恐惧矿工", "托举": "托举工匠",
    "点头": "通用", "坐下": "通用", "大叫": "通用",
    "牵手": "通用", "拥抱": "通用",
}

def get_spirit_info(name):
    """获取先祖信息"""
    return SPIRITS.get(name, None)

def search_spirit(query):
    """搜索先祖"""
    results = []
    for name, info in SPIRITS.items():
        if query in name or query in info.get("map", "") or query in info.get("emote", ""):
            results.append({name: info})
    return results

def find_spirit_by_emote(emote_name):
    """通过动作名查找先祖"""
    spirit_name = EMOTE_MAP.get(emote_name)
    if spirit_name and spirit_name in SPIRITS:
        return {spirit_name: SPIRITS[spirit_name]}
    return None
