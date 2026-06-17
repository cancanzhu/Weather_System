"""
数据调度管理器
==============
根据当前时间和起报时刻，统一调度 MICAPS4 / MICAPS14 数据读取。
返回标准化的字典结构供后续的识别、可视化、报告模块使用。

数据键格式:
    (time_label: str, level: int)

    time_label 示例:
        实况: "2025060108(实况)"
        预报: "2025060108(+000h)", "2025060111(+003h)", ...

数据值格式:
    {
        "GH":  xarray.DataArray / None,   # 预报高度场（MICAPS4）
        "T":   xarray.DataArray / None,   # 预报温度场（MICAPS4）
        "U":   xarray.DataArray / None,   # 预报U风场（MICAPS4）
        "V":   xarray.DataArray / None,   # 预报V风场（MICAPS4）
        "HGT": dict / None,              # 实况高度场（MICAPS14 字典）
        "TMP": dict / None,              # 实况温度场（MICAPS14 字典）
        "time":          datetime,
        "level":         int,
        "data_type":     "obs" / "fcst",
        "init_time":     datetime,        # 仅预报
        "forecast_hour": int,             # 仅预报
    }
"""
import logging
from datetime import datetime, timedelta
from typing import Dict, Tuple, Any

from config import settings
from modules.data_io.micaps4_reader import Micaps4Reader
from modules.data_io.micaps14_reader import Micaps14Reader
from modules.data_io.mdfs_wind_reader import MdfsWindReader
from utils.path_builder import build_micaps4_path, build_micaps14_path, build_mdfs_wind_path

logger = logging.getLogger(__name__)

# 数据字典的键类型
DataKey = Tuple[str, int]


class DataManager:
    """
    数据调度管理器

    统一管理预报数据和实况数据的读取，为下游模块提供一致的数据访问接口。

    Attributes:
        current_time: 用户输入的当前时间
        init_hour:    起报时刻 (8 或 20)
        init_time:    起报时间（datetime，分/秒归零）
    """

    def __init__(self, current_time: datetime, init_hour: int):
        self.current_time = current_time
        self.init_hour = init_hour
        self.init_time = current_time.replace(
            hour=init_hour, minute=0, second=0, microsecond=0
        )
        self._micaps4_reader = Micaps4Reader()
        self._micaps14_reader = Micaps14Reader()
        self._mdfs_reader = MdfsWindReader()

    def load_forecast_data(self) -> Dict[DataKey, Dict[str, Any]]:
        """
        读取未来 12h 的 MICAPS4 预报数据（含起报时刻）。

        遍历: 预报时效 [0,3,6,9,12] × 层次 [500,700,850] × 变量 [GH,T,U,V]

        Returns:
            {(time_label, level): {变量名: 数据, ...}, ...}
        """
        result = {}

        for fh in settings.FORECAST_HOURS:
            valid_time = self.init_time + timedelta(hours=fh)
            time_label = valid_time.strftime("%Y%m%d%H") + f"(+{fh:03d}h)"

            for level in settings.PLOT_LEVELS:
                data_dict: Dict[str, Any] = {
                    "time": valid_time,
                    "level": level,
                    "data_type": "fcst",
                    "init_time": self.init_time,
                    "forecast_hour": fh,
                }

                has_data = False
                for var_name, var_levels in settings.MICAPS4_VARIABLES.items():
                    if level not in var_levels:
                        continue

                    filepath = build_micaps4_path(
                        root=settings.MICAPS4_ROOT,
                        model=settings.MICAPS4_MODEL,
                        variable=var_name,
                        level=level,
                        init_time=self.init_time,
                        forecast_hour=fh,
                    )

                    data = self._micaps4_reader.read(filepath)
                    if data is not None:
                        data_dict[var_name] = data
                        has_data = True
                    else:
                        logger.debug(
                            f"预报数据缺失: {var_name}/{level}/{time_label}"
                        )

                if has_data:
                    result[(time_label, level)] = data_dict

        logger.info(
            f"预报数据读取完成: 共 {len(result)} 组 "
            f"(起报: {self.init_time.strftime('%Y%m%d%H')})"
        )
        return result

    def load_observation_data(self) -> Dict[DataKey, Dict[str, Any]]:
        """
        读取 MICAPS14 实况数据（仅起报时刻）。

        遍历: 层次 [500,700,850] × 变量 [HGT,TMP]

        Returns:
            {(time_label, level): {变量名: 数据, ...}, ...}
        """
        result = {}
        obs_time = self.init_time
        time_label = obs_time.strftime("%Y%m%d%H") + "(实况)"

        for level in settings.PLOT_LEVELS:
            data_dict: Dict[str, Any] = {
                "time": obs_time,
                "level": level,
                "data_type": "obs",
            }

            has_data = False
            for var_name, var_levels in settings.MICAPS14_VARIABLES.items():
                if level not in var_levels:
                    continue

                filepath = build_micaps14_path(
                    root=settings.MICAPS14_ROOT,
                    variable=var_name,
                    level=level,
                    obs_time=obs_time,
                )

                data = self._micaps14_reader.read(filepath)
                if data is not None:
                    data_dict[var_name] = data
                    has_data = True
                else:
                    logger.debug(
                        f"实况数据缺失: {var_name}/{level}/{time_label}"
                    )

            # 加载 MDFS 站点风场数据
            wind_path = build_mdfs_wind_path(
                root=settings.MICAPS14_ROOT,
                level=level,
                obs_time=obs_time,
            )
            wind_df = self._mdfs_reader.read(wind_path)
            if wind_df is not None:
                data_dict["wind_df"] = wind_df

            if has_data:
                result[(time_label, level)] = data_dict

        logger.info(
            f"实况数据读取完成: 共 {len(result)} 组 "
            f"(观测时间: {obs_time.strftime('%Y%m%d%H')})"
        )
        return result
