"""
路径构建工具
============
根据时间、变量、层次等参数构建 MICAPS4 / MICAPS14 数据文件的完整路径。

路径规则:
    MICAPS4:  {root}/{YYYYMMDD}/{model}/{variable}/{level}/{YYMMDDhh}.{FFF}
    MICAPS14: {root}/{YYYY}/{YYYYMMDD}/UPPER_AIR/MANUAL_ANALYSIS/{variable}/{level}/{YYYYMMDDHHmmss}.000
"""
import os
from datetime import datetime, timedelta
from typing import List


def build_micaps4_path(
    root: str,
    model: str,
    variable: str,
    level: int,
    init_time: datetime,
    forecast_hour: int,
) -> str:
    """
    构建 MICAPS4 预报数据文件路径。

    Args:
        root:          MICAPS4 根目录
        model:         模式名称，如 "ECWMF"
        variable:      变量名，如 "GH", "T", "U", "V"
        level:         层次，如 500, 700, 850, 925
        init_time:     起报时间
        forecast_hour: 预报时效（小时）

    Returns:
        完整文件路径

    示例:
        >>> build_micaps4_path("/data/micaps4", "ECWMF", "GH", 500,
        ...                    datetime(2025,6,1,8), 3)
        "/data/micaps4/20250601/ECWMF/GH/500/25060108.003"
    """
    date_dir = init_time.strftime("%Y%m%d")
    filename = f"{init_time.strftime('%y%m%d%H')}.{forecast_hour:03d}"
    return os.path.join(root, date_dir, model, variable, str(level), filename)


def build_micaps14_path(
    root: str,
    variable: str,
    level: int,
    obs_time: datetime,
) -> str:
    """
    构建 MICAPS14 实况数据文件路径。

    Args:
        root:     MICAPS14 根目录
        variable: 变量名，如 "HGT", "TMP"
        level:    层次，如 500, 700, 850
        obs_time: 观测时间

    Returns:
        完整文件路径

    示例:
        >>> build_micaps14_path("/data/UPPER_AIR", "HGT", 500,
        ...                     datetime(2025,6,1,8))
        "/data/UPPER_AIR/2025/20250601/UPPER_AIR/MANUAL_ANALYSIS/HGT/500/20250601080000.000"
    """
    year_dir = obs_time.strftime("%Y")
    date_dir = obs_time.strftime("%Y%m%d")
    filename = f"{obs_time.strftime('%Y%m%d%H%M%S')}.000"
    return os.path.join(root, year_dir, date_dir, "UPPER_AIR",
                        "MANUAL_ANALYSIS", variable, str(level), filename)


def build_mdfs_wind_path(
    root: str,
    level: int,
    obs_time: datetime,
) -> str:
    """
    构建 MDFS 高空站点风场数据文件路径。

    Args:
        root:     MICAPS14 根目录
        level:    层次，如 500, 700, 850
        obs_time: 观测时间

    Returns:
        完整文件路径
    """
    year_dir = obs_time.strftime("%Y")
    date_dir = obs_time.strftime("%Y%m%d")
    filename = f"{obs_time.strftime('%Y%m%d%H%M%S')}.000"
    return os.path.join(root, year_dir, date_dir, "UPPER_AIR",
                        "PLOT", str(level), filename)


def get_forecast_valid_times(
    init_time: datetime, forecast_hours: List[int]
) -> List[datetime]:
    """
    根据起报时间和预报时效列表，计算所有预报有效时间。

    Args:
        init_time:      起报时间
        forecast_hours: 预报时效列表，如 [0, 3, 6, 9, 12]

    Returns:
        预报有效时间列表
    """
    return [init_time + timedelta(hours=h) for h in forecast_hours]
