"""
冷涡识别器
==========
识别 500hPa 层次的温度冷中心。

命名说明:
    本识别器单独输出的是"温度冷中心"，并非严格意义的冷涡。
    真正的冷涡判定（GH 低压中心 + 冷中心配合，距离 ≤ 300km）在
    modules/tracking/cold_vortex_analysis.py 中完成。
    第一份识别报告中以"冷涡"标注的点实为冷中心，阅读时注意区分。
    另: required_vars 声明 GH+T 是为了保证配合判断所需数据齐全，
    本识别器 detect() 实际只使用 T。

预报数据识别方式:
    使用 metdig.cal.high_low_center() 对 T（温度场）识别冷暖中心，
    筛选 feature_id < 0 的冷中心。

实况数据识别方式:
    从 MICAPS14 HGT 数据的符号标注中提取 symbol_code == 63（冷中心）。
"""
import logging
import meteva.base as meb
from config.settings import SMOOTH_POINTS_DETECT
from typing import List, Dict, Any
import metdig.cal as mdgcal
from modules.detection.base_detector import BaseDetector

logger = logging.getLogger(__name__)


class ColdVortexDetector(BaseDetector):
    """冷涡识别器"""

    system_name = "冷涡"
    required_vars = ["GH", "T"]

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
        从 MICAPS4 预报数据中识别冷涡。

        对 T（温度场）使用 high_low_center()，
        筛选 feature_id < 0 的冷中心。
        """
        grd = data_dict.get("T")
        if grd is None:
            logger.debug("预报数据中无 T 变量，跳过冷涡识别")
            return []

        try:
            grd = meb.comp.smooth(grd, SMOOTH_POINTS_DETECT)
            grd.attrs["var_units"] = "gpm"
            grd.attrs["var_name"] = "hgt"

            caldata = mdgcal.high_low_center(grd)
            graphy = caldata.get("graphy", {})
            features = graphy.get("features", {})

            if not features:
                logger.info(f"预报 {level}hPa: 未识别到冷暖中心")
                return []

            results = []
            for feature_id, feature in features.items():
                if int(feature_id) < 0:  # 负数ID = 冷中心
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
                        },
                    })

            logger.info(f"预报 {level}hPa: 识别到 {len(results)} 个冷涡")
            return results

        except Exception as e:
            logger.error(f"预报冷涡识别失败: {e}")
            return []

    def _detect_from_observation(self, data_dict: dict, level: int) -> List[Dict[str, Any]]:
        """
        从 MICAPS14 实况数据中提取冷中心（symbol_code == 63）。
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
                if code == 63:  # 冷中心
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

            logger.info(f"实况 {level}hPa: 提取到 {len(results)} 个冷涡")
            return results

        except Exception as e:
            logger.error(f"实况冷涡提取失败: {e}")
            return []