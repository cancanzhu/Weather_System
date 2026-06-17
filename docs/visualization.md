# 可视化模块 — `modules/visualization/`

## 三个文件

| 文件 | 用途 | 对应 Word |
|------|------|----------|
| `field_plotter.py` | 气象要素场（等值线+风场） | 第一份 |
| `system_plotter.py` | 天气系统识别结果叠加 | 第一份 |
| `analysis_plotter.py` | 实况分析图 + 预报追踪图 | 第二份 |

---

## field_plotter.py

- 预报: `ax.contour` + `ax.barbs`，588线红色加粗
- 实况: `meb.add_solid_lines` + 符号标注，588线红色加粗
- 标签: 取线上在地图范围内的中间点

## system_plotter.py

`PLOT_HANDLERS` 注册表:
```
高空槽 → 棕色线(graphy_raw用meb方法, line用ax.plot)
副热带高压 → 红色粗线
冷涡 → 蓝色"C"
低空低涡 → 红色"L"（第一份 Word 的系统识别图，带范围过滤）
低空急流 → 红色箭头(meb.add_curved_arrows)
```

## analysis_plotter.py

### `plot_obs_analysis` — 实况分析图
等值线底图 + 按层次叠加天气系统:
- 500: 槽线(棕色) + 副高588(红色,仅影响时) + 冷涡(蓝色C)
- 700: 低涡(红色D)
- 850: 低涡(红色D) + 急流(红色箭头)

### `plot_fcst_tracking` — 预报追踪图
签名: `plot_fcst_tracking(tracker, tianjin_ids, level, time_label, cold_vortex_tracks=None, cold_vortex_impact_ids=None)`

地图底图（无等值线）+ 按层次绘制轨迹:
- 500: `_draw_trough_tracks`(棕色/灰色) + `_draw_cold_vortex_tracks`(蓝色/灰色)
- 700/850: `_draw_vortex_tracks`(红色/灰色)

所有轨迹: 影响天津→彩色, 不影响→灰色, 透明度递减, 时间标签

---

## 注意事项
1. 实况等值线必须用 `meb.add_solid_lines()`，不能用 `ax.plot()`
2. `ax.text()` 必须范围过滤或 `clip_on=True`
3. 副高 588 线仅 `max_lat >= 36°N` 时绘制
4. 无轨迹时用 dummy 线触发布局
