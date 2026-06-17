"""
天气系统追踪器 — 抽象基类
=========================
所有天气系统追踪器继承此基类。

追踪器的职责:
    1. 从识别结果中提取特征
    2. 在相邻时次间匹配同一系统
    3. 维护轨迹字典 tracks = {track_id: [位置列表]}
    4. 判断哪些轨迹影响天津
"""
from abc import ABC, abstractmethod
from typing import List, Dict


class BaseTracker(ABC):
    """天气系统追踪器基类"""

    def __init__(self):
        self.tracks: Dict[int, List[Dict]] = {}
        self.next_track_id: int = 1

    @abstractmethod
    def update(self, detection_result, time_str: str, fcst_time=None):
        """
        用新一时次的识别结果更新追踪。

        Args:
            detection_result: 该时次的识别结果
            time_str:         时次标识（如 ".000", ".003"）
            fcst_time:        预报有效时间 (datetime)
        """
        pass

    @abstractmethod
    def get_tianjin_tracks(self, tianjin_range: dict) -> List[int]:
        """
        获取影响天津的轨迹ID列表。

        Args:
            tianjin_range: {"lon_min", "lon_max", "lat_min", "lat_max"}

        Returns:
            影响天津的 track_id 列表
        """
        pass