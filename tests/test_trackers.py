# -*- coding: utf-8 -*-
"""
追踪器单元测试
==============
覆盖 2026-06 修复:
    - 缺测容忍: 单个空时次不断轨, 连续两个空时次才断轨
    - 速度约束按实际时间间隔计算, 不再硬编码 3 小时

运行: 工程根目录执行  python -m pytest tests/ -v
不依赖 meteva/metdig, 仅需 numpy (scipy 可选)。
"""
import os
import sys
from datetime import datetime, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from modules.tracking.vortex_tracker import VortexTracker
from modules.tracking.trough_tracker import TroughTracker


def _det(lon, lat):
    """构造一个低涡识别结果"""
    return [{
        "geometry": {"type": "point", "lon": lon, "lat": lat},
        "properties": {"value": 300, "strength": 1},
    }]


def test_vortex_track_survives_one_missing_timestep():
    """中间缺测一个时次, 轨迹应接上而不是断成两条"""
    t0 = datetime(2025, 6, 1, 8)
    tr = VortexTracker()
    tr.update(_det(115.0, 40.0), ".000", t0)
    tr.update([], ".003", t0 + timedelta(hours=3))            # 缺测
    tr.update(_det(115.6, 40.2), ".006", t0 + timedelta(hours=6))

    assert len(tr.tracks) == 1, f"轨迹被错误切断, 实际 {len(tr.tracks)} 条"
    assert len(tr.tracks[1]) == 2


def test_vortex_track_breaks_after_two_missing_timesteps():
    """连续缺测两个时次, 应判定系统消亡并断轨"""
    t0 = datetime(2025, 6, 1, 8)
    tr = VortexTracker()
    tr.update(_det(115.0, 40.0), ".000", t0)
    tr.update([], ".003", t0 + timedelta(hours=3))
    tr.update([], ".006", t0 + timedelta(hours=6))
    tr.update(_det(115.6, 40.2), ".009", t0 + timedelta(hours=9))

    assert len(tr.tracks) == 2, "连续两个空时次后应新建轨迹"


def test_vortex_speed_constraint_uses_actual_time_gap():
    """
    跨缺测时次后实际间隔 6h。约 230km 位移 → 38km/h, 低于 60km/h 限速,
    应能接上。旧版硬编码 3h 会按 77km/h 误判断开。
    """
    t0 = datetime(2025, 6, 1, 8)
    tr = VortexTracker()
    tr.update(_det(115.0, 40.0), ".000", t0)
    tr.update([], ".003", t0 + timedelta(hours=3))
    # 2.7 个经度 ≈ 230km (40°N)
    tr.update(_det(117.7, 40.0), ".006", t0 + timedelta(hours=6))

    assert len(tr.tracks) == 1, "速度约束未按实际 6h 间隔计算"
    assert len(tr.tracks[1]) == 2


def test_vortex_speed_constraint_still_rejects_too_fast():
    """正常 3h 间隔下超速移动仍应判为不同系统"""
    t0 = datetime(2025, 6, 1, 8)
    tr = VortexTracker()
    tr.update(_det(115.0, 40.0), ".000", t0)
    # 2.7 个经度 ≈ 230km / 3h ≈ 77km/h > 60km/h 限速 → 断开
    tr.update(_det(117.7, 40.0), ".003", t0 + timedelta(hours=3))

    assert len(tr.tracks) == 2, "超速移动应判为新系统"


def _trough_caldata(lon, lat):
    """构造一个最小可用的 metdig trough 返回结构（仅含追踪所需字段）"""
    return {
        "graphy": {
            "features": {
                "1": {
                    "axes": {
                        "point": [[lon, lat + 1.0], [lon, lat - 1.0]],
                        "lenght": 10,   # metdig 原始字段拼写如此
                    },
                    "center": {"lon": lon, "lat": lat},
                    "region": {"strength": 5},
                },
            },
        },
    }


def test_trough_track_survives_one_missing_timestep():
    t0 = datetime(2025, 6, 1, 8)
    tr = TroughTracker()
    tr.update(_trough_caldata(110.0, 40.0), ".000", t0)
    tr.update({"graphy": {"features": {}}}, ".003", t0 + timedelta(hours=3))  # 空时次
    tr.update(_trough_caldata(110.8, 40.0), ".006", t0 + timedelta(hours=6))

    assert len(tr.tracks) == 1, f"槽线轨迹被错误切断, 实际 {len(tr.tracks)} 条"
    assert len(tr.tracks[1]) == 2


def test_trough_track_breaks_after_two_missing_timesteps():
    t0 = datetime(2025, 6, 1, 8)
    tr = TroughTracker()
    tr.update(_trough_caldata(110.0, 40.0), ".000", t0)
    tr.update({"graphy": {"features": {}}}, ".003", t0 + timedelta(hours=3))
    tr.update({"graphy": {"features": {}}}, ".006", t0 + timedelta(hours=6))
    tr.update(_trough_caldata(110.8, 40.0), ".009", t0 + timedelta(hours=9))

    assert len(tr.tracks) == 2
