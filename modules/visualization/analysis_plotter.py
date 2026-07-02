"""
分析报告可视化模块
==================
为第二份 Word 分析报告生成图片：
    - 实况图：等值线底图 + 天气系统叠加
    - 预报追踪图：地图底图 + 多时次轨迹叠加

按层次分别生成：500hPa、700hPa、850hPa
后续新增天气系统时，在对应层次的绑图函数中添加即可。
"""
import os
import logging
import numpy as np
import matplotlib.pyplot as plt
import meteva.base as meb
from typing import Dict, List, Any, Optional
from config.settings import MAP_CONFIG, FIGURE_DIR
from modules.visualization.system_plotter import draw_ocean_land, add_wind_barbs_from_df

plt.rcParams["font.sans-serif"] = ["SimHei"]
plt.rcParams["axes.unicode_minus"] = False

logger = logging.getLogger(__name__)


class AnalysisPlotter:
    """分析报告可视化器"""

    def __init__(self, map_config=None):
        self.map_config = map_config or MAP_CONFIG
        os.makedirs(FIGURE_DIR, exist_ok=True)

    def _in_extent(self, lon: float, lat: float) -> bool:
        """判断经纬度是否在地图范围内"""
        ext = self.map_config.extent
        return ext[0] <= lon <= ext[1] and ext[2] <= lat <= ext[3]

    # ================================================================
    # 实况图：等值线底图 + 天气系统叠加
    # ================================================================

    def plot_obs_analysis(
        self,
        obs_data: dict,
        obs_detection: dict,
        level: int,
        time_label: str,
        jet_viz: dict = None,
    ) -> str:
        """
        生成实况分析图。

        Args:
            obs_data:      该层次的实况数据字典
            obs_detection: 该层次的识别结果
            level:         层次
            time_label:    时间标签

        Returns:
            图片路径
        """
        title = f"实况分析 {time_label} {level}hPa"
        fig_name = f"analysis_obs_{time_label}_{level}hPa.png"
        fig_path = os.path.join(FIGURE_DIR, fig_name)

        try:
            axs = meb.creat_axs(
                1, self.map_config.extent,
                sup_title=title, sup_fontsize=10,
                add_minmap=False, add_worldmap=False, width=12,
            )
            ax = axs[0]

            # 海陆填充
            draw_ocean_land(ax)

            # 绘制等值线底图
            hgt_data = obs_data.get("HGT")
            if hgt_data is not None:
                self._draw_obs_isolines(ax, hgt_data)
                self._draw_obs_symbols(ax, hgt_data)
                self._draw_obs_labels(ax, hgt_data)

            tmp_data = obs_data.get("TMP")
            if tmp_data is not None:
                self._draw_obs_symbols(ax, tmp_data)

            # 叠加天气系统识别结果（按层次分派）
            self._overlay_obs_systems(ax, obs_detection, level, jet_viz)

            # 叠加实况站点风羽
            add_wind_barbs_from_df(ax, obs_data.get("wind_df"), self.map_config)

            # 天津标记
            ax.plot(
                self.map_config.tianjin_lon, self.map_config.tianjin_lat,
                "r*", markersize=10, zorder=100,
            )

            plt.savefig(fig_path, dpi=self.map_config.dpi, bbox_inches="tight")
            plt.close()
            logger.debug(f"实况分析图已保存: {fig_path}")
            return fig_path

        except Exception as e:
            logger.error(f"实况分析图生成失败 [{level}hPa]: {e}")
            plt.close("all")
            return ""

    def _overlay_obs_systems(self, ax, detection: dict, level: int, jet_viz: dict = None):
        """
        在实况图上叠加天气系统。
        按层次分派，后续新增系统在此添加。
        """
        if level == 500:
            # 高空槽
            troughs = detection.get("高空槽", [])
            for item in troughs:
                geo = item.get("geometry", {})
                if geo.get("type") == "line":
                    points = np.array(geo["points"])
                    if len(points) >= 2:
                        ax.plot(
                            points[:, 0], points[:, 1],
                            color="brown", linewidth=2.0, zorder=50,
                        )

            # 副热带高压 588线：影响天津才标红，否则画深蓝
            from config.settings import SUBTROPICAL_HIGH_LAT_THRESHOLD
            from modules.tracking.subtropical_high_analysis import (
                _max_lat_in_lon_window,
            )
            sub_highs = detection.get("副热带高压", [])
            for item in sub_highs:
                geo = item.get("geometry", {})
                if geo.get("type") == "line":
                    points = np.array(geo["points"])
                    if len(points) >= 2:
                        win_max_lat = _max_lat_in_lon_window(points)
                        affecting = (
                            not np.isnan(win_max_lat)
                            and win_max_lat >= SUBTROPICAL_HIGH_LAT_THRESHOLD
                        )
                        line_color = "red" if affecting else "darkblue"
                        ax.plot(
                            points[:, 0], points[:, 1],
                            color=line_color, linewidth=2.0, zorder=50,
                        )

            # 冷涡
            cold_vortex = detection.get("冷涡", [])
            for item in cold_vortex:
                geo = item.get("geometry", {})
                if geo.get("type") == "point":
                    lon, lat = geo["lon"], geo["lat"]
                    if (self.map_config.lon_min <= lon <= self.map_config.lon_max and
                            self.map_config.lat_min <= lat <= self.map_config.lat_max):
                        ax.text(lon, lat, "C", color="blue", fontsize=14,
                                ha="center", va="center", weight="bold", zorder=100)

        elif level == 700:
            # 低空低涡
            vortex = detection.get("低空低涡", [])
            for item in vortex:
                geo = item.get("geometry", {})
                if geo.get("type") == "point":
                    lon, lat = geo["lon"], geo["lat"]
                    if (self.map_config.lon_min <= lon <= self.map_config.lon_max and
                            self.map_config.lat_min <= lat <= self.map_config.lat_max):
                        ax.text(lon, lat, "L", color="red", fontsize=14,
                                ha="center", va="center", weight="bold", zorder=100)
            self._draw_shear_lines(ax, detection)

        elif level == 850:
            # 低空低涡
            vortex = detection.get("低空低涡", [])
            for item in vortex:
                geo = item.get("geometry", {})
                if geo.get("type") == "point":
                    lon, lat = geo["lon"], geo["lat"]
                    if (self.map_config.lon_min <= lon <= self.map_config.lon_max and
                            self.map_config.lat_min <= lat <= self.map_config.lat_max):
                        ax.text(lon, lat, "L", color="red", fontsize=14,
                                ha="center", va="center", weight="bold", zorder=100)

            # 低空急流：只在"第一个影响时次"为实况时绘制（影响=红，不影响=灰）
            self._draw_jet_viz(ax, jet_viz, source="obs")
            self._draw_shear_lines(ax, detection)

    def _draw_shear_lines(self, ax, detection: dict):
        """绘制实况切变线（700/850hPa），紫色实线，与第一份识别报告配色一致"""
        for item in detection.get("切变线", []):
            geo = item.get("geometry", {})
            if geo.get("type") != "line":
                continue
            points = np.array(geo.get("points", []))
            if len(points) >= 2:
                ax.plot(
                    points[:, 0], points[:, 1],
                    color="purple", linewidth=2.0, zorder=50,
                )

    def _draw_jet_viz(self, ax, jet_viz: dict, source: str):
        """
        绘制"第一个影响时次"的低空急流（850hPa）。
        影响天津=红色，同时次不影响=灰色。仅当 jet_viz 来源与当前图一致时绘制。
        """
        if not jet_viz or jet_viz.get("source") != source:
            return
        for jet in jet_viz.get("jets", []):
            axis = jet.get("axis", [])
            if len(axis) < 2:
                continue
            color = "red" if jet.get("affecting") else "grey"
            try:
                meb.add_curved_arrows(ax, [axis], color=color,
                                      linewidth=1.5, head_width=1, head_length=1)
            except Exception as e:
                logger.warning(f"急流绘制失败: {e}")

    # ================================================================
    # 预报追踪图：地图底图 + 多时次轨迹叠加
    # ================================================================

    def plot_fcst_tracking(
        self,
        tracker,
        tianjin_track_ids: List[int],
        level: int,
        time_label: str,
        cold_low_tracks: List = None,
        cold_center_tracks: List = None,
        jet_viz: dict = None,
    ) -> str:
        """
        生成预报追踪图。

        Args:
            tracker:           追踪器对象（有 .tracks 属性）
            tianjin_track_ids: 影响天津的轨迹ID列表
            level:             层次
            time_label:        时间标签

        Returns:
            图片路径
        """
        title = f"预报追踪 {time_label} {level}hPa"
        fig_name = f"analysis_fcst_{time_label}_{level}hPa_tracking.png"
        fig_path = os.path.join(FIGURE_DIR, fig_name)

        try:
            axs = meb.creat_axs(
                1, self.map_config.extent,
                sup_title=title, sup_fontsize=10,
                add_minmap=False, add_worldmap=False, width=12,
            )
            ax = axs[0]

            # 海陆填充
            draw_ocean_land(ax)

            # 需要调用一次 meb 方法触发布局
            dummy = [[[self.map_config.lon_min, self.map_config.lat_min],
                      [self.map_config.lon_min + 0.01, self.map_config.lat_min + 0.01]]]
            meb.add_solid_lines(ax, dummy, color="white", linewidth=0)

            # 按层次绘制轨迹
            if level == 500:
                self._draw_trough_tracks(ax, tracker, tianjin_track_ids)
                # 低压中心轨迹：影响天津=红 L，不影响=灰 L
                self._draw_center_tracks(ax, cold_low_tracks or [], "L", "red")
                # 冷中心轨迹：影响天津=蓝 C，不影响=灰 C
                self._draw_center_tracks(ax, cold_center_tracks or [], "C", "blue")
            elif level in [700, 850]:
                self._draw_vortex_tracks(ax, tracker, tianjin_track_ids)

            # 低空急流：只在"第一个影响时次"为预报时绘制（影响=红，不影响=灰）
            self._draw_jet_viz(ax, jet_viz, source="fcst")

            # 天津标记
            ax.plot(
                self.map_config.tianjin_lon, self.map_config.tianjin_lat,
                "r*", markersize=10, zorder=100,
            )

            plt.savefig(fig_path, dpi=self.map_config.dpi, bbox_inches="tight")
            plt.close()
            logger.debug(f"预报追踪图已保存: {fig_path}")
            return fig_path

        except Exception as e:
            logger.error(f"预报追踪图生成失败 [{level}hPa]: {e}")
            plt.close("all")
            return ""

    def _draw_trough_tracks(self, ax, tracker, tianjin_track_ids: List[int]):
        """
        绘制高空槽追踪轨迹。

        影响天津的：棕色，透明度递减，标注时间
        不影响天津的：灰色，透明度递减，标注时间
        """
        if tracker is None or not tracker.tracks:
            return

        tianjin_set = set(tianjin_track_ids) if tianjin_track_ids else set()

        for track_id, troughs in tracker.tracks.items():
            # 确定颜色
            if track_id in tianjin_set:
                color = "brown"
            else:
                color = "grey"

            num_troughs = len(troughs)

            for idx, trough in enumerate(troughs):
                points = trough.get("points", [])
                if isinstance(points, np.ndarray):
                    points = points.tolist()
                if len(points) < 2:
                    continue

                # 透明度递减
                alpha = 1.0 - 0.7 * idx / max(1, num_troughs - 1)

                # 绘制槽线
                lons = [p[0] for p in points]
                lats = [p[1] for p in points]
                ax.plot(lons, lats, color=color, linewidth=2.0, alpha=alpha)

                # 时间标签
                fcst_time = trough.get("fcst_time")
                if fcst_time:
                    time_text = f"{fcst_time.hour}时"
                    mid_idx = len(points) // 2
                    ax.text(
                        points[mid_idx][0], points[mid_idx][1], time_text,
                        fontsize=8, color=color, ha="center", va="center",
                        clip_on=True,
                        bbox=dict(facecolor="white", edgecolor=color,
                                  alpha=0.8, pad=1, linewidth=0.5),
                    )

    def _draw_vortex_tracks(self, ax, tracker, tianjin_track_ids: List[int]):
        """
        绘制低涡追踪轨迹。

        影响天津的：红色标记+轨迹线，透明度递减，标注时间
        不影响天津的：灰色标记+轨迹线
        """
        if tracker is None or not tracker.tracks:
            return

        tianjin_set = set(tianjin_track_ids) if tianjin_track_ids else set()

        for track_id, vortices in tracker.tracks.items():
            if track_id in tianjin_set:
                color = "red"
            else:
                color = "grey"

            num_vortices = len(vortices)

            # 绘制轨迹连线
            if num_vortices >= 2:
                lons = [v["lon"] for v in vortices]
                lats = [v["lat"] for v in vortices]
                ax.plot(lons, lats, color=color, linewidth=1.5,
                        linestyle="--", alpha=0.6, zorder=40)

            # 绘制每个时次的低涡中心
            for idx, v in enumerate(vortices):
                lon, lat = v["lon"], v["lat"]

                if not (self.map_config.lon_min <= lon <= self.map_config.lon_max and
                        self.map_config.lat_min <= lat <= self.map_config.lat_max):
                    continue

                # 透明度递减
                alpha = 1.0 - 0.7 * idx / max(1, num_vortices - 1)

                # 低涡标记
                ax.text(
                    lon, lat, "L",
                    color=color, fontsize=14, alpha=alpha,
                    ha="center", va="center",
                    weight="bold", zorder=100,
                )

                # 时间标签
                fcst_time = v.get("fcst_time")
                if fcst_time:
                    time_text = f"{fcst_time.hour}时"
                    ax.text(
                        lon, lat - 0.8, time_text,
                        fontsize=7, color=color, ha="center", va="center",
                        clip_on=True, alpha=alpha,
                        bbox=dict(facecolor="white", edgecolor=color,
                                  alpha=0.6, pad=1, linewidth=0.5),
                    )

    def _draw_center_tracks(self, ax, tracks: List[Dict], letter: str,
                             impact_color: str):
        
        logger.info(f"{letter} 收到轨迹数: {len(tracks)}; "
            f"各条点数: {[len(t.get('positions', [])) for t in tracks]}")
        """
        绘制中心点轨迹（低压中心或冷中心，各自独立一套，互不连线）。

        影响天津：impact_color（L红 / C蓝）+ 同色虚线轨迹
        不影响：  灰色
        时间越晚越透明，并在标记下方标注时刻。

        Args:
            tracks:       [{"positions":[{"lon","lat","fcst_time"}], "is_impact"}, ...]
            letter:       标记字母 "L" 或 "C"
            impact_color: 影响天津时的颜色，如 "red" / "blue"
        """
        if not tracks:
            return

        for tk in tracks:
            positions = tk.get("positions", [])
            if not positions:
                continue

            color = impact_color if tk.get("is_impact") else "grey"
            num_pos = len(positions)

            # 轨迹连线
            if num_pos >= 2:
                lons = [p["lon"] for p in positions]
                lats = [p["lat"] for p in positions]
                ax.plot(lons, lats, color=color, linewidth=1.5,
                        linestyle="--", alpha=0.6, zorder=40)

            # 逐时次画字母 + 时间
            for idx, pos in enumerate(positions):
                lon, lat = pos["lon"], pos["lat"]
                logger.info(f"{letter} pt({idx}): ({lon:.1f}, {lat:.1f}) in={self._in_extent(lon, lat)}")   # 临时调试
                if not self._in_extent(lon, lat):
                    continue

                alpha = 1.0 - 0.7 * idx / max(1, num_pos - 1)

                ax.text(lon, lat, letter, color=color, fontsize=14,
                        alpha=alpha, ha="center", va="center",
                        weight="bold", zorder=100)

                fcst_time = pos.get("fcst_time")
                if fcst_time:
                    ax.text(lon, lat - 0.8, f"{fcst_time.hour}时",
                            fontsize=7, color=color, ha="center", va="center",
                            clip_on=True, alpha=alpha,
                            bbox=dict(facecolor="white", edgecolor=color,
                                      alpha=0.6, pad=1, linewidth=0.5))

    # ================================================================
    # 辅助方法：绘制 MICAPS14 等值线底图
    # ================================================================

    def _draw_obs_isolines(self, ax, hgt_data: dict):
        """绘制实况等值线"""
        lines = hgt_data.get("lines")
        if lines is None:
            return

        from config.settings import SUBTROPICAL_HIGH_LAT_THRESHOLD
        from modules.tracking.subtropical_high_analysis import (
            _max_lat_in_lon_window,
        )

        normal_lines = []
        line_588 = []
        for i in range(len(lines["line_xyz"])):
            line_xyz = lines["line_xyz"][i]
            line_points = line_xyz[:, 0:2].tolist()
            label = str(lines["line_label"][i]).strip()
            if label == "588":
                win_max_lat = _max_lat_in_lon_window(np.array(line_points))
                if (not np.isnan(win_max_lat)
                        and win_max_lat >= SUBTROPICAL_HIGH_LAT_THRESHOLD):
                    line_588.append(line_points)
                else:
                    normal_lines.append(line_points)
            else:
                normal_lines.append(line_points)

        if normal_lines:
            meb.add_solid_lines(ax, normal_lines, color="blue", linewidth=0.8)
        if line_588:
            meb.add_solid_lines(ax, line_588, color="red", linewidth=2.0)

    def _draw_obs_symbols(self, ax, hgt_data: dict):
        """绘制实况符号"""
        symbols = hgt_data.get("symbols")
        if symbols is None:
            return

        symbol_map = {
            # 60: ("H", "blue"),
            61: ("L", "red"),
            # 62: ("W", "red"),
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
                ax.text(lon, lat, text, color=color, fontsize=14,
                        ha="center", va="center", weight="bold", zorder=100)

    def _draw_obs_labels(self, ax, hgt_data: dict):
        """绘制实况等值线标签"""
        lines = hgt_data.get("lines")
        if lines is None:
            return

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
                clip_on=True,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.7, pad=1),
            )