"""
低空急流识别器
==============
识别 850hPa 层次的低空急流。

预报数据识别方式:
    使用 metdig.cal.jet() 对 U/V 风场自动识别急流轴线。
    graphy 数据不可拆解，原样存储供绑图使用。

实况数据识别方式:
    从 MICAPS14 HGT 数据的 fill_area 字段中提取
    code 为 1102 或 1110~1116 的线条。
"""
import logging
from typing import List, Dict, Any
import numpy as np
import metdig.cal as mdgcal
from modules.detection.base_detector import BaseDetector
from config.settings import JET_RESOLUTION, JET_SMOOTH_TIMES, JET_MIN_SIZE, JET_MIN_SPEED, JET_ONLY_SOUTH

logger = logging.getLogger(__name__)


class LowLevelJetDetector(BaseDetector):
    """低空急流识别器"""

    system_name = "低空急流"
    required_vars = ["U", "V"]

    # metdig.cal.jet 参数
    RESOLUTION = JET_RESOLUTION
    SMOOTH_TIMES = JET_SMOOTH_TIMES
    MIN_SIZE = JET_MIN_SIZE
    JET_MIN_SPEED = JET_MIN_SPEED
    ONLY_SOUTH_JET = JET_ONLY_SOUTH

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
        从 MICAPS4 预报数据中识别低空急流。

        使用 metdig.cal.jet() 识别急流轴线。
        graphy 数据不可拆解，原样存储。
        """
        u_grd = data_dict.get("U")
        v_grd = data_dict.get("V")
        if u_grd is None or v_grd is None:
            logger.debug("预报数据中无 U/V 变量，跳过低空急流识别")
            return []

        try:
            jet_result = mdgcal.jet(
                u_grd, v_grd,
                resolution=self.RESOLUTION,
                smooth_times=self.SMOOTH_TIMES,
                min_size=self.MIN_SIZE,
                jet_min_speed=self.JET_MIN_SPEED,
                only_south_jet=self.ONLY_SOUTH_JET,
            )

            graphy = jet_result.get("graphy", None)
            if not graphy:
                logger.info(f"预报 {level}hPa: 未识别到低空急流")
                return []

            # graphy 不可拆解，原样存储
            results = [{
                "system_name": self.system_name,
                "level": level,
                "center_lon": None,
                "center_lat": None,
                "geometry": {
                    "type": "graphy_raw",
                    "graphy": graphy,
                },
                "properties": {
                    "source": "metdig_auto",
                },
            }]

            logger.info(f"预报 {level}hPa: 识别到低空急流")
            return results

        except Exception as e:
            logger.error(f"预报低空急流识别失败: {e}")
            return []

    def _detect_from_observation(self, data_dict: dict, level: int) -> List[Dict[str, Any]]:
        """
        从 MICAPS14 实况数据中提取低空急流。

        从 fill_area 字段中筛选 code 为 1102 或 1110~1116 的线条。
        """
        hgt_data = data_dict.get("HGT")
        if hgt_data is None:
            return []

        try:
            fillarea = hgt_data.get("fill_area")
            if fillarea is None:
                logger.debug(f"实况 {level}hPa: 无 fill_area 字段")
                return []

            # 自动匹配 code 和 xyz 字段名
            code_key = None
            xyz_key = None
            for k in fillarea.keys():
                kl = k.lower()
                if "code" in kl or "type" in kl:
                    code_key = k
                if "xyz" in kl or "point" in kl or "line" in kl:
                    xyz_key = k

            if code_key is None or xyz_key is None:
                logger.warning(f"实况 {level}hPa: fill_area 字段中未找到 code/xyz 子字段")
                return []

            codes = fillarea[code_key]
            xyzs = fillarea[xyz_key]

            jet_lines = []
            for i in range(len(codes)):
                code = codes[i]
                if code == 1102 or (1110 <= code <= 1116):
                    line_xyz = xyzs[i]
                    jet_lines.append(line_xyz[:, 0:2].tolist())

            if not jet_lines:
                logger.info(f"实况 {level}hPa: 未找到低空急流线条")
                return []

            results = [{
                "system_name": self.system_name,
                "level": level,
                "center_lon": None,
                "center_lat": None,
                "geometry": {
                    "type": "jet_lines",
                    "lines": jet_lines,
                },
                "properties": {
                    "source": "manual_analysis",
                    "line_count": len(jet_lines),
                },
            }]

            logger.info(f"实况 {level}hPa: 提取到 {len(jet_lines)} 条低空急流")
            return results

        except Exception as e:
            logger.error(f"实况低空急流提取失败: {e}")
            return []