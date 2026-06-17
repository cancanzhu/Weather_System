# 数据输入输出模块 — `modules/data_io/`

## 概述

负责用户时间输入、数据文件路径构建、MICAPS4/MICAPS14 数据读取，以及将读取结果组织成统一格式供下游模块使用。

## 文件清单

| 文件 | 职责 |
|------|------|
| `time_input.py` | 终端时间输入 + 起报时刻判断 |
| `micaps4_reader.py` | MICAPS4 格网数据读取 |
| `micaps14_reader.py` | MICAPS14 等值线数据读取 |
| `data_manager.py` | 数据调度管理器（核心协调者） |

辅助工具 `utils/path_builder.py` 负责构建文件路径。

---

## time_input.py

### `get_user_time() -> datetime`

- 终端交互，提示用户输入 `年-月-日-时-分` 格式时间
- 解析失败时循环重试
- 返回 `datetime` 对象

### `determine_init_hour(current_time) -> int`

- `hour < 20` → 返回 `8`
- `hour >= 20` → 返回 `20`
- 阈值由 `config.settings.INIT_HOUR_THRESHOLD` 控制

---

## micaps4_reader.py

### `Micaps4Reader.read(filepath, smooth=True, smooth_points=5) -> xarray.DataArray | None`

底层调用 `meteva.base.read_griddata_from_micaps4(filepath)`。

**返回的 DataArray 结构:**
```
维度: (member=1, level=1, time=1, dtime=1, lat=N, lon=M)
坐标: grd['lon'].values → 1D 经度数组, shape=(M,)
      grd['lat'].values → 1D 纬度数组, shape=(N,)
数据: grd.squeeze().values → 2D numpy 数组, shape=(N, M)
```

**平滑处理:** 当前代码中 `Micaps4Reader.read()` 默认 `smooth=True, smooth_points=5`，因此读取 MICAPS4 文件时会先执行一次 `meb.comp.smooth(grd, 5)`。随后绘图模块和识别模块还会分别使用 `SMOOTH_POINTS_PLOT`、`SMOOTH_POINTS_DETECT` 再次平滑，因此当前流程可能存在二次平滑现象。

当前实际调用链为：

```python
DataManager.load_forecast_data()
    └── Micaps4Reader.read(filepath)
            └── 默认 smooth=True, smooth_points=5
            
如后续希望“读取阶段只读取原始数据”，需要修改 data_manager.py 或 micaps4_reader.py

**失败处理:** 文件不存在或读取异常时返回 `None`，不抛出异常。

---

## micaps14_reader.py

### `Micaps14Reader.read(filepath) -> dict | None`

底层调用 `meteva.base.read_micaps14(filepath)`。

**返回的字典结构:**
```python
{
    "lines": {
        "line_xyz":       [ndarray, ...],  # 每条线坐标, shape=(n,3), [lon,lat,z]
        "line_label":     [str, ...],       # 标签文字
        "line_label_num": [int, ...],       # 标签数量
        "line_label_xyz": [ndarray, ...],   # 标签位置
    },
    "symbols": {
        "symbol_code": [int, ...],          # 60=H, 61=L, 62=W, 63=C
        "symbol_xyz":  [ndarray, ...],      # [lon, lat]
    },
    "lines_symbol": {
        "linesym_code": [int, ...],         # 0=槽线
        "linesym_xyz":  [ndarray, ...],     # shape=(n,3), 取 [:, 0:2]
    },
}
```

**注意:** MICAPS14 是矢量等值线数据，与 MICAPS4 的格网数据本质不同。下游模块需要根据 `data_type` 区分处理方式。

---

## data_manager.py

### `DataManager(current_time, init_hour)`

核心数据调度器，根据时间参数批量读取所有数据。

### `load_forecast_data() -> dict`

遍历: `预报时效 [0,3,6,9,12] × 层次 [500,700,850] × 变量 [GH,T,U,V]`

**返回格式:**
```python
{
    ("2025060108(+000h)", 500): {
        "GH": xarray.DataArray,      # 高度场
        "T":  xarray.DataArray,      # 温度场
        "U":  xarray.DataArray,      # U 风场
        "V":  xarray.DataArray,      # V 风场
        "time": datetime,
        "level": 500,
        "data_type": "fcst",
        "init_time": datetime,
        "forecast_hour": 0,
    },
    ...
}
```

缺失的变量不会出现在字典中（而非设为 None）。

### `load_observation_data() -> dict`

遍历: `层次 [500,700,850] × 变量 [HGT,TMP]`

**返回格式:**
```python
{
    ("2025060108(实况)", 500): {
        "HGT": dict,      # MICAPS14 高度场字典
        "TMP": dict,       # MICAPS14 温度场字典
        "time": datetime,
        "level": 500,
        "data_type": "obs",
    },
    ...
}
```

---

## utils/path_builder.py

### `build_micaps4_path(root, model, variable, level, init_time, forecast_hour) -> str`

```
路径: {root}/{YYYYMMDD}/{model}/{variable}/{level}/{YYMMDDhh}.{FFF}
示例: micaps4/20250601/ECWMF/GH/500/25060108.003
```

### `build_micaps14_path(root, variable, level, obs_time) -> str`

```
路径: {root}/{YYYYMMDD}/UPPER_AIR/MANUAL_ANALYSIS/{variable}/{level}/{YYYYMMDDHHmmss}.000
示例: data/20250601/UPPER_AIR/MANUAL_ANALYSIS/HGT/500/20250601080000.000
```

---

## 数据流向

```
time_input         path_builder
    │                   │
    ▼                   ▼
DataManager ──► Micaps4Reader  ──► xarray.DataArray (预报)
            ──► Micaps14Reader ──► dict             (实况)
                    │
                    ▼
            统一字典结构 → detection / visualization / report
```

---

## 注意事项

1. **numpy 兼容补丁必须加**: `micaps4_reader.py` 和 `micaps14_reader.py` 中在 `import meteva` 之前必须添加 `np.float = float` 等兼容补丁，否则 numpy >= 1.24 环境下会报错。详见 [known_issues.md](known_issues.md) 第 1 条。

2. **MICAPS4 和 MICAPS14 返回类型完全不同**: MICAPS4 返回 xarray.DataArray，MICAPS14 返回 dict。下游模块必须根据 `data_dict["data_type"]`（"obs" 或 "fcst"）区分处理方式，不能混用。

3. **TMP 实况数据可能不存在**: `meb.read_micaps14()` 对 TMP 文件可能返回 None，这不影响当前功能（仅高度场参与识别）。后续实现冷涡识别时需要注意 TMP 数据可用性。

4. **MICAPS4 数据范围**: 实测 GH 数据覆盖范围为 105-135°E, 20-50°N，`MapConfig` 设置需与此匹配，否则等值线无法填满地图。

5. **MICAPS14 路径结构**: 路径中有 `{YYYYMMDD}/UPPER_AIR/MANUAL_ANALYSIS/` 这一层目录，如果数据目录结构不同需要修改 `utils/path_builder.py` 中的 `build_micaps14_path()`。
