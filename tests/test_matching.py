# -*- coding: utf-8 -*-
"""
实况-预报匹配单元测试
====================
覆盖 2026-06 修复:
    - 一对一约束: 多条实况不可匹配同一条预报轨迹
    - 距离改用球面 haversine
    - track_id 为 0 不再被 if best_track_id 误判（旧版埋雷）

运行: 工程根目录执行  python -m pytest tests/ -v
"""
import os
import sys

import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.tracking.trough_tracker import TroughTracker
from modules.tracking.vortex_tracker import VortexTracker
from modules.tracking import trough_analysis
from modules.tracking import vortex_analysis


# ---------------- 高空槽 ----------------

def _trough_track(tracker, track_id, lon, lat):
    tracker.tracks[track_id] = [{
        "center_lon": lon, "center_lat": lat,
        "points": np.array([[lon, lat + 1.0], [lon, lat - 1.0]]),
        "length": 10, "strength": 5, "direction": 90,
        "time_str": ".000", "fcst_time": None,
    }]


def _obs_trough(lon, lat):
    """中心位于 (lon, lat) 的实况槽线"""
    return {"geometry": {"type": "line",
                         "points": [[lon, lat + 1.0], [lon, lat - 1.0]]}}


def test_trough_one_to_one_matching():
    """两条实况槽都靠近同一轨迹时, 只允许更近的一条匹配上"""
    tracker = TroughTracker()
    _trough_track(tracker, 1, 115.0, 39.0)

    obs = [_obs_trough(115.1, 39.0),   # ≈ 8.6km, 更近
           _obs_trough(115.3, 39.1)]   # ≈ 28km

    pairs, ids = trough_analysis._match_obs_with_forecast(obs, tracker)

    assert len(pairs) == 1, "同一轨迹被匹配了多次（一对一约束失效）"
    assert pairs[0][0] is obs[0], "应匹配距离更近的实况槽"
    assert ids == {1}


def test_trough_two_obs_two_tracks():
    """两条实况、两条轨迹, 应各自匹配最近的, 互不抢占"""
    tracker = TroughTracker()
    _trough_track(tracker, 1, 115.0, 39.0)
    _trough_track(tracker, 2, 118.0, 41.0)

    obs = [_obs_trough(115.2, 39.0), _obs_trough(117.8, 41.1)]
    pairs, ids = trough_analysis._match_obs_with_forecast(obs, tracker)

    assert len(pairs) == 2
    assert ids == {1, 2}
    matched = {id(p[0]): p[1] for p in pairs}
    assert matched[id(obs[0])] == 1
    assert matched[id(obs[1])] == 2


def test_trough_haversine_threshold():
    """
    40°N 处经向 2° ≈ 170km, 球面距离应在 200km 阈值内匹配成功。
    旧版平面近似 sqrt(2²)*111=222km 会误判超阈值 → 漏匹配。
    """
    tracker = TroughTracker()
    _trough_track(tracker, 1, 115.0, 40.0)

    obs = [_obs_trough(117.0, 40.0)]
    pairs, _ = trough_analysis._match_obs_with_forecast(obs, tracker)

    assert len(pairs) == 1, "球面距离 170km 应在 200km 阈值内匹配成功"


def test_trough_track_id_zero_not_dropped():
    """track_id 为 0 时不应因布尔判断被丢弃（旧版 if best_track_id 埋雷）"""
    tracker = TroughTracker()
    _trough_track(tracker, 0, 115.0, 39.0)

    obs = [_obs_trough(115.1, 39.0)]
    pairs, ids = trough_analysis._match_obs_with_forecast(obs, tracker)

    assert len(pairs) == 1
    assert ids == {0}


# ---------------- 低涡 ----------------

def _vortex_track(tracker, track_id, lon, lat):
    tracker.tracks[track_id] = [{
        "lon": lon, "lat": lat, "value": 300, "strength": 1,
        "time_str": ".000", "fcst_time": None, "forecast_hour": 0,
    }]


def _obs_vortex(lon, lat):
    return {"geometry": {"type": "point", "lon": lon, "lat": lat},
            "properties": {"value": 300}}


def test_vortex_one_to_one_matching():
    tracker = VortexTracker()
    _vortex_track(tracker, 1, 115.0, 39.0)

    obs = [_obs_vortex(115.1, 39.0), _obs_vortex(115.5, 39.2)]
    pairs, ids = vortex_analysis._match_obs_with_forecast(obs, tracker)

    assert len(pairs) == 1, "同一低涡轨迹被匹配了多次"
    assert pairs[0][0] is obs[0]
    assert ids == {1}
