"""
天气系统识别器 — 抽象基类
=========================
所有天气系统识别器必须继承此基类并实现 detect() 方法。

新增天气系统步骤:
    1. 在 config/settings.py 的 WEATHER_SYSTEM_REGISTRY 中注册
    2. 在 modules/detection/ 下新建模块文件
    3. 创建类继承 BaseDetector，实现 detect() 方法
    4. 在 modules/visualization/system_plotter.py 的 PLOT_HANDLERS 中注册绘图函数

detect() 返回值约定:
    返回 list[dict]，每个 dict 代表一个识别到的天气系统实例。
    必须包含以下字段:
    {
        "system_name":  str,        # 天气系统名称（如 "高空槽"）
        "level":        int,        # 层次
        "geometry":     dict,       # 几何描述（见下方约定）
        "properties":   dict,       # 其他属性（各系统自定义）
    }

geometry 字段约定:
    | 几何类型 | 适用系统              | 格式                                                       |
    |---------|----------------------|------------------------------------------------------------|
    | line    | 高空槽、切变线         | {"type": "line", "points": [[lon,lat], ...]}               |
    | line    | 副热带高压            | {"type": "line", "points": [[lon,lat], ...]}            |
    | point   | 冷涡、低空低涡        | {"type": "point", "lon": x, "lat": y, "radius_km": r}     |

    后续追踪模块和大模型模块依赖此结构，新增系统请遵循。
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any
import logging

logger = logging.getLogger(__name__)


class BaseDetector(ABC):
    """天气系统识别器抽象基类"""

    # ---- 子类必须声明的类属性 ----
    system_name: str = ""           # 天气系统名称
    required_vars: List[str] = []   # 所需变量列表

    @abstractmethod
    def detect(self, data_dict: dict, level: int) -> List[Dict[str, Any]]:
        """
        执行天气系统识别。

        Args:
            data_dict: DataManager 返回的单个 (time_label, level) 数据字典。
                       预报数据通过 data_dict["GH"] 访问 xarray.DataArray；
                       实况数据通过 data_dict["HGT"] 访问 MICAPS14 字典。
            level:     当前层次 (500 / 700 / 850)

        Returns:
            识别到的天气系统列表，空列表表示未识别到。
        """
        pass

    def check_data(self, data_dict: dict) -> bool:
        """
        检查识别所需的变量是否齐全。

        Args:
            data_dict: 数据字典

        Returns:
            True 表示所需变量齐全，False 表示缺失
        """
        for var in self.required_vars:
            if var not in data_dict or data_dict[var] is None:
                logger.debug(
                    f"{self.system_name} 缺少变量 {var}，跳过识别"
                )
                return False
        return True
