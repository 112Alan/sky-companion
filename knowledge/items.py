# -*- coding: utf-8 -*-
"""
Sky Companion - 物品与任务知识库
"""

ITEMS = {
    "蜡烛": {"type": "货币", "acquisition": "跑图收集、每日任务", "usage": "兑换先祖物品、好友交互"},
    "爱心": {"type": "货币", "acquisition": "好友赠送、先祖兑换", "usage": "兑换高级装扮"},
    "升华蜡烛": {"type": "货币", "acquisition": "伊甸献祭", "usage": "解锁先祖节点、永久光翼"},
    "光之翼": {"type": "能力", "acquisition": "各地图收集", "usage": "提升飞行等级"},
    "蜡烛堆": {"type": "资源", "acquisition": "各地图固定位置", "usage": "收集蜡烛"},
    "季蜡": {"type": "货币", "acquisition": "季节任务", "usage": "兑换季节物品"},
    "魔法": {"type": "消耗品", "acquisition": "魔法工坊、先祖", "usage": "临时效果"},
}

DAILY_TASKS = [
    "在云野向一位朋友鞠躬",
    "在雨林追逐散落的星光",
    "在霞谷点燃蜡烛堆",
    "在禁阁与好友一起冥想",
    "在墓土拯救被困的遥鲲",
    "收集30根蜡烛",
    "送给好友5颗爱心",
]

SEASONS = {
    "追光季": {"status": "常驻", "features": ["季节先祖", "季节项链"]},
    "归属季": {"status": "常驻", "features": ["季节先祖", "季节家具"]},
    "音韵季": {"status": "常驻", "features": ["音乐相关"]},
}

def get_item_info(item_name):
    """获取物品信息"""
    return ITEMS.get(item_name, None)

def get_daily_task(today_index=None):
    """获取每日任务"""
    import datetime
    if today_index is None:
        today_index = datetime.date.today().day % len(DAILY_TASKS)
    return DAILY_TASKS[today_index % len(DAILY_TASKS)]

def get_all_tasks():
    """获取所有每日任务"""
    return DAILY_TASKS.copy()
