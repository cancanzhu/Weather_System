"""
MICAPS14 数据读取器
===================
使用 meteva 库读取 MICAPS14 等值线分析数据文件。

返回数据格式:
    dict，包含以下键（均可能为 None）:
    {
        "lines": {                              # 等值线数据
            "line_xyz":       [ndarray, ...],   # 每条线的坐标, shape=(n,3), 列=[lon,lat,z]
            "line_label":     [str, ...],        # 每条线的标签文字
            "line_label_num": [int, ...],        # 标签数量
            "line_label_xyz": [ndarray, ...],    # 标签位置坐标
        },
        "symbols": {                            # 符号标注
            "symbol_code": [int, ...],           # 符号代码: 60=高压, 61=低压, 62=暖中心, 63=冷中心
            "symbol_xyz":  [ndarray, ...],       # 符号位置 [lon, lat]
        },
        "lines_symbol": {                       # 特殊线符号（槽线等）
            "linesym_code": [int, ...],          # 线符号代码: 0=槽线
            "linesym_xyz":  [ndarray, ...],      # 线坐标, shape=(n,3), 取 [:, 0:2] 得 lon/lat
        },
    }

依赖:
    meteva (pip install meteva)
"""
import logging
from typing import Optional, Dict, Any
import numpy as np

# ── numpy 兼容补丁 ──
# meteva 内部使用了 np.float 等旧别名，在 numpy>=1.24 中已移除
# 在导入 meteva 前补回这些别名
if not hasattr(np, 'float'):
    np.float = float
if not hasattr(np, 'int'):
    np.int = int
if not hasattr(np, 'bool'):
    np.bool = bool

import meteva.base as meb

logger = logging.getLogger(__name__)


class Micaps14Reader:
    """MICAPS14 等值线分析数据读取器"""

    @staticmethod
    def read(filepath: str) -> Optional[Dict[str, Any]]:
        """
        读取单个 MICAPS14 文件。

        Args:
            filepath: 文件路径

        Returns:
            dict: 成功时返回包含 lines / symbols / lines_symbol 的字典
            None: 文件不存在或读取失败时返回 None
        """
        logger.debug(f"读取 MICAPS14: {filepath}")
        try:
            graphy_data = meb.read_micaps14(filepath)
            if graphy_data is None:
                logger.warning(f"meteva 返回 None: {filepath}")
                return None

            # 统计读取内容
            n_lines = len((graphy_data.get("lines") or {}).get("line_xyz", []))
            n_symbols = len((graphy_data.get("symbols") or {}).get("symbol_code", []))
            n_line_sym = len((graphy_data.get("lines_symbol") or {}).get("linesym_code", []))
            logger.debug(f"读取成功: {n_lines} 条等值线, "
                         f"{n_symbols} 个符号, {n_line_sym} 条线符号")
            return graphy_data

        except FileNotFoundError:
            logger.warning(f"文件不存在: {filepath}")
            return None
        except Exception as e:
            logger.error(f"读取 MICAPS14 失败 [{filepath}]: {e}")
            return None
