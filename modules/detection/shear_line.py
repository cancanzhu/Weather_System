"""
切变线识别器
============
700/850hPa 切变线。

预报数据识别方式:
    使用 metdig.cal.shear() 对 U/V 风场识别切变线。
    结果存于 caldata["graphy"]（与高空槽 trough 同一套机制），
    graphy 原样存储供 add_solid_lines 绑图、caldata 供追踪器抽线。

实况数据识别方式:
    从 MICAPS14 HGT 的 lines_symbol 中提取 code 为 0 或 1 的线
    （700/850 的槽线即切变线）。
"""
import logging
from typing import List, Dict, Any
import numpy as np
import metdig.cal as mdgcal
from modules.detection.base_detector import BaseDetector
from config.settings import SHEAR_RESOLUTION, SHEAR_SMOOTH_TIMES, SHEAR_MIN_SIZE

logger = logging.getLogger(__name__)


class ShearLineDetector(BaseDetector):
    """切变线识别器"""

    system_name = "切变线"
    required_vars = ["U", "V"]

    def detect(self, data_dict: dict, level: int) -> List[Dict[str, Any]]:
        data_type = data_dict.get("data_type", "fcst")
        if data_type == "fcst":
            return self._detect_from_forecast(data_dict, level)
        elif data_type == "obs":
            return self._detect_from_observation(data_dict, level)
        return []

    def _detect_from_forecast(self, data_dict: dict, level: int) -> List[Dict[str, Any]]:
        """
        从 MICAPS4 预报数据中识别切变线。

        mdgcal.shear() 的返回结构（已实测）:
            caldata["graphy"]["features"] → {编号: {axes, center, region, type}}
            每条线坐标在 axes["point"]，长度在 axes["lenght"]。
            graphy 原样存储，用 meb.add_solid_lines 绘制。
        """
        u = data_dict.get("U")
        v = data_dict.get("V")
        if u is None or v is None:
            logger.debug("预报数据中无 U/V 变量，跳过切变线识别")
            return []

        try:
            caldata = mdgcal.shear(
                u, v,
                resolution=SHEAR_RESOLUTION,
                smooth_times=SHEAR_SMOOTH_TIMES,
                min_size=SHEAR_MIN_SIZE,
            )

            graphy = caldata.get("graphy") if caldata else None
            features = graphy.get("features", {}) if isinstance(graphy, dict) else {}
            if not features:
                logger.info(f"预报 {level}hPa: 未识别到切变线")
                return []

            logger.info(f"预报 {level}hPa: 识别到 {len(features)} 条切变线")
            return [{
                "system_name": self.system_name,
                "level": level,
                "center_lon": None,
                "center_lat": None,
                "geometry": {
                    "type": "graphy_raw",
                    "graphy": graphy,        # 原样存储供 add_solid_lines
                },
                "properties": {
                    "source": "metdig_auto",
                    "caldata": caldata,      # 供追踪器从 graphy.features 抽线
                    "shear_count": len(features),
                },
            }]

        except Exception as e:
            logger.error(f"预报切变线识别失败: {e}")
            return []

    def _detect_from_observation(self, data_dict: dict, level: int) -> List[Dict[str, Any]]:
        """
        从 MICAPS14 实况数据中提取切变线。

        lines_symbol 中 code 为 0 或 1 的线即为槽线/切变线。
        """
        hgt_data = data_dict.get("HGT")
        if hgt_data is None:
            return []

        try:
            lines_symbol = hgt_data.get("lines_symbol")
            if lines_symbol is None:
                logger.info(f"实况 {level}hPa: 无线符号数据")
                return []

            results = []
            for i in range(len(lines_symbol["linesym_code"])):
                code = lines_symbol["linesym_code"][i]
                if code in (0, 1):                       # 0、1 均为槽线/切变线
                    line_xyz = lines_symbol["linesym_xyz"][i]
                    points = line_xyz[:, 0:2]            # 取 lon, lat
                    results.append({
                        "system_name": self.system_name,
                        "level": level,
                        "geometry": {"type": "line", "points": points.tolist()},
                        "center_lon": float(np.mean(points[:, 0])),
                        "center_lat": float(np.mean(points[:, 1])),
                        "properties": {"source": "manual_analysis", "index": i},
                    })

            logger.info(f"实况 {level}hPa: 提取到 {len(results)} 条切变线")
            return results

        except Exception as e:
            logger.error(f"实况切变线提取失败: {e}")
            return []