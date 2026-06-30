"""
天气系统识别结果绘图模块
========================
在气象场底图上叠加天气系统识别结果。

设计模式:
    采用绘图函数注册表（PLOT_HANDLERS），每种天气系统对应一个绘图函数。
    新增天气系统时，只需:
        1. 编写绘图函数 _plot_xxx(ax, results)
        2. 在 PLOT_HANDLERS 中注册

已实现:
    - 高空槽 (trough): 绘制棕色加粗槽线

待实现:
    - 副热带高压: 绘制边界、填色、脊线
    - 冷涡: 绘制中心标记、影响范围
    - 低空低涡: 绘制中心标记、影响范围

输出:
    PNG 图片，保存到 output/figures/ 目录
"""
import os
import shapefile as shp
from matplotlib.patches import Polygon
from matplotlib.collections import PatchCollection
import logging
import numpy as np
import matplotlib.pyplot as plt
import meteva.base as meb
from typing import Dict, List, Any, Callable
from config.settings import MAP_CONFIG, FIGURE_DIR, CONTOUR_LEVELS, \
    WIND_BARB_LENGTH, WIND_BARB_LINEWIDTH, WIND_BARB_COLOR, WIND_BARB_INCREMENTS, \
    WIND_BARB_SKIP_OBS, SMOOTH_POINTS_PLOT
from modules.data_io.mdfs_wind_reader import wind_dir_speed_to_uv

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

logger = logging.getLogger(__name__)


# ============================================================
# 各天气系统的绘图函数
# ============================================================

def _plot_trough(ax, results: List[Dict[str, Any]]):
    """
    绘制高空槽线。

    支持两种 geometry 格式:
        - graphy_raw: 预报数据，使用 meb.add_solid_lines 直接绘制
        - line:       实况数据，使用 ax.plot 逐条绘制
    """
    for item in results:
        geometry = item.get("geometry", {})
        geo_type = geometry.get("type", "")

        if geo_type == "graphy_raw":
            # 预报: 使用 meteva 原生方法绘制
            graphy = geometry.get("graphy", [])
            if graphy:
                meb.add_solid_lines(ax, graphy, color="brown", linewidth=2.0)

        elif geo_type == "line":
            # 实况: 逐条绘制
            points = np.array(geometry.get("points", []))
            if len(points) >= 2:
                ax.plot(
                    points[:, 0], points[:, 1],
                    color="brown", linewidth=2.0, zorder=50,
                )

def _plot_subtropical_high(ax, results: List[Dict[str, Any]]):
    """绘制副热带高压（588线红色加粗）"""
    for item in results:
        geometry = item.get("geometry", {})
        if geometry.get("type") != "line":
            continue

        points = np.array(geometry.get("points", []))
        if len(points) < 2:
            continue

        ax.plot(
            points[:, 0], points[:, 1],
            color="red", linewidth=2.0, zorder=50,
        )

def _plot_cold_vortex(ax, results: List[Dict[str, Any]]):
    """绘制冷涡，蓝色 C 标记冷中心，仅绘制地图范围内的标记"""
    for item in results:
        geometry = item.get("geometry", {})
        if geometry.get("type") != "point":
            continue

        lon = geometry["lon"]
        lat = geometry["lat"]

        if not (MAP_CONFIG.lon_min <= lon <= MAP_CONFIG.lon_max and
                MAP_CONFIG.lat_min <= lat <= MAP_CONFIG.lat_max):
            continue

        ax.text(
            lon, lat, "C",
            color="blue", fontsize=20,
            ha="center", va="center",
            weight="bold", zorder=100,
        )


def _plot_low_level_vortex(ax, results: List[Dict[str, Any]]):
    """绘制低空低涡，仅绘制地图范围内的标记"""
    for item in results:
        geometry = item.get("geometry", {})
        if geometry.get("type") != "point":
            continue

        lon = geometry["lon"]
        lat = geometry["lat"]

        # 过滤地图范围外的点
        if not (MAP_CONFIG.lon_min <= lon <= MAP_CONFIG.lon_max and
                MAP_CONFIG.lat_min <= lat <= MAP_CONFIG.lat_max):
            continue

        ax.text(
            lon, lat, "L",
            color="red", fontsize=20,
            ha="center", va="center",
            weight="bold", zorder=100,
        )

def _plot_low_level_jet(ax, results: List[Dict[str, Any]]):
    """
    绘制低空急流轴线（带箭头的曲线）。

    支持两种 geometry 格式:
        - graphy_raw: 预报数据，使用 meb.add_curved_arrows 直接绘制
        - jet_lines:  实况数据，使用 meb.add_curved_arrows 绘制
    """
    for item in results:
        geometry = item.get("geometry", {})
        geo_type = geometry.get("type", "")

        if geo_type == "graphy_raw":
            graphy = geometry.get("graphy", None)
            if graphy:
                meb.add_curved_arrows(ax, graphy, color="brown", linewidth=1.5,
                                      head_width=1, head_length=1)

        elif geo_type == "jet_lines":
            jet_lines = geometry.get("lines", [])
            if jet_lines:
                meb.add_curved_arrows(ax, jet_lines, color="brown", linewidth=1.5,
                                      head_width=1, head_length=1)
                
def _plot_shear_line(ax, results):
    """
    绘制切变线。
        graphy_raw: 预报，meb.add_solid_lines 直接绘制
        line:       实况，ax.plot 逐条绘制
    """
    for item in results:
        geometry = item.get("geometry", {})
        geo_type = geometry.get("type", "")

        if geo_type == "graphy_raw":
            graphy = geometry.get("graphy", None)
            if graphy:
                meb.add_solid_lines(ax, graphy, color="purple", linewidth=2.0)

        elif geo_type == "line":
            points = np.array(geometry.get("points", []))
            if len(points) >= 2:
                ax.plot(points[:, 0], points[:, 1], color="purple",
                        linewidth=2.0, zorder=50)


# ============================================================
# 绘图函数注册表
# ============================================================
# key = 天气系统名称（与 WEATHER_SYSTEM_REGISTRY 中的 key 一致）
# value = 绘图函数
# 新增天气系统时，编写绘图函数后在此注册即可

PLOT_HANDLERS: Dict[str, Callable] = {
    "高空槽":     _plot_trough,
    "副热带高压": _plot_subtropical_high,
    "冷涡":       _plot_cold_vortex,
    "低空低涡":   _plot_low_level_vortex,
    "低压中心":   _plot_low_level_vortex, 
    "低空急流":   _plot_low_level_jet,
    "切变线": _plot_shear_line,
}

_land_shp = os.path.join(
    os.path.dirname(os.path.abspath(__file__)),
    '..', '..', 'ne_110m_land', 'ne_110m_land.shp'
)


_land_polygons_cache = None


def _load_land_polygons():
    """读取陆地 shapefile（含全部 parts），模块级缓存，磁盘只读一次"""
    global _land_polygons_cache
    if _land_polygons_cache is None:
        sf = shp.Reader(_land_shp)
        polys = []
        for shape in sf.shapes():
            parts = list(shape.parts) + [len(shape.points)]
            # 遍历该 shape 的所有 part（多部分多边形：大陆 + 岛屿）。
            # 旧版只取 parts[0]:parts[1]，岛屿环全部丢失
            for k in range(len(parts) - 1):
                pts = shape.points[parts[k]:parts[k + 1]]
                if len(pts) >= 3:
                    polys.append(pts)
        _land_polygons_cache = polys
    return _land_polygons_cache


def draw_ocean_land(ax, map_config=None):
    """
    绘制海洋蓝色背景和陆地填充，区分海陆边界。

    陆地多边形坐标首次调用时读取并缓存；PatchCollection 不能跨
    figure 复用，因此每次重建 Polygon 对象（很廉价），磁盘只读一次。

    Args:
        ax:         matplotlib axes
        map_config: MapConfig（可选，未使用）
    """
    ax.set_facecolor('#A8D4F0')

    patches = [Polygon(p, closed=True) for p in _load_land_polygons()]
    if patches:
        pc = PatchCollection(
            patches, facecolor='white', edgecolor='none', zorder=1
        )
        ax.add_collection(pc)


# def draw_ocean_land(ax, map_config=None):
#     """
#     绘制海洋蓝色背景和陆地填充，区分海陆边界。

#     Args:
#         ax:         matplotlib axes
#         map_config: MapConfig（可选，未使用）
#     """
#     try:
#         import pkg_resources
#         import shapefile as shp
#         from matplotlib.patches import Polygon
#         from matplotlib.collections import PatchCollection

#         # 全域陆地白色背景
#         ax.set_facecolor('#A8D4F0')

#         # 读取 meteva 内置省份 shapefile，绘制白色填充陆地
#         shpfile = pkg_resources.resource_filename(
#             'meteva', 'resources/maps/Province'
#         )
#         shp.default_encoding = 'gbk'
#         sf = shp.Reader(shpfile, encoding='gbk')

#         patches = []
#         for shape in sf.shapes():
#             parts = list(shape.parts) + [len(shape.points)]
#             for i in range(len(parts) - 1):
#                 points = shape.points[parts[i]:parts[i + 1]]
#                 if len(points) >= 3:
#                     patches.append(Polygon(points, closed=True))

#         if patches:
#             pc = PatchCollection(
#                 patches, facecolor='white', edgecolor='none', zorder=1,
#             )
#             ax.add_collection(pc)

#     except Exception as e:
#         logger.warning(f"海陆填充失败，跳过: {e}")


def add_wind_barbs_from_df(ax, wind_df, map_config=None, skip=None):
    """
    从 MDFS 站点 DataFrame 叠加风向杆到实况图上。

    Args:
        ax:         matplotlib axes
        wind_df:    pandas.DataFrame, 含 lon, lat, wind_dir, wind_speed 列
        map_config: MapConfig（用于过滤范围内站点）
        skip:       站点抽稀间隔，1=全部，2=隔1站，默认取 WIND_BARB_SKIP_OBS
    """
    if wind_df is None or wind_df.empty:
        return

    try:
        cfg = map_config or MAP_CONFIG
        if skip is None:
            skip = WIND_BARB_SKIP_OBS

        # 过滤地图范围内的站点
        mask = (
            (wind_df["lon"] >= cfg.lon_min) & (wind_df["lon"] <= cfg.lon_max) &
            (wind_df["lat"] >= cfg.lat_min) & (wind_df["lat"] <= cfg.lat_max)
        )
        filtered = wind_df[mask]
        if filtered.empty:
            return

        # 站点抽稀
        if skip > 1:
            filtered = filtered.iloc[::skip]

        u, v = wind_dir_speed_to_uv(
            filtered["wind_dir"].values, filtered["wind_speed"].values
        )

        ax.barbs(
            filtered["lon"].values, filtered["lat"].values,
            u, v,
            length=WIND_BARB_LENGTH,
            linewidth=WIND_BARB_LINEWIDTH,
            color=WIND_BARB_COLOR,
            barbcolor=WIND_BARB_COLOR,
            pivot="middle",
            barb_increments=WIND_BARB_INCREMENTS,
        )
    except Exception as e:
        logger.warning(f"实况风向杆绘制失败: {e}")


# ============================================================
# SystemPlotter 主类
# ============================================================

class SystemPlotter:
    """
    天气系统识别结果绘图器

    在气象场底图上叠加所有识别到的天气系统，并添加图例。
    底图内容与 FieldPlotter 一致（等值线 + 符号），但额外叠加识别结果。
    """

    def __init__(self, map_config=None):
        self.map_config = map_config or MAP_CONFIG
        os.makedirs(FIGURE_DIR, exist_ok=True)

    def plot(
        self,
        data_dict: dict,
        detection_results: Dict[str, List[Dict[str, Any]]],
        time_label: str,
        level: int,
        data_type: str,
    ) -> str:
        """
        绘制天气系统识别结果图片。

        底图上先绘制气象场（等值线），再叠加识别结果。

        Args:
            data_dict:         数据字典
            detection_results: 识别结果 {"系统名": [结果列表], ...}
            time_label:        时间标签
            level:             层次
            data_type:         "obs" 或 "fcst"

        Returns:
            保存的图片文件路径
        """
        type_cn = "实况" if data_type == "obs" else "预报"
        title = f"{type_cn} {time_label} {level}hPa 系统识别"
        fig_name = f"{data_type}_{time_label}_{level}hPa_system.png"
        fig_path = os.path.join(FIGURE_DIR, fig_name)

        try:
            # 创建底图
            axs = meb.creat_axs(
                1,
                self.map_config.extent,
                sup_title=title,
                sup_fontsize=8,
                add_minmap=False,
                add_worldmap=False,
                width=12,
            )
            ax = axs[0]

            # 海陆填充
            draw_ocean_land(ax)

            # 绘制底图气象场
            self._draw_background(ax, data_dict, data_type, level)

            # 叠加天气系统识别结果
            for system_name, results in detection_results.items():
                handler = PLOT_HANDLERS.get(system_name)
                if handler is not None and results:
                    try:
                        handler(ax, results)
                    except Exception as e:
                        logger.error(
                            f"绘制 {system_name} 失败: {e}"
                        )

            # 添加图例（只显示有 label 的项）
            handles, labels = ax.get_legend_handles_labels()
            if handles:
                ax.legend(loc="upper right", fontsize=8)

            # 标记天津位置
            ax.plot(
                self.map_config.tianjin_lon,
                self.map_config.tianjin_lat,
                "r*",
                markersize=10,
                zorder=100,
            )

            plt.savefig(fig_path, dpi=self.map_config.dpi, bbox_inches="tight")
            plt.close()
            logger.debug(f"系统识别图片已保存: {fig_path}")
            return fig_path

        except Exception as e:
            logger.error(
                f"系统识别绘图失败 [{time_label}/{level}]: {e}"
            )
            plt.close("all")
            return ""

    def _draw_background(
        self, ax, data_dict: dict, data_type: str, level: int
    ):
        """绘制底图气象场（等值线），作为识别结果的背景"""
        if data_type == "fcst":
            grd = data_dict.get("GH")
            if grd is not None:
                grd_2d = meb.comp.smooth(grd, SMOOTH_POINTS_PLOT).squeeze()
                levels = CONTOUR_LEVELS.get(level, list(range(500, 601, 4)))
                cs = ax.contour(
                    grd_2d["lon"].values,
                    grd_2d["lat"].values,
                    grd_2d.values,
                    levels=levels,
                    colors="blue",
                    linewidths=0.8,
                    alpha=0.7,
                )
                ax.clabel(cs, fmt="%d", fontsize=8)

        elif data_type == "obs":
            hgt_data = data_dict.get("HGT")
            if hgt_data is not None:
                lines = hgt_data.get("lines")
                if lines is not None:
                    graphy = []
                    for i in range(len(lines["line_xyz"])):
                        line_xyz = lines["line_xyz"][i]
                        line_points = line_xyz[:, 0:2].tolist()
                        graphy.append(line_points)
                    if graphy:
                        meb.add_solid_lines(ax, graphy, color="blue", linewidth=0.8)

                    for i in range(len(lines["line_xyz"])):
                        label = str(lines["line_label"][i]).strip()
                        if not label:
                            continue

                        line_xyz = lines["line_xyz"][i]

                        in_range_indices = []
                        for j in range(len(line_xyz)):
                            lon_j = line_xyz[j, 0]
                            lat_j = line_xyz[j, 1]
                            if (self.map_config.lon_min <= lon_j <= self.map_config.lon_max and
                                    self.map_config.lat_min <= lat_j <= self.map_config.lat_max):
                                in_range_indices.append(j)

                        if not in_range_indices:
                            continue

                        mid = in_range_indices[len(in_range_indices) // 2]
                        lon = line_xyz[mid, 0]
                        lat = line_xyz[mid, 1]

                        ax.text(
                            lon, lat, label,
                            fontsize=8, color="b", ha="center", va="center",
                            clip_on=True, alpha=0.7,
                            bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1),
                        )

            # 实况叠加站点风羽
            add_wind_barbs_from_df(ax, data_dict.get("wind_df"), self.map_config)