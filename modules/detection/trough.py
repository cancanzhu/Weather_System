"""
高空槽识别器
============
识别 500hPa 层次的高空槽线。

预报数据识别方式:
    使用 metdig.cal.trough() 算法自动识别 MICAPS4 格网数据中的槽线。
    输入: GH 高度场 xarray.DataArray
    输出: 槽线坐标列表

实况数据识别方式:
    MICAPS14 手工分析数据中已包含人工标注的槽线（lines_symbol, code=0）。
    直接从数据字典中提取。

依赖:
    metdig (pip install metdig) — 仅预报识别需要
"""
import logging
import meteva.base as meb
from config.settings import SMOOTH_POINTS_DETECT
from config.settings import TROUGH_RESOLUTION, TROUGH_SMOOTH_TIMES, TROUGH_MIN_SIZE
from typing import List, Dict, Any
import numpy as np
import metdig.cal as mdgcal
from modules.detection.base_detector import BaseDetector

logger = logging.getLogger(__name__)


class TroughDetector(BaseDetector):
    """
    高空槽识别器

    支持两种数据源:
        - 预报 (fcst): 使用 metdig 算法从格网数据自动识别
        - 实况 (obs):  从 MICAPS14 手工分析数据中提取已标注的槽线
    """

    system_name = "高空槽"
    required_vars = ["GH"]  # 预报变量名; 实况为 "HGT"

    # metdig.cal.trough 参数
    RESOLUTION = TROUGH_RESOLUTION
    SMOOTH_TIMES = TROUGH_SMOOTH_TIMES
    MIN_SIZE = TROUGH_MIN_SIZE

    def detect(self, data_dict: dict, level: int) -> List[Dict[str, Any]]:
        """
        执行高空槽识别。

        Args:
            data_dict: 数据字典，包含 data_type 标识
            level:     层次（通常为 500）

        Returns:
            识别到的槽线列表
        """
        data_type = data_dict.get("data_type", "fcst")

        if data_type == "fcst":
            return self._detect_from_forecast(data_dict, level)
        elif data_type == "obs":
            return self._detect_from_observation(data_dict, level)
        else:
            logger.warning(f"未知 data_type: {data_type}")
            return []

    def _detect_from_forecast(
        self, data_dict: dict, level: int
    ) -> List[Dict[str, Any]]:
        """
        从 MICAPS4 预报数据中识别高空槽。

        使用 metdig.cal.trough() 进行自动识别。
        graphy 数据直接存储原始格式，供 system_plotter 使用 meb.add_solid_lines 绘制。
        """
        grd = data_dict.get("GH")
        if grd is None:
            logger.debug("预报数据中无 GH 变量，跳过高空槽识别")
            return []

        try:
            # 添加 metdig 需要的属性
            grd = meb.comp.smooth(grd, SMOOTH_POINTS_DETECT)
            grd.attrs["var_units"] = "gpm"
            grd.attrs["var_name"] = "hgt"

            # 调用 metdig 槽线识别算法
            caldata = mdgcal.trough(
                grd,
                resolution=self.RESOLUTION,
                smooth_times=self.SMOOTH_TIMES,
                min_size=self.MIN_SIZE,
            )

            graphy = caldata.get("graphy", [])
            if not graphy:
                logger.info(f"预报 {level}hPa: 未识别到高空槽")
                return []

            # 直接将 graphy 作为整体存入一个结果中
            # graphy 是 meb.add_solid_lines 所需的三层嵌套列表格式
            # 不做拆分，保持原始结构以确保绘图兼容性
            results = [{
                "system_name": self.system_name,
                "level": level,
                "geometry": {
                    "type": "graphy_raw",
                    "graphy": graphy,
                },
                "center_lon": None,
                "center_lat": None,
                "properties": {
                    "source": "metdig_auto",
                    "trough_count": len(graphy.get("features", {})),
                    "caldata": caldata,
                },
            }]

            logger.info(
                f"预报 {level}hPa: 识别到 "
                f"{len(graphy.get('features', {}))} 条高空槽"
            )
            return results

        except Exception as e:
            logger.error(f"预报高空槽识别失败: {e}")
            return []

    def _detect_from_observation(
        self, data_dict: dict, level: int
    ) -> List[Dict[str, Any]]:
        """
        从 MICAPS14 实况数据中提取人工标注的槽线。

        MICAPS14 数据结构:
            data_dict["HGT"]["lines_symbol"]["linesym_code"]  → 代码列表（0=槽线）
            data_dict["HGT"]["lines_symbol"]["linesym_xyz"]   → 坐标列表
        """
        hgt_data = data_dict.get("HGT")
        if hgt_data is None:
            logger.debug("实况数据中无 HGT 变量，跳过高空槽识别")
            return []

        try:
            lines_symbol = hgt_data.get("lines_symbol")
            if lines_symbol is None:
                logger.info(f"实况 {level}hPa: 无线符号数据")
                return []

            results = []
            for i in range(len(lines_symbol["linesym_code"])):
                code = lines_symbol["linesym_code"][i]
                if code == 0:  # 0 = 槽线
                    line_xyz = lines_symbol["linesym_xyz"][i]
                    points = line_xyz[:, 0:2]  # 取 lon, lat
                    center_lon = float(np.mean(points[:, 0]))
                    center_lat = float(np.mean(points[:, 1]))

                    results.append({
                        "system_name": self.system_name,
                        "level": level,
                        "geometry": {
                            "type": "line",
                            "points": points.tolist(),
                        },
                        "center_lon": center_lon,
                        "center_lat": center_lat,
                        "properties": {
                            "source": "manual_analysis",
                            "index": i,
                        },
                    })

            logger.info(
                f"实况 {level}hPa: 提取到 {len(results)} 条高空槽"
            )
            return results

        except Exception as e:
            logger.error(f"实况高空槽提取失败: {e}")
            return []
