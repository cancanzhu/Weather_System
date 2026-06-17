"""
MDFS 高空站点风场读取器
=======================
读取 MDFS 二进制站点资料文件，提取风向风速要素。

MDFS 高空站点资料二进制结构:
    288 bytes 文件头 (mdfs)
    int32 station_count
    uint16 element_count
    element_count 组:
        uint16 element_id
        uint16 value_type
    station_count 组:
        uint16 station_id_length
        char[] station_id
        float32 lon
        float32 lat
        uint16 value_count
        value_count 组:
            uint16 element_id
            float32 value

已知要素:
    201 = 风向（°）
    203 = 风速（m/s）
"""
import os
import struct
import logging

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)


def wind_dir_speed_to_uv(wind_dir, wind_speed):
    """
    气象风向/风速转 matplotlib barbs 所需 u/v 分量。

    气象风向: 0°=北, 90°=东, 180°=南, 270°=西
    u > 0 向东, v > 0 向北
    """
    rad = np.deg2rad(wind_dir)
    u = -wind_speed * np.sin(rad)
    v = -wind_speed * np.cos(rad)
    return u, v


class MdfsWindReader:
    """MDFS 高空站点风场读取器"""

    @staticmethod
    def read(filepath: str):
        """
        读取 MDFS 高空站点风场文件。

        Returns:
            pandas.DataFrame (lon, lat, wind_dir, wind_speed) 或 None
        """
        if not os.path.exists(filepath):
            logger.debug(f"MDFS 风场文件不存在: {filepath}")
            return None

        try:
            with open(filepath, "rb") as f:
                data = f.read()

            if len(data) < 300:
                logger.warning(f"MDFS 文件过短: {filepath}")
                return None

            if data[:4] != b"mdfs":
                logger.warning(f"文件头不是 mdfs: {filepath}")
                return None

            offset = 288

            station_count = struct.unpack_from("<i", data, offset)[0]
            offset += 4

            element_count = struct.unpack_from("<H", data, offset)[0]
            offset += 2

            elements = []
            for _ in range(element_count):
                element_id, value_type = struct.unpack_from("<HH", data, offset)
                offset += 4
                elements.append((element_id, value_type))

            stations = []
            for _ in range(station_count):
                if offset + 2 > len(data):
                    break

                sid_len = struct.unpack_from("<H", data, offset)[0]
                offset += 2

                station_id = data[offset:offset + sid_len].decode(
                    "ascii", errors="ignore"
                )
                offset += sid_len

                lon, lat = struct.unpack_from("<ff", data, offset)
                offset += 8

                value_count = struct.unpack_from("<H", data, offset)[0]
                offset += 2

                values = {}
                for _ in range(value_count):
                    element_id = struct.unpack_from("<H", data, offset)[0]
                    offset += 2
                    value = struct.unpack_from("<f", data, offset)[0]
                    offset += 4
                    values[element_id] = value

                stations.append({
                    "station_id": station_id,
                    "lon": lon,
                    "lat": lat,
                    "wind_dir": values.get(201, np.nan),
                    "wind_speed": values.get(203, np.nan),
                })

            df = pd.DataFrame(stations)

            if df.empty:
                logger.debug(f"MDFS 风场文件无站点数据: {filepath}")
                return None

            # 过滤无效数据
            df = df.dropna(subset=["lon", "lat", "wind_dir", "wind_speed"])
            df = df[
                (df["wind_dir"] >= 0) & (df["wind_dir"] <= 360) &
                (df["wind_speed"] >= 0)
            ]

            if df.empty:
                return None

            logger.debug(f"MDFS 风场读取成功: {filepath} ({len(df)} 站)")
            return df

        except Exception as e:
            logger.error(f"MDFS 风场读取失败 [{filepath}]: {e}")
            return None
