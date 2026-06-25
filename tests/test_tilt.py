import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from utils.geo_utils import judge_trough_tilt

def _line(lon, lat_top=45, lat_bot=35, n=11):
    # 一条竖直槽线，固定经度 lon，从 lat_top 到 lat_bot
    import numpy as np
    lats = np.linspace(lat_top, lat_bot, n)
    return [[lon, float(la)] for la in lats]

def test_back_tilt_low_west_of_500():
    # 低层(115)在 500(120)西侧 → 后倾
    assert judge_trough_tilt(_line(120), _line(115)) == "后倾"

def test_front_tilt_low_east_of_500():
    # 低层(125)在 500(120)东侧 → 前倾
    assert judge_trough_tilt(_line(120), _line(125)) == "前倾"

def test_no_lat_overlap_returns_unknown():
    # 500 在 45~40N，低层在 35~30N，纬度不重叠 → 未知
    assert judge_trough_tilt(_line(120, 45, 40), _line(115, 35, 30)) == "未知"

def test_tilted_trough_not_fooled_by_centroid():
    # 关键回归：500 是长斜槽(南段拖到低纬、整体偏西)，低层是北段短槽。
    # 旧版按重心经度会判错；新版在重叠纬度带(40~45)上比较应判对。
    import numpy as np
    # 500槽：从(122,45)斜拉到(110,30)，重心经度被南段拉到~116
    p500 = [[122 - (122-110)*(45-la)/15, float(la)] for la in np.linspace(45,30,16)]
    # 低层槽：40~45N，经度118（在40~45N的500槽经度~120以西）→ 后倾
    plow = [[118.0, float(la)] for la in np.linspace(45,40,6)]
    assert judge_trough_tilt(p500, plow) == "后倾"