"""
大模型分析器（后续实现）
========================
调用大模型 API，根据天气系统识别和追踪结果生成分析文字。

工作流:
    1. 调用 data_serializer 将结构化数据转为 JSON
    2. 拼接 prompt 模板 + JSON 数据
    3. 调用大模型 API
    4. 解析返回结果

Prompt 模板应包含:
    - 角色设定（天气预报分析师）
    - 输出格式要求（按模板描述影响天津的天气系统）
    - 需要描述的要点:
        - 系统位置、移动方向、强度变化
        - 对天津的影响时间和方式
        - 未来 12h 的演变趋势
"""
import logging
from datetime import datetime
from typing import List, Dict, Any

from modules.llm.data_serializer import serialize_for_llm

logger = logging.getLogger(__name__)


class LLMAnalyzer:
    """大模型分析器（待实现）"""

    def __init__(self, llm_config):
        self.config = llm_config

    def analyze(
        self,
        tracking_results: List[Dict[str, Any]],
        current_time: datetime,
    ) -> str:
        """
        TODO: 实现大模型调用

        步骤:
            1. data_json = serialize_for_llm(tracking_results, current_time)
            2. prompt = self.config.prompt_template.format(data=data_json)
            3. response = requests.post(self.config.api_url, ...)
            4. return response.text
        """
        logger.info("大模型分析器尚未实现")
        return ""
