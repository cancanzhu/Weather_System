"""
MICAPS4 数据读取器
==================
使用 meteva 库读取 MICAPS4 格网数据文件。

返回数据格式:
    xarray.DataArray（meteva 原生格式），包含以下坐标:
    - lon: 经度
    - lat: 纬度
    以及可能的 member, level, time, dtime 等维度。

    使用 .squeeze() 可压缩为 2D (lat, lon) 数组。
    使用 grd['lon'].values / grd['lat'].values 获取坐标。

依赖:
    meteva (pip install meteva)
"""
import logging
from typing import Optional
import numpy as np

if not hasattr(np, 'float'):
    np.float = float
if not hasattr(np, 'int'):
    np.int = int
if not hasattr(np, 'bool'):
    np.bool = bool
    
import meteva.base as meb

logger = logging.getLogger(__name__)


class Micaps4Reader:
    """MICAPS4 格网数据读取器"""

    @staticmethod
    def read(filepath: str, smooth: bool = False, smooth_points: int = 5) -> Optional[object]:
        """
        读取单个 MICAPS4 文件。

        默认返回未平滑的原始数据。平滑由下游各环节自行负责:
            - 识别模块使用 SMOOTH_POINTS_DETECT
            - 绘图模块使用 SMOOTH_POINTS_PLOT
        （历史版本默认 smooth=True 导致读取/识别/绘图三重叠加平滑，已修正）

        Args:
            filepath:      文件路径
            smooth:        是否对数据做平滑处理（默认 False）
            smooth_points: 平滑点数（传给 meb.comp.smooth）

        Returns:
            xarray.DataArray: 成功时返回 meteva 格网数据
            None:             文件不存在或读取失败时返回 None

        返回的 DataArray 结构:
            维度:   (member, level, time, dtime, lat, lon)
            坐标:   grd['lon'].values → 1D经度数组
                    grd['lat'].values → 1D纬度数组
            数据:   grd.squeeze().values → 2D numpy数组 (lat, lon)
        """
        logger.debug(f"读取 MICAPS4: {filepath}")
        try:
            grd = meb.read_griddata_from_micaps4(filepath)
            if grd is None:
                logger.warning(f"meteva 返回 None: {filepath}")
                return None

            # 平滑处理
            if smooth:
                grd = meb.comp.smooth(grd, smooth_points)

            logger.debug(f"读取成功: shape={grd.shape}, "
                         f"range=[{float(grd.min()):.1f}, {float(grd.max()):.1f}]")
            return grd

        except FileNotFoundError:
            logger.warning(f"文件不存在: {filepath}")
            return None
        except Exception as e:
            logger.error(f"读取 MICAPS4 失败 [{filepath}]: {e}")
            return None
