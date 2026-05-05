# prompt_manager.py
import os
import json

# 导入包含提示词的纯文本模块
from prompts import chapter_analysis, chapter_generation, entity_shaping, storyline

# 注册模块（以后新增 prompt 文件，只需加进这个列表）
PROMPT_MODULES = [chapter_analysis, chapter_generation, entity_shaping, storyline]

# 中文别名映射字典（前端展示用，找不到的会自动用英文变量名顶替）
ALIASES = {
    "PROMPT_PLOT_ENGINE_COLD_START_SYSTEM": "定稿分析(冷启动)",
    "PROMPT_PLOT_ENGINE_COLD_START_USER": "定稿分析(冷启动)",
    "PROMPT_PLOT_ENGINE_SYSTEM": "定稿分析(常规)",
    "PROMPT_PLOT_ENGINE_USER": "定稿分析(常规)",
    "PROMPT_ENTITY_ENGINE_SYSTEM": "角色势力",
    "PROMPT_ENTITY_ENGINE_USER": "角色势力",
    "PROMPT_VECTOR_TAGS_SYSTEM": "向量",
    "PROMPT_VECTOR_TAGS_USER": "向量",
    "PROMPT_PLAN_SYSTEM": "想法分析",
    "PROMPT_PLAN_USER": "想法分析",
    "PROMPT_CONTENT_SYSTEM": "正文编写",
    "PROMPT_CONTENT_USER": "正文编写",
    "PROMPT_SHAPING_SYSTEM": "实体塑造",
    "PROMPT_SHAPING_USER": "实体塑造",
    "PROMPT_MAIN_NODE_SYSTEM": "故事大总结",
    "PROMPT_SUB_NODE_SYSTEM": "故事小总结",
    "PROMPT_STORYLINE_USER": "故事线总结",
    "PROMPT_CHAT_SYSTEM": "自由聊天",
    "PROMPT_CHAT_ASSISTANT": "自由聊天"
}

class PromptManager:
    def __init__(self):
        # 将自定义提示词保存在全局 data 目录下
        current_dir = os.path.dirname(os.path.abspath(__file__))
        self.filepath = os.path.join(current_dir, 'data', 'custom_prompts.json')
        if not os.path.exists(os.path.dirname(self.filepath)):
            os.makedirs(os.path.dirname(self.filepath))

    def _load_customs(self):
        if os.path.exists(self.filepath):
            with open(self.filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_all_prompts(self):
        """前端拉取列表时使用：动态扫描 + 合并自定义配置"""
        customs = self._load_customs()
        results = []
        for mod in PROMPT_MODULES:
            for var_name in dir(mod):
                # 动态捕捉所有以 PROMPT_ 开头的变量
                if var_name.startswith("PROMPT_") and isinstance(getattr(mod, var_name), str):
                    role = "system" if "SYSTEM" in var_name else "user"
                    # 自定义存在就用自定义的，不存在就用默认的
                    content = customs.get(var_name, {}).get("content", getattr(mod, var_name))
                    alias = customs.get(var_name, {}).get("alias", ALIASES.get(var_name, var_name))
                    results.append({
                        "name": var_name,
                        "role": role,
                        "alias": alias,
                        "content": content
                    })
        return results

    def save_prompts(self, prompt_list):
        """前端保存时使用：仅保存需要自定义的内容"""
        customs = self._load_customs()
        for p in prompt_list:
            customs[p['name']] = {"alias": p['alias'], "content": p['content']}
        with open(self.filepath, 'w', encoding='utf-8') as f:
            json.dump(customs, f, ensure_ascii=False, indent=2)

    def get(self, var_name):
        """后台业务调用时使用：自定义优先，默认保底"""
        customs = self._load_customs()
        if var_name in customs and customs[var_name].get("content"):
            return customs[var_name]["content"]

        # 兜底：从原本的模块里取默认值
        for mod in PROMPT_MODULES:
            if hasattr(mod, var_name):
                return getattr(mod, var_name)
        return ""

# 导出单例
prompt_manager = PromptManager()