"""Sky Companion - 画面视觉分析
纯 numpy + Pillow，无需 OpenCV
检测：人形、亮度变化、烛光、场景切换
"""

import numpy as np
from PIL import Image
from config import SCREENSHOT_DIR, TEMPLATE_MATCH_THRESHOLD

# 烛光颜色范围 (HSV)
CANDLE_LOWER = np.array([15, 50, 200])
CANDLE_UPPER = np.array([35, 255, 255])

# 人形/白点的亮度阈值
PLAYER_BRIGHT_THRESHOLD = 220

# 天空/云的颜色范围
SKY_LOWER = np.array([90, 20, 180])
SKY_UPPER = np.array([130, 80, 255])


def pil_to_np(pil_img):
    """PIL Image → numpy array"""
    return np.array(pil_img)


def np_to_pil(np_img):
    """numpy array → PIL Image"""
    return Image.fromarray(np_img)


def rgb_to_hsv(rgb):
    """RGB numpy → HSV"""
    from PIL import Image
    img = Image.fromarray(rgb)
    return np.array(img.convert("HSV"))


def detect_players(image, min_brightness=PLAYER_BRIGHT_THRESHOLD, min_area=20):
    """检测画面中的发光玩家/光崽（纯numpy实现，不需要scipy）"""
    if isinstance(image, Image.Image):
        image = pil_to_np(image)
    
    gray = np.mean(image, axis=2)
    bright = (gray > min_brightness).astype(np.uint8)
    
    # 纯numpy连通域分析（2-pass算法简化版）
    h, w = bright.shape
    labeled = np.zeros((h, w), dtype=np.int32)
    label = 1
    equivalence = {}
    
    # First pass
    for y in range(h):
        for x in range(w):
            if bright[y, x] == 0:
                continue
            neighbors = []
            if y > 0 and labeled[y-1, x] > 0:
                neighbors.append(labeled[y-1, x])
            if x > 0 and labeled[y, x-1] > 0:
                neighbors.append(labeled[y, x-1])
            if not neighbors:
                labeled[y, x] = label
                equivalence[label] = label
                label += 1
            else:
                min_n = min(neighbors)
                labeled[y, x] = min_n
                for n in neighbors:
                    if n != min_n:
                        equivalence[n] = min_n
    
    # Second pass - resolve equivalences
    for y in range(h):
        for x in range(w):
            l = labeled[y, x]
            if l > 0:
                while equivalence.get(l, l) != l:
                    l = equivalence[l]
                labeled[y, x] = l
    
    # Extract connected components
    players = []
    for lbl in range(1, label):
        ys, xs = np.where(labeled == lbl)
        area = len(ys)
        if area >= min_area:
            players.append({
                "x": int(np.min(xs)),
                "y": int(np.min(ys)),
                "width": int(np.max(xs) - np.min(xs)),
                "height": int(np.max(ys) - np.min(ys)),
                "center_x": int(np.mean(xs)),
                "center_y": int(np.mean(ys)),
                "area": area,
            })
    
    return players


def detect_candles(image):
    """检测蜡烛/烛光（暖黄色高亮区域）"""
    if isinstance(image, Image.Image):
        image = pil_to_np(image)
    
    try:
        hsv = rgb_to_hsv(image)
        mask = np.all([
            hsv[:,:,0] >= CANDLE_LOWER[0], hsv[:,:,0] <= CANDLE_UPPER[0],
            hsv[:,:,1] >= CANDLE_LOWER[1], hsv[:,:,1] <= CANDLE_UPPER[1],
            hsv[:,:,2] >= CANDLE_LOWER[2], hsv[:,:,2] <= CANDLE_UPPER[2],
        ], axis=0)
        return int(np.sum(mask))
    except:
        return 0


def detect_scene_change(current, previous, threshold=0.15):
    """检测画面是否发生明显变化（场景切换/移动中）"""
    if previous is None:
        return False
    
    if isinstance(current, Image.Image):
        current = pil_to_np(current)
    if isinstance(previous, Image.Image):
        previous = pil_to_np(previous)
    
    # 缩放到小尺寸再比较
    from PIL import Image
    c = Image.fromarray(current).resize((64, 48))
    p = Image.fromarray(previous).resize((64, 48))
    
    diff = np.abs(np.array(c).astype(float) - np.array(p).astype(float))
    change_ratio = np.mean(diff) / 255.0
    
    return change_ratio > threshold, change_ratio


def estimate_sky_lightness(image):
    """估计天空亮度（用于判断室内/室外/夜晚）"""
    if isinstance(image, Image.Image):
        image = pil_to_np(image)
    
    # 取画面上半部分
    top_half = image[:image.shape[0]//2, :, :]
    return float(np.mean(top_half))


def describe_scene(image):
    """生成画面文字描述（给 AI 看）"""
    if image is None:
        return "（暂无画面信息）"
    
    players = detect_players(image)
    candles = detect_candles(image)
    brightness = estimate_sky_lightness(image)
    
    desc = ""
    if brightness > 180:
        desc += "室外，明亮"
    elif brightness > 100:
        desc += "半明亮环境"
    else:
        desc += "较暗环境"
    
    if candles > 500:
        desc += "，有蜡烛/光源"
    
    if players:
        closest = min(players, key=lambda p: p["center_y"])
        desc += f"，附近有光崽（距离：{'近' if closest['area'] > 100 else '中等' if closest['area'] > 50 else '远'}）"
        desc += f"，共检测到 {len(players)} 个光崽"
    else:
        desc += "，周围没有其他光崽"
    
    return desc
