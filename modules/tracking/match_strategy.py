"""
天气系统匹配策略（后续实现）
============================
提供可扩展的匹配算法，用于在相邻时刻间关联同一天气系统。

已预留策略:
    - NearestMatchStrategy:  基于距离阈值的最近邻匹配（默认）
    - ShapeMatchStrategy:    基于形态相似度的匹配（适用于槽线等线状系统）
    - KalmanMatchStrategy:   基于卡尔曼滤波的预测匹配（适用于快速移动系统）

扩展方式:
    1. 继承 BaseMatchStrategy
    2. 实现 match() 方法
    3. 在 tracker.py 中选用
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseMatchStrategy(ABC):
    """匹配策略抽象基类"""

    @abstractmethod
    def match(
        self,
        prev_results: List[Dict[str, Any]],
        curr_results: List[Dict[str, Any]],
    ) -> List[tuple]:
        """
        在相邻时刻间匹配同一天气系统。

        Args:
            prev_results: 前一时刻的识别结果列表
            curr_results: 当前时刻的识别结果列表

        Returns:
            匹配对列表: [(prev_index, curr_index), ...]
            未匹配的用 None 表示（如新生成或消亡的系统）
        """
        pass


class NearestMatchStrategy(BaseMatchStrategy):
    """基于距离阈值的最近邻匹配（待实现）"""

    def __init__(self, max_distance_km: float = 500.0):
        self.max_distance_km = max_distance_km

    def match(self, prev_results, curr_results):
        """TODO: 实现最近邻匹配"""
        logger.debug("NearestMatchStrategy 尚未实现")
        return []
