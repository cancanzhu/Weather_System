# 配置参数说明 — `config/settings.py`

本文档记录当前工程中主要配置项的含义，方便后续部署、调试和交接。

## 数据路径配置

| 参数 | 说明 |
|---|---|
| `MICAPS4_ROOT` | MICAPS4 预报数据根目录 |
| `MICAPS14_ROOT` | MICAPS14 实况数据根目录 |
| `MICAPS4_MODEL` | 预报模式名，当前默认为 `ECWMF` |
| `OUTPUT_DIR` | 输出目录 |
| `FIGURE_DIR` | 图片输出目录 |
| `REPORT_DIR` | Word 报告输出目录 |

## 时间与层次配置

| 参数 | 说明 |
|---|---|
| `FORECAST_HOURS` | 预报时效列表，当前为 `[0, 3, 6, 9, 12]` |
| `PLOT_LEVELS` | 处理层次，当前为 `[500, 700, 850]` |
| `INIT_HOUR_THRESHOLD` | 起报时刻判断阈值；当前小时小于阈值时使用 08 时起报，否则使用 20 时起报 |

## 平滑参数

| 参数 | 说明 |
|---|---|
| `SMOOTH_POINTS_PLOT` | 绘图阶段平滑点数 |
| `SMOOTH_POINTS_DETECT` | 识别阶段平滑点数 |

注意：当前 `Micaps4Reader.read()` 读取阶段默认还会进行一次 `smooth_points=5` 的平滑，因此实际流程中可能存在读取平滑 + 绘图/识别平滑。

## 高空槽参数

| 参数 | 说明 |
|---|---|
| `TROUGH_RESOLUTION` | metdig 槽线识别分辨率 |
| `TROUGH_SMOOTH_TIMES` | metdig 槽线识别内部平滑次数 |
| `TROUGH_MIN_SIZE` | 槽线最小尺寸阈值 |
| `TROUGH_TRACK_DISTANCE_MAX` | 高空槽跨时次追踪最大匹配距离 |
| `TROUGH_TRACK_SIMILARITY_THRESHOLD` | 高空槽追踪相似度阈值 |
| `TROUGH_MATCH_DISTANCE_THRESHOLD` | 实况-预报高空槽匹配距离阈值 |

## 低空低涡参数

| 参数 | 说明 |
|---|---|
| `VORTEX_TRACK_DISTANCE_MAX` | 低涡追踪最大匹配距离 |
| `VORTEX_TRACK_MAX_SPEED` | 低涡最大移动速度约束 |
| `VORTEX_TIANJIN_IMPACT_DISTANCE` | 低涡影响天津的缓冲距离 |

## 冷涡参数

| 参数 | 说明 |
|---|---|
| `COLD_VORTEX_COUPLING_DISTANCE` | 高度场低压中心与温度场冷中心的配合距离 |
| `COLD_VORTEX_IMPACT_REGION` | 冷涡影响判断区域 |
| `NORTHEAST_COLD_VORTEX_REGION` | 东北冷涡分类区域 |
| `MONGOLIA_COLD_VORTEX_REGION` | 蒙古冷涡分类区域 |

## 副热带高压参数

| 参数 | 说明 |
|---|---|
| `SUBTROPICAL_HIGH_LAT_THRESHOLD` | 副高影响天津的纬度阈值，当前为 36°N |

## 大模型参数

| 参数 | 说明 |
|---|---|
| `LLM_API_KEY` | 从环境变量 `DASHSCOPE_API_KEY` 读取（禁止硬编码） |
| `LLM_BASE_URL` | API 地址 |
| `LLM_MODEL` | 当前配置模型 |
| `LLM_ENABLED` | 是否启用大模型位置描述 |

API Key 从环境变量 `DASHSCOPE_API_KEY` 读取，代码中不保存任何真实 Key。新增 `LLM_TIMEOUT_SECONDS`（默认10秒）控制单次调用超时。