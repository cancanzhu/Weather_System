# 大模型模块 — `modules/llm/`

## 概述

根据经纬度坐标调用大模型判断天气系统所在省份和方位。
设计上做了接口隔离，后续替换 LangChain 只改 `llm_client.py`，其他模块零改动。

## 文件结构
modules/llm/
├── __init__.py
├── llm_client.py          # 底层 API 封装
├── location_service.py    # 经纬度位置描述服务
├── analyzer.py            # 预留：完整天气分析生成，当前未接入主流程
└── data_serializer.py     # 预留：追踪结果序列化，当前未接入主流程

## llm_client.py — API 客户端

### `call_llm(prompt: str, system_prompt: str = None) -> str | None`
- 输入：提示词、系统提示词
- 输出：模型返回文本，失败返回 None
- 依赖：`openai` 库、`settings.LLM_*` 配置
- 降级机制：API Key 未配置、库未安装、调用失败时均返回 None，不影响程序运行

## location_service.py — 位置描述服务

### `get_location_description(coords, system_type) -> str`
- 输入：坐标列表 `[(lon, lat), ...]`、系统类型
- 输出：`"内蒙古自治区的中部"` 或降级 `"(115.0°E, 42.0°N)附近"`

### `get_point_location(lon, lat, system_type) -> str`
- 单点位置描述（低涡中心用）

### `get_line_location(points, system_type) -> str`
- 线状系统位置描述（高空槽用）
- 输入：`[[lon, lat], ...]`

## 调用关系
trough_analysis._analyze_single_trough → get_line_location（高空槽整条线坐标）
vortex_analysis.run                    → get_point_location（低涡中心坐标）
↓
location_service.py
↓
llm_client.call_llm → qwen API
↓ (失败时)
降级返回坐标描述

## 哪些系统调用大模型

| 系统 | 是否调用 | 说明 |
|------|---------|------|
| 高空槽 | ✅ | 实况匹配的槽线，用整条线坐标判断省份 |
| 低涡 | ✅ | 实况匹配的低涡，用中心坐标判断省份 |
| 冷涡 | ❌ | 只需分类（东北/蒙古）和强度，不需要省份 |
| 副高 | ❌ | 只需纬度阈值判断 |
| 急流 | ❌ | 暂无追踪分析 |
| 新生系统 | ❌ | 位置描述为"新生成"，不调用 |

## 当前实现范围

当前大模型模块只用于“经纬度坐标 → 省份/方位描述”，不是完整的天气形势自动解读模块。

已经接入主流程的能力：

| 功能 | 状态 |
|---|---|
| 高空槽位置描述 | 已实现 |
| 低涡中心位置描述 | 已实现 |
| 冷涡文字分析 | 未使用大模型 |
| 副热带高压文字分析 | 未使用大模型 |
| 低空急流文字分析 | 未实现 |
| 完整天气过程自动解读 | 预留，尚未接入主流程 |

当前未接入主流程的文件：

- `analyzer.py`
- `data_serializer.py`

这两个文件属于后续扩展预留，不参与当前报告生成。

## 配置（settings.py）

```python
LLM_API_KEY = "your-api-key-here"
LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL = "qwen3.6-plus"
LLM_ENABLED = True    # False 关闭大模型，使用坐标降级
```

注意：当前版本的大模型配置直接写在 `config/settings.py` 中，代码不会自动读取环境变量。因此运行前需要在 `settings.py` 中配置 `LLM_API_KEY`、`LLM_BASE_URL`、`LLM_MODEL` 和 `LLM_ENABLED`。

出于安全考虑，分享工程、提交仓库或发送压缩包前，应删除或脱敏真实 API Key。

## 后续替换 LangChain

1. 只修改 `llm_client.py`，把 `call_llm` 内部实现从 raw OpenAI API 换成 LangChain 的 Chain/Agent
2. `location_service.py` 的函数签名不变
3. 所有调用方（`trough_analysis.py`、`vortex_analysis.py`）零改动
4. 可在 `modules/llm/` 下新增更多服务文件（如 `weather_interpreter.py`）

## 注意事项

1. API 免费额度耗尽时返回 403 错误，自动降级为坐标描述
2. `openai` 库未安装时自动降级，不报错
3. `LLM_ENABLED = False` 可全局关闭大模型调用
4. `temperature=0.1` 确保输出稳定一致