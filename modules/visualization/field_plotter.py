"""
气象要素场绘图模块
==================
绘制高度场等值线 + 风场（如有）的气象场底图。

预报数据 (MICAPS4):
    - 高度场: xarray.DataArray → contour 等值线
    - 风场:   xarray.DataArray → barbs 风向杆

实况数据 (MICAPS14):
    - 高度场: dict → 直接绘制等值线坐标和符号标注
    - 风场:   暂无

底图使用 meteva 的 meb.creat_axs() 创建，自带中国地图。

输出:
    PNG 图片，保存到 output/figures/ 目录
"""
import os
import logging
import numpy as np
import matplotlib.pyplot as plt
import meteva.base as meb
from config.settings import SMOOTH_POINTS_PLOT
from config.settings import MAP_CONFIG, FIGURE_DIR, CONTOUR_LEVELS, WIND_BARB_SKIP, \
    WIND_BARB_LENGTH, WIND_BARB_LINEWIDTH, WIND_BARB_COLOR, WIND_BARB_INCREMENTS
from modules.visualization.system_plotter import PLOT_HANDLERS, draw_ocean_land, \
    add_wind_barbs_from_df

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

logger = logging.getLogger(__name__)


class FieldPlotter:
    """
    气象要素场绘图器

    根据数据类型（预报/实况）自动选择绘图方式:
        - 预报: 从 xarray 格网数据绘制等值线和风场
        - 实况: 从 MICAPS14 矢量数据绘制等值线和符号
    """

    def __init__(self, map_config=None):
        self.map_config = map_config or MAP_CONFIG
        os.makedirs(FIGURE_DIR, exist_ok=True)

    def plot(
        self,
        data_dict: dict,
        time_label: str,
        level: int,
        data_type: str,
        detection_results: dict = None,
    ) -> str:
        """
        绘制气象场图片。

        Args:
            data_dict:         数据字典
            time_label:        时间标签（用于标题和文件名）
            level:             层次
            data_type:         "obs" 或 "fcst"
            detection_results: 天气系统识别结果（可选），叠加到场上

        Returns:
            保存的图片文件路径
        """
        if data_type == "fcst":
            return self._plot_forecast(data_dict, time_label, level, detection_results)
        elif data_type == "obs":
            return self._plot_observation(data_dict, time_label, level, detection_results)
        else:
            logger.warning(f"未知 data_type: {data_type}")
            return ""

    def _plot_forecast(
        self, data_dict: dict, time_label: str, level: int,
        detection_results: dict = None,
    ) -> str:
        """绘制预报数据的气象场（MICAPS4 格网数据）"""
        title = f"预报 {time_label} {level}hPa 高度场"
        fig_name = f"fcst_{time_label}_{level}hPa_field.png"
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

            # 绘制高度场等值线
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
                )
                ax.clabel(cs, fmt="%d", fontsize=8)

            # 绘制风场（如有）
            u_grd = data_dict.get("U")
            v_grd = data_dict.get("V")
            if u_grd is not None and v_grd is not None:
                u_2d = u_grd.squeeze()
                v_2d = v_grd.squeeze()
                skip = WIND_BARB_SKIP
                ax.barbs(
                    u_2d["lon"].values[::skip],
                    u_2d["lat"].values[::skip],
                    u_2d.values[::skip, ::skip],
                    v_2d.values[::skip, ::skip],
                    length=WIND_BARB_LENGTH,
                    linewidth=WIND_BARB_LINEWIDTH,
                    color=WIND_BARB_COLOR,
                    barbcolor=WIND_BARB_COLOR,
                    pivot="middle",
                    barb_increments=WIND_BARB_INCREMENTS,
                )

            # 标记天津位置
            ax.plot(
                self.map_config.tianjin_lon,
                self.map_config.tianjin_lat,
                "r*",
                markersize=10,
                zorder=100,
            )

            # 叠加天气系统识别结果
            if detection_results:
                for system_name, results in detection_results.items():
                    handler = PLOT_HANDLERS.get(system_name)
                    if handler and results:
                        try:
                            handler(ax, results)
                        except Exception as e:
                            logger.error(f"叠加 {system_name} 失败: {e}")

            plt.savefig(fig_path, dpi=self.map_config.dpi, bbox_inches="tight")
            plt.close()
            logger.debug(f"预报气象场图片已保存: {fig_path}")
            return fig_path

        except Exception as e:
            logger.error(f"预报气象场绘图失败 [{time_label}/{level}]: {e}")
            plt.close("all")
            return ""

    def _plot_observation(
        self, data_dict: dict, time_label: str, level: int,
        detection_results: dict = None,
    ) -> str:
        """绘制实况数据的气象场（MICAPS14 矢量数据）"""
        title = f"实况 {time_label} {level}hPa 高度场"
        fig_name = f"obs_{time_label}_{level}hPa_field.png"
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

            hgt_data = data_dict.get("HGT")
            if hgt_data is not None:
                # 绘制等高线
                self._draw_micaps14_lines(ax, hgt_data)
                # 绘制符号（H/L/W/C）
                self._draw_micaps14_symbols(ax, hgt_data)

            # 叠加实况站点风羽
            add_wind_barbs_from_df(ax, data_dict.get("wind_df"), self.map_config)

            # 标记天津位置
            ax.plot(
                self.map_config.tianjin_lon,
                self.map_config.tianjin_lat,
                "r*",
                markersize=10,
                zorder=100,
            )

            # 叠加天气系统识别结果
            if detection_results:
                for system_name, results in detection_results.items():
                    handler = PLOT_HANDLERS.get(system_name)
                    if handler and results:
                        try:
                            handler(ax, results)
                        except Exception as e:
                            logger.error(f"叠加 {system_name} 失败: {e}")

            plt.savefig(fig_path, dpi=self.map_config.dpi, bbox_inches="tight")
            plt.close()
            logger.debug(f"实况气象场图片已保存: {fig_path}")
            return fig_path

        except Exception as e:
            logger.error(f"实况气象场绘图失败 [{time_label}/{level}]: {e}")
            plt.close("all")
            return ""

    def _draw_micaps14_lines(self, ax, graphy_data: dict):
        """绘制 MICAPS14 的等值线"""
        lines = graphy_data.get("lines")
        if lines is None:
            return

        # 区分588线和普通线
        normal_lines = []
        line_588 = []
        for i in range(len(lines["line_xyz"])):
            line_xyz = lines["line_xyz"][i]
            line_points = line_xyz[:, 0:2].tolist()
            label = str(lines["line_label"][i]).strip()
            if label == "588":
                line_588.append(line_points)
            else:
                normal_lines.append(line_points)

        if normal_lines:
            meb.add_solid_lines(ax, normal_lines, color="blue", linewidth=0.8)
        if line_588:
            meb.add_solid_lines(ax, line_588, color="red", linewidth=2.0)

        # 标签：在每条等值线上找地图范围内的点放标签
        for i in range(len(lines["line_xyz"])):
            label = str(lines["line_label"][i]).strip()
            if not label:
                continue

            line_xyz = lines["line_xyz"][i]

            # 找线上在地图范围内的中间点
            in_range_indices = []
            for j in range(len(line_xyz)):
                lon_j = line_xyz[j, 0]
                lat_j = line_xyz[j, 1]
                if (self.map_config.lon_min <= lon_j <= self.map_config.lon_max and
                        self.map_config.lat_min <= lat_j <= self.map_config.lat_max):
                    in_range_indices.append(j)

            if not in_range_indices:
                continue

            # 取范围内点的中间位置
            mid = in_range_indices[len(in_range_indices) // 2]
            lon = line_xyz[mid, 0]
            lat = line_xyz[mid, 1]

            ax.text(
                lon, lat, label,
                fontsize=8, color="b", ha="center", va="center",
                clip_on=True,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1),
            )

    def _draw_micaps14_symbols(self, ax, graphy_data: dict):
        """绘制 MICAPS14 的符号标注（H/L/W/C）"""
        symbols = graphy_data.get("symbols")
        if symbols is None:
            return

        symbol_map = {
            60: ("H", "blue"),
            61: ("L", "red"),
            62: ("W", "red"),
            63: ("C", "blue"),
        }

        for i, code in enumerate(symbols["symbol_code"]):
            lon = symbols["symbol_xyz"][i][0]
            lat = symbols["symbol_xyz"][i][1]

            if not (self.map_config.lon_min <= lon <= self.map_config.lon_max and
                    self.map_config.lat_min <= lat <= self.map_config.lat_max):
                continue

            if code in symbol_map:
                text, color = symbol_map[code]
                ax.text(
                    lon, lat, text,
                    color=color, fontsize=16,
                    ha="center", va="center",
                    weight="bold", zorder=100,
                )
            else:
                ax.text(
                    lon, lat, str(code),
                    fontsize=20, ha="center", va="center", zorder=100,
                )