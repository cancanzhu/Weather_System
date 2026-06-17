"""
槽线追踪器
==========
跨时次追踪高空槽线，基于距离+方向+长度+强度的综合相似度匹配。

从 metdig.cal.trough() 的返回结果中提取槽线特征，
在相邻时次间进行贪心匹配，形成轨迹。
"""
import numpy as np
from typing import List, Dict, Optional
from modules.tracking.base_tracker import BaseTracker
from config.settings import TROUGH_TRACK_DISTANCE_MAX, TROUGH_TRACK_SIMILARITY_THRESHOLD


def extract_trough_features(caldata) -> List[Dict]:
    """
    从 metdig.trough 返回结果中提取槽线特征。

    Args:
        caldata: mdgcal.trough() 返回的结果

    Returns:
        槽线特征列表
    """
    if not caldata or "graphy" not in caldata:
        return []

    features = []
    graphy = caldata["graphy"]

    if "features" not in graphy:
        return []

    for raw_id, trough_data in graphy["features"].items():
        axes = trough_data.get("axes", {})
        center = trough_data.get("center", {})
        region = trough_data.get("region", {})

        points = np.array(axes.get("point", []))
        if len(points) < 2:
            continue

        # 计算槽线方向
        start_point = points[0]
        end_point = points[-1]
        dx = end_point[0] - start_point[0]
        dy = end_point[1] - start_point[1]
        lat = center.get("lat", 30)
        dx_km = dx * 111 * np.cos(np.radians(lat))
        dy_km = dy * 111
        direction = np.arctan2(dy_km, dx_km) * 180 / np.pi

        feature = {
            "center_lon": center.get("lon", 0),
            "center_lat": center.get("lat", 0),
            # 注意: "lenght" 是 metdig 返回结果的原始字段名（上游拼写如此），
            # 切勿"修正"为 "length"，否则所有槽线长度都会变成 0
            "length": axes.get("lenght", 0),
            "strength": region.get("strength", 0),
            "points": points,
            "direction": direction,
            "raw_id": raw_id,
        }
        features.append(feature)

    return features


def calculate_similarity(trough1: Dict, trough2: Dict) -> float:
    """
    计算两条槽线的综合相似度 (0~1)。

    权重: 距离 0.5, 长度 0.2, 方向 0.2, 强度 0.1
    """
    # 球面距离
    R = 6371
    lat1, lon1 = np.radians(trough1["center_lat"]), np.radians(trough1["center_lon"])
    lat2, lon2 = np.radians(trough2["center_lat"]), np.radians(trough2["center_lon"])
    dlat, dlon = lat2 - lat1, lon2 - lon1
    a = np.sin(dlat / 2) ** 2 + np.cos(lat1) * np.cos(lat2) * np.sin(dlon / 2) ** 2
    distance = R * 2 * np.arcsin(np.sqrt(a))

    if distance > TROUGH_TRACK_DISTANCE_MAX:
        return 0.0

    # 距离得分
    threshold = TROUGH_TRACK_DISTANCE_MAX * 0.8
    if distance <= threshold:
        distance_score = 1.0
    else:
        distance_score = 1 - (distance - threshold) / (TROUGH_TRACK_DISTANCE_MAX - threshold)

    # 长度得分
    len1, len2 = trough1["length"], trough2["length"]
    max_len = max(len1, len2)
    length_score = max(0, 1 - abs(len1 - len2) / max_len) if max_len > 0 else 1.0

    # 方向得分
    angle_diff = abs(trough1["direction"] - trough2["direction"]) % 180
    if angle_diff > 90:
        angle_diff = 180 - angle_diff
    direction_score = 1 - angle_diff / 90

    # 强度得分
    str1, str2 = trough1["strength"], trough2["strength"]
    max_str = max(str1, str2)
    strength_score = max(0, 1 - abs(str1 - str2) / max_str) if max_str > 0 else 1.0

    return (0.5 * distance_score + 0.2 * length_score +
            0.2 * direction_score + 0.1 * strength_score)


class TroughTracker(BaseTracker):
    """
    槽线追踪器

    维护 tracks 字典:
        {track_id: [trough_dict, trough_dict, ...]}
    每个 trough_dict 包含:
        center_lon, center_lat, points, time_str, fcst_time, ...
    """

    def __init__(self):
        super().__init__()
        self._prev_features: List[Dict] = []
        self._prev_feature_to_track: Dict[int, int] = {}
        self._miss_count: int = 0
        self.MAX_MISS: int = 1   # 最多容忍连续 1 个空时次，超过才断开轨迹

    def update(self, caldata, time_str: str, fcst_time=None):
        """
        用新一时次的识别结果更新追踪。

        Args:
            caldata:   mdgcal.trough() 的返回结果
            time_str:  时次标识
            fcst_time: 预报有效时间
        """
        curr_features = extract_trough_features(caldata)

        if not curr_features:
            # 单个时次缺测/无槽线不立即断轨，容忍 MAX_MISS 个空时次
            self._miss_count += 1
            if self._miss_count > self.MAX_MISS:
                self._prev_features = []
                self._prev_feature_to_track = {}
            return

        self._miss_count = 0

        if not self._prev_features:
            # 第一个时次，每条槽线新建轨迹
            new_mapping = {}
            for i, feat in enumerate(curr_features):
                track_id = self.next_track_id
                self.next_track_id += 1
                trough_dict = self._feature_to_dict(feat, time_str, fcst_time)
                self.tracks[track_id] = [trough_dict]
                new_mapping[i] = track_id
            self._prev_features = curr_features
            self._prev_feature_to_track = new_mapping
            return

        # 贪心匹配
        n_prev = len(self._prev_features)
        n_curr = len(curr_features)
        sim_matrix = np.zeros((n_prev, n_curr))

        for i in range(n_prev):
            for j in range(n_curr):
                sim_matrix[i, j] = calculate_similarity(
                    self._prev_features[i], curr_features[j]
                )

        matched_prev = set()
        matched_curr = set()
        new_mapping = {}

        while True:
            max_val = sim_matrix.max()
            if max_val < TROUGH_TRACK_SIMILARITY_THRESHOLD:
                break
            idx = np.unravel_index(sim_matrix.argmax(), sim_matrix.shape)
            i, j = int(idx[0]), int(idx[1])

            if i in matched_prev or j in matched_curr:
                sim_matrix[i, j] = 0
                continue

            # 匹配成功，延续轨迹
            track_id = self._prev_feature_to_track.get(i)
            if track_id is not None:
                trough_dict = self._feature_to_dict(curr_features[j], time_str, fcst_time)
                self.tracks[track_id].append(trough_dict)
                new_mapping[j] = track_id

            matched_prev.add(i)
            matched_curr.add(j)
            sim_matrix[i, :] = 0
            sim_matrix[:, j] = 0

        # 未匹配的当前槽线 → 新轨迹
        for j in range(n_curr):
            if j not in matched_curr:
                track_id = self.next_track_id
                self.next_track_id += 1
                trough_dict = self._feature_to_dict(curr_features[j], time_str, fcst_time)
                self.tracks[track_id] = [trough_dict]
                new_mapping[j] = track_id

        self._prev_features = curr_features
        self._prev_feature_to_track = new_mapping

    def get_tianjin_tracks(self, tianjin_range: dict) -> List[int]:
        """获取任意时次穿过天津区域的轨迹ID"""
        result = []
        for track_id, troughs in self.tracks.items():
            for trough in troughs:
                points = trough.get("points", [])
                if isinstance(points, np.ndarray):
                    points = points.tolist()
                for lon, lat in points:
                    if (tianjin_range["lon_min"] <= lon <= tianjin_range["lon_max"] and
                            tianjin_range["lat_min"] <= lat <= tianjin_range["lat_max"]):
                        result.append(track_id)
                        break
                else:
                    continue
                break
        return result

    @staticmethod
    def _feature_to_dict(feature: Dict, time_str: str, fcst_time) -> Dict:
        """将特征转为存储字典"""
        return {
            "center_lon": feature["center_lon"],
            "center_lat": feature["center_lat"],
            "points": feature["points"],
            "length": feature["length"],
            "strength": feature["strength"],
            "direction": feature["direction"],
            "time_str": time_str,
            "fcst_time": fcst_time,
        }