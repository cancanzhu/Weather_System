"""
低空低涡识别器
==============
识别 700hPa 和 850hPa 层次的低空低涡。

预报数据识别方式:
    使用 metdig.cal.high_low_center() 算法识别高低压中心，
    从中筛选低压中心（feature_id < 0）作为低涡。

实况数据识别方式:
    从 MICAPS14 符号标注中提取 symbol_code == 61（低压中心）。
"""
import logging
import meteva.base as meb
from config.settings import SMOOTH_POINTS_DETECT
from typing import List, Dict, Any
import metdig.cal as mdgcal
from modules.detection.base_detector import BaseDetector

logger = logging.getLogger(__name__)


class LowLevelVortexDetector(BaseDetector):
    """低空低涡识别器"""

    system_name = "低空低涡"
    required_vars = ["GH"]

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
        从 MICAPS4 预报数据中识别低空低涡。

        使用 metdig.cal.high_low_center() 识别高低压中心，
        筛选 feature_id < 0 的低压中心。
        """
        grd = data_dict.get("GH")
        if grd is None:
            return []

        try:
            grd = meb.comp.smooth(grd, SMOOTH_POINTS_DETECT)
            grd.attrs["var_units"] = "gpm"
            grd.attrs["var_name"] = "hgt"

            caldata = mdgcal.high_low_center(grd)
            graphy = caldata.get("graphy", {})
            features = graphy.get("features", {})

            if not features:
                logger.info(f"预报 {level}hPa: 未识别到高低压中心")
                return []

            results = []
            for feature_id, feature in features.items():
                if int(feature_id) < 0:  # 负数ID = 低压中心 = 低涡
                    center = feature["center"]
                    lon = center["lon"]
                    lat = center["lat"]
                    value = center["value"]

                    results.append({
                        "system_name": self.system_name,
                        "level": level,
                        "center_lon": lon,
                        "center_lat": lat,
                        "geometry": {
                            "type": "point",
                            "lon": lon,
                            "lat": lat,
                        },
                        "properties": {
                            "source": "metdig_auto",
                            "feature_id": feature_id,
                            "value": value,
                            "strength": value,
                            "caldata": caldata,
                        },
                    })

            logger.info(f"预报 {level}hPa: 识别到 {len(results)} 个低空低涡")
            return results

        except Exception as e:
            logger.error(f"预报低空低涡识别失败: {e}")
            return []

    def _detect_from_observation(self, data_dict: dict, level: int) -> List[Dict[str, Any]]:
        """
        从 MICAPS14 实况数据中提取低压中心（symbol_code == 61）。
        """
        hgt_data = data_dict.get("HGT")
        if hgt_data is None:
            return []

        try:
            symbols = hgt_data.get("symbols")
            if symbols is None:
                return []

            results = []
            for i, code in enumerate(symbols["symbol_code"]):
                if code == 61:  # 低压中心
                    lon = symbols["symbol_xyz"][i][0]
                    lat = symbols["symbol_xyz"][i][1]

                    results.append({
                        "system_name": self.system_name,
                        "level": level,
                        "center_lon": lon,
                        "center_lat": lat,
                        "geometry": {
                            "type": "point",
                            "lon": lon,
                            "lat": lat,
                        },
                        "properties": {
                            "source": "manual_analysis",
                            "index": i,
                        },
                    })

            logger.info(f"实况 {level}hPa: 提取到 {len(results)} 个低空低涡")
            return results

        except Exception as e:
            logger.error(f"实况低空低涡提取失败: {e}")
            return []