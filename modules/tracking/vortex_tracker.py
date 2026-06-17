"""
低涡追踪器
==========
跨时次追踪低压中心，基于匈牙利算法进行全局最优一对一匹配。
使用距离约束和速度约束，避免错误匹配和多对一匹配。

与槽线追踪器的区别：
    - 低涡是点特征（中心坐标），槽线是线特征（多点坐标）
    - 使用匈牙利算法（全局最优），槽线用贪心匹配
    - 增加速度约束（最大移动速度限制）
"""
import logging
import numpy as np
from typing import List, Dict, Tuple
from modules.tracking.base_tracker import BaseTracker
from utils.geo_utils import haversine_distance
from config.settings import (
    VORTEX_TRACK_DISTANCE_MAX,
    VORTEX_TRACK_MAX_SPEED,
    VORTEX_TIANJIN_IMPACT_DISTANCE,
)

try:
    from scipy.optimize import linear_sum_assignment
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False

logger = logging.getLogger(__name__)


class VortexTracker(BaseTracker):
    """
    低涡追踪器

    维护 tracks 字典:
        {track_id: [vortex_dict, vortex_dict, ...]}
    每个 vortex_dict 包含:
        lon, lat, value, strength, time_str, fcst_time, forecast_hour
    """

    def __init__(self):
        super().__init__()
        self._prev_vortices: List[Dict] = []
        self._prev_vortex_to_track: Dict[int, int] = {}
        self._prev_fcst_time = None   # 上一有效时次的预报时间
        self._miss_count: int = 0
        self.MAX_MISS: int = 1        # 最多容忍连续 1 个空时次

    def update(self, detection_results: List[Dict], time_str: str, fcst_time=None):
        """
        用新一时次的识别结果更新追踪。

        Args:
            detection_results: 该时次的低涡识别结果列表
                               [{"center_lon", "center_lat", "properties": {"value", "strength"}}, ...]
            time_str:          时次标识（如 ".000", ".003"）
            fcst_time:         预报有效时间 (datetime)
        """
        # 从识别结果中提取低涡特征
        curr_vortices = []
        for item in detection_results:
            geo = item.get("geometry", {})
            props = item.get("properties", {})
            if geo.get("type") != "point":
                continue
            curr_vortices.append({
                "lon": geo["lon"],
                "lat": geo["lat"],
                "value": props.get("value", 0),
                "strength": props.get("strength", 0),
                "time_str": time_str,
                "fcst_time": fcst_time,
                "forecast_hour": self._parse_forecast_hour(time_str),
            })

        if not curr_vortices:
            # 单个时次缺测不立即断轨，容忍 MAX_MISS 个空时次
            self._miss_count += 1
            if self._miss_count > self.MAX_MISS:
                self._prev_vortices = []
                self._prev_vortex_to_track = {}
                self._prev_fcst_time = None
            return

        self._miss_count = 0

        if not self._prev_vortices:
            # 第一个时次，每个低涡新建轨迹
            new_mapping = {}
            for i, v in enumerate(curr_vortices):
                track_id = self.next_track_id
                self.next_track_id += 1
                self.tracks[track_id] = [v.copy()]
                new_mapping[i] = track_id
            self._prev_vortices = curr_vortices
            self._prev_vortex_to_track = new_mapping
            self._prev_fcst_time = fcst_time
            return

        # 计算与上一有效时次的实际时间间隔（小时）。
        # 跨过缺测时次时间隔自动变大，速度约束随之放宽，不再硬编码 3h
        time_hours = 3.0
        if fcst_time is not None and self._prev_fcst_time is not None:
            delta = (fcst_time - self._prev_fcst_time).total_seconds() / 3600.0
            if delta > 0:
                time_hours = delta

        # 匈牙利算法匹配
        matches, new_indices, _ = self._hungarian_match(
            self._prev_vortices, curr_vortices, time_hours=time_hours
        )

        new_mapping = {}

        # 匹配成功的延续轨迹
        for curr_idx, prev_idx in matches.items():
            track_id = self._prev_vortex_to_track.get(prev_idx)
            if track_id is not None:
                self.tracks[track_id].append(curr_vortices[curr_idx].copy())
                new_mapping[curr_idx] = track_id

        # 未匹配的新建轨迹
        for curr_idx in new_indices:
            track_id = self.next_track_id
            self.next_track_id += 1
            self.tracks[track_id] = [curr_vortices[curr_idx].copy()]
            new_mapping[curr_idx] = track_id

        self._prev_vortices = curr_vortices
        self._prev_vortex_to_track = new_mapping
        self._prev_fcst_time = fcst_time

    def get_tianjin_tracks(self, tianjin_range: dict) -> List[int]:
        """
        获取影响天津的轨迹ID（使用150km缓冲区）。

        Args:
            tianjin_range: {"lon_min", "lon_max", "lat_min", "lat_max"}

        Returns:
            影响天津的 track_id 列表
        """
        result = []
        for track_id, vortices in self.tracks.items():
            for v in vortices:
                dist = self._point_to_rect_distance(
                    v["lon"], v["lat"], tianjin_range
                )
                if dist <= VORTEX_TIANJIN_IMPACT_DISTANCE:
                    result.append(track_id)
                    break
        return result

    def _hungarian_match(
        self, prev_list: List[Dict], curr_list: List[Dict],
        time_hours: float = 3.0
    ) -> Tuple[Dict, List, List]:
        """
        匈牙利算法全局最优匹配。

        Returns:
            (matches, new_indices, dead_indices)
            matches: {curr_idx: prev_idx}
        """
        n_prev = len(prev_list)
        n_curr = len(curr_list)

        INF = 1e9
        cost_matrix = np.full((n_curr, n_prev), INF)

        for i, curr in enumerate(curr_list):
            for j, prev in enumerate(prev_list):
                dist = haversine_distance(
                    prev["lon"], prev["lat"], curr["lon"], curr["lat"]
                )
                # 距离约束
                if dist > VORTEX_TRACK_DISTANCE_MAX:
                    continue
                # 速度约束
                if time_hours > 0:
                    speed = dist / time_hours
                    if speed > VORTEX_TRACK_MAX_SPEED:
                        continue
                cost_matrix[i, j] = dist

        if HAS_SCIPY:
            row_ind, col_ind = linear_sum_assignment(cost_matrix)
            matches = {}
            matched_curr = set()
            matched_prev = set()
            for i, j in zip(row_ind, col_ind):
                if cost_matrix[i, j] < INF:
                    matches[i] = j
                    matched_curr.add(i)
                    matched_prev.add(j)
        else:
            # 贪心备用方案
            matches, matched_curr, matched_prev = self._greedy_match(
                cost_matrix, n_curr, n_prev, INF
            )

        new_indices = [i for i in range(n_curr) if i not in matched_curr]
        dead_indices = [j for j in range(n_prev) if j not in matched_prev]

        return matches, new_indices, dead_indices

    @staticmethod
    def _greedy_match(cost_matrix, n_curr, n_prev, INF):
        """贪心匹配备用方案"""
        matches = {}
        matched_curr = set()
        matched_prev = set()

        candidates = []
        for i in range(n_curr):
            for j in range(n_prev):
                if cost_matrix[i, j] < INF:
                    candidates.append((cost_matrix[i, j], i, j))
        candidates.sort()

        for dist, i, j in candidates:
            if i not in matched_curr and j not in matched_prev:
                matches[i] = j
                matched_curr.add(i)
                matched_prev.add(j)

        return matches, matched_curr, matched_prev

    @staticmethod
    def _point_to_rect_distance(lon: float, lat: float, rect: dict) -> float:
        """
        计算点到矩形边界的最短距离（km）。
        点在矩形内返回 0。
        """
        if (rect["lon_min"] <= lon <= rect["lon_max"] and
                rect["lat_min"] <= lat <= rect["lat_max"]):
            return 0.0

        # 钳位到矩形
        nearest_lon = max(rect["lon_min"], min(lon, rect["lon_max"]))
        nearest_lat = max(rect["lat_min"], min(lat, rect["lat_max"]))

        # 转换为 km
        lat_center = (rect["lat_min"] + rect["lat_max"]) / 2
        dx = (lon - nearest_lon) * 111.0 * np.cos(np.radians(lat_center))
        dy = (lat - nearest_lat) * 111.0

        return np.sqrt(dx ** 2 + dy ** 2)

    @staticmethod
    def _parse_forecast_hour(time_str: str) -> int:
        """从时次标识解析预报时效"""
        if time_str.startswith("."):
            try:
                return int(time_str[1:])
            except ValueError:
                return 0
        return 0