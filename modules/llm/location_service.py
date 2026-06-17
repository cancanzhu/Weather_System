"""
地理位置描述服务
================
对外接口：根据经纬度坐标获取省份和方位描述。
内部调用大模型 API，外部模块不关心具体实现。

后续替换 LangChain 时只改本文件内部，函数签名不变。
"""
import logging
from typing import List, Tuple, Optional

from modules.llm.llm_client import call_llm

logger = logging.getLogger(__name__)

# 位置描述缓存: {(round(lon,1), round(lat,1)): 描述文本}
# 同一系统在分析和报告阶段会重复查询同一坐标，缓存避免重复调用 API
_location_cache = {}

SYSTEM_PROMPT = """你是一个地理位置助手。用户给你中国范围内的经纬度坐标，你需要判断这些坐标位于哪个省份（或自治区），以及相对于该省份的大致方位（东部/南部/西部/北部/中部）。

要求：
1. 只回答省份名称和方位，不要多余解释
2. 格式：xx省（自治区）的xx部
3. 例如：内蒙古自治区的中部、河北省的北部、黑龙江省的西南部
4. 如果是一条线（多个坐标），根据线的中心位置判断"""


def get_location_description(
    coords: List[Tuple[float, float]],
    system_type: str = "天气系统",
) -> str:
    """
    根据经纬度获取位置描述。

    Args:
        coords: 坐标列表 [(lon, lat), ...] 可以是单个点或一条线
        system_type: 系统类型（用于构建 prompt）

    Returns:
        位置描述字符串，如 "内蒙古自治区的中部"
        大模型不可用时返回坐标描述
    """
    if not coords:
        return "未知位置"

    # 计算中心点
    center_lon = sum(c[0] for c in coords) / len(coords)
    center_lat = sum(c[1] for c in coords) / len(coords)

    # 命中缓存直接返回
    cache_key = (round(center_lon, 1), round(center_lat, 1))
    if cache_key in _location_cache:
        return _location_cache[cache_key]

    # 构建 prompt
    if len(coords) == 1:
        prompt = f"{system_type}中心位于经度{center_lon:.1f}°E，纬度{center_lat:.1f}°N，请判断位于哪个省份的什么方位。"
    else:
        prompt = (
            f"{system_type}经过的区域中心位于经度{center_lon:.1f}°E，纬度{center_lat:.1f}°N，"
            f"坐标范围从({coords[0][0]:.1f}°E,{coords[0][1]:.1f}°N)"
            f"到({coords[-1][0]:.1f}°E,{coords[-1][1]:.1f}°N)，"
            f"请判断位于哪个省份的什么方位。"
        )

    result = call_llm(prompt, SYSTEM_PROMPT)

    if result:
        # 仅缓存成功结果；失败不缓存，避免一次网络抖动钉死整轮降级
        _location_cache[cache_key] = result
        return result
    else:
        # 降级：返回坐标描述
        return f"({center_lon:.1f}°E, {center_lat:.1f}°N)附近"


def get_point_location(lon: float, lat: float, system_type: str = "天气系统") -> str:
    """
    获取单个点的位置描述（低涡、冷涡中心用）。

    Args:
        lon: 经度
        lat: 纬度
        system_type: 系统类型

    Returns:
        位置描述字符串
    """
    return get_location_description([(lon, lat)], system_type)


def get_line_location(
    points: List[List[float]], system_type: str = "天气系统"
) -> str:
    """
    获取线状系统的位置描述（高空槽用）。

    Args:
        points: [[lon, lat], ...] 线上的坐标点
        system_type: 系统类型

    Returns:
        位置描述字符串
    """
    coords = [(p[0], p[1]) for p in points]
    return get_location_description(coords, system_type)