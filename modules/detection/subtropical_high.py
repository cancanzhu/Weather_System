"""
副热带高压识别器
================
识别 500hPa 层次的副热带高压（588线）。

预报数据识别方式:
    从 GH（高度场）格网数据中提取 588 等值线（即 5880gpm）。
    使用 matplotlib 的 contour 提取等值线坐标。

实况数据识别方式:
    从 MICAPS14 HGT 数据的等值线中筛选标签为 "588" 的线。
"""
import logging
from typing import List, Dict, Any
import numpy as np
from modules.detection.base_detector import BaseDetector
import meteva.base as meb
from config.settings import SMOOTH_POINTS_PLOT

logger = logging.getLogger(__name__)


class SubtropicalHighDetector(BaseDetector):
    """副热带高压识别器"""

    system_name = "副热带高压"
    required_vars = ["GH"]

    # 588线对应的等值线值（500hPa高度场单位为10gpm，所以是588）
    CONTOUR_VALUE = 588

    def detect(self, data_dict: dict, level: int) -> List[Dict[str, Any]]:
        data_type = data_dict.get("data_type", "fcst")

        if data_type == "fcst":
            return self._detect_from_forecast(data_dict, level)
        elif data_type == "obs":
            return self._detect_from_observation(data_dict, level)
        else:
            return []

    def _detect_from_forecast(self, data_dict: dict, level: int) -> List[Dict[str, Any]]:
        """
        从 MICAPS4 预报数据中提取 588 等值线。

        使用 matplotlib.contour 提取等值线坐标，不实际绑图。
        """
        grd = data_dict.get("GH")
        if grd is None:
            return []

        try:
            import matplotlib.pyplot as plt

            grd = meb.comp.smooth(grd, SMOOTH_POINTS_PLOT)
            grd_2d = grd.squeeze()
            lons = grd_2d["lon"].values
            lats = grd_2d["lat"].values

            # 用临时 figure 提取等值线坐标
            fig_tmp, ax_tmp = plt.subplots()
            cs = ax_tmp.contour(lons, lats, grd_2d.values, levels=[self.CONTOUR_VALUE])
            plt.close(fig_tmp)

            results = []
            # cs.allsegs[i] 对应第 i 个 level 的所有线段
            # 我们只传了一个 level（588），所以取 allsegs[0]
            if len(cs.allsegs) > 0:
                for seg in cs.allsegs[0]:
                    if len(seg) < 2:
                        continue

                    results.append({
                        "system_name": self.system_name,
                        "level": level,
                        "center_lon": float(np.mean(seg[:, 0])),
                        "center_lat": float(np.mean(seg[:, 1])),
                        "geometry": {
                            "type": "line",
                            "points": seg.tolist(),
                        },
                        "properties": {
                            "source": "contour_extract",
                            "contour_value": self.CONTOUR_VALUE,
                        },
                    })

            logger.info(f"预报 {level}hPa: 识别到 {len(results)} 条588线")
            return results
        
        except Exception as e:
            logger.error(f"预报副热带高压识别失败: {e}")
            return []

    def _detect_from_observation(self, data_dict: dict, level: int) -> List[Dict[str, Any]]:
        """
        从 MICAPS14 实况数据中筛选标签为 "588" 的等值线。
        """
        hgt_data = data_dict.get("HGT")
        if hgt_data is None:
            return []

        try:
            lines = hgt_data.get("lines")
            if lines is None:
                return []

            results = []
            for i in range(len(lines["line_label"])):
                label = str(lines["line_label"][i]).strip()
                if label == "588":
                    line_xyz = lines["line_xyz"][i]
                    points = line_xyz[:, 0:2]

                    results.append({
                        "system_name": self.system_name,
                        "level": level,
                        "center_lon": float(np.mean(points[:, 0])),
                        "center_lat": float(np.mean(points[:, 1])),
                        "geometry": {
                            "type": "line",
                            "points": points.tolist(),
                        },
                        "properties": {
                            "source": "manual_analysis",
                            "index": i,
                        },
                    })

            logger.info(f"实况 {level}hPa: 提取到 {len(results)} 条588线")
            return results

        except Exception as e:
            logger.error(f"实况副热带高压提取失败: {e}")
            return []