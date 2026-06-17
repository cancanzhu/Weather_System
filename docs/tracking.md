# 追踪模块 — `modules/tracking/`

## 概述

负责天气系统的跨时次追踪和影响分析。每个天气系统一个分析文件，main.py 只调用一行。

```
main.py Step 6:
  trough_analysis.run(...)             → 3行  高空槽
  vortex_analysis.run(...)             → 3行  低涡
  cold_vortex_analysis.run(...)        → 3行  冷涡
  subtropical_high_analysis.run(...)   → 2行  副高
```

## 四种分析模式

| 系统 | 追踪方式 | 影响判断 | 特殊逻辑 |
|------|---------|---------|---------|
| 高空槽 | 贪心匹配（线特征） | 点在天津矩形内 | 前倾/后倾 |
| 低涡 | 匈牙利算法（点特征） | 150km缓冲区 | 700/850独立追踪 |
| 冷涡 | 分别追踪低压和冷中心→配合 | 大区域(105-140°E,39-55°N) | 东北/蒙古分类 |
| 副高 | 不追踪 | 纬度≥36°N | 找首次影响时次 |

---

## trough_analysis.py — 高空槽

```python
trough_analyses, trough_tracker, tianjin_track_ids = trough_analysis.run(
    forecast_data, fcst_detection_results, obs_detection_results)
```

流程: 追踪→影响判断→实况匹配→前倾/后倾→移动方向→影响时间

返回 `trough_analyses`:
```python
[{"trough_num", "track_id", "location", "tilt_type", "from_dir", "to_dir", "impact_time", "is_new"}]
```

caldata 来源: `fcst_detection_results[(tl,500)]["高空槽"][0]["properties"]["caldata"]`

---

## vortex_analysis.py — 低涡

```python
vortex_analyses, vortex_trackers, vortex_tianjin_ids = vortex_analysis.run(
    forecast_data, fcst_detection_results, obs_detection_results)
```

在 700hPa 和 850hPa 独立追踪。使用匈牙利算法+速度约束。

返回:
- `vortex_trackers`: `{700: VortexTracker, 850: VortexTracker}`
- `vortex_tianjin_ids`: `{700: [ids], 850: [ids]}`
- `vortex_analyses`: `[{"vortex_num", "level", "location", "strength", "quadrant", "from_dir", "to_dir", "impact_time", "is_new"}]`

---

## cold_vortex_analysis.py — 冷涡

```python
cold_vortex_analyses, cold_vortex_tracks, cold_vortex_impact_ids = \
    cold_vortex_analysis.run(
        forecast_data, fcst_detection_results, obs_detection_results, obs_data)
```

**注意**: 比其他分析多一个 `obs_data` 参数。

流程:
1. 从预报 GH 识别低压中心，从 T 识别冷中心
2. 分别用 VortexTracker 追踪
3. 每个时次配合判断: 低压+冷中心距离≤300km → 冷涡
4. 分类: 东北冷涡(115-140°E,41-55°N) / 蒙古冷涡(105-120°E,39-50°N)
5. 影响判断: 大区域(105-140°E,39-55°N)

返回 `cold_vortex_analyses`:
```python
[{"cv_num", "vortex_id", "vortex_type", "strength", "quadrant", "from_dir", "to_dir", "impact_time", "is_new"}]
```

---

## subtropical_high_analysis.py — 副高

```python
subtropical_high_analyses = subtropical_high_analysis.run(
    forecast_data, fcst_detection_results, obs_detection_results)
```

**不需要追踪器**，只做纬度阈值判断。

返回:
```python
[
    {"type": "obs", "is_affecting": bool, "max_latitude": float, "description": str},
    {"type": "fcst", "is_affecting": bool, "first_affecting_time": int, "impact_time": str, "description": str},
]
```

只有 `is_affecting=True` 时才在报告中显示。

---

## 追踪器详解

### TroughTracker（贪心匹配）
- 相似度 = 距离(0.5) + 长度(0.2) + 方向(0.2) + 强度(0.1)
- 阈值: 距离250km, 相似度0.4

### VortexTracker（匈牙利算法）
- scipy.optimize.linear_sum_assignment 全局最优
- 约束: 距离300km, 速度60km/h
- 天津影响: 点到矩形距离≤150km

---

## 注意事项

1. **caldata 必须从识别器传递**: 追踪器需要 metdig 原始返回值，存在 `properties["caldata"]`
2. **冷涡需要 obs_data**: 因为要从实况 HGT symbols 提取低压中心(code==61)做配合
3. **不同系统不要强行统一**: 追踪逻辑差异大，各自文件独立实现
4. **副高不需要追踪**: 只判断纬度，不影响时不显示
