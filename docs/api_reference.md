# 代码接口文档 — `docs/api_reference.md`

本文档列出项目中每个 `.py` 文件的每个类/函数的输入、输出、依赖关系。
新接手的 AI 通过本文档即可定位需要查看和修改的源文件。

---

## config/settings.py

全局配置，所有模块从此读取参数。

### 关键配置项

| 配置 | 说明 |
|------|------|
| `MICAPS4_ROOT` / `MICAPS14_ROOT` | 数据根目录 |
| `MICAPS4_VARIABLES` / `MICAPS14_VARIABLES` | 变量→层次映射 |
| `FORECAST_HOURS` | `[0, 3, 6, 9, 12]` |
| `PLOT_LEVELS` | `[500, 700, 850]` |
| `MAP_CONFIG` | 地图范围、DPI、天津坐标 |
| `TIANJIN_RANGE` | 天津矩形区域 `{lon_min:116, lon_max:118, lat_min:38, lat_max:40}` |
| `SMOOTH_POINTS_PLOT` / `SMOOTH_POINTS_DETECT` | 绘图/识别平滑点数 |
| `WEATHER_SYSTEM_REGISTRY` | 天气系统注册表（识别器插件化） |
| `TROUGH_*` | 高空槽识别+追踪参数 |
| `JET_*` | 低空急流识别参数 |
| `VORTEX_TRACK_*` / `VORTEX_TIANJIN_IMPACT_DISTANCE` | 低涡追踪参数（150km缓冲） |
| `COLD_VORTEX_*` | 冷涡配合距离(300km)、分类区域、影响区域 |
| `SUBTROPICAL_HIGH_LAT_THRESHOLD` | 副高影响纬度阈值(36°N) |
| `LLM_API_KEY` | 阿里云 DashScope API Key |
| `LLM_BASE_URL` | API 地址 |
| `LLM_MODEL` | 模型名称（如 qwen-plus） |
| `LLM_ENABLED` | True 启用，False 关闭大模型（降级为坐标描述） |

---

## main.py — 主入口

### 7 步流程

| 步骤 | 调用 | 产出 |
|------|------|------|
| Step 1 | `time_input` | `current_time`, `init_hour` |
| Step 2 | `DataManager` | `forecast_data`, `obs_data` |
| Step 3 | `DetectorFactory.detect_all()` | `fcst/obs_detection_results` |
| Step 4 | `FieldPlotter` + `SystemPlotter` | `figure_paths` |
| Step 5 | `WordReportGenerator` | 第一份 Word |
| Step 6 | `trough_analysis.run()` + `vortex_analysis.run()` + `cold_vortex_analysis.run()` + `subtropical_high_analysis.run()` | 各系统分析结果 |
| Step 7 | `AnalysisPlotter` + `AnalysisReportGenerator` | 第二份 Word |

---

## modules/data_io/

### `time_input.py`
- `get_user_time() -> datetime`
- `determine_init_hour(current_time) -> int` → 8 或 20

### `micaps4_reader.py`
- `Micaps4Reader.read(filepath, smooth=True, smooth_points=5) -> xarray.DataArray | None`
- 注意：当前 `DataManager.load_forecast_data()` 调用 `read(filepath)` 时没有显式关闭平滑，因此 MICAPS4 数据读取阶段默认已经平滑一次；后续绘图和识别模块还会再次按各自参数平滑。
- 返回的 DataArray: `grd.squeeze()` → 2D, `grd['lon'].values`, `grd['lat'].values`

### `micaps14_reader.py`
- `Micaps14Reader.read(filepath) -> dict | None`
- 返回 dict: `{"lines": {...}, "symbols": {...}, "lines_symbol": {...}, "fill_area": {...}}`
- 注意: `(val or {}).get(key)` 模式处理 None 值

### `data_manager.py`
- `DataManager(current_time, init_hour)`
- `load_forecast_data() -> {(time_label, level): data_dict}`
- `load_observation_data() -> {(time_label, level): data_dict}`
- data_dict 预报: `{"GH": xarray, "T": xarray, "U": xarray, "V": xarray, "data_type": "fcst", "time": datetime, "forecast_hour": int}`
- data_dict 实况: `{"HGT": dict, "TMP": dict, "data_type": "obs"}`

---

## modules/detection/ — 识别模块

### `base_detector.py`
- `BaseDetector.detect(data_dict, level) -> list[dict]` — 抽象方法
- 识别结果格式: `{"system_name", "level", "center_lon", "center_lat", "geometry": {"type", ...}, "properties": {...}}`

### `detector_factory.py`
- `DetectorFactory.detect_all(data_dict, data_type) -> {"系统名": [结果列表]}`

### 各识别器

| 文件 | 预报算法 | 实况提取 | geometry type | 特殊属性 |
|------|---------|---------|---------------|---------|
| `trough.py` | `mdgcal.trough()` | `linesym_code==0` | `graphy_raw` / `line` | `properties.caldata` |
| `subtropical_high.py` | `ax.contour([588])` + `cs.allsegs` | `line_label=="588"` | `line` | — |
| `cold_vortex.py` | `mdgcal.high_low_center(T)` fid<0 | `symbol_code==63` | `point` | — |
| `low_level_vortex.py` | `mdgcal.high_low_center(GH)` fid<0 | `symbol_code==61` | `point` | `properties.caldata`, `properties.strength` |
| `low_level_jet.py` | `mdgcal.jet(U,V)` | `fill_area` code 1102/1110~1116 | `graphy_raw` / `jet_lines` | — |

---

## modules/visualization/

### `field_plotter.py` — 气象要素场图（第一份 Word）
- `FieldPlotter(map_config).plot(data_dict, time_label, level, data_type) -> str`(PNG路径)
- `_draw_micaps14_lines(ax, graphy_data)` — 实况等值线，588红色加粗，标签取线内中点
- `_draw_micaps14_symbols(ax, graphy_data)` — 实况符号，范围过滤

### `system_plotter.py` — 系统识别图（第一份 Word）
- `SystemPlotter(map_config).plot(data_dict, detection_results, ...) -> str`
- `PLOT_HANDLERS` 注册表: `{"高空槽", "副热带高压", "冷涡", "低空低涡", "低空急流"}`
- `_draw_background` — 底图等值线+标签（实况用 `meb.add_solid_lines`）

### `analysis_plotter.py` — 分析报告图（第二份 Word）
- `AnalysisPlotter(map_config)`
- `plot_obs_analysis(obs_data, obs_detection, level, time_label) -> str` — 实况分析图
- `plot_fcst_tracking(tracker, tianjin_track_ids, level, time_label, cold_vortex_tracks=None, cold_vortex_impact_ids=None) -> str` — 预报追踪图
- `_overlay_obs_systems(ax, detection, level)` — 按层次叠加:
  - 500: 槽线(棕色) + 副高588线(红色,仅影响时) + 冷涡(蓝色C)
  - 700: 低涡(红色D)
  - 850: 低涡(红色D) + 急流(红色箭头)
- `_draw_trough_tracks(ax, tracker, tianjin_track_ids)` — 槽线轨迹(棕色/灰色)
- `_draw_vortex_tracks(ax, tracker, tianjin_track_ids)` — 低涡轨迹(红色/灰色)
- `_draw_cold_vortex_tracks(ax, vortex_tracks, impact_ids)` — 冷涡轨迹(蓝色/灰色)

---

## modules/report/

### `word_generator.py` — 第一份 Word
- `WordReportGenerator(current_time, init_hour)`
- `generate(figure_paths) -> str`
- 输入: `{("obs"/"fcst", time_label, level): (field_path, system_path, system_names)}`

### `analysis_report.py` — 第二份 Word
- `AnalysisReportGenerator(current_time, init_hour)`
- `generate(trough_analyses, vortex_analyses=None, cold_vortex_analyses=None, subtropical_high_analyses=None, analysis_figures=None) -> str`
- 输入:
  - `trough_analyses`: `[{"trough_num", "track_id", "location", "tilt_type", "from_dir", "to_dir", "impact_time", "is_new"}]`
  - `vortex_analyses`: `[{"vortex_num", "track_id", "level", "location", "strength", "quadrant", "from_dir", "to_dir", "impact_time", "is_new"}]`
  - `cold_vortex_analyses`: `[{"cv_num", "vortex_id", "vortex_type", "strength", "quadrant", "from_dir", "to_dir", "impact_time", "is_new"}]`

---

## modules/tracking/ — 追踪模块

### `base_tracker.py`
- `BaseTracker` 抽象基类
- `tracks: Dict[int, List[Dict]]`, `next_track_id: int`
- `update(detection_result, time_str, fcst_time)` — 抽象
- `get_tianjin_tracks(tianjin_range) -> List[int]` — 抽象

### `trough_tracker.py` — 高空槽追踪器
- `extract_trough_features(caldata) -> list[dict]` — 从 metdig trough 结果提取特征
- `calculate_similarity(t1, t2) -> float` — 距离0.5+长度0.2+方向0.2+强度0.1
- `TroughTracker.update(caldata, time_str, fcst_time)` — 贪心匹配
- `TroughTracker.get_tianjin_tracks(tianjin_range) -> List[int]` — 点在矩形内

### `trough_analysis.py` — 高空槽分析
- `run(forecast_data, fcst_detection_results, obs_detection_results) -> (trough_analyses, trough_tracker, tianjin_track_ids)`
- 流程: 追踪→影响判断→实况匹配→前倾后倾→移动方向→影响时间
- 返回 `trough_analyses`: `[{"trough_num", "track_id", "location", "tilt_type", "from_dir", "to_dir", "impact_time", "is_new"}]`
- 返回 `trough_tracker`: TroughTracker 实例（供可视化使用）
- 返回 `tianjin_track_ids`: `[int, ...]`
- caldata 来源: `fcst_detection_results[(tl,500)]["高空槽"][0]["properties"]["caldata"]`

### `vortex_tracker.py` — 低涡追踪器
- `VortexTracker.update(detection_results, time_str, fcst_time)` — 匈牙利算法匹配
- `VortexTracker.get_tianjin_tracks(tianjin_range) -> List[int]` — 150km缓冲区
- `_point_to_rect_distance(lon, lat, rect) -> float` — 点到矩形距离(km)
- `_hungarian_match(prev, curr, time_hours) -> (matches, new, dead)` — 含速度约束

### `vortex_analysis.py` — 低涡分析
- `run(forecast_data, fcst_detection_results, obs_detection_results) -> (vortex_analyses, trackers_by_level, tianjin_ids_by_level)`
- 在 700hPa 和 850hPa 独立追踪
- 返回 `vortex_analyses`: `[{"vortex_num", "track_id", "level", "location", "strength", "quadrant", "from_dir", "to_dir", "impact_time", "is_new"}]`
- `trackers_by_level`: `{700: VortexTracker, 850: VortexTracker}`
- `tianjin_ids_by_level`: `{700: [ids], 850: [ids]}`


### `cold_vortex_analysis.py` — 冷涡分析
- `run(forecast_data, fcst_detection_results, obs_detection_results, obs_data) -> (cold_vortex_analyses, vortex_tracks, impact_ids)`
- **注意**: 比其他分析多一个 `obs_data` 参数（需要从实况 HGT symbols 提取低压中心）
- 流程: GH识别低压+T识别冷中心→分别追踪→配合判断(300km)→分类(东北/蒙古)→大区域影响判断
- 返回 `cold_vortex_analyses`: `[{"cv_num", "vortex_id", "vortex_type", "strength", "quadrant", "from_dir", "to_dir", "impact_time", "is_new"}]`
- `vortex_tracks`: `[{"vortex_id", "positions": [{"lon","lat","fcst_time",...}], "vortex_type"}]`
- `impact_ids`: `[int, ...]`

### `subtropical_high_analysis.py` — 副高分析
- `run(forecast_data, fcst_detection_results, obs_detection_results) -> subtropical_high_analyses`
- **不需要追踪器**，只做纬度阈值判断
- 实况: 588线最北纬度 ≥ 36°N → 影响
- 预报: 逐时次检查，找第一个影响的时次
- 返回: `[{"type":"obs","is_affecting","max_latitude","description"}, {"type":"fcst",...}]`

---

## modules/llm/ — 大模型模块

### `llm_client.py` — API 客户端（底层）
- `call_llm(prompt: str, system_prompt: str = None) -> str | None`
- 输入：提示词、系统提示词
- 输出：模型返回文本，失败返回 None（自动降级）
- 依赖：`openai` 库、`settings.LLM_*` 配置
- 后续替换 LangChain 只改此文件

### `location_service.py` — 位置描述服务（对外接口）
- `get_location_description(coords: List[Tuple[float,float]], system_type: str) -> str`
  - 输入：坐标列表、系统类型
  - 输出："内蒙古自治区的中部" 或降级 "(115.0°E, 42.0°N)附近"
- `get_point_location(lon, lat, system_type) -> str` — 单点（低涡/冷涡中心用）
- `get_line_location(points, system_type) -> str` — 线状（高空槽用）
### `analyzer.py` — 预留模块
- 当前用于后续扩展完整天气形势解读。
- 目前未接入 `main.py` 主流程。

### `data_serializer.py` — 预留模块
- 当前用于后续扩展追踪结果、识别结果的结构化序列化。
- 目前未接入 `main.py` 主流程。

### 调用关系
trough_analysis._analyze_single_trough → get_line_location（高空槽整条线坐标）
vortex_analysis.run                    → get_point_location（低涡中心坐标）
↓
location_service.py
↓
llm_client.call_llm → qwen API
↓ (失败时)
降级返回坐标描述

### 配置（settings.py）
| 配置 | 说明 |
|------|------|
| `LLM_API_KEY` | 阿里云 DashScope API Key |
| `LLM_BASE_URL` | API 地址 |
| `LLM_MODEL` | 模型名称，当前代码中配置为 `qwen3.6-plus` |
| `LLM_ENABLED` | True/False 开关 |


## utils/

### `path_builder.py`
- `build_micaps4_path(root, model, variable, level, init_time, forecast_hour) -> str`
- `build_micaps14_path(root, variable, level, obs_time) -> str`

### `geo_utils.py`
- `calculate_direction(from_lon, from_lat, to_lon, to_lat) -> str` — 8方位
- `get_opposite_direction(direction) -> str`
- `get_direction_from_vector(dx, dy) -> str`
- `calculate_center(points) -> (lon, lat)`
- `is_in_region(points, region) -> bool`
- `haversine_distance(lon1, lat1, lon2, lat2) -> float` — km
- `judge_trough_tilt(center_500, center_lower) -> str` — "前倾"/"后倾"
- `calculate_impact_time(track_positions, tianjin_range) -> str`
### `calculate_quadrant(center_lon, center_lat, target_lon, target_lat) -> str`
- 输入：系统中心坐标、目标点坐标
- 输出：`"东北"` / `"东南"` / `"西南"` / `"西北"`

---

## 依赖关系

```
main.py
  ├── DataManager → Micaps4Reader + Micaps14Reader
  ├── DetectorFactory → 5个识别器
  ├── FieldPlotter + SystemPlotter → 第一份 Word (WordReportGenerator)
  ├── trough_analysis → TroughTracker + geo_utils + llm.location_service
  ├── vortex_analysis → VortexTracker + geo_utils + llm.location_service
  ├── cold_vortex_analysis → VortexTracker + metdig + geo_utils
  ├── subtropical_high_analysis → (无追踪器)
  └── AnalysisPlotter + AnalysisReportGenerator → 第二份 Word
```

---

## 新增模块时需要查看的源文件

| 任务 | 必须看 | 参考看 |
|------|--------|--------|
| 新增识别器 | `base_detector.py`, `settings.py`, `system_plotter.py` | `trough.py` |
| 新增追踪（线特征） | `base_tracker.py`, `trough_tracker.py`, `trough_analysis.py` | `main.py` Step 6 |
| 新增追踪（点特征） | `base_tracker.py`, `vortex_tracker.py`, `vortex_analysis.py` | `main.py` Step 6 |
| 新增复合分析（如冷涡） | `cold_vortex_analysis.py` | `vortex_tracker.py` |
| 新增纬度分析（如副高） | `subtropical_high_analysis.py` | — |
| 修改第一份 Word | `word_generator.py` | — |
| 修改第二份 Word | `analysis_report.py`, `analysis_plotter.py` | 各 xxx_analysis.py |
| 修改可视化参数 | `settings.py` + 对应 plotter | — |
| 修改大模型逻辑 | `llm_client.py`, `location_service.py` | `settings.py` |
| 替换 LangChain | `llm_client.py`（只改此文件） | `location_service.py`（签名不变） |
