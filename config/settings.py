"""
全局配置文件
============
集中管理所有路径、参数、天气系统注册表等配置。
其他模块一律从此处读取配置，不硬编码任何路径或参数。

修改指南:
    - 部署到新环境时，只需修改 MICAPS4_ROOT 和 MICAPS14_ROOT 两个路径
    - 新增天气系统时，只需在 WEATHER_SYSTEM_REGISTRY 中添加注册项
"""
import os
from dataclasses import dataclass
from typing import Dict, Tuple, List

# ============================================================
# 路径配置
# ============================================================
BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# MICAPS4 预报数据根目录（请修改为实际路径）
MICAPS4_ROOT = r"D:\zzq\Desktop\ZZQ\气象工作\3 天气系统识别\data\micaps4"

# MICAPS14 实况数据根目录（请修改为实际路径）
MICAPS14_ROOT = r"D:\zzq\Desktop\ZZQ\气象工作\3 天气系统识别\data\测试\M4"

# 输出目录
OUTPUT_DIR = os.path.join(BASE_DIR, "output")
FIGURE_DIR = os.path.join(OUTPUT_DIR, "figures")
REPORT_DIR = os.path.join(OUTPUT_DIR, "reports")

# ============================================================
# 数据配置
# ============================================================
# MICAPS4 预报数据：变量 -> 可用层次列表
MICAPS4_VARIABLES = {
    "GH": [500, 700, 850, 925],
    "T":  [500, 700, 850, 925],
    "U":  [500, 700, 850, 925],
    "V":  [500, 700, 850, 925],
}

# MICAPS4 预报模式名称
MICAPS4_MODEL = "ECWMF"

# 预报时效列表（小时），含起报时刻
FORECAST_HOURS = list(range(0, 13, 3))  # [0, 3, 6, 9, 12]

# MICAPS14 实况数据：变量 -> 可用层次列表
MICAPS14_VARIABLES = {
    "HGT": [500, 700, 850],
    "TMP": [500, 700, 850],
}

# 起报时刻判断阈值（小时）
# 当前小时 < 该值 → 用08时起报；>= 该值 → 用20时起报
INIT_HOUR_THRESHOLD = 20

# 需要出图的层次列表
PLOT_LEVELS = [500, 700, 850]

# MICAPS4 高度场等值线配置（按层次区分）
CONTOUR_LEVELS = {
    500: list(range(500, 601, 4)),   # 500hPa: 500~600, 间隔4 (单位: 10gpm)
    700: list(range(280, 341, 4)),   # 700hPa: 280~340, 间隔4
    850: list(range(120, 171, 4)),   # 850hPa: 120~170, 间隔4
}

# 数据平滑参数（按用途分离，谁使用谁平滑）
# 平滑策略约定:
#   - Micaps4Reader.read() 默认不平滑，返回原始格网数据
#   - 绘图模块在绘制前用 SMOOTH_POINTS_PLOT 平滑（让等值线更顺）
#   - 识别模块在识别前用 SMOOTH_POINTS_DETECT 平滑（抑制噪声中心）
#   两者互不叠加。修改任一数值只影响对应环节。
# 注意: 数值越大平滑越强。当前 DETECT=50 平滑强度远大于 PLOT=10，
#       会抹掉较小尺度的槽线/低涡，如发现漏报小系统，优先调小此值验证。
SMOOTH_POINTS_PLOT = 15     # 绘图用平滑
SMOOTH_POINTS_DETECT = 10   # 识别用平滑

# ============================================================
# 可视化配置
# ============================================================
@dataclass
class MapConfig:
    """地图范围和可视化参数"""
    lon_min: float = 95.0
    lon_max: float = 135.0
    lat_min: float = 20.0
    lat_max: float = 55.0
    dpi: int = 150
    figsize: Tuple[float, float] = (12, 9)
    # 天津坐标（用于后续影响判断和标注）
    tianjin_lon: float = 117.2
    tianjin_lat: float = 39.13

    @property
    def extent(self) -> list:
        """返回 [lon_min, lon_max, lat_min, lat_max] 格式"""
        return [self.lon_min, self.lon_max, self.lat_min, self.lat_max]

MAP_CONFIG = MapConfig()

# 天津影响判断区域（用于追踪模块判断槽线是否影响天津）
TIANJIN_RANGE = {
    "lon_min": 116,
    "lon_max": 118,
    "lat_min": 38,
    "lat_max": 40,
}

# 风场绘图参数
WIND_BARB_SKIP = 8       # 风向杆采样间隔（预报格点用）
WIND_BARB_LENGTH = 6     # 风向杆长度
WIND_BARB_LINEWIDTH = 0.6
WIND_BARB_COLOR = "black"
WIND_BARB_INCREMENTS = {"half": 2, "full": 4, "flag": 20}  # 短横2m/s, 长横4m/s, 三角20m/s

# 实况站点风羽参数（MDFS 站点数据）
WIND_BARB_SKIP_OBS = 1   # 站点抽稀：1=全部绘制，2=每隔1站绘制

# ============================================================
# 天气系统识别注册表（插件化设计）
# ============================================================
# 扩展方式:
#   1. 在此字典中新增一条注册项
#   2. 在 modules/detection/ 下新建对应模块文件，继承 BaseDetector
#   3. 在 modules/visualization/system_plotter.py 的 PLOT_HANDLERS 中注册绘图函数
#   无需修改 main.py、detector_factory.py、data_manager.py 等其他文件
#
# 各字段说明:
#   levels:         在哪些层次上执行识别
#   required_vars:  识别所需的变量名（对应 MICAPS4_VARIABLES 或 MICAPS14_VARIABLES 的 key）
#   detector_class: 识别器类名
#   module:         模块文件名（不含 .py）
#   description:    简要说明
#   fcst_vars:      预报数据中对应的变量名
#   obs_vars:       实况数据中对应的变量名

# ============================================================
# 天气系统识别算法参数
# ============================================================
# 高空槽识别参数
TROUGH_RESOLUTION = "low"
TROUGH_SMOOTH_TIMES = 35 # metdig内部平滑
TROUGH_MIN_SIZE = 20 

# 低空低涡/冷涡 高低压中心识别（暂无额外参数）

# 低空急流识别参数
JET_RESOLUTION = "low"
JET_SMOOTH_TIMES = 5
JET_MIN_SIZE = 100
JET_MIN_SPEED = 12
JET_ONLY_SOUTH = False

# 槽线追踪配置
TROUGH_TRACK_DISTANCE_MAX = 250          # 追踪匹配最大距离(km)，超过视为不同槽线
TROUGH_TRACK_SIMILARITY_THRESHOLD = 0.4  # 追踪相似度阈值
TROUGH_MATCH_DISTANCE_THRESHOLD = 200    # 实况-预报匹配距离阈值(km)

# 低涡追踪配置
VORTEX_TRACK_DISTANCE_MAX = 300          # 追踪匹配最大距离(km)
VORTEX_TRACK_MAX_SPEED = 60.0            # 最大移动速度(km/h)
VORTEX_MATCH_DISTANCE_THRESHOLD = 300    # 实况-预报匹配距离阈值(km)
VORTEX_TIANJIN_IMPACT_DISTANCE = 150     # 天津影响缓冲区距离(km)

# 冷涡追踪配置
COLD_VORTEX_COUPLING_DISTANCE = 300      # 低压-冷中心配合距离(km)
COLD_VORTEX_TRACK_DISTANCE_MAX = 300     # 追踪最大距离(km)
COLD_VORTEX_MATCH_DISTANCE = 200         # 实况-预报匹配距离(km)

# 副热带高压分析配置
SUBTROPICAL_HIGH_LAT_THRESHOLD = 36.0    # 影响天津的纬度阈值（°N）
SUBTROPICAL_HIGH_LAT_THRESHOLD = 36.0    # 影响天津的纬度阈值（°N）
# 副高影响天津的经度窗口：只统计该经度范围内的 588 线最北纬度，
# 避免远离天津的副高西段（如 105°E 一带）北抬被误判为影响天津。
# 天津约 117.2°E，窗口取其两侧若干度。
SUBTROPICAL_HIGH_LON_MIN = 110.0
SUBTROPICAL_HIGH_LON_MAX = 122.0

# 切变线识别参数
SHEAR_RESOLUTION = "low"
SHEAR_SMOOTH_TIMES = 0       # shear 默认 0，先按默认
SHEAR_MIN_SIZE = 200         # 文档示例用 200，识别太多/太碎就调大

# 切变线追踪配置（阶段二用，先一起放进来）
SHEAR_TRACK_DISTANCE_MAX = 250
SHEAR_TRACK_SIMILARITY_THRESHOLD = 0.4
SHEAR_MATCH_DISTANCE_THRESHOLD = 200


# 冷涡分类区域
COLD_VORTEX_TYPES = {
    "东北冷涡": {"lon_range": [115, 140], "lat_range": [41, 55]},
    "蒙古冷涡": {"lon_range": [95, 120], "lat_range": [39, 55]},
}

# 冷涡影响天津判断区域（大范围）
COLD_VORTEX_IMPACT_REGION = {
    "lon_min": 95,
    "lon_max": 140,
    "lat_min": 39,
    "lat_max": 55,
}

WEATHER_SYSTEM_REGISTRY: Dict[str, dict] = {
    "高空槽": {
        "levels": [500],
        "required_vars": ["GH"],
        "detector_class": "TroughDetector",
        "module": "trough",
        "description": "500hPa高空槽识别",
        "fcst_vars": ["GH"],
        "obs_vars": ["HGT"],
    },
    "副热带高压": {
        "levels": [500],
        "required_vars": ["GH"],
        "detector_class": "SubtropicalHighDetector",
        "module": "subtropical_high",
        "description": "500hPa副热带高压识别",
        "fcst_vars": ["GH"],
        "obs_vars": ["HGT"],
    },
    "冷涡": {
        "levels": [500],
        "required_vars": ["GH", "T"],
        "detector_class": "ColdVortexDetector",
        "module": "cold_vortex",
        "description": "500hPa冷涡识别",
        "fcst_vars": ["GH", "T"],
        "obs_vars": ["HGT", "TMP"],
    },
    "低空低涡": {
        "levels": [700, 850],
        "required_vars": ["GH"],
        "detector_class": "LowLevelVortexDetector",
        "module": "low_level_vortex",
        "description": "700hPa/850hPa低空低涡识别",
        "fcst_vars": ["GH"],
        "obs_vars": ["HGT"],
    },
        "低空急流": {
        "levels": [850],
        "required_vars": ["U", "V"],
        "detector_class": "LowLevelJetDetector",
        "module": "low_level_jet",
        "description": "850hPa低空急流识别",
        "fcst_vars": ["U", "V"],
        "obs_vars": ["HGT"],
    },
    "切变线": {
    "levels": [700, 850],
    "required_vars": ["U", "V"],
    "detector_class": "ShearLineDetector",
    "module": "shear_line",
    "description": "700/850hPa切变线识别",
    "fcst_vars": ["U", "V"],
    "obs_vars": ["HGT"],
},
}

# ============================================================
# Word 报告配置
# ============================================================
@dataclass
class ReportConfig:
    """Word报告参数"""
    image_width_inches: float = 3.0   # 单张图片宽度（两张并排）
    image_height_inches: float = 2.8

REPORT_CONFIG = ReportConfig()

# ============================================================
# 大模型配置
# ============================================================
# 安全要求: API Key 一律从环境变量读取，禁止硬编码到代码中。
# 配置方式:
#   Windows (PowerShell):  $env:DASHSCOPE_API_KEY = "sk-xxx"
#   Windows (永久):        系统设置 → 环境变量 → 新建 DASHSCOPE_API_KEY
#   Linux/macOS:           export DASHSCOPE_API_KEY="sk-xxx"
# 注意: 旧版本曾将真实 Key 写死在此文件并随工程分发，该 Key 视为已泄露，
#       必须在 DashScope 控制台吊销后更换新 Key。
LLM_API_KEY = os.environ.get("DASHSCOPE_API_KEY", "")
LLM_BASE_URL = "https://dashscope.aliyuncs.com/compatible-mode/v1"
LLM_MODEL = "qwen3.6-plus"
LLM_ENABLED = True    # 设为 False 可关闭大模型，使用坐标代替省份
LLM_TIMEOUT_SECONDS = 10   # 单次 API 调用超时（秒），防止网络问题卡死主流程

# ============================================================
# 后续扩展配置（预留）
# ============================================================
@dataclass
class TrackingConfig:
    """天气系统追踪参数"""
    max_distance_km: float = 500.0
    tianjin_radius_km: float = 800.0

@dataclass
class LLMConfig:
    """大模型接入配置"""
    api_url: str = ""
    api_key: str = ""
    model_name: str = ""
    max_tokens: int = 2000
    prompt_template: str = ""

TRACKING_CONFIG = TrackingConfig()
LLM_CONFIG = LLMConfig()
