# ai_handler.py
import os
import json
import re
import threading
from datetime import datetime
from typing import List, Dict, Optional, Generator, Union
import litellm
from litellm import completion, ModelResponse
from threading import Event

# 配置文件路径
AI_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'ai_config.json')
# 允许丢弃不支持的参数，避免报错
litellm.drop_params = True

class AIHandler:
    """统一的大模型调用处理器，支持多模型切换、参数调节、日志记录"""

    # 预定义可用模型列表（前端展示用）
    AVAILABLE_MODELS = [
        {"id": "deepseek/deepseek-v4-flash", "name": "DeepSeek-flash", "provider": "DeepSeek"},
        {"id": "deepseek/deepseek-v4-pro", "name": "DeepSeek-pro", "provider": "DeepSeek"},
        {"id": "dashscope/qwen3-max-preview", "name": "通义千问 Max", "provider": "Alibaba"},
        {"id": "dashscope/qwen-plus-latest", "name": "通义千问 Plus", "provider": "Alibaba"},
        {"id": "gemini/gemini-2.0-flash", "name": "Gemini 2.0 Flash", "provider": "Google"},
        {"id": "gemini/gemini-2.5-pro", "name": "Gemini 2.5 Pro", "provider": "Google"},
        {"id": "moonshot/kimi-k2.5", "name": "Kimi (K2.5)", "provider": "Moonshot"},
        {"id": "zhipu/glm-4.5", "name": "智谱 GLM-4.5", "provider": "Zhipu"},
        {"id": "openai/gpt-4o", "name": "GPT-4o", "provider": "OpenAI"},
        {"id": "openai/gpt-4o-mini", "name": "GPT-4o Mini", "provider": "OpenAI"},
        {"id": "anthropic/claude-3.5-sonnet", "name": "Claude 3.5 Sonnet", "provider": "Anthropic"},
    ]

    def __init__(self, log_dir: str = "logs"):
        self.log_dir = log_dir
        os.makedirs(self.log_dir, exist_ok=True)
        self._stop_event = Event()          # 用于中断生成
        self._current_stream = None
        self._lock = threading.Lock()  # 【新增】日志写入锁，防止并发写乱

    def get_available_models(self) -> List[Dict]:
        """返回可用模型列表"""
        return self.AVAILABLE_MODELS

    def chat(
            self,
            messages: List[Dict[str, str]],
            model: str = "openai/gpt-4o-mini",
            temperature: float = 0.7,
            max_tokens: int = 1024,
            top_p: float = 1.0,
            stream: bool = False,
            api_key: Optional[str] = None,
            **kwargs
    ) -> Union[ModelResponse, Generator]:
        """
        发起对话请求
        """
        self._stop_event.clear()

        # 如果传入了 api_key，临时设置到环境变量
        if api_key:
            self._set_api_key_for_model(model, api_key)

        try:
            response = completion(
                model=model, messages=messages, temperature=temperature,
                max_tokens=max_tokens, top_p=top_p, stream=stream, **kwargs
            )

            # 非流式调用，直接记录
            if not stream:
                assistant_content = response.choices[0].message.content
                user_msg = messages[-1]['content'] if messages else "SYSTEM_CALL"
                self.save_conversation_log(
                    session_id="SYSTEM_AUTO_LOG",
                    user_message=user_msg,
                    assistant_message=assistant_content,
                    model=model,
                    params={"temperature": temperature, "max_tokens": max_tokens, "top_p": top_p}
                )
                return response
            else:
                self._current_stream = response

                # 【底层解药】：包装流式返回，在流断开或完成时，强制拦截并落盘日志！
                def stream_wrapper():
                    full_text = ""
                    reasoning_text = ""
                    try:
                        for chunk in response:
                            if self._stop_event.is_set():
                                break

                            delta = chunk.choices[0].delta
                            content = delta.content or ""
                            full_text += content

                            # 连同 DeepSeek 的思考过程一起捕获保存
                            reasoning = getattr(delta, 'reasoning_content', '')
                            if not reasoning and hasattr(delta, 'model_extra') and delta.model_extra:
                                reasoning = delta.model_extra.get('reasoning_content', '')
                            if reasoning:
                                reasoning_text += reasoning

                            yield chunk
                    finally:
                        # 不管是生成完毕还是中途被掐断，都会走到 finally 进行落盘！
                        final_save_text = full_text
                        if reasoning_text:
                            final_save_text = f"【AI思考过程】:\n{reasoning_text}\n\n【正式回复】:\n{full_text}"

                        user_msg = messages[-1]['content'] if messages else "SYSTEM_CALL"
                        self.save_conversation_log(
                            session_id="SYSTEM_AUTO_LOG_STREAM",
                            user_message=user_msg,
                            assistant_message=final_save_text,
                            model=model,
                            params={"temperature": temperature, "max_tokens": max_tokens, "top_p": top_p}
                        )

                return stream_wrapper()
        except Exception as e:
            raise e

    def stop_generation(self):
        """停止当前的流式生成"""
        self._stop_event.set()
        self._current_stream = None

    def _set_api_key_for_model(self, model: str, api_key: str):
        """根据模型名称设置对应的 API Key 环境变量"""
        if model.startswith("openai/"):
            os.environ["OPENAI_API_KEY"] = api_key
        elif model.startswith("anthropic/"):
            os.environ["ANTHROPIC_API_KEY"] = api_key
        elif model.startswith("gemini/"):
            os.environ["GEMINI_API_KEY"] = api_key
        elif model.startswith("deepseek/"):
            os.environ["DEEPSEEK_API_KEY"] = api_key
        # 如有其他可在此扩展

    def save_conversation_log(
        self,
        session_id: str,
        user_message: str,
        assistant_message: str,
        model: str,
        params: Dict,
        metadata: Optional[Dict] = None
    ):
        """
        保存单轮对话日志到日期文件

        :param session_id: 会话ID
        :param user_message: 用户消息
        :param assistant_message: AI回复
        :param model: 使用的模型
        :param params: 调用参数
        :param metadata: 额外元数据
        """
        log_entry = {
            "timestamp": datetime.now().isoformat(),
            "session_id": session_id,
            "model": model,
            "user": user_message,
            "assistant": assistant_message,
            "params": params,
            "metadata": metadata or {}
        }
        filename = datetime.now().strftime("%Y-%m-%d") + ".jsonl"
        filepath = os.path.join(self.log_dir, filename)
        with self._lock:
            with open(filepath, "a", encoding="utf-8") as f:
                f.write(json.dumps(log_entry, ensure_ascii=False) + "\n")

def load_ai_config():
    """加载AI配置，若文件不存在则返回默认配置"""
    default_config = {
        "model": "openai/gpt-4o-mini",
        "api_key": "",
        "temperature": 0.7,
        "max_tokens": 1024,
        "top_p": 1.0
    }
    if not os.path.exists(AI_CONFIG_PATH):
        return default_config
    try:
        with open(AI_CONFIG_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except:
        return default_config

def save_ai_config(config):
    """保存AI配置到文件"""
    with open(AI_CONFIG_PATH, 'w', encoding='utf-8') as f:
        json.dump(config, f, ensure_ascii=False, indent=2)

# 全局单例（便于在 Flask 中复用）
ai_handler = AIHandler()


