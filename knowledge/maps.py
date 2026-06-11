# -*- coding: utf-8 -*-
"""
Sky Companion - 地图知识库
光遇全地图数据
"""

MAPS = {
    "晨岛": {
        "description": "新手地图，天空王国的起点，广阔草地和遗迹",
        "difficulty": "简单",
        "spirits": ["引导先知", "筑巢工匠", "浮空旅人", "水面先知", "云野贤者", "暴风先知", "祈祷旅人", "狐狸面具"],
        "features": ["蝴蝶引导", "飞行教学", "神庙", "星图石板"],
        "collectibles": ["光之翼（x5）", "蜡烛堆"],
        "hidden_areas": ["云洞", "高塔", "浮空岛"],
    },
    "云野": {
        "description": "云海覆盖的广阔地图，有大量浮空岛屿",
        "difficulty": "简单",
        "spirits": ["鼓掌农夫", "笑脸矿工", "挥手旅人", "旋转舞者", "感谢舞者", "哈欠矿工", "擦汗矿工", "捉迷藏"],
        "features": ["蝴蝶群", "幽光山洞", "神庙", "三塔试炼"],
        "collectibles": ["光之翼（x8）", "蜡烛堆"],
        "hidden_areas": ["幽光山洞", "圣岛", "八人门"],
    },
    "雨林": {
        "description": "持续下雨的茂密森林地图，有能量恢复点",
        "difficulty": "中等",
        "spirits": ["发怒矿工", "哭泣矿工", "惊恐矿工", "悲伤矿工", "祈祷矿工", "呕吐矿工", "爱心矿工", "捉迷藏"],
        "features": ["雨林亭子", "树屋", "神庙", "荧光森林"],
        "collectibles": ["光之翼（x12）", "蜡烛堆"],
        "hidden_areas": ["隐藏图", "树屋", "雨林神殿"],
    },
    "霞谷": {
        "description": "日落时分的峡谷，有滑雪和滑行赛道",
        "difficulty": "中等",
        "spirits": ["鼓掌旅人", "鞠躬旅人", "倒立旅人", "叉腰旅人", "磕头旅人", "电摇旅人", "挥手旅人", "敬礼旅人"],
        "features": ["滑雪赛道", "滑行赛道", "神庙", "落日竞技场"],
        "collectibles": ["光之翼（x7）", "蜡烛堆"],
        "hidden_areas": ["飞行赛道终点", "迷宫"],
    },
    "墓土": {
        "description": "阴暗的沙漠地图，有螃蟹和冥龙",
        "difficulty": "困难",
        "spirits": ["恐惧矿工", "哆嗦矿工", "害怕矿工", "召唤矿工", "鞠躬矿工", "抱头矿工"],
        "features": ["螃蟹", "冥龙", "沉船", "神庙"],
        "collectibles": ["光之翼（x14）", "蜡烛堆"],
        "hidden_areas": ["四龙图", "沉船图", "黑水港湾"],
    },
    "禁阁": {
        "description": "高耸的塔楼地图，需要多人合作",
        "difficulty": "困难",
        "spirits": ["托举工匠", "打气工匠", "沉思工匠", "推搡工匠", "招手工匠", "祈祷工匠"],
        "features": ["电梯", "四人门", "八人门", "神庙"],
        "collectibles": ["光之翼（x5）", "蜡烛堆"],
        "hidden_areas": ["顶层花园"],
    },
    "暴风眼": {
        "description": "最终的挑战之地，风险极高",
        "difficulty": "极难",
        "spirits": [],
        "features": ["碎石雨", "冥龙集群", "暴风眼神殿"],
        "collectibles": ["光之翼"],
        "hidden_areas": [],
    },
    "伊甸": {
        "description": "献祭地图，重生之路",
        "difficulty": "极难",
        "spirits": [],
        "features": ["献祭", "重生之路", "星河"],
        "collectibles": ["升华蜡烛"],
        "hidden_areas": [],
    },
}

MAP_CONNECTIONS = {
    "晨岛": ["云野"],
    "云野": ["晨岛", "雨林", "墓土"],
    "雨林": ["云野", "霞谷"],
    "霞谷": ["雨林", "墓土"],
    "墓土": ["云野", "霞谷", "禁阁"],
    "禁阁": ["墓土", "暴风眼"],
    "暴风眼": ["禁阁", "伊甸"],
    "伊甸": ["暴风眼"],
}

def get_map_info(map_name):
    """获取指定地图的信息"""
    return MAPS.get(map_name, None)

def get_all_maps():
    """获取所有地图名称"""
    return list(MAPS.keys())

def get_connected_maps(map_name):
    """获取与指定地图相连的地图"""
    return MAP_CONNECTIONS.get(map_name, [])

def get_spirits_by_map(map_name):
    """获取某地图的先祖列表"""
    info = MAPS.get(map_name, {})
    return info.get("spirits", [])
