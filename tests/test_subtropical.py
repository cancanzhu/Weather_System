import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import numpy as np
from modules.tracking import subtropical_high_analysis as sh

def test_window_filters_far_west_ridge():
    # 588线在105°E北抬到38°N（窗口外），在117°E只到32°N（窗口内）
    # 旧逻辑：全域最北38°N → 误判影响
    # 新逻辑：窗口(110-122)内最北32°N → 不影响
    pts = np.array([[105, 38], [108, 36], [117, 32], [120, 31]], dtype=float)
    max_lat = sh._max_lat_in_lon_window(pts)
    assert abs(max_lat - 32.0) < 1e-6, f"窗口内最北应为32, 实际{max_lat}"
    assert max_lat < sh.SUBTROPICAL_HIGH_LAT_THRESHOLD  # 不影响

def test_window_keeps_near_tianjin_ridge():
    # 117°E北抬到37°N（窗口内）→ 应影响
    pts = np.array([[105, 30], [117, 37], [120, 36]], dtype=float)
    max_lat = sh._max_lat_in_lon_window(pts)
    assert abs(max_lat - 37.0) < 1e-6
    assert max_lat >= sh.SUBTROPICAL_HIGH_LAT_THRESHOLD  # 影响

def test_no_point_in_window_returns_nan():
    # 588线全在窗口外（都在100-108°E）
    pts = np.array([[100, 40], [105, 39], [108, 38]], dtype=float)
    assert np.isnan(sh._max_lat_in_lon_window(pts))