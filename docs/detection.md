# 天气系统识别模块 — `modules/detection/`

## 概述

采用插件化设计，通过注册表 + 工厂模式实现天气系统识别器的动态加载。新增天气系统只需添加注册项和识别器文件，无需修改任何框架代码。

## 文件清单

| 文件 | 职责 | 状态 |
|------|------|------|
| `base_detector.py` | 识别器抽象基类 | ✅ |
| `detector_factory.py` | 识别器工厂（动态加载） | ✅ |
| `trough.py` | 高空槽识别器 | ✅ |
| `subtropical_high.py` | 副热带高压识别器 | ✅ |
| `cold_vortex.py` | 冷涡识别器 | ✅ |
| `low_level_vortex.py` | 低空低涡识别器 | ✅ |
| `low_level_jet.py` | 低空急流识别器 | ✅ |

---

## base_detector.py — 抽象基类

所有识别器必须继承 `BaseDetector` 并实现 `detect()` 方法。

### 类属性（子类必须声明）

```python
system_name: str         # 天气系统名称，如 "高空槽"
required_vars: list      # 所需变量列表，如 ["GH"]
```

### `detect(data_dict, level) -> list[dict]`

**参数:**
- `data_dict`: DataManager 返回的数据字典，通过变量名访问数据
  - 预报: `data_dict["GH"]` → xarray.DataArray
  - 实况: `data_dict["HGT"]` → MICAPS14 字典
- `level`: 当前层次

**返回值:** 识别到的天气系统列表，每个元素格式:
```python
{
    "system_name": "高空槽",
    "level": 500,
    "center_lon": 115.0,
    "center_lat": 40.0,
    "geometry": {
        "type": "line",                        # line / polygon / point
        "points": [[lon, lat], ...],           # line 和 polygon
        # 或
        "lon": x, "lat": y, "radius_km": r,   # point
    },
    "properties": { ... },    # 各系统自定义
}
```

### `check_data(data_dict) -> bool`

检查所需变量是否齐全。

### geometry 字段约定

| 类型 | 适用系统 | 格式 |
|------|---------|------|
| `line` | 实况高空槽、副热带高压588线 | `{"type":"line", "points":[[lon,lat],...]}` |
| `point` | 冷涡、低空低涡 | `{"type":"point", "lon":x, "lat":y, "radius_km":r}` |
| `graphy_raw` | 预报高空槽、预报低空急流 | `{"type":"graphy_raw", "graphy": graphy}` |
| `jet_lines` | 实况低空急流 | `{"type":"jet_lines", "lines":[...]}` |
| `polygon` | 预留：闭合区域型系统 | `{"type":"polygon", "points":[[lon,lat],...]}` |

---

## detector_factory.py — 识别器工厂

### 工作原理

1. 构造时读取 `config.settings.WEATHER_SYSTEM_REGISTRY`
2. 对每条注册项，使用 `importlib.import_module()` 动态导入模块
3. 使用 `getattr()` 获取识别器类并实例化
4. 加载失败的识别器会跳过，不影响其他系统

### `detect_all(data_dict, data_type) -> dict`

对给定数据执行所有适用的识别:
1. 检查当前层次是否在识别器的 `levels` 列表中
2. 检查所需变量是否齐全（预报/实况使用不同的变量名）
3. 调用 `detector.detect()` 获取结果

**返回格式:**
```python
{
    "高空槽": [result1, result2, ...],
    "冷涡":  [result1, ...],
}
# 未识别到结果的系统不包含在返回值中
```

---

## trough.py — 高空槽识别器（已实现）

### 预报识别 (`_detect_from_forecast`)

- 输入: `data_dict["GH"]` — xarray.DataArray
- 算法: `metdig.cal.trough()`，参数来自 `config/settings.py`：

```python
TROUGH_RESOLUTION = "low"
TROUGH_SMOOTH_TIMES = 50
TROUGH_MIN_SIZE = 20

- 需要先设置属性: `grd.attrs["var_units"] = "gpm"`, `grd.attrs["var_name"] = "hgt"`
- 输出: `caldata["graphy"]` 是 metdig/meteva 内部 graphy 格式，不应手动拆解。
- 当前预报高空槽不会拆成多条普通 `line`，而是整体保存为一个 `geometry.type="graphy_raw"` 的结果。
- 原始 `caldata` 会保存到 `properties["caldata"]` 中，供后续高空槽追踪使用。

返回格式示例：

```python
{
    "system_name": "高空槽",
    "level": 500,
    "geometry": {
        "type": "graphy_raw",
        "graphy": graphy,
    },
    "properties": {
        "source": "metdig_auto",
        "trough_count": len(graphy.get("features", {})),
        "caldata": caldata,
    },
}

### 实况识别 (`_detect_from_observation`)

- 输入: `data_dict["HGT"]` — MICAPS14 字典
- 提取: `lines_symbol` 中 `linesym_code == 0` 的线即为槽线
- 坐标: `linesym_xyz[i][:, 0:2]` 取 lon/lat

---

## 待实现识别器开发指南

以副热带高压为例:

### 第一步: 编辑 `subtropical_high.py`

```python
class SubtropicalHighDetector(BaseDetector):
    system_name = "副热带高压"
    required_vars = ["GH"]

    def detect(self, data_dict, level):
        data_type = data_dict.get("data_type", "fcst")
        if data_type == "fcst":
            return self._detect_from_forecast(data_dict, level)
        else:
            return self._detect_from_observation(data_dict, level)

    def _detect_from_forecast(self, data_dict, level):
        grd = data_dict["GH"]
        # ... 你的识别算法 ...
        return [{
            "system_name": self.system_name,
            "level": level,
            "geometry": {"type": "line", "points": [...]},
            "center_lon": ...,
            "center_lat": ...,
            "properties": {"ridge_line": ...},
        }]

    def _detect_from_observation(self, data_dict, level):
        hgt_data = data_dict["HGT"]
        # ... 从 MICAPS14 提取 ...
        return [...]
```

当前副热带高压识别的是 500hPa 的 588 等值线，因此结果为线状系统 `line`，不是闭合区域 `polygon`。

### 第二步: 确认注册表已有该系统

`config/settings.py` 中的 `WEATHER_SYSTEM_REGISTRY` 已包含副热带高压，无需额外操作。

### 第三步: 在 system_plotter.py 中实现绘图函数

见 [visualization.md](visualization.md)。

---

## 注册表结构

```python
# config/settings.py
WEATHER_SYSTEM_REGISTRY = {
    "系统名称": {
        "levels":         [500],              # 适用层次
        "required_vars":  ["GH"],             # 通用变量名
        "detector_class": "ClassName",        # 识别器类名
        "module":         "module_file",      # 模块文件名（不含.py）
        "description":    "说明文字",
        "fcst_vars":      ["GH"],             # 预报数据中的变量名
        "obs_vars":       ["HGT"],            # 实况数据中的变量名
    },
}
```

---

## 注意事项

1. **graphy 数据不可拆解**: `metdig.cal.trough()` 返回的 `caldata["graphy"]` 是 meteva 内部格式，不能用 `np.array()` 拆解后按索引取值，否则会报 `too many indices for array` 错误。必须原样存储，绘图时传给 `meb.add_solid_lines()`。详见 [known_issues.md](known_issues.md) 第 2 条。

2. **预报和实况使用不同变量名**: 注册表中 `fcst_vars` 和 `obs_vars` 区分了预报和实况的变量名（如 GH vs HGT）。`DetectorFactory.detect_all()` 根据 `data_type` 选择检查哪一组变量。新增天气系统时务必同时填写两组变量名。

3. **识别器 detect() 必须区分 data_type**: 因为预报数据是 xarray.DataArray，实况数据是 dict，`detect()` 方法内部必须根据 `data_dict["data_type"]` 分派到不同处理分支。参考 `trough.py` 的 `_detect_from_forecast` 和 `_detect_from_observation` 模式。

4. **metdig 属性要求**: 调用 `metdig.cal` 的识别算法前，必须手动设置 `grd.attrs["var_units"]` 和 `grd.attrs["var_name"]`，否则 metdig 可能报错或返回空结果。

5. **实况识别是提取而非算法**: MICAPS14 是人工分析数据，已包含标注好的天气系统（槽线、高低压中心等）。实况"识别"实际上是从数据字典中提取已标注的信息，不需要运行识别算法。
