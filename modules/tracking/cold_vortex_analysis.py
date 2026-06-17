"""
冷涡追踪与分析
==============
封装冷涡的完整分析流程：
    1. 从 500hPa GH 识别低压中心，从 T 识别冷中心
    2. 分别追踪低压和冷中心
    3. 配合判断：低压+冷中心距离≤300km → 冷涡
    4. 分类：东北冷涡 / 蒙古冷涡
    5. 影响天津判断（大区域）
    6. 实况-预报匹配
    7. 生成分析结果

与高空槽/低涡追踪的区别：
    - 冷涡是两个场（GH+T）的复合特征
    - 追踪分别对低压和冷中心进行
    - 配合判断在追踪之后
    - 影响判断使用大区域而非缓冲距离
"""
import logging
import numpy as np
from typing import Dict, List, Tuple, Any

import meteva.base as meb
import metdig.cal as mdgcal

from modules.tracking.vortex_tracker import VortexTracker
from utils.geo_utils import (
    haversine_distance, get_direction_from_vector, get_opposite_direction,
)
from config.settings import (
    TIANJIN_RANGE, SMOOTH_POINTS_DETECT,
    COLD_VORTEX_COUPLING_DISTANCE,
    COLD_VORTEX_TRACK_DISTANCE_MAX,
    COLD_VORTEX_MATCH_DISTANCE,
    COLD_VORTEX_TYPES,
    COLD_VORTEX_IMPACT_REGION,
)

logger = logging.getLogger(__name__)


def run(
    forecast_data: Dict,
    fcst_detection_results: Dict,
    obs_detection_results: Dict,
    obs_data: Dict,
) -> Tuple[List[Dict], Dict, List]:
    """
    执行冷涡追踪与分析的完整流程。

    Args:
        forecast_data:          预报数据字典
        fcst_detection_results: 预报识别结果（未使用，冷涡分析自行检测）
        obs_detection_results:  实况识别结果
        obs_data:               实况原始数据（需要从中提取低压中心）

    Returns:
        (cold_vortex_analyses, vortex_tracks_info, impact_vortex_ids)
    """
    logger.info("开始冷涡追踪...")

    # ── 1. 从预报数据中识别低压中心和冷中心 ──
    fcst_500_keys = [
        (tl, lv) for (tl, lv) in forecast_data.keys() if lv == 500
    ]
    fcst_500_keys.sort(key=lambda x: forecast_data[x]["time"])

    # 分别收集每个时次的低压中心和冷中心
    lp_by_time = {}   # {time_index: [{"lon","lat","value","strength"}, ...]}
    cc_by_time = {}
    time_info = {}     # {time_index: {"time_str", "fcst_time", "forecast_hour"}}

    for idx, key in enumerate(fcst_500_keys):
        data_dict = forecast_data[key]
        fh = data_dict.get("forecast_hour", 0)
        fcst_time = data_dict.get("time")

        # 从 GH 识别低压中心
        gh_data = data_dict.get("GH")
        lp_centers = _detect_centers_from_grid(gh_data, center_type="low")

        # 从 T 识别冷中心
        t_data = data_dict.get("T")
        cold_centers = _detect_centers_from_grid(t_data, center_type="cold")

        lp_by_time[idx] = lp_centers
        cc_by_time[idx] = cold_centers
        time_info[idx] = {
            "time_str": f".{fh:03d}",
            "fcst_time": fcst_time,
            "forecast_hour": fh,
        }

        logger.debug(f"  +{fh:03d}h: 低压 {len(lp_centers)} 个, 冷中心 {len(cold_centers)} 个")

    # ── 2. 分别追踪 ──
    lp_tracker = _track_centers(lp_by_time, time_info)
    cc_tracker = _track_centers(cc_by_time, time_info)

    logger.info(f"  低压追踪: {len(lp_tracker.tracks)} 条轨迹")
    logger.info(f"  冷中心追踪: {len(cc_tracker.tracks)} 条轨迹")

    # ── 3. 配合判断：在每个时次将低压+冷中心配对 → 冷涡 ──
    vortex_tracks = _couple_and_build_tracks(
        lp_tracker, cc_tracker, time_info
    )

    logger.info(f"  配合后冷涡轨迹: {len(vortex_tracks)} 条")

    # ── 4. 分类 ──
    for vt in vortex_tracks:
        vt["vortex_type"] = _classify_vortex(vt)

    # ── 5. 影响天津判断 ──
    impact_vortex_ids = []
    for vt in vortex_tracks:
        if _is_impact_tianjin(vt):
            impact_vortex_ids.append(vt["vortex_id"])

    logger.info(f"  影响天津: {len(impact_vortex_ids)} 个冷涡")

    # ── 6. 实况-预报匹配 ──
    obs_cold_vortices = _extract_obs_cold_vortices(
        obs_detection_results, obs_data
    )

    matched_pairs, matched_vortex_ids = _match_obs_with_forecast(
        obs_cold_vortices, vortex_tracks
    )

    logger.info(f"  实况匹配: {len(matched_pairs)} 个")

    # ── 7. 生成分析结果 ──
    cold_vortex_analyses = []
    num = 1

    # 已匹配且影响天津的
    for obs_item, vortex_id, distance in matched_pairs:
        if vortex_id not in impact_vortex_ids:
            continue

        vt = _find_vortex_track(vortex_tracks, vortex_id)
        if vt is None:
            continue

        from_dir, to_dir = _analyze_movement(vt)
        impact_time = _find_impact_time(vt)

        # 中心强度（取第一个位置的低压值）
        strength = vt["positions"][0].get("lp_value", "未知") if vt["positions"] else "未知"

        # 象限
        from utils.geo_utils import calculate_quadrant
        from config.settings import MAP_CONFIG
        first_pos = vt["positions"][0]
        quadrant = calculate_quadrant(
            first_pos["lon"], first_pos["lat"],
            MAP_CONFIG.tianjin_lon, MAP_CONFIG.tianjin_lat,
        )

        cold_vortex_analyses.append({
            "cv_num": num,
            "vortex_id": vortex_id,
            "vortex_type": vt["vortex_type"],
            "strength": strength,
            "quadrant": quadrant,
            "from_dir": from_dir,
            "to_dir": to_dir,
            "impact_time": impact_time,
            "is_new": False,
        })
        num += 1

    # 新生冷涡（影响天津但未匹配）
    new_ids = [vid for vid in impact_vortex_ids if vid not in matched_vortex_ids]
    for vortex_id in new_ids:
        vt = _find_vortex_track(vortex_tracks, vortex_id)
        if vt is None:
            continue

        from_dir, to_dir = _analyze_movement(vt)
        impact_time = _find_impact_time(vt)

        from utils.geo_utils import calculate_quadrant
        from config.settings import MAP_CONFIG
        first_pos = vt["positions"][0]
        quadrant = calculate_quadrant(
            first_pos["lon"], first_pos["lat"],
            MAP_CONFIG.tianjin_lon, MAP_CONFIG.tianjin_lat,
        )

        cold_vortex_analyses.append({
            "cv_num": num,
            "vortex_id": vortex_id,
            "vortex_type": vt["vortex_type"],
            "strength": "未知",
            "quadrant": quadrant,
            "from_dir": from_dir,
            "to_dir": to_dir,
            "impact_time": impact_time,
            "is_new": True,
        })
        num += 1

    # 打印结果
    logger.info(f"冷涡分析完成: {len(cold_vortex_analyses)} 个冷涡")
    for a in cold_vortex_analyses:
        prefix = "新生" if a["is_new"] else ""
        logger.info(f"  {prefix}{a['vortex_type']}{a['cv_num']}: "
                    f"{a['from_dir']}→{a['to_dir']}, "
                    f"影响时间={a['impact_time']}")

    return cold_vortex_analyses, vortex_tracks, impact_vortex_ids


# ================================================================
# 内部函数
# ================================================================

def _detect_centers_from_grid(grd, center_type: str) -> List[Dict]:
    """
    从格网数据中识别中心。

    Args:
        grd: xarray.DataArray
        center_type: "low"（低压）或 "cold"（冷中心）

    Returns:
        [{"lon", "lat", "value", "strength"}, ...]
    """
    if grd is None:
        return []

    try:
        grd = meb.comp.smooth(grd, SMOOTH_POINTS_DETECT)
        grd.attrs["var_units"] = "gpm"
        grd.attrs["var_name"] = "hgt"

        caldata = mdgcal.high_low_center(grd)
        features = caldata.get("graphy", {}).get("features", {})

        centers = []
        for fid, feature in features.items():
            # 低压/冷中心都是 feature_id < 0
            if int(fid) < 0:
                center = feature.get("center", {})
                region = feature.get("region", {})
                lon = center.get("lon")
                lat = center.get("lat")
                if lon is not None and lat is not None:
                    centers.append({
                        "lon": lon,
                        "lat": lat,
                        "value": center.get("value", 0),
                        "strength": region.get("strength", 0),
                    })
        return centers

    except Exception as e:
        logger.debug(f"中心识别失败: {e}")
        return []


def _track_centers(
    centers_by_time: Dict[int, List[Dict]],
    time_info: Dict[int, Dict],
) -> VortexTracker:
    """
    使用 VortexTracker 追踪中心点序列。
    将简单 dict 转换为 VortexTracker 需要的格式。
    """
    tracker = VortexTracker()
    # 覆盖追踪距离
    from config.settings import COLD_VORTEX_TRACK_DISTANCE_MAX
    # VortexTracker 使用 VORTEX_TRACK_DISTANCE_MAX，需要临时适配

    for idx in sorted(centers_by_time.keys()):
        centers = centers_by_time[idx]
        info = time_info[idx]

        # 转换为 VortexTracker 期望的格式
        detection_results = []
        for c in centers:
            detection_results.append({
                "geometry": {"type": "point", "lon": c["lon"], "lat": c["lat"]},
                "properties": {
                    "value": c["value"],
                    "strength": c["strength"],
                },
            })

        tracker.update(detection_results, info["time_str"], info["fcst_time"])

    return tracker


def _couple_and_build_tracks(
    lp_tracker: VortexTracker,
    cc_tracker: VortexTracker,
    time_info: Dict[int, Dict],
) -> List[Dict]:
    """
    在每个时次对低压和冷中心进行配合，构建冷涡轨迹。

    配合规则：距离 ≤ COLD_VORTEX_COUPLING_DISTANCE km

    Returns:
        [{"vortex_id", "lp_track_id", "cc_track_id", "positions": [...]}, ...]
    """
    # 收集所有时次的低压和冷中心（带 track_id）
    lp_by_time = _collect_by_time(lp_tracker)
    cc_by_time = _collect_by_time(cc_tracker)

    all_times = sorted(set(list(lp_by_time.keys()) + list(cc_by_time.keys())))

    # 在每个时次配合
    coupled_by_time = {}
    for t in all_times:
        lps = lp_by_time.get(t, [])
        ccs = cc_by_time.get(t, [])
        coupled = _couple_at_time(lps, ccs)
        coupled_by_time[t] = coupled

    # 根据 lp_track_id 构建冷涡轨迹
    vortex_tracks = {}
    for t, pairs in coupled_by_time.items():
        for pair in pairs:
            lp_tid = pair["lp_track_id"]
            if lp_tid not in vortex_tracks:
                vortex_tracks[lp_tid] = {
                    "vortex_id": lp_tid,
                    "lp_track_id": lp_tid,
                    "positions": [],
                }
            vortex_tracks[lp_tid]["positions"].append({
                "lon": pair["lon"],
                "lat": pair["lat"],
                "lp_value": pair["lp_value"],
                "cc_value": pair["cc_value"],
                "distance_km": pair["distance_km"],
                "time_str": pair["time_str"],
                "fcst_time": pair["fcst_time"],
            })

    # 按时间排序
    result = []
    for vt in vortex_tracks.values():
        vt["positions"].sort(key=lambda x: x.get("time_str", ""))
        result.append(vt)

    return result


def _collect_by_time(tracker: VortexTracker) -> Dict[str, List[Dict]]:
    """从追踪器中按时次收集数据，附带 track_id"""
    by_time = {}
    for track_id, vortices in tracker.tracks.items():
        for v in vortices:
            t = v["time_str"]
            if t not in by_time:
                by_time[t] = []
            item = v.copy()
            item["track_id"] = track_id
            by_time[t].append(item)
    return by_time


def _couple_at_time(lps: List[Dict], ccs: List[Dict]) -> List[Dict]:
    """在单个时次中配合低压和冷中心"""
    pairs = []
    used_cc = set()

    for lp in lps:
        best_cc = None
        best_dist = float("inf")
        best_idx = -1

        for idx, cc in enumerate(ccs):
            if idx in used_cc:
                continue
            dist = haversine_distance(lp["lon"], lp["lat"], cc["lon"], cc["lat"])
            if dist <= COLD_VORTEX_COUPLING_DISTANCE and dist < best_dist:
                best_dist = dist
                best_cc = cc
                best_idx = idx

        if best_cc is not None:
            used_cc.add(best_idx)
            pairs.append({
                "lon": lp["lon"],
                "lat": lp["lat"],
                "lp_track_id": lp["track_id"],
                "cc_track_id": best_cc["track_id"],
                "lp_value": lp.get("value", 0),
                "cc_value": best_cc.get("value", 0),
                "distance_km": best_dist,
                "time_str": lp.get("time_str", ""),
                "fcst_time": lp.get("fcst_time"),
            })

    return pairs


def _classify_vortex(vt: Dict) -> str:
    """分类冷涡为东北冷涡或蒙古冷涡"""
    positions = vt.get("positions", [])
    if not positions:
        return "未分类冷涡"

    lon = positions[0]["lon"]
    lat = positions[0]["lat"]

    for vtype, region in COLD_VORTEX_TYPES.items():
        lon_range = region["lon_range"]
        lat_range = region["lat_range"]
        if lon_range[0] <= lon <= lon_range[1] and lat_range[0] <= lat <= lat_range[1]:
            return vtype

    return "未分类冷涡"


def _is_impact_tianjin(vt: Dict) -> bool:
    """判断冷涡是否影响天津（大区域判断）"""
    region = COLD_VORTEX_IMPACT_REGION
    for pos in vt.get("positions", []):
        if (region["lon_min"] <= pos["lon"] <= region["lon_max"] and
                region["lat_min"] <= pos["lat"] <= region["lat_max"]):
            return True
    return False


def _extract_obs_cold_vortices(
    obs_detection_results: Dict, obs_data: Dict
) -> List[Dict]:
    """
    从实况数据中提取冷涡（低压+冷中心配合）。

    低压中心：从 obs_data 500hPa HGT 的 symbols 中提取 code==61
    冷中心：从 obs_detection_results 中提取已识别的冷涡（cold_vortex 检测器）
    """
    # 提取 500hPa 低压中心
    obs_lp = []
    for (tl, lv), data_dict in obs_data.items():
        if lv != 500:
            continue
        hgt = data_dict.get("HGT")
        if hgt is None:
            continue
        symbols = hgt.get("symbols")
        if symbols is None:
            continue
        for i, code in enumerate(symbols["symbol_code"]):
            if code == 61:  # 低压中心
                obs_lp.append({
                    "lon": symbols["symbol_xyz"][i][0],
                    "lat": symbols["symbol_xyz"][i][1],
                })

    # 提取 500hPa 冷中心
    obs_cc = []
    for (tl, lv), detection in obs_detection_results.items():
        if lv != 500:
            continue
        for item in detection.get("冷涡", []):
            geo = item.get("geometry", {})
            if geo.get("type") == "point":
                obs_cc.append({
                    "lon": geo["lon"],
                    "lat": geo["lat"],
                })

    # 配合
    coupled = []
    used_cc = set()
    for lp in obs_lp:
        best_idx = -1
        best_dist = float("inf")
        for idx, cc in enumerate(obs_cc):
            if idx in used_cc:
                continue
            dist = haversine_distance(lp["lon"], lp["lat"], cc["lon"], cc["lat"])
            if dist <= COLD_VORTEX_COUPLING_DISTANCE and dist < best_dist:
                best_dist = dist
                best_idx = idx

        if best_idx >= 0:
            used_cc.add(best_idx)
            coupled.append({
                "lon": lp["lon"],
                "lat": lp["lat"],
                "distance_km": best_dist,
            })

    return coupled


def _match_obs_with_forecast(
    obs_vortices: List[Dict], vortex_tracks: List[Dict]
) -> Tuple[List, set]:
    """
    实况冷涡与预报冷涡轨迹匹配（全局一对一）。

    注意：冷涡轨迹首位置可能晚于 +000h（低压与冷中心后期才配合成功），
    属正常情况，此处不做 .000 检查。
    """
    # 1. 收集所有阈值内的 (距离, obs序号, vortex_id) 候选
    candidates = []
    for oi, obs in enumerate(obs_vortices):
        for vt in vortex_tracks:
            positions = vt.get("positions", [])
            if not positions:
                continue
            first = positions[0]
            dist = haversine_distance(
                obs["lon"], obs["lat"], first["lon"], first["lat"]
            )
            if dist <= COLD_VORTEX_MATCH_DISTANCE:
                candidates.append((dist, oi, vt["vortex_id"]))

    # 2. 按距离从近到远贪心一对一分配
    candidates.sort()
    matched = []
    matched_ids = set()
    used_obs = set()
    for dist, oi, vortex_id in candidates:
        if oi in used_obs or vortex_id in matched_ids:
            continue
        matched.append((obs_vortices[oi], vortex_id, dist))
        matched_ids.add(vortex_id)
        used_obs.add(oi)

    return matched, matched_ids


def _find_vortex_track(vortex_tracks: List[Dict], vortex_id: int) -> Dict:
    """根据 ID 找到冷涡轨迹"""
    for vt in vortex_tracks:
        if vt["vortex_id"] == vortex_id:
            return vt
    return None


def _analyze_movement(vt: Dict) -> Tuple[str, str]:
    """分析冷涡移动方向"""
    positions = vt.get("positions", [])
    if len(positions) >= 2:
        first = positions[0]
        last = positions[-1]
        dx = last["lon"] - first["lon"]
        dy = last["lat"] - first["lat"]
        to_dir = get_direction_from_vector(dx, dy)
        from_dir = get_opposite_direction(to_dir)
        return from_dir, to_dir
    return "未知", "未知"


def _find_impact_time(vt: Dict) -> str:
    """找到冷涡首次进入影响区域的时间"""
    region = COLD_VORTEX_IMPACT_REGION
    for pos in vt.get("positions", []):
        if (region["lon_min"] <= pos["lon"] <= region["lon_max"] and
                region["lat_min"] <= pos["lat"] <= region["lat_max"]):
            fcst_time = pos.get("fcst_time")
            if fcst_time:
                return f"{fcst_time.month}月{fcst_time.day}日{fcst_time.hour}时"
    return "未知时间"