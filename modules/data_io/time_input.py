"""
时间输入模块
============
从终端获取用户输入的当前时间，并据此判断使用哪个起报时刻。

起报时刻判断规则:
    - 当前小时 < 20  → 使用 08 时起报
    - 当前小时 >= 20 → 使用 20 时起报
"""
from datetime import datetime
import logging

logger = logging.getLogger(__name__)


def get_user_time() -> datetime:
    """
    从终端获取用户输入的当前时间。

    输入格式: 年-月-日-时-分（例: 2025-06-01-14-30）
    输入错误时会循环提示重新输入，不会崩溃。

    Returns:
        解析后的 datetime 对象
    """
    while True:
        time_str = input(
            "请输入当前时间（格式: 年-月-日-时-分，例: 2025-06-01-14-30）: "
        ).strip()
        try:
            current_time = datetime.strptime(time_str, "%Y-%m-%d-%H-%M")
            logger.info(f"输入时间解析成功: {current_time}")
            return current_time
        except ValueError:
            print(f"  时间格式错误: '{time_str}'，请按 年-月-日-时-分 格式重新输入。")


def determine_init_hour(current_time: datetime) -> int:
    """
    根据当前时间判断使用哪个起报时刻。

    Args:
        current_time: 当前时间

    Returns:
        起报时刻 (8 或 20)
    """
    from config.settings import INIT_HOUR_THRESHOLD

    if current_time.hour < INIT_HOUR_THRESHOLD:
        return 8
    else:
        return 20
