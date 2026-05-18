# prompt_manager.py
import os
import json
from base_dao import NovelModel

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
        current_dir = os.path.dirname(os.path.abspath(__file__))
        # 全局配置路径
        self.global_filepath = os.path.join(current_dir, 'data', 'custom_prompts.json')
        if not os.path.exists(os.path.dirname(self.global_filepath)):
            os.makedirs(os.path.dirname(self.global_filepath))
        self.dao = NovelModel()

    def _load_global_customs(self):
        """加载全局自定义配置"""
        if os.path.exists(self.global_filepath):
            with open(self.global_filepath, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def _load_book_customs(self, book_name):
        """加载当前书籍专属的配置"""
        if not book_name:
            return {}
        book_prompt_path = os.path.join(self.dao.data_root, book_name, 'custom_prompts.json')
        if os.path.exists(book_prompt_path):
            with open(book_prompt_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        return {}

    def get_all_prompts(self, book_name=None):
        """前端拉取列表时使用：层级合并 (书籍专属 > 全局自定义 > 默认配置)"""
        global_customs = self._load_global_customs()
        book_customs = self._load_book_customs(book_name)

        results = []
        for mod in PROMPT_MODULES:
            for var_name in dir(mod):
                if var_name.startswith("PROMPT_") and isinstance(getattr(mod, var_name), str):
                    if "SYSTEM" in var_name:
                        role = "system"
                    elif "ASSISTANT" in var_name:
                        role = "assistant"
                    else:
                        role = "user"

                    # 确定最终生效的内容和别名
                    content = getattr(mod, var_name)
                    alias = ALIASES.get(var_name, var_name)

                    # 全局覆盖
                    if var_name in global_customs:
                        content = global_customs[var_name].get("content", content)
                        alias = global_customs[var_name].get("alias", alias)

                    # 书籍专属覆盖
                    if var_name in book_customs:
                        content = book_customs[var_name].get("content", content)
                        alias = book_customs[var_name].get("alias", alias)

                    results.append({
                        "name": var_name,
                        "role": role,
                        "alias": alias,
                        "content": content
                    })
        return results

    def save_prompts(self, prompt_list, book_name=None):
        """前端保存时使用：若存在书籍则保存为书籍专属，否则为全局默认"""
        if book_name:
            customs = self._load_book_customs(book_name)
            for p in prompt_list:
                customs[p['name']] = {"alias": p['alias'], "content": p['content']}
            book_prompt_path = os.path.join(self.dao.data_root, book_name, 'custom_prompts.json')
            with open(book_prompt_path, 'w', encoding='utf-8') as f:
                json.dump(customs, f, ensure_ascii=False, indent=2)
        else:
            customs = self._load_global_customs()
            for p in prompt_list:
                customs[p['name']] = {"alias": p['alias'], "content": p['content']}
            with open(self.global_filepath, 'w', encoding='utf-8') as f:
                json.dump(customs, f, ensure_ascii=False, indent=2)

    def get(self, var_name, book_name=None):
        """后台业务调用时使用：书籍专属 > 全局自定义 > 默认保底"""
        book_customs = self._load_book_customs(book_name)
        if var_name in book_customs and book_customs[var_name].get("content"):
            return book_customs[var_name]["content"]

        global_customs = self._load_global_customs()
        if var_name in global_customs and global_customs[var_name].get("content"):
            return global_customs[var_name]["content"]

        for mod in PROMPT_MODULES:
            if hasattr(mod, var_name):
                return getattr(mod, var_name)
        return ""


# 导出单例
prompt_manager = PromptManager()