"""
数据序列化器（后续实现）
========================
将天气系统识别和追踪的结构化结果转换为大模型可理解的输入格式。

输出格式为 JSON 字符串，包含:
    - 分析时间、起报时间
    - 目标城市信息（天津）
    - 各天气系统的追踪轨迹、移动趋势、是否影响天津
    - 关键格点的原始数值（供大模型参考）

设计考虑:
    - 结构化数据让大模型更容易理解和引用
    - 保留原始数值便于大模型做定量分析
    - 与 prompt 模板配合使用
"""
import json
import logging
from datetime import datetime
from typing import List, Dict, Any

logger = logging.getLogger(__name__)


def serialize_for_llm(
    tracking_results: List[Dict[str, Any]],
    current_time: datetime,
    map_config=None,
) -> str:
    """
    将追踪结果序列化为大模型输入。

    TODO: 根据实际追踪结果格式完善此函数

    Args:
        tracking_results: SystemTracker.track() 的返回值
        current_time:     当前时间
        map_config:       地图配置（含天津坐标）

    Returns:
        JSON 格式字符串

    输出示例:
        {
            "analysis_time": "2025-06-01 14:30",
            "init_time": "2025-06-01 08:00",
            "target_city": {"name": "天津", "lon": 117.2, "lat": 39.13},
            "weather_systems": [
                {
                    "type": "高空槽",
                    "track_id": "trough_001",
                    "trajectory": [...],
                    "movement": "东南移，速度约30km/h",
                    "affects_tianjin": true
                }
            ]
        }
    """
    logger.info("数据序列化器尚未实现")
    return json.dumps({"status": "not_implemented"}, ensure_ascii=False)
