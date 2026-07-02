"""
低空急流分析（850hPa）
======================
判断 850hPa 低空急流是否影响天津，并给出文字描述与可视化所需的急流集合。

影响判据（两者同时满足）：
    1. 距离：急流轴线到天津矩形(TIANJIN_RANGE)的最近距离 ≤ JET_AFFECT_DISTANCE_KM
    2. 辐合侧：天津位于急流轴的辐合一侧（默认沿流向左侧，见 JET_CONVERGENCE_SIDE）

措辞判据（在"影响"的前提下细分）：
    - 出口端风向"对着"天津矩形（夹角 ≤ JET_EXIT_ANGLE_MAX）→ "处于低空急流出口区"
    - 否则                                              → "受低空急流边缘影响"

第一个影响时次：先实况，再按预报时效从小到大。只可视化该时次的急流。

与副高分析一致：不做轨迹追踪，逐时次独立判断。
预报急流以 graphy_raw 存储，需从 graphy["features"][id]["axes"]["point"] 抽轴线；
实况急流以 jet_lines 存储，直接取 lines。
"""
import logging
import numpy as np
from typing import Dict, List, Optional, Tuple

from config.settings import (
    TIANJIN_RANGE, MAP_CONFIG,
    JET_AFFECT_DISTANCE_KM,
    JET_EXIT_ANGLE_MAX,
    JET_CONVERGENCE_SIDE,
)
from utils.geo_utils import haversine_distance

logger = logging.getLogger(__name__)

JET_LEVEL = 850
TIANJIN_POINT = (MAP_CONFIG.tianjin_lon, MAP_CONFIG.tianjin_lat)  # 天津城区点


# ────────────────────────────────────────────────────────────────
# 入口
# ────────────────────────────────────────────────────────────────
def run(
    forecast_data: Dict,
    fcst_detection_results: Dict,
    obs_detection_results: Dict,
    obs_data: Dict = None,
) -> Dict:
    """
    执行低空急流分析。

    Returns:
        {
          "is_affecting":   bool,                 # 是否存在影响天津的时次
          "first_source":   "obs"/"fcst"/None,    # 第一个影响时次来源
          "wording":        str/None,             # 出口区 / 边缘 措辞
          "impact_time":    str/None,             # 预报时次的时间描述
          "forecast_hour":  int/None,
          "viz": {                                # 第一个影响时次要画的急流集合
              "source": "obs"/"fcst",
              "level": 850,
              "time_label": str,
              "jets": [{"axis": [[lon,lat],...], "affecting": bool}],
          } or None,
        }
    """
    logger.info("开始低空急流分析...")
    rect = TIANJIN_RANGE

    # ── 实况时次 ──
    obs_step = _analyze_obs(obs_detection_results, rect)

    # ── 预报各时次（按时效升序）──
    fcst_steps = _analyze_forecast(forecast_data, fcst_detection_results, rect)

    # ── 确定第一个影响时次：先实况，再预报 ──
    result = {
        "is_affecting": False,
        "first_source": None,
        "wording": None,
        "impact_time": None,
        "forecast_hour": None,
        "viz": None,
    }

    if obs_step and obs_step["any_affecting"]:
        result.update({
            "is_affecting": True,
            "first_source": "obs",
            "wording": _wording(obs_step),
            "viz": {
                "source": "obs",
                "level": JET_LEVEL,
                "time_label": obs_step["time_label"],
                "jets": obs_step["jets"],
            },
        })
        logger.info(f"  实况 850hPa 急流影响天津：{result['wording']}")
        return result

    for step in fcst_steps:
        if step["any_affecting"]:
            result.update({
                "is_affecting": True,
                "first_source": "fcst",
                "wording": _wording(step),
                "impact_time": step["time_desc"],
                "forecast_hour": step["forecast_hour"],
                "viz": {
                    "source": "fcst",
                    "level": JET_LEVEL,
                    "time_label": step["time_label"],
                    "jets": step["jets"],
                },
            })
            logger.info(f"  预报 +{step['forecast_hour']:03d}h（{step['time_desc']}）"
                        f"850hPa 急流影响天津：{result['wording']}")
            return result

    logger.info("  低空急流未影响天津")
    return result


def _wording(step: Dict) -> str:
    """根据该时次影响急流是否有出口对着天津，给出措辞。"""
    points_at = any(j["affecting"] and j["points_at"] for j in step["jets"])
    return "处于低空急流出口区" if points_at else "受低空急流边缘影响"


# ────────────────────────────────────────────────────────────────
# 逐时次分析
# ────────────────────────────────────────────────────────────────
def _analyze_obs(obs_detection_results: Dict, rect: Dict) -> Optional[Dict]:
    for (tl, lv), detection in obs_detection_results.items():
        if lv != JET_LEVEL:
            continue
        step = _analyze_step(detection, rect, tl)
        if step["jets"]:
            return step
    return None


def _analyze_forecast(forecast_data: Dict, fcst_detection_results: Dict,
                      rect: Dict) -> List[Dict]:
    keys = [(tl, lv) for (tl, lv) in forecast_data.keys() if lv == JET_LEVEL]
    keys.sort(key=lambda k: forecast_data[k]["time"])

    steps = []
    for key in keys:
        data_dict = forecast_data[key]
        fh = data_dict.get("forecast_hour", 0)
        fcst_time = data_dict.get("time")
        detection = fcst_detection_results.get(key, {})

        step = _analyze_step(detection, rect, key[0])
        step["forecast_hour"] = fh
        step["time_desc"] = (
            f"{fcst_time.month}月{fcst_time.day}日{fcst_time.hour}时"
            if fcst_time else "未知时间"
        )
        steps.append(step)
        logger.debug(f"  +{fh:03d}h: 急流 {len(step['jets'])} 条 "
                     f"{'影响' if step['any_affecting'] else '未影响'}")
    return steps


def _analyze_step(detection: Dict, rect: Dict, time_label: str) -> Dict:
    """对单个时次的 850hPa 急流逐条判断。"""
    jets = []
    for item in detection.get("低空急流", []):
        for axis in _extract_jet_axes(item.get("geometry", {})):
            affecting, points_at = _judge_jet(axis, rect)
            jets.append({
                "axis": axis.tolist(),
                "affecting": affecting,
                "points_at": points_at,
            })
    return {
        "time_label": time_label,
        "jets": jets,
        "any_affecting": any(j["affecting"] for j in jets),
    }


# ────────────────────────────────────────────────────────────────
# 几何工具
# ────────────────────────────────────────────────────────────────
def _extract_jet_axes(geometry: Dict) -> List[np.ndarray]:
    """从急流 geometry 提取轴线坐标列表（统一 obs/fcst）。"""
    gtype = geometry.get("type")
    axes_list = []

    if gtype == "jet_lines":                       # 实况
        for line in geometry.get("lines", []):
            pts = np.asarray(line, dtype=float)
            if len(pts) >= 2:
                axes_list.append(pts[:, :2])

    elif gtype == "graphy_raw":                    # 预报
        graphy = geometry.get("graphy") or {}
        features = graphy.get("features", {}) if isinstance(graphy, dict) else {}
        for _fid, feat in features.items():
            pts = np.asarray((feat.get("axes", {}) or {}).get("point", []),
                             dtype=float)
            if len(pts) >= 2:
                axes_list.append(pts[:, :2])

    return axes_list


def _orient_downwind(axis: np.ndarray) -> np.ndarray:
    """
    把急流轴定向为"入口→出口"。
    only_south_jet 下急流为偏南气流，下游(出口)在偏北端，
    故按纬度升序定向：axis[0]=入口(南)，axis[-1]=出口(北)。
    """
    return axis if axis[-1, 1] >= axis[0, 1] else axis[::-1]


def _km_vec(p_from, p_to) -> np.ndarray:
    """两经纬度点之间的近似平面向量(km)，东西方向按纬度做 cos 修正。"""
    lat0 = np.radians((p_from[1] + p_to[1]) / 2.0)
    dx = (p_to[0] - p_from[0]) * 111.0 * np.cos(lat0)
    dy = (p_to[1] - p_from[1]) * 111.0
    return np.array([dx, dy])


def _nearest_point_on_rect(lon: float, lat: float, rect: Dict) -> Tuple[float, float]:
    """天津矩形上离给定点最近的点（点在矩形内则返回自身）。"""
    clon = min(max(lon, rect["lon_min"]), rect["lon_max"])
    clat = min(max(lat, rect["lat_min"]), rect["lat_max"])
    return clon, clat


def _axis_min_dist_to_rect(axis: np.ndarray, rect: Dict) -> float:
    """急流轴线各点到天津矩形最近距离(km)。"""
    dmin = float("inf")
    for lon, lat in axis:
        clon, clat = _nearest_point_on_rect(lon, lat, rect)
        d = haversine_distance(lon, lat, clon, clat)
        if d < dmin:
            dmin = d
    return dmin


def _rect_center(rect: Dict) -> Tuple[float, float]:
    return ((rect["lon_min"] + rect["lon_max"]) / 2.0,
            (rect["lat_min"] + rect["lat_max"]) / 2.0)


def _on_convergence_side(axis: np.ndarray, rect: Dict) -> bool:
    """
    天津是否位于急流轴的辐合侧。
    默认辐合侧 = 沿流向左侧（北半球气旋式切变侧）。
    用 流向向量 × 指向天津向量 的 z 分量符号判断：>0 为左侧。
    """
    flow = _km_vec(axis[0], axis[-1])              # 入口→出口 的流向
    if np.linalg.norm(flow) < 1e-6:
        return False
    # 以离天津最近的轴点为基准，指向天津城区点（不再用大矩形中心，避免偏西失真）
    tj = TIANJIN_POINT
    base_idx = int(np.argmin([haversine_distance(p[0], p[1], tj[0], tj[1])
                              for p in axis]))
    to_tj = _km_vec(axis[base_idx], tj)
    cross_z = flow[0] * to_tj[1] - flow[1] * to_tj[0]
    left = cross_z > 0
    return left if JET_CONVERGENCE_SIDE == "left" else (not left)


def _exit_points_at_rect(axis: np.ndarray, rect: Dict) -> bool:
    """
    出口端风向是否"正对着"天津（夹角 ≤ JET_EXIT_ANGLE_MAX）。
    出口端 = 定向后轴线末端；出口风向 = 末段指向（顺流向外）。
    参照方向取"出口端 → 天津城区点"，不再用"矩形最近点"——
    否则出口落在矩形内时会退化为零向量、被误判为对着。
    """
    exit_pt = axis[-1]
    exit_dir = _km_vec(axis[-2], axis[-1])         # 出口处的风向
    if np.linalg.norm(exit_dir) < 1e-6:
        return False
    to_tj = _km_vec(exit_pt, TIANJIN_POINT)        # 出口端指向天津
    if np.linalg.norm(to_tj) < 1e-6:
        return True
    cosang = float(np.dot(exit_dir, to_tj) /
                   (np.linalg.norm(exit_dir) * np.linalg.norm(to_tj)))
    cosang = max(-1.0, min(1.0, cosang))
    angle = np.degrees(np.arccos(cosang))
    return angle <= JET_EXIT_ANGLE_MAX


def _judge_jet(axis: np.ndarray, rect: Dict) -> Tuple[bool, bool]:
    """
    返回 (是否影响天津, 出口是否对着天津)。
    影响 = 距离≤阈值 且（出口正对天津 或 天津在辐合侧），二者其一即可。
    """
    axis = _orient_downwind(np.asarray(axis, dtype=float))
    if _axis_min_dist_to_rect(axis, rect) > JET_AFFECT_DISTANCE_KM:
        return False, False
    points_at = _exit_points_at_rect(axis, rect)   # 出口正对天津(以天津点为靶)
    on_side = _on_convergence_side(axis, rect)     # 天津在辐合(左)侧
    affecting = points_at or on_side               # 出口对着 或 侧翼辐合，其一即影响
    return affecting, points_at