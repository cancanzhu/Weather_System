"""
地理工具模块
============
提供方位计算、天津影响判断、前倾/后倾判断等通用地理功能。
所有天气系统的追踪和报告都会用到。
"""
import numpy as np
import math
from typing import List, Tuple, Dict


def calculate_direction(from_lon: float, from_lat: float,
                        to_lon: float, to_lat: float) -> str:
    """
    计算从一个点到另一个点的8方位方向。

    Returns:
        str: 方向（北/东北/东/东南/南/西南/西/西北）
    """
    directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    dx = to_lon - from_lon
    dy = to_lat - from_lat
    angle = math.degrees(math.atan2(dy, dx))
    bearing = (90 - angle) % 360
    sector = int((bearing + 22.5) / 45) % 8
    return directions[sector]


def get_opposite_direction(direction: str) -> str:
    """获取相反方向"""
    opposites = {
        "北": "南", "东北": "西南", "东": "西", "东南": "西北",
        "南": "北", "西南": "东北", "西": "东", "西北": "东南",
    }
    return opposites.get(direction, direction)


def get_direction_from_vector(dx: float, dy: float) -> str:
    """根据位移向量计算方向"""
    directions = ["北", "东北", "东", "东南", "南", "西南", "西", "西北"]
    angle = math.degrees(math.atan2(dy, dx))
    bearing = (90 - angle) % 360
    sector = int((bearing + 22.5) / 45) % 8
    return directions[sector]


def calculate_center(points: List[List[float]]) -> Tuple[float, float]:
    """
    计算坐标点列表的重心。

    Args:
        points: [[lon, lat], ...]

    Returns:
        (center_lon, center_lat)
    """
    if not points:
        return (0.0, 0.0)
    coords = np.array(points)
    return (float(np.mean(coords[:, 0])), float(np.mean(coords[:, 1])))


def is_in_region(points: List[List[float]], region: Dict) -> bool:
    """
    判断坐标点列表中是否有任意一点在区域内。

    Args:
        points: [[lon, lat], ...]
        region: {"lon_min", "lon_max", "lat_min", "lat_max"}
    """
    for lon, lat in points:
        if (region["lon_min"] <= lon <= region["lon_max"] and
                region["lat_min"] <= lat <= region["lat_max"]):
            return True
    return False


def haversine_distance(lon1: float, lat1: float,
                       lon2: float, lat2: float) -> float:
    """
    计算两点间的球面距离（km）。
    """
    R = 6371
    lat1_r, lon1_r = np.radians(lat1), np.radians(lon1)
    lat2_r, lon2_r = np.radians(lat2), np.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1_r) * np.cos(lat2_r) * np.sin(dlon / 2) ** 2
    return R * 2 * np.arcsin(np.sqrt(a))


# def judge_trough_tilt(center_500: Tuple[float, float],
#                       center_lower: Tuple[float, float]) -> str:
#     """
#     判断槽线前倾/后倾。

#     规则: 低层槽线在500hPa西侧 → 前倾，东侧 → 后倾

#     Args:
#         center_500:  500hPa槽线重心 (lon, lat)
#         center_lower: 700/850hPa槽线重心 (lon, lat)

#     Returns:
#         "前倾" 或 "后倾"
#     """
#     return "前倾" if center_lower[0] < center_500[0] else "后倾"

def judge_trough_tilt(points_500, points_lower) -> str:
    """
    判断槽线前倾/后倾（在重叠纬度带上逐纬度比较两层槽线经度）。

    定义: 槽线随高度向西倾 → 后倾（高层在低层西侧，发展性槽）；
          槽线随高度向东倾 → 前倾（高层在低层东侧）。

    实现: 不再比较整条槽的重心经度（纬度范围不一致时会判错），
    而是在两条槽线共同覆盖的纬度区间内，按若干代表纬度分别比较
    500 槽与低层槽的经度，多数票决定倾向。

    Args:
        points_500:   500hPa 槽线坐标 [[lon, lat], ...]
        points_lower: 700/850hPa 槽线坐标 [[lon, lat], ...]

    Returns:
        "前倾"、"后倾" 或 "未知"（无重叠纬度带时）
    """
    import numpy as np

    p5 = np.asarray(points_500, dtype=float)
    pl = np.asarray(points_lower, dtype=float)
    if len(p5) < 2 or len(pl) < 2:
        return "未知"

    # 两条槽线共同覆盖的纬度区间
    lat_lo = max(p5[:, 1].min(), pl[:, 1].min())
    lat_hi = min(p5[:, 1].max(), pl[:, 1].max())
    if lat_hi <= lat_lo:
        # 纬度无重叠，无法在同纬度比较
        return "未知"

    # 在重叠带内取若干代表纬度，分别插值出两层槽的经度并比较
    sample_lats = np.linspace(lat_lo, lat_hi, 5)
    front = 0  # 前倾票（低层在 500 东侧）
    back = 0   # 后倾票（低层在 500 西侧）
    for lat in sample_lats:
        lon5 = _interp_lon_at_lat(p5, lat)
        lonl = _interp_lon_at_lat(pl, lat)
        if lon5 is None or lonl is None:
            continue
        if lonl < lon5:        # 低层在 500 西侧 → 后倾
            back += 1
        elif lonl > lon5:      # 低层在 500 东侧 → 前倾
            front += 1

    if front == 0 and back == 0:
        return "未知"
    return "前倾" if front > back else "后倾"


def _interp_lon_at_lat(points, lat):
    """
    给定槽线坐标 points([[lon,lat],...]) 和一个纬度 lat，
    返回该纬度处槽线的经度（线性插值）。槽线可能非单调，
    取第一段跨过该纬度的线段插值。lat 超出范围返回 None。
    """
    import numpy as np

    pts = np.asarray(points, dtype=float)
    lats = pts[:, 1]
    lons = pts[:, 0]
    if lat < lats.min() or lat > lats.max():
        return None
    # 找跨过 lat 的相邻点对
    for i in range(len(pts) - 1):
        la, lb = lats[i], lats[i + 1]
        if (la - lat) * (lb - lat) <= 0 and la != lb:
            t = (lat - la) / (lb - la)
            return float(lons[i] + t * (lons[i + 1] - lons[i]))
    return None


def calculate_impact_time(track_positions: List[Dict],
                          tianjin_range: Dict) -> str:
    """
    从追踪轨迹中找到第一个进入天津的时次。

    Args:
        track_positions: [{"time": datetime, "points": [...], ...}, ...]
        tianjin_range: {"lon_min", "lon_max", "lat_min", "lat_max"}

    Returns:
        影响时间描述字符串，如 "6月1日20时"
    """
    for pos in track_positions:
        points = pos.get("points", [])
        if isinstance(points, np.ndarray):
            points = points.tolist()
        for lon, lat in points:
            if (tianjin_range["lon_min"] <= lon <= tianjin_range["lon_max"] and
                    tianjin_range["lat_min"] <= lat <= tianjin_range["lat_max"]):
                fcst_time = pos.get("fcst_time")
                if fcst_time:
                    return f"{fcst_time.month}月{fcst_time.day}日{fcst_time.hour}时"
    return "未知时间"

def calculate_quadrant(center_lon: float, center_lat: float,
                       target_lon: float, target_lat: float) -> str:
    """
    计算目标点位于中心点的哪个象限。

    Args:
        center_lon, center_lat: 系统中心坐标
        target_lon, target_lat: 目标点坐标（如天津）

    Returns:
        "东北" / "东南" / "西南" / "西北"
    """
    if target_lon >= center_lon:
        if target_lat >= center_lat:
            return "东北"
        else:
            return "东南"
    else:
        if target_lat >= center_lat:
            return "西北"
        else:
            return "西南"