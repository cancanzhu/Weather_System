"""
副热带高压分析
==============
封装副热带高压的完整分析流程：
    1. 从预报识别结果中提取 588 线坐标
    2. 计算每个时次的最北纬度
    3. 判断是否影响天津（最北纬度 ≥ 36°N）
    4. 找到第一个影响天津的预报时次
    5. 从实况识别结果中提取 588 线做同样判断

与高空槽/低涡的区别：
    - 不需要追踪，只需要纬度阈值判断
    - 分析的是特征线的位置而非系统中心
"""
import logging
import numpy as np
from typing import Dict, List, Tuple, Any

from config.settings import SUBTROPICAL_HIGH_LAT_THRESHOLD

logger = logging.getLogger(__name__)


def run(
    forecast_data: Dict,
    fcst_detection_results: Dict,
    obs_detection_results: Dict,
) -> List[Dict]:
    """
    执行副热带高压分析的完整流程。

    Args:
        forecast_data:          预报数据字典
        fcst_detection_results: 预报识别结果
        obs_detection_results:  实况识别结果

    Returns:
        subtropical_high_analyses: 分析结果列表
    """
    logger.info("开始副热带高压分析...")

    # ── 1. 实况分析 ──
    obs_result = _analyze_obs(obs_detection_results)

    # ── 2. 预报分析 ──
    fcst_results = _analyze_forecast(forecast_data, fcst_detection_results)

    # ── 3. 生成分析结果 ──
    analyses = []

    # 实况
    if obs_result["is_affecting"]:
        analyses.append({
            "type": "obs",
            "is_affecting": True,
            "max_latitude": obs_result["max_latitude"],
            "description": f"588线位于{obs_result['max_latitude']:.1f}°N",
        })
    else:
        analyses.append({
            "type": "obs",
            "is_affecting": False,
            "max_latitude": obs_result["max_latitude"],
            "description": f"588线未影响天津（最北位于{obs_result['max_latitude']:.1f}°N）"
                if not np.isnan(obs_result["max_latitude"])
                else "未检测到588线",
        })

    # 预报
    first_time = fcst_results.get("first_affecting_time")
    first_lat = fcst_results.get("first_affecting_lat")

    if first_time is not None:
        fcst_time = fcst_results["time_info"].get(first_time)
        time_desc = "未知时间"
        if fcst_time:
            time_desc = f"{fcst_time.month}月{fcst_time.day}日{fcst_time.hour}时"

        analyses.append({
            "type": "fcst",
            "is_affecting": True,
            "first_affecting_time": first_time,
            "first_affecting_lat": first_lat,
            "impact_time": time_desc,
            "description": f"预计+{first_time:03d}h（{time_desc}）588线北抬至{first_lat:.1f}°N，影响天津",
        })
    else:
        analyses.append({
            "type": "fcst",
            "is_affecting": False,
            "description": "未来12h 588线不影响天津",
        })

    # 打印结果
    for a in analyses:
        logger.info(f"  {a['type']}: {a['description']}")

    return analyses


def _analyze_obs(obs_detection_results: Dict) -> Dict:
    """分析实况 500hPa 588线"""
    max_lat = float("nan")

    for (tl, lv), detection in obs_detection_results.items():
        if lv != 500:
            continue
        for item in detection.get("副热带高压", []):
            geo = item.get("geometry", {})
            if geo.get("type") != "line":
                continue
            points = np.array(geo.get("points", []))
            if len(points) > 0:
                line_max_lat = np.max(points[:, 1])
                if np.isnan(max_lat) or line_max_lat > max_lat:
                    max_lat = line_max_lat

    is_affecting = (not np.isnan(max_lat)) and (max_lat >= SUBTROPICAL_HIGH_LAT_THRESHOLD)

    return {
        "is_affecting": is_affecting,
        "max_latitude": max_lat,
    }


def _analyze_forecast(
    forecast_data: Dict, fcst_detection_results: Dict
) -> Dict:
    """
    分析预报 500hPa 588线，逐时次检查最北纬度。
    找到第一个影响天津的时次。
    """
    fcst_500_keys = [
        (tl, lv) for (tl, lv) in forecast_data.keys() if lv == 500
    ]
    fcst_500_keys.sort(key=lambda x: forecast_data[x]["time"])

    all_results = {}   # {forecast_hour: max_latitude}
    time_info = {}     # {forecast_hour: fcst_time}
    first_affecting_time = None
    first_affecting_lat = None

    for key in fcst_500_keys:
        data_dict = forecast_data[key]
        fh = data_dict.get("forecast_hour", 0)
        fcst_time = data_dict.get("time")
        time_info[fh] = fcst_time

        detection = fcst_detection_results.get(key, {})
        max_lat = float("nan")

        for item in detection.get("副热带高压", []):
            geo = item.get("geometry", {})
            if geo.get("type") != "line":
                continue
            points = np.array(geo.get("points", []))
            if len(points) > 0:
                line_max_lat = np.max(points[:, 1])
                if np.isnan(max_lat) or line_max_lat > max_lat:
                    max_lat = line_max_lat

        all_results[fh] = max_lat

        is_affecting = (not np.isnan(max_lat)) and (max_lat >= SUBTROPICAL_HIGH_LAT_THRESHOLD)
        if is_affecting and first_affecting_time is None:
            first_affecting_time = fh
            first_affecting_lat = max_lat

        logger.debug(f"  +{fh:03d}h: 最北{max_lat:.1f}°N"
                     f" {'影响' if is_affecting else '未影响'}")

    return {
        "all_results": all_results,
        "time_info": time_info,
        "first_affecting_time": first_affecting_time,
        "first_affecting_lat": first_affecting_lat,
    }