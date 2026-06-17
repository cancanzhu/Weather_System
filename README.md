# 天气系统识别与分析系统

基于 MICAPS4 预报数据和 MICAPS14 实况数据，实现天气系统的自动识别、追踪、可视化和报告生成。

## 快速开始

```bash
pip install meteva metdig numpy matplotlib python-docx scipy openai
cd weather_system_project
python main.py
```

输入时间格式：`2025-06-01-14-30`

## 运行前配置

运行前需要先检查 `config/settings.py` 中的路径和大模型配置：

| 配置项 | 说明 |
|---|---|
| `MICAPS4_ROOT` | MICAPS4 预报数据根目录 |
| `MICAPS14_ROOT` | MICAPS14 实况数据根目录 |
| `MICAPS4_MODEL` | 预报模式名，当前默认为 `ECWMF` |
| `FORECAST_HOURS` | 预报时效，当前为 `[0, 3, 6, 9, 12]` |
| `PLOT_LEVELS` | 处理层次，当前为 `[500, 700, 850]` |
| `MAP_CONFIG` | 绘图范围、DPI、天津坐标等 |
| `LLM_API_KEY` | 从环境变量 `DASHSCOPE_API_KEY` 读取，不再写在代码中 |
| `LLM_MODEL` | 当前配置模型为 `qwen3.6-plus` |
| `LLM_ENABLED` | 是否启用大模型位置描述 |

注意：API Key 统一从环境变量 `DASHSCOPE_API_KEY` 读取，禁止写入代码。运行前设置：PowerShell `$env:DASHSCOPE_API_KEY="sk-xxx"`（永久生效走"系统设置 → 环境变量"）；Linux/macOS `export DASHSCOPE_API_KEY="sk-xxx"`。未设置时大模型自动降级为坐标描述，不影响流程。

## 输出

- `output/figures/` — 图片文件
- `output/reports/天气系统识别报告_*.docx` — 第一份 Word（天气图+系统识别图并排）
- `output/reports/天气系统分析报告_*.docx` — 第二份 Word（追踪分析+文字描述+分析图片）

## 项目结构

```
weather_system_project/
├── main.py
├── config/
│   └── settings.py
├── modules/
│   ├── data_io/
│   │   ├── time_input.py
│   │   ├── micaps4_reader.py
│   │   ├── micaps14_reader.py
│   │   └── data_manager.py
│   ├── detection/
│   │   ├── base_detector.py
│   │   ├── detector_factory.py
│   │   ├── trough.py              ✅
│   │   ├── subtropical_high.py    ✅
│   │   ├── cold_vortex.py         ✅
│   │   ├── low_level_vortex.py    ✅
│   │   └── low_level_jet.py       ✅
│   ├── visualization/
│   │   ├── field_plotter.py
│   │   ├── system_plotter.py
│   │   └── analysis_plotter.py
│   ├── report/
│   │   ├── word_generator.py
│   │   └── analysis_report.py
│   ├── tracking/
│   │   ├── base_tracker.py
│   │   ├── trough_tracker.py           ✅
│   │   ├── trough_analysis.py          ✅
│   │   ├── vortex_tracker.py           ✅
│   │   ├── vortex_analysis.py          ✅
│   │   ├── cold_vortex_analysis.py     ✅
│   │   └── subtropical_high_analysis.py ✅
│   └── llm/                            # ✅ 大模型位置描述模块
│       ├── __init__.py
│       ├── llm_client.py               # API 客户端
│       ├── location_service.py         # 经纬度位置描述服务
│       ├── analyzer.py                 # 预留：完整天气分析生成，当前未接入主流程
│       └── data_serializer.py          # 预留：追踪结果序列化，当前未接入主流程
├── utils/
│   ├── path_builder.py
│   └── geo_utils.py
├── docs/
│   ├── api_reference.md        # 代码接口文档（每个函数的输入输出）
│   ├── data_io.md
│   ├── detection.md
│   ├── visualization.md
│   ├── report.md
│   ├── tracking.md
│   ├── extension_guide.md
│   ├── known_issues.md         # 踩坑记录（必读）
│   └── reference_code.md
└── output/{figures,reports}
```

## 核心流程

```
Step 1: 时间输入 → init_hour
Step 2: 数据读取 → forecast_data, obs_data
Step 3: 天气系统识别（5种）
Step 4: 可视化（要素场图 + 系统识别图）
Step 5: 第一份 Word
Step 6: 追踪与分析
  ├── trough_analysis.run()             高空槽追踪
  ├── vortex_analysis.run()             低涡追踪（700/850hPa）
  ├── cold_vortex_analysis.run()        冷涡追踪（500hPa GH+T配合）
  └── subtropical_high_analysis.run()   副高分析（纬度阈值）
Step 7: 分析报告图片 + 第二份 Word
```

## 天气系统完成状态

| 天气系统 | 层次 | 识别 | 可视化 | 追踪/分析 | 分析报告 |
|---------|------|------|--------|----------|---------|
| 高空槽 | 500 | ✅ | ✅ | ✅ 线追踪+前倾后倾 | ✅ |
| 副热带高压 | 500 | ✅ | ✅ | ✅ 纬度阈值36°N | ✅ |
| 冷涡 | 500 | ✅ | ✅ | ✅ GH低压+T冷中心配合+分类 | ✅ |
| 低空低涡 | 700/850 | ✅ | ✅ | ✅ 匈牙利算法+150km缓冲 | ✅ |
| 低空急流 | 850 | ✅ | ✅ | ⬜ | ⬜ |

## 文档索引

| 文档 | 内容 |
|------|------|
| **[docs/api_reference.md](docs/api_reference.md)** | **代码接口文档（核心）** |
| **[docs/known_issues.md](docs/known_issues.md)** | **踩坑记录（必读）** |
| [docs/tracking.md](docs/tracking.md) | 追踪模块详解 |
| [docs/extension_guide.md](docs/extension_guide.md) | 扩展指南 |
| [docs/visualization.md](docs/visualization.md) | 可视化模块 |
| [docs/report.md](docs/report.md) | 报告生成模块 |
| [docs/data_io.md](docs/data_io.md) | 数据读取模块 |
| [docs/detection.md](docs/detection.md) | 识别模块 |
| [docs/reference_code.md](docs/reference_code.md) | 原始参考代码 |
| [docs/llm.md](docs/llm.md) | 大模型模块 |
| [docs/configuration.md](docs/configuration.md) | 配置参数说明 |