"""
识别器工厂
==========
根据 WEATHER_SYSTEM_REGISTRY 配置，动态加载并管理所有天气系统识别器。

本模块是插件化设计的核心:
    - 新增天气系统时，此文件无需修改
    - 工厂自动从注册表读取模块路径和类名，动态实例化识别器
    - 运行时自动跳过加载失败的识别器（不影响其他系统）
"""
import importlib
import logging
from typing import Dict, List, Any

from config.settings import WEATHER_SYSTEM_REGISTRY
from modules.detection.base_detector import BaseDetector

logger = logging.getLogger(__name__)


class DetectorFactory:
    """
    识别器工厂

    构造时自动加载注册表中所有识别器。
    调用 detect_all() 对给定数据执行全部适用的识别。
    """

    def __init__(self):
        self.detectors: Dict[str, BaseDetector] = {}
        self._load_all()

    def _load_all(self):
        """从注册表动态加载所有识别器"""
        for system_name, config in WEATHER_SYSTEM_REGISTRY.items():
            module_name = config["module"]
            class_name = config["detector_class"]

            try:
                module = importlib.import_module(
                    f"modules.detection.{module_name}"
                )
                detector_cls = getattr(module, class_name)
                detector = detector_cls()

                if not isinstance(detector, BaseDetector):
                    logger.warning(
                        f"{class_name} 未继承 BaseDetector，跳过"
                    )
                    continue

                self.detectors[system_name] = detector
                logger.debug(f"加载识别器: {system_name} ({class_name})")

            except (ImportError, AttributeError) as e:
                logger.warning(
                    f"加载识别器失败 [{system_name}]: {e}，跳过"
                )

        logger.info(
            f"识别器工厂初始化完成: 已加载 {len(self.detectors)} 个识别器 "
            f"({', '.join(self.detectors.keys())})"
        )

    def detect_all(
        self, data_dict: dict, data_type: str
    ) -> Dict[str, List[Dict[str, Any]]]:
        """
        对给定数据执行所有适用的天气系统识别。

        Args:
            data_dict: DataManager 返回的单个 (time_label, level) 数据字典
            data_type: "obs" 或 "fcst"

        Returns:
            {天气系统名: [识别结果列表], ...}
            未识别到的系统不包含在返回值中。
        """
        level = data_dict.get("level", 0)
        results = {}

        for system_name, detector in self.detectors.items():
            reg_config = WEATHER_SYSTEM_REGISTRY.get(system_name, {})

            # 检查当前层次是否适用
            applicable_levels = reg_config.get("levels", [])
            if level not in applicable_levels:
                continue

            # 检查所需变量
            # 预报和实况的变量名不同，需要分别检查
            if data_type == "fcst":
                check_vars = reg_config.get("fcst_vars", [])
            else:
                check_vars = reg_config.get("obs_vars", [])

            vars_ok = all(
                var in data_dict and data_dict[var] is not None
                for var in check_vars
            )
            if not vars_ok:
                logger.debug(
                    f"{system_name}: 变量不齐全 (需要 {check_vars})，跳过"
                )
                continue

            # 执行识别
            try:
                detections = detector.detect(data_dict, level)
                if detections:
                    results[system_name] = detections
            except Exception as e:
                logger.error(
                    f"{system_name} 识别异常 (level={level}): {e}"
                )

        return results
