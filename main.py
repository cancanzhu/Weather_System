"""
主入口文件
==========
串联全部流程: 时间输入 → 数据读取 → 天气系统识别 → 可视化 → Word 报告生成

使用方式:
    cd weather_system_project
    python main.py

运行后在终端输入当前时间（格式: 年-月-日-时-分），系统自动完成后续全部流程。
"""
import matplotlib
matplotlib.use('Agg')

import os
import sys
import logging
from datetime import datetime

# 将项目根目录加入 sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from config import settings
from modules.data_io.time_input import get_user_time, determine_init_hour
from modules.data_io.data_manager import DataManager
from modules.detection.detector_factory import DetectorFactory
from modules.visualization.field_plotter import FieldPlotter
from modules.visualization.system_plotter import SystemPlotter
from modules.report.word_generator import WordReportGenerator


# 配置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


def main():
    """主流程"""

    # ══════════════════════════════════════════
    # Step 1: 时间输入
    # ══════════════════════════════════════════
    logger.info("=" * 60)
    logger.info("天气系统识别与分析系统")
    logger.info("=" * 60)

    current_time = get_user_time()
    init_hour = determine_init_hour(current_time)
    logger.info(f"当前时间: {current_time.strftime('%Y-%m-%d %H:%M')}")
    logger.info(f"起报时刻: {init_hour:02d}时")

    # 确保输出目录存在
    os.makedirs(settings.FIGURE_DIR, exist_ok=True)
    os.makedirs(settings.REPORT_DIR, exist_ok=True)

    # ══════════════════════════════════════════
    # Step 2: 数据读取
    # ══════════════════════════════════════════
    logger.info("-" * 40)
    logger.info("开始读取数据...")

    data_manager = DataManager(current_time, init_hour)
    forecast_data = data_manager.load_forecast_data()
    obs_data = data_manager.load_observation_data()

    logger.info(f"预报数据: {len(forecast_data)} 组")
    logger.info(f"实况数据: {len(obs_data)} 组")

    if not forecast_data and not obs_data:
        logger.error("未读取到任何数据，请检查数据路径和文件是否存在")
        return

    # ══════════════════════════════════════════
    # Step 3: 天气系统识别
    # ══════════════════════════════════════════
    logger.info("-" * 40)
    logger.info("开始天气系统识别...")

    detector_factory = DetectorFactory()

    # 实况识别
    obs_detection_results = {}
    for key, data_dict in obs_data.items():
        results = detector_factory.detect_all(data_dict, data_type="obs")
        obs_detection_results[key] = results
        if results:
            systems = ", ".join(
                f"{name}({len(items)})"
                for name, items in results.items()
            )
            logger.info(f"  实况 {key}: {systems}")

    # 预报识别
    fcst_detection_results = {}
    for key, data_dict in forecast_data.items():
        results = detector_factory.detect_all(data_dict, data_type="fcst")
        fcst_detection_results[key] = results
        if results:
            systems = ", ".join(
                f"{name}({len(items)})"
                for name, items in results.items()
            )
            logger.info(f"  预报 {key}: {systems}")

    logger.info("天气系统识别完成")

    # ══════════════════════════════════════════
    # Step 4: 可视化（生成图片）
    # ══════════════════════════════════════════
    logger.info("-" * 40)
    logger.info("开始生成图片...")

    field_plotter = FieldPlotter(settings.MAP_CONFIG)
    system_plotter = SystemPlotter(settings.MAP_CONFIG)

    # figure_paths: {(data_type, time_label, level): (field_path, system_path)}
    figure_paths = {}

    # 生成实况图片
    for (time_label, level), data_dict in obs_data.items():
        detection = obs_detection_results.get((time_label, level), {})

        field_fig = field_plotter.plot(
            data_dict, time_label=time_label, level=level, data_type="obs",
            detection_results=detection,
        )
        system_fig = system_plotter.plot(
            data_dict, detection,
            time_label=time_label, level=level, data_type="obs"
        )
        system_names = "、".join(detection.keys()) if detection else "无"
        figure_paths[("obs", time_label, level)] = (field_fig, system_fig, system_names)

    # 生成预报图片
    for (time_label, level), data_dict in forecast_data.items():
        detection = fcst_detection_results.get((time_label, level), {})

        field_fig = field_plotter.plot(
            data_dict, time_label=time_label, level=level, data_type="fcst",
            detection_results=detection,
        )
        system_fig = system_plotter.plot(
            data_dict, detection,
            time_label=time_label, level=level, data_type="fcst"
        )
        system_names = "、".join(detection.keys()) if detection else "无"
        figure_paths[("fcst", time_label, level)] = (field_fig, system_fig, system_names)

    logger.info(f"图片生成完成: 共 {len(figure_paths)} 组")

    # ══════════════════════════════════════════
    # Step 5: 生成 Word 报告
    # ══════════════════════════════════════════
    logger.info("-" * 40)
    logger.info("开始生成 Word 报告...")

    report_gen = WordReportGenerator(current_time, init_hour)
    report_path = report_gen.generate(figure_paths)
    logger.info(f"报告已保存: {report_path}")

    # ══════════════════════════════════════════
    # Step 6: 天气系统追踪与分析+LLM
    # ══════════════════════════════════════════
    logger.info("-" * 40)
    logger.info("开始天气系统追踪与分析...")

    # 高空槽追踪
    from modules.tracking import trough_analysis
    trough_analyses, trough_tracker, trough_tianjin_ids = trough_analysis.run(
        forecast_data, fcst_detection_results, obs_detection_results,
    )

    # 低涡追踪
    from modules.tracking import vortex_analysis
    vortex_analyses, vortex_trackers, vortex_tianjin_ids = vortex_analysis.run(
        forecast_data, fcst_detection_results, obs_detection_results,
    )

    # 冷涡追踪
    from modules.tracking import cold_vortex_analysis
    cold_vortex_analyses, cold_vortex_tracks, cold_vortex_impact_ids, \
        cold_lp_tracks, cold_cc_tracks = cold_vortex_analysis.run(
            forecast_data, fcst_detection_results, obs_detection_results, obs_data,
        )
    
    # 副热带高压分析
    from modules.tracking import subtropical_high_analysis
    subtropical_high_analyses = subtropical_high_analysis.run(
        forecast_data, fcst_detection_results, obs_detection_results,
    )

    # 低空急流分析（850hPa）
    from modules.tracking import low_level_jet_analysis
    jet_analysis = low_level_jet_analysis.run(
        forecast_data, fcst_detection_results, obs_detection_results, obs_data,
    )

    # ══════════════════════════════════════════
    # Step 7: 生成分析报告图片 + 第二份 Word
    # ══════════════════════════════════════════
    logger.info("-" * 40)
    logger.info("开始生成分析报告图片...")

    from modules.visualization.analysis_plotter import AnalysisPlotter
    from modules.report.analysis_report import AnalysisReportGenerator

    analysis_plotter = AnalysisPlotter(settings.MAP_CONFIG)

    analysis_figures = {}
    obs_time_label = None
    for (tl, lv) in obs_data.keys():
        obs_time_label = tl
        break

    for level in settings.PLOT_LEVELS:
        level_figs = {}

        # 实况分析图
        obs_key = None
        for (tl, lv) in obs_data.keys():
            if lv == level:
                obs_key = (tl, lv)
                break

        if obs_key:
            obs_det = obs_detection_results.get(obs_key, {})
            obs_fig = analysis_plotter.plot_obs_analysis(
                obs_data[obs_key], obs_det, level,
                time_label=obs_time_label or "实况",
                jet_viz=jet_analysis.get("viz") if level == 850 else None,
            )
            level_figs["obs"] = obs_fig

        # 预报追踪图
        jv = jet_analysis.get("viz") if level == 850 else None
        if level == 500 and (trough_tracker.tracks or cold_lp_tracks or cold_cc_tracks):
            fcst_fig = analysis_plotter.plot_fcst_tracking(
                trough_tracker, trough_tianjin_ids, level,
                time_label=obs_time_label or "预报",
                cold_low_tracks=cold_lp_tracks,
                cold_center_tracks=cold_cc_tracks,
                jet_viz=jv,
            )
        elif level in vortex_trackers and vortex_trackers[level].tracks:
            fcst_fig = analysis_plotter.plot_fcst_tracking(
                vortex_trackers[level],
                vortex_tianjin_ids.get(level, []),
                level,
                time_label=obs_time_label or "预报",
                jet_viz=jv,
            )
        else:
            fcst_fig = analysis_plotter.plot_fcst_tracking(
                None, [], level,
                time_label=obs_time_label or "预报",
                jet_viz=jv,
            )
        level_figs["fcst_tracking"] = fcst_fig

        analysis_figures[level] = level_figs

    logger.info("分析报告图片生成完成")

    # 生成第二份 Word
    logger.info("开始生成分析报告...")
    analysis_gen = AnalysisReportGenerator(current_time, init_hour)
    analysis_path = analysis_gen.generate(
        trough_analyses,
        vortex_analyses=vortex_analyses,
        cold_vortex_analyses=cold_vortex_analyses,
        subtropical_high_analyses=subtropical_high_analyses,
        analysis_figures=analysis_figures,
        low_level_jet_analysis=jet_analysis,
    )
    logger.info(f"分析报告已保存: {analysis_path}")

    # ══════════════════════════════════════════
    # （后续）Step 8: 大模型进一步分析
    # ══════════════════════════════════════════
    # from modules.llm.analyzer import LLMAnalyzer
    # analyzer = LLMAnalyzer(settings.LLM_CONFIG)
    # analysis_text = analyzer.analyze(tracking_results, current_time)

    logger.info("=" * 60)
    logger.info("全部流程完成!")


if __name__ == "__main__":
    main()