"""
高空槽追踪与分析
================
封装高空槽的追踪、实况-预报匹配、前倾/后倾分析、移动方向分析等全部逻辑。
main.py 只需调用 run() 即可获得分析结果。

后续其他天气系统参照此文件模式，新建对应的 xxx_analysis.py。
"""
import logging
import numpy as np
from typing import Dict, List, Tuple, Any

from modules.tracking.trough_tracker import TroughTracker
from utils.geo_utils import (
    calculate_center, judge_trough_tilt, calculate_impact_time,
    get_direction_from_vector, get_opposite_direction, haversine_distance,
)
from config.settings import (
    TIANJIN_RANGE, TROUGH_MATCH_DISTANCE_THRESHOLD,
    TILT_MATCH_WEIGHTS, TILT_MATCH_DIST_SCALE, TILT_MATCH_SCORE_MIN,
)

logger = logging.getLogger(__name__)


def run(
    forecast_data: Dict,
    fcst_detection_results: Dict,
    obs_detection_results: Dict,
) -> Tuple[List[Dict], TroughTracker, List[int]]:
    """
    执行高空槽追踪与分析的完整流程。

    流程:
        1. 从预报识别结果中提取 caldata，喂给追踪器
        2. 获取影响天津的轨迹
        3. 实况-预报匹配
        4. 前倾/后倾分析
        5. 移动方向和影响时间分析

    Args:
        forecast_data:          预报数据字典（DataManager 输出）
        fcst_detection_results: 预报识别结果
        obs_detection_results:  实况识别结果

    Returns:
        (trough_analyses, trough_tracker, tianjin_track_ids)
        - trough_analyses:    分析结果列表
        - trough_tracker:     追踪器对象（供可视化使用）
        - tianjin_track_ids:  影响天津的轨迹ID列表
    """
    logger.info("开始高空槽追踪...")

    # ── 1. 追踪 ──
    trough_tracker = TroughTracker()

    fcst_500_keys = [
        (tl, lv) for (tl, lv) in forecast_data.keys() if lv == 500
    ]
    fcst_500_keys.sort(key=lambda x: forecast_data[x]["time"])

    for key in fcst_500_keys:
        data_dict = forecast_data[key]
        detection = fcst_detection_results.get(key, {})
        trough_results = detection.get("高空槽", [])

        if trough_results:
            caldata = trough_results[0].get("properties", {}).get("caldata")
            if caldata:
                fh = data_dict.get("forecast_hour", 0)
                time_str = f".{fh:03d}"
                fcst_time = data_dict.get("time")
                trough_tracker.update(caldata, time_str, fcst_time)

    # ── 2. 影响天津的轨迹 ──
    tianjin_track_ids = trough_tracker.get_tianjin_tracks(TIANJIN_RANGE)

    logger.info(f"追踪结果: 总轨迹数={len(trough_tracker.tracks)}, "
                f"影响天津={len(tianjin_track_ids)}")

    # ── 3. 实况-预报匹配 ──
    obs_500_troughs = _extract_obs_troughs(obs_detection_results)

    matched_pairs, matched_track_ids = _match_obs_with_forecast(
        obs_500_troughs, trough_tracker
    )

    new_track_ids = [
        tid for tid in tianjin_track_ids if tid not in matched_track_ids
    ]

    logger.info(f"匹配结果: 匹配成功={len(matched_pairs)}, "
                f"新生槽={len(new_track_ids)}")

    # ── 4. 分析 ──
    trough_analyses = []

    # 已匹配的槽线分析
    trough_num = 1
    for obs_item, track_id, distance in matched_pairs:
        if track_id not in tianjin_track_ids:
            continue

        analysis = _analyze_single_trough(
            obs_item, track_id, trough_tracker, obs_detection_results,
            trough_num, is_new=False,
        )
        trough_analyses.append(analysis)
        trough_num += 1

    # 新生槽分析
    new_num = 1
    for track_id in new_track_ids:
        analysis = _analyze_new_trough(
            track_id, trough_tracker, new_num,
        )
        trough_analyses.append(analysis)
        new_num += 1

    # 打印分析结果
    logger.info(f"分析完成: {len(trough_analyses)} 条槽线")
    for a in trough_analyses:
        prefix = "新生槽" if a["is_new"] else "高空槽"
        logger.info(f"  {prefix}{a['trough_num']}: "
                    f"{a['tilt_type']}, {a['from_dir']}→{a['to_dir']}, "
                    f"影响时间={a['impact_time']}")

    return trough_analyses, trough_tracker, tianjin_track_ids


def _extract_obs_troughs(obs_detection_results: Dict) -> List[Dict]:
    """从实况识别结果中提取 500hPa 槽线"""
    obs_troughs = []
    for (tl, lv), detection in obs_detection_results.items():
        if lv == 500 and "高空槽" in detection:
            for item in detection["高空槽"]:
                geo = item.get("geometry", {})
                if geo.get("type") == "line":
                    obs_troughs.append(item)
    return obs_troughs


def _match_obs_with_forecast(
    obs_troughs: List[Dict], tracker: TroughTracker
) -> Tuple[List, set]:
    """
    实况槽线与预报追踪轨迹匹配（球面距离 + 全局一对一）。

    旧版逐条找最近会出现多条实况匹配同一轨迹（报告重复条目），
    且使用不带 cos(lat) 的平面近似（40°N 处东西向距离高估约 30%）。
    """
    # 预提取各轨迹首位置（正常应为 +000h 时次）
    track_firsts = []
    for track_id, troughs in tracker.tracks.items():
        if not troughs:
            continue
        first = troughs[0]
        if first.get("time_str") != ".000":
            logger.warning(
                f"槽线轨迹{track_id}首位置非+000h"
                f"({first.get('time_str')})，匹配距离可能偏移"
            )
        track_firsts.append((track_id, first))

    # 1. 收集所有阈值内的 (距离, obs序号, track_id) 候选
    candidates = []
    for oi, obs_item in enumerate(obs_troughs):
        obs_center = calculate_center(obs_item["geometry"]["points"])
        for track_id, first in track_firsts:
            dist = haversine_distance(
                obs_center[0], obs_center[1],
                first["center_lon"], first["center_lat"],
            )
            if dist <= TROUGH_MATCH_DISTANCE_THRESHOLD:
                candidates.append((dist, oi, track_id))

    # 2. 按距离从近到远贪心一对一分配
    candidates.sort()
    matched_pairs = []
    matched_track_ids = set()
    used_obs = set()
    for dist, oi, track_id in candidates:
        if oi in used_obs or track_id in matched_track_ids:
            continue
        matched_pairs.append((obs_troughs[oi], track_id, dist))
        matched_track_ids.add(track_id)
        used_obs.add(oi)

    return matched_pairs, matched_track_ids


def _analyze_single_trough(
    obs_item: Dict,
    track_id: int,
    tracker: TroughTracker,
    obs_detection_results: Dict,
    trough_num: int,
    is_new: bool,
) -> Dict:
    """分析单条已匹配的槽线（位置+前倾/后倾+移动方向+影响时间）"""
    obs_center = calculate_center(obs_item["geometry"]["points"])

    # 大模型获取位置描述（用中心点查询，与低涡一致）
    from modules.llm.location_service import get_point_location
    location = get_point_location(obs_center[0], obs_center[1], "高空槽")

    # 前倾/后倾
    tilt_type = _judge_tilt(obs_item["geometry"]["points"], obs_detection_results)

    # 移动方向
    from_dir, to_dir = _analyze_movement(tracker, track_id)

    # 影响时间
    troughs = tracker.tracks.get(track_id, [])
    impact_time = calculate_impact_time(troughs, TIANJIN_RANGE)

    return {
        "trough_num": trough_num,
        "track_id": track_id,
        "location": location,
        "tilt_type": tilt_type,
        "from_dir": from_dir,
        "to_dir": to_dir,
        "impact_time": impact_time,
        "is_new": is_new,
    }


def _analyze_new_trough(
    track_id: int,
    tracker: TroughTracker,
    new_num: int,
) -> Dict:
    """分析新生槽（移动方向+影响时间）"""
    from_dir, to_dir = _analyze_movement(tracker, track_id)

    troughs = tracker.tracks.get(track_id, [])
    impact_time = calculate_impact_time(troughs, TIANJIN_RANGE)

    return {
        "trough_num": new_num,
        "track_id": track_id,
        "location": "新生成",
        "tilt_type": "未知",
        "from_dir": from_dir,
        "to_dir": to_dir,
        "impact_time": impact_time,
        "is_new": True,
    }


def _judge_tilt(obs_points: list, obs_detection_results: Dict) -> str:
    best_points = None
    best_score = -float("inf")
    cand_count = 0

    for (tl, lv), det in obs_detection_results.items():
        if lv not in [700, 850]:
            continue
        if "切变线" not in det:
            continue
        for item in det["切变线"]:
            geo = item.get("geometry", {})
            if geo.get("type") != "line":
                continue
            cand = geo["points"]
            cand_count += 1
            score = _trough_match_score(obs_points, cand)
            logger.info(f"[倾向候选] lv={lv} score={score} "
                        f"首尾=({cand[0]},{cand[-1]}) 点数={len(cand)}")
            if score is None:
                continue
            if score > best_score:
                best_score = score
                best_points = cand

    logger.info(f"[倾向] 候选总数={cand_count} best_score={best_score} "
                f"best_points={'有' if best_points else '无'}")

    if best_points is None:
        logger.info("[倾向] → 未知（没有可用候选低层槽）")
        return "未知"

    result = judge_trough_tilt(obs_points, best_points)
    logger.info(f"[倾向] 500槽首尾=({obs_points[0]},{obs_points[-1]}) "
                f"选中低层槽首尾=({best_points[0]},{best_points[-1]}) → {result}")
    return result


def _trough_match_score(p500: list, plow: list):
    """
    两条槽线的匹配度评分（0~1，越大越匹配）。综合三项：
      1) 重心距离接近度：重心越近分越高（TILT_MATCH_DIST_SCALE 度内线性衰减）
      2) 纬度重叠比例：两条槽共同覆盖的纬度带占比越大越匹配
      3) 走向一致度：两条槽首尾方向向量的余弦相似度

    纬度无重叠 → 返回 None（无法做纬度对齐比较，直接排除）。
    """
    a = np.asarray(p500, dtype=float)
    b = np.asarray(plow, dtype=float)
    if len(a) < 2 or len(b) < 2:
        return None

    # 1) 重心距离接近度
    ca = a.mean(axis=0)
    cb = b.mean(axis=0)
    dist = float(np.hypot(ca[0] - cb[0], ca[1] - cb[1]))
    dist_score = max(0.0, 1.0 - dist / TILT_MATCH_DIST_SCALE)

    # 2) 纬度重叠比例
    lat_lo = max(a[:, 1].min(), b[:, 1].min())
    lat_hi = min(a[:, 1].max(), b[:, 1].max())
    if lat_hi <= lat_lo:
        return None                              # 纬度不重叠 → 排除
    span = max(a[:, 1].max() - a[:, 1].min(),
               b[:, 1].max() - b[:, 1].min(), 1e-6)
    overlap_score = (lat_hi - lat_lo) / span     # 0~1

    # 3) 走向一致度（首尾连线方向的余弦相似度，映射到 0~1）
    va = a[-1] - a[0]
    vb = b[-1] - b[0]
    na = np.linalg.norm(va)
    nb = np.linalg.norm(vb)
    if na < 1e-6 or nb < 1e-6:
        dir_score = 0.0
    else:
        cos = float(np.dot(va, vb) / (na * nb))
        dir_score = (cos + 1.0) / 2.0            # -1~1 → 0~1

    w = TILT_MATCH_WEIGHTS
    return (w["dist"] * dist_score
            + w["overlap"] * overlap_score
            + w["direction"] * dir_score)


def _analyze_movement(tracker: TroughTracker, track_id: int) -> Tuple[str, str]:
    """分析轨迹的移动方向"""
    troughs = tracker.tracks.get(track_id, [])
    if len(troughs) >= 2:
        first = troughs[0]
        last = troughs[-1]
        dx = last["center_lon"] - first["center_lon"]
        dy = last["center_lat"] - first["center_lat"]
        to_dir = get_direction_from_vector(dx, dy)
        from_dir = get_opposite_direction(to_dir)
        return from_dir, to_dir
    return "未知", "未知"