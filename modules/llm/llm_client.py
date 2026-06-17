"""
大模型 API 客户端
=================
封装大模型 API 调用。后续替换 LangChain 只改此文件。
"""
import logging
from typing import Optional

logger = logging.getLogger(__name__)

_client = None


def _get_client():
    """惰性创建并复用 OpenAI 客户端（带超时），避免每次调用重建连接"""
    global _client
    if _client is None:
        from openai import OpenAI
        from config.settings import (
            LLM_API_KEY, LLM_BASE_URL, LLM_TIMEOUT_SECONDS,
        )
        _client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
            timeout=LLM_TIMEOUT_SECONDS,   # 防止网络问题卡死主流程
            max_retries=1,
        )
    return _client


def call_llm(prompt: str, system_prompt: str = None) -> Optional[str]:
    """
    调用大模型 API。

    Args:
        prompt:        用户提示词
        system_prompt: 系统提示词（可选）

    Returns:
        模型返回的文本，失败返回 None
    """
    from config.settings import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL, LLM_ENABLED

    if not LLM_ENABLED:
        return None

    if not LLM_API_KEY or LLM_API_KEY == "your-api-key-here":
        logger.warning("LLM API Key 未配置，跳过大模型调用")
        return None

    try:
        client = _get_client()

        messages = []
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        messages.append({"role": "user", "content": prompt})

        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=messages,
            temperature=0.1,
            max_tokens=200,
        )

        result = response.choices[0].message.content.strip()
        logger.debug(f"LLM 返回: {result}")
        return result

    except ImportError:
        logger.warning("openai 库未安装，跳过大模型调用。pip install openai")
        return None
    except Exception as e:
        logger.error(f"LLM 调用失败: {e}")
        return None