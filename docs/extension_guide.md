# 扩展指南

## 一、新增识别（影响第一份 Word）

三步完成，无需修改框架核心代码：

1. `config/settings.py` — `WEATHER_SYSTEM_REGISTRY` 添加注册
2. `modules/detection/xxx.py` — 新建识别器，继承 `BaseDetector`
3. `modules/visualization/system_plotter.py` — `PLOT_HANDLERS` 添加绘图函数

---

## 二、新增追踪+分析（影响第二份 Word）

根据天气系统特点选择模式：

### 模式 A：线特征追踪（参考高空槽）
适用于：槽线、切变线等线状系统

1. 新建 `modules/tracking/xxx_tracker.py`（继承 BaseTracker，贪心匹配）
2. 新建 `modules/tracking/xxx_analysis.py`（封装完整流程）
3. `main.py` Step 6 加调用
4. `analysis_plotter.py` 对应层次加轨迹绘制
5. `analysis_report.py` 扩展文字生成（修改 generate 签名 + 三个文字函数）

### 模式 B：点特征追踪（参考低涡）
适用于：气旋中心、低压中心等点状系统

同模式 A，但使用 `VortexTracker`（匈牙利算法）。

### 模式 C：复合特征分析（参考冷涡）
适用于：需要多个场配合判断的系统

`cold_vortex_analysis.py` 自行从数据中识别中心、追踪、配合。

### 模式 D：阈值分析（参考副高）
适用于：不需要追踪，只需判断是否达到阈值

只需新建 `xxx_analysis.py`，不需要追踪器。

---

## 三、修改检查清单

### 新增识别（第一份 Word）
- [ ] `config/settings.py` — WEATHER_SYSTEM_REGISTRY
- [ ] `modules/detection/xxx.py` — 识别器
- [ ] `system_plotter.py` — PLOT_HANDLERS

### 新增追踪+分析（第二份 Word）
- [ ] `config/settings.py` — 追踪参数
- [ ] `modules/tracking/xxx_analysis.py` — 分析流程
- [ ] `modules/tracking/xxx_tracker.py` — 追踪器（模式 D 不需要）
- [ ] `main.py` Step 6 — 加调用
- [ ] `main.py` Step 7 — 传入 generate()
- [ ] `analysis_plotter.py` — 对应层次加绘图
- [ ] `analysis_report.py` — generate 签名 + 三个文字函数
- [ ] 如果追踪器需要 metdig 原始结果 → 确认识别器 `properties["caldata"]`
- [ ] 如果需要实况原始数据 → 确认 run() 接收 `obs_data` 参数
- [ ] 如果需要大模型判断省份 → 在 xxx_analysis.py 中调用 `location_service.get_point_location` 或 `get_line_location`
