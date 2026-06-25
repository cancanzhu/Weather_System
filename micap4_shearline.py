import os
import meteva.base as meb
import metdig.cal as mdgcal
import numpy as np
import matplotlib.pyplot as plt

# =========================
# 0. matplotlib 设置
# =========================
plt.rcParams['font.sans-serif'] = ['SimHei']   # 显示中文
plt.rcParams['axes.unicode_minus'] = False     # 正常显示负号


# =========================
# 1. 路径与公共参数
# =========================
# 文件目录结构: ...\ECWMF\{要素}\{层次}\{文件名}
#   要素: U / V / GH    层次: 500 / 700 / 850
base_dir  = r"D:\zzq\Desktop\ZZQ\气象工作\3 天气系统识别\data\micaps4\20250601\ECWMF"
file_name = "25060120.003"

# 绘图范围
map_extend = [70, 140, 15, 55]

# 要识别切变线的层次
levels_to_plot = [700, 850]


def get_path(var, level):
    """根据要素名和层次拼出 micaps4 文件路径"""
    return os.path.join(base_dir, var, str(level), file_name)


# =========================
# 2. 单个层次的切变线绘制函数
# =========================
def plot_shear(level, smooth_times=0, min_size=200, skip=8, draw_height=False):
    """
    读取指定层次的 U/V 风场，绘制风向杆并识别、绘制切变线。

    level        : 层次 (700 / 850)
    smooth_times : shear 算法内部对风场的平滑次数，用于过滤小尺度噪音
    min_size     : 按切变线长度(km)过滤掉过小的系统
    skip         : 风向杆抽稀间隔
    draw_height  : 是否叠加该层高度场等值线作为背景(需要对应 GH 文件)
    """
    print("=" * 60)
    print(f"处理 {level}hPa 切变线")
    print("=" * 60)

    # ---- 2.1 读取 U / V 风场 ----
    u_grd = meb.read_griddata_from_micaps4(get_path("U", level))
    v_grd = meb.read_griddata_from_micaps4(get_path("V", level))

    print(f"U风场形状: {u_grd.shape}, V风场形状: {v_grd.shape}")

    # ---- 2.2 设置识别所需的 stda 属性 ----
    # shear 内部会用到 u.stda.level / time / dtime，并以 var_name 判定是否为 stda。
    # 这里显式写入层次坐标和要素属性，保证算法拿到正确的元数据。
    u_grd['level'] = [level]
    v_grd['level'] = [level]
    u_grd.attrs['var_name'] = 'u'
    u_grd.attrs['var_units'] = 'm/s'
    v_grd.attrs['var_name'] = 'v'
    v_grd.attrs['var_units'] = 'm/s'

    # ---- 2.3 压缩成二维(仅用于画风向杆) ----
    u_2d = u_grd.squeeze()
    v_2d = v_grd.squeeze()

    # ---- 2.4 创建底图 ----
    axs = meb.creat_axs(
        1,
        map_extend,
        sup_title=f"2025年6月1日20时 {level}hPa 风场与切变线",
        sup_fontsize=10,
        add_minmap=False,
        add_worldmap=False,
        width=12
    )
    ax = axs[0]

    # ---- 2.5 (可选)叠加高度场等值线作为背景 ----
    if draw_height:
        try:
            h = meb.read_griddata_from_micaps4(get_path("GH", level))
            h = meb.comp.smooth(h, 10)
            h2d = h.squeeze()
            # 不同层次高度值差异很大，这里按数据范围自动确定等值线
            vmin = np.floor(float(h2d.min()) / 4) * 4
            vmax = np.ceil(float(h2d.max()) / 4) * 4
            levs = np.arange(vmin, vmax + 1, 4)
            cs = ax.contour(
                h2d['lon'].values, h2d['lat'].values, h2d.values,
                levels=levs, colors='black', linewidths=0.8
            )
            ax.clabel(cs, fmt='%d', fontsize=8)
            print("高度场背景绘制成功")
        except Exception as e:
            print(f"高度场绘制失败(可忽略): {e}")

    # ---- 2.6 风向杆 ----
    try:
        ax.barbs(
            u_2d['lon'].values[::skip],
            u_2d['lat'].values[::skip],
            u_2d.values[::skip, ::skip],
            v_2d.values[::skip, ::skip],
            length=4,
            linewidth=0.35,
            color='blue',
            barbcolor='blue',
            pivot='middle'
        )
        print("风向杆绘制完成")
    except Exception as e:
        print(f"风向杆绘制失败: {e}")

    # ---- 2.7 切变线识别与绘制 ----
    try:
        caldata = mdgcal.shear(
            u_grd, v_grd,
            resolution="low",
            smooth_times=smooth_times,
            min_size=min_size
        )

        print("切变线识别结果:", type(caldata))
        if caldata is not None:
            # 与 trough 一致，结果通过 'graphy' 给出，可直接用 add_solid_lines 绘制
            meb.add_solid_lines(ax, caldata['graphy'], color="red", linewidth=2.0)
            print(f"{level}hPa 切变线绘制完成")
        else:
            print(f"{level}hPa 未识别到切变线(可调小 min_size 再试)")
    except Exception as e:
        print(f"切变线识别或绘制失败: {e}")

    return ax


# =========================
# 3. 对各层次逐一处理
# =========================
for lev in levels_to_plot:
    plot_shear(
        lev,
        smooth_times=0,    # 如噪音多可适当增大, 如 10~50
        min_size=200,      # 切变线最短长度(km), 想保留更短的系统就调小
        skip=8,            # 风向杆抽稀间隔
        draw_height=False  # 若有对应层 GH 文件, 设为 True 可叠加高度场背景
    )


# =========================
# 4. 显示图像(两张图一起弹出)
# =========================
print("=" * 60)
print("显示图片...")
print("=" * 60)

plt.show()

print("程序结束")