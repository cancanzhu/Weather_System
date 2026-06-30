"""
低涡追踪与分析
==============
封装低涡的追踪、实况-预报匹配、移动方向分析等全部逻辑。
main.py 只需调用 run() 即可获得分析结果。

与高空槽分析的区别：
    - 低涡是点特征，追踪器使用匈牙利算法
    - 在 700hPa 和 850hPa 两个层次独立追踪
    - 天津影响判断使用 150km 缓冲区
    - 无前倾/后倾分析
"""
import logging
import numpy as np
from typing import Dict, List, Tuple

from modules.tracking.vortex_tracker import VortexTracker
from utils.geo_utils import (
    get_direction_from_vector, get_opposite_direction, haversine_distance,
)
from config.settings import (
    TIANJIN_RANGE, VORTEX_MATCH_DISTANCE_THRESHOLD,
)

logger = logging.getLogger(__name__)


def run(
    forecast_data: Dict,
    fcst_detection_results: Dict,
    obs_detection_results: Dict,
) -> Tuple[List[Dict], Dict[int, VortexTracker], Dict[int, List[int]]]:
    """
    执行低涡追踪与分析的完整流程。

    在 700hPa 和 850hPa 两个层次独立追踪。

    Args:
        forecast_data:          预报数据字典
        fcst_detection_results: 预报识别结果
        obs_detection_results:  实况识别结果

    Returns:
        (vortex_analyses, trackers, tianjin_track_ids_by_level)
        - vortex_analyses:           分析结果列表
        - trackers:                  {level: VortexTracker}
        - tianjin_track_ids_by_level: {level: [track_id, ...]}
    """
    logger.info("开始低涡追踪...")

    tracking_levels = [700, 850]
    trackers = {}
    tianjin_track_ids_by_level = {}

    # ── 1. 按层次独立追踪 ──
    for level in tracking_levels:
        tracker = VortexTracker()

        # 获取该层次的预报时间键，按时间排序
        fcst_keys = [
            (tl, lv) for (tl, lv) in forecast_data.keys() if lv == level
        ]
        fcst_keys.sort(key=lambda x: forecast_data[x]["time"])

        for key in fcst_keys:
            data_dict = forecast_data[key]
            detection = fcst_detection_results.get(key, {})
            vortex_results = detection.get("低空低涡", [])

            if vortex_results:
                fh = data_dict.get("forecast_hour", 0)
                time_str = f".{fh:03d}"
                fcst_time = data_dict.get("time")
                tracker.update(vortex_results, time_str, fcst_time)

        trackers[level] = tracker
        tianjin_ids = tracker.get_tianjin_tracks(TIANJIN_RANGE)
        tianjin_track_ids_by_level[level] = tianjin_ids

        logger.info(f"  {level}hPa: 追踪到 {len(tracker.tracks)} 条轨迹, "
                    f"影响天津 {len(tianjin_ids)} 条")

    # ── 2. 实况-预报匹配 ──
    all_matched = {}  # {level: [(obs_item, track_id, distance), ...]}
    all_matched_track_ids = {}  # {level: set()}

    for level in tracking_levels:
        obs_vortices = _extract_obs_vortices(obs_detection_results, level)
        tracker = trackers[level]

        matched, matched_ids = _match_obs_with_forecast(
            obs_vortices, tracker
        )
        all_matched[level] = matched
        all_matched_track_ids[level] = matched_ids

        logger.info(f"  {level}hPa: 实况匹配 {len(matched)} 个")

    # ── 3. 分析 ──
    vortex_analyses = []
    vortex_num = 1

    for level in tracking_levels:
        tracker = trackers[level]
        tianjin_ids = tianjin_track_ids_by_level[level]
        matched_ids = all_matched_track_ids.get(level, set())

        # 已匹配且影响天津的
        for obs_item, track_id, distance in all_matched.get(level, []):
            if track_id not in tianjin_ids:
                continue

            from_dir, to_dir = _analyze_movement(tracker, track_id)
            impact_time = _calculate_impact_time(tracker, track_id)

            # 大模型获取位置描述
            from modules.llm.location_service import get_point_location
            geo = obs_item.get("geometry", {})
            location = get_point_location(geo["lon"], geo["lat"], "低涡")

            # 中心强度：实况低压符号(MICAPS14 code 61)不带数值，
            # 改用匹配到的预报轨迹首位置(≈+000h)的低压中心值
            first_v = tracker.tracks[track_id][0]
            strength = first_v.get("value", "未知")

            # 象限
            from utils.geo_utils import calculate_quadrant
            from config.settings import MAP_CONFIG
            first_v = tracker.tracks[track_id][0]
            quadrant = calculate_quadrant(
                first_v["lon"], first_v["lat"],
                MAP_CONFIG.tianjin_lon, MAP_CONFIG.tianjin_lat,
            )

            vortex_analyses.append({
                "vortex_num": vortex_num,
                "track_id": track_id,
                "level": level,
                "location": location,
                "strength": strength,
                "quadrant": quadrant,
                "from_dir": from_dir,
                "to_dir": to_dir,
                "impact_time": impact_time,
                "is_new": False,
            })
            vortex_num += 1
            
        # 新生低涡（影响天津但未与实况匹配）
        new_ids = [tid for tid in tianjin_ids if tid not in matched_ids]
        for track_id in new_ids:
            from_dir, to_dir = _analyze_movement(tracker, track_id)
            impact_time = _calculate_impact_time(tracker, track_id)

            from utils.geo_utils import calculate_quadrant
            from config.settings import MAP_CONFIG
            first_v = tracker.tracks[track_id][0]
            quadrant = calculate_quadrant(
                first_v["lon"], first_v["lat"],
                MAP_CONFIG.tianjin_lon, MAP_CONFIG.tianjin_lat,
            )

            vortex_analyses.append({
                "vortex_num": vortex_num,
                "track_id": track_id,
                "level": level,
                "location": "新生成",
                "strength": "未知",
                "quadrant": quadrant,
                "from_dir": from_dir,
                "to_dir": to_dir,
                "impact_time": impact_time,
                "is_new": True,
            })
            vortex_num += 1

    # 打印分析结果
    logger.info(f"低涡分析完成: {len(vortex_analyses)} 个低涡")
    for a in vortex_analyses:
        prefix = "新生低涡" if a["is_new"] else "低涡"
        logger.info(f"  {prefix}{a['vortex_num']} ({a['level']}hPa): "
                    f"{a['from_dir']}→{a['to_dir']}, "
                    f"影响时间={a['impact_time']}")

    return vortex_analyses, trackers, tianjin_track_ids_by_level


def _extract_obs_vortices(obs_detection_results: Dict, level: int) -> List[Dict]:
    """从实况识别结果中提取指定层次的低涡"""
    obs_vortices = []
    for (tl, lv), detection in obs_detection_results.items():
        if lv == level and "低空低涡" in detection:
            for item in detection["低空低涡"]:
                geo = item.get("geometry", {})
                if geo.get("type") == "point":
                    obs_vortices.append(item)
    return obs_vortices


def _match_obs_with_forecast(
    obs_vortices: List[Dict], tracker: VortexTracker
) -> Tuple[List, set]:
    """实况低涡与预报追踪轨迹匹配（全局一对一）"""
    # 预提取各轨迹首位置（正常应为 +000h 时次）
    track_firsts = []
    for track_id, vortices in tracker.tracks.items():
        if not vortices:
            continue
        first = vortices[0]
        if first.get("time_str") != ".000":
            logger.warning(
                f"低涡轨迹{track_id}首位置非+000h"
                f"({first.get('time_str')})，匹配距离可能偏移"
            )
        track_firsts.append((track_id, first))

    # 1. 收集所有阈值内的 (距离, obs序号, track_id) 候选
    candidates = []
    for oi, obs_item in enumerate(obs_vortices):
        geo = obs_item["geometry"]
        obs_lon, obs_lat = geo["lon"], geo["lat"]
        for track_id, first in track_firsts:
            dist = haversine_distance(
                obs_lon, obs_lat, first["lon"], first["lat"]
            )
            if dist <= VORTEX_MATCH_DISTANCE_THRESHOLD:
                candidates.append((dist, oi, track_id))

    # 2. 按距离从近到远贪心一对一分配
    candidates.sort()
    matched_pairs = []
    matched_track_ids = set()
    used_obs = set()
    for dist, oi, track_id in candidates:
        if oi in used_obs or track_id in matched_track_ids:
            continue
        matched_pairs.append((obs_vortices[oi], track_id, dist))
        matched_track_ids.add(track_id)
        used_obs.add(oi)

    return matched_pairs, matched_track_ids


def _analyze_movement(tracker: VortexTracker, track_id: int) -> Tuple[str, str]:
    """分析轨迹移动方向"""
    vortices = tracker.tracks.get(track_id, [])
    if len(vortices) >= 2:
        first = vortices[0]
        last = vortices[-1]
        dx = last["lon"] - first["lon"]
        dy = last["lat"] - first["lat"]
        to_dir = get_direction_from_vector(dx, dy)
        from_dir = get_opposite_direction(to_dir)
        return from_dir, to_dir
    return "未知", "未知"


def _calculate_impact_time(tracker: VortexTracker, track_id: int) -> str:
    """计算首次影响天津的时间"""
    from config.settings import VORTEX_TIANJIN_IMPACT_DISTANCE

    vortices = tracker.tracks.get(track_id, [])
    for v in vortices:
        dist = VortexTracker._point_to_rect_distance(
            v["lon"], v["lat"], TIANJIN_RANGE
        )
        if dist <= VORTEX_TIANJIN_IMPACT_DISTANCE:
            fcst_time = v.get("fcst_time")
            if fcst_time:
                return f"{fcst_time.month}月{fcst_time.day}日{fcst_time.hour}时"
    return "未知时间"