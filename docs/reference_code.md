# 原始参考代码 — `docs/reference_code.md`

本文档保存用户提供的原始代码片段，是整个框架设计的基础。
新接手的开发者（包括 AI）可以参考这些代码理解数据格式和绑图方式。

---

## 1. MICAPS4 数据读取 + 高空槽识别 + 可视化

这是整个框架的核心参考。展示了预报数据的完整处理流程。

```python
import meteva.base as meb
import metdig.cal as mdgcal
import numpy as np
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['SimHei']
plt.rcParams['axes.unicode_minus']=False
from meteva.base.tool.plot_tools import add_china_map_2basemap
import pandas as pd
from metdig.products import diag_identify as draw_identify


# 读取MICAPS 4数据
filename = r"D:\zzq\Desktop\天气系统识别\data\micaps4\20250601\ECWMF\GH\500\25060108.000"
grd = meb.read_griddata_from_micaps4(filename)
print(f"数据形状: {grd.shape}")
print(f"数据维度: {grd.dims}")
print(f"数据范围: {grd.min().values:.1f} - {grd.max().values:.1f} gpm")

grd = meb.comp.smooth(grd,5)

# 添加 metdig 需要的属性
grd.attrs['var_units'] = 'gpm'
grd.attrs['var_name'] = 'hgt'

# 读取风场数据
filename_u = r"D:\zzq\Desktop\天气系统识别\data\micaps4\20250601\ECWMF\U\500\25060108.000"
filename_v = r"D:\zzq\Desktop\天气系统识别\data\micaps4\20250601\ECWMF\V\500\25060108.000"
u_grd = meb.read_griddata_from_micaps4(filename_u)
v_grd = meb.read_griddata_from_micaps4(filename_v)

# 提取 2D 数据
u_2d = u_grd.squeeze()
v_2d = v_grd.squeeze()

map_extend = [70,140,15,55]
axs = meb.creat_axs(1, map_extend, sup_title="2025年6月1日20时500hPa高度场",
                    sup_fontsize=8, add_minmap=False, add_worldmap=False,
                    width=12)

# 提取 2D 数据（去掉多余维度）
grd_2d = grd.squeeze()

# 等值线
levels = list(range(550, 601, 4))
cs = axs[0].contour(grd_2d['lon'].values, grd_2d['lat'].values, grd_2d.values,
                    levels=levels, colors='black', linewidths=0.8)
axs[0].clabel(cs, fmt='%d', fontsize=8)

# 槽线识别
caldata = mdgcal.trough(grd, resolution="low", smooth_times=50, min_size=20)
graphy = caldata['graphy']

# 槽线绑制（使用 meteva 原生方法）
meb.add_solid_lines(axs[0], graphy, color="brown", linewidth=1.5)

# 风向杆
skip = 8
axs[0].barbs(u_2d['lon'].values[::skip], u_2d['lat'].values[::skip],
             u_2d.values[::skip, ::skip], v_2d.values[::skip, ::skip],
             length=3, linewidth=0.3, color='blue', barbcolor='blue',
             pivot='middle')

plt.show()
```

### 关键要点

1. **读取方式**: `meb.read_griddata_from_micaps4()` 返回 xarray.DataArray
2. **数据维度**: 有多余维度，需要 `.squeeze()` 压缩为 2D
3. **坐标访问**: `grd['lon'].values`, `grd['lat'].values`
4. **平滑处理**: `meb.comp.smooth(grd, 5)` 在绘图和识别前执行
5. **metdig 要求**: 必须设置 `grd.attrs['var_units']` 和 `grd.attrs['var_name']`
6. **槽线识别**: `mdgcal.trough(grd, ...)` 输入是未 squeeze 的原始 DataArray
7. **graphy 不可拆解**: `caldata['graphy']` 必须原样传给 `meb.add_solid_lines()`
8. **底图创建**: `meb.creat_axs(1, map_extend, ...)` 返回 axes 列表

---

## 2. MICAPS14 数据读取 + 实况可视化

展示了实况数据的完整处理流程。MICAPS14 是矢量等值线格式，与 MICAPS4 的格网格式本质不同。

```python
import meteva.base as meb
import numpy as np
import matplotlib.pyplot as plt
plt.rcParams['font.sans-serif']=['SimHei']
plt.rcParams['axes.unicode_minus']=False

# 读取micaps14格式文件
file_path = r"D:\...\HGT\500\20250804080000.000"
graphy_data = meb.read_micaps14(file_path)

# 创建底图
map_extend = [70,140,15,55]
axs = meb.creat_axs(1, map_extend, sup_title="2025年6月1日500hPa形势场",
                    sup_fontsize=8, add_minmap=False, add_worldmap=False,
                    width=12)

# 绘制等高线
lines = graphy_data.get("lines")
if lines is not None:
    for i in range(len(lines["line_xyz"])):
        line_xyz = lines["line_xyz"][i]
        label = lines["line_label"][i]
        axs[0].plot(line_xyz[:, 0], line_xyz[:, 1], 'b-', linewidth=0.5)
        if lines["line_label_num"][i] > 0:
            label_xyz = lines["line_label_xyz"][i]
            axs[0].text(label_xyz[0, 0], label_xyz[0, 1], label,
                       fontsize=8, color='b', ha='center', va='center',
                       bbox=dict(facecolor='white', edgecolor='none', alpha=0.7, pad=1))

# 绘制符号（H高压/L低压/W暖中心/C冷中心）
symbols = graphy_data.get("symbols")
if symbols is not None:
    symbol_codes = symbols["symbol_code"]
    symbol_xyz = symbols["symbol_xyz"]
    for i, code in enumerate(symbol_codes):
        lon = symbol_xyz[i][0]
        lat = symbol_xyz[i][1]
        if code == 60:    # H 高压
            axs[0].text(lon, lat, 'H', color='blue', fontsize=14,
                       ha='center', va='center', weight='bold', zorder=100)
        elif code == 61:  # L 低压
            axs[0].text(lon, lat, 'L', color='red', fontsize=14,
                       ha='center', va='center', weight='bold', zorder=100)
        elif code == 62:  # W 暖中心
            axs[0].text(lon, lat, 'W', color='red', fontsize=14,
                       ha='center', va='center', weight='bold', zorder=100)
        elif code == 63:  # C 冷中心
            axs[0].text(lon, lat, 'C', color='blue', fontsize=14,
                       ha='center', va='center', weight='bold', zorder=100)

# 绘制槽线（从 lines_symbol 中提取 code=0 的线）
lines_symbol = graphy_data.get("lines_symbol")
if lines_symbol is not None:
    trough_lines = []
    for i in range(len(lines_symbol["linesym_code"])):
        code = lines_symbol["linesym_code"][i]
        if code == 0:  # 槽线
            line_xyz = lines_symbol["linesym_xyz"][i]
            line_points = line_xyz[:, 0:2].tolist()
            trough_lines.append(line_points)
    if len(trough_lines) > 0:
        meb.add_solid_lines(axs[0], trough_lines, color='brown', linewidth=1.5)

plt.show()
```

### 关键要点

1. **读取方式**: `meb.read_micaps14()` 返回 dict（不是 xarray）
2. **三个数据部分**:
   - `"lines"`: 等值线（`line_xyz` 坐标 + `line_label` 标签）
   - `"symbols"`: 符号标注（`symbol_code` + `symbol_xyz`）
   - `"lines_symbol"`: 特殊线符号（`linesym_code` + `linesym_xyz`）
3. **符号代码**: 60=H高压, 61=L低压, 62=W暖中心, 63=C冷中心
4. **槽线代码**: `linesym_code == 0`
5. **坐标格式**: `line_xyz` shape=(n,3)，列为 [lon, lat, z]，取 `[:, 0:2]` 得 lon/lat
6. **框架中的改动**: 原始代码用 `ax.plot()` 画等值线，框架中改为 `meb.add_solid_lines()` 以解决布局问题（见 known_issues.md 第 3 条）

---

## 3. 两种数据格式对比

| 特性 | MICAPS4（预报） | MICAPS14（实况） |
|------|----------------|-----------------|
| 读取函数 | `meb.read_griddata_from_micaps4()` | `meb.read_micaps14()` |
| 返回类型 | `xarray.DataArray` | `dict` |
| 数据形式 | 规则格网（lat × lon 矩阵） | 矢量等值线 + 符号标注 |
| 等值线绘制 | `ax.contour()` | `meb.add_solid_lines()` |
| 识别算法输入 | xarray.DataArray（传给 metdig） | dict（直接提取已标注的系统） |
| 坐标访问 | `grd['lon'].values` | `lines["line_xyz"][:, 0]` |
