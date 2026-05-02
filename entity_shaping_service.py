# entity_shaping_service.py
import json
from base_dao import NovelModel
from ai_handler import ai_handler, load_ai_config
from context_builder import build_global_knowledge, build_full_lifecycle_entities

dao = NovelModel()

# ==========================================
# 专属 Prompts：全知视角的人设/势力架构师
# ==========================================
PROMPT_SHAPING_SYSTEM = """
=============== 身份 ===============
你是一位顶级的网文世界观架构师与人设大师。你的任务是根据用户的诉求，辅助创建全新的角色/势力，或者补全现有实体的设定细节。

=============== 设定铁律 ===============
1. 【深度契合】：严密贴合现有的世界观法则、战力体系和行文氛围，绝不生成破坏平衡或画风突变的内容。
2. 【面向未来】：深入理解提供的“故事线大纲（含未来规划）”，让你设计/补全的实体能够完美嵌入或推动未来的剧情冲突。
3. 【拒绝废话】：不要写小说正文，不要有“好的，为您生成”之类的客套话。直接输出干练、有质感的设定资料。
4. 【精准响应】：严格针对用户提出的具体诉求进行发散创作，不偏题。

=============== 输出结构要求 ===============
如果是【创建角色】或【补全角色】，请严格按照以下模块进行排版输出，确保信息层次清晰，方便主编直接复制使用：
【角色姓名】：(设定一个符合世界观的名字或代号)
【个人资料】：(角色的基础身份、战力境界、核心身世背景或过往重要经历)
【外貌与性格】：(极具辨识度的外貌特写，以及性格底色、行事作风)
【初始弧光】：(角色当前的核心欲望、内心矛盾，或初次登场时的精神状态)
【潜在关系网】：(结合已有资料，推演其与现有角色/势力的预设交集与态度)

如果是【创建势力】，请输出：【势力名称】、【宗旨底色】、【核心架构】、【历史动态】。
"""

PROMPT_SHAPING_USER = """
=============== 1. 全书设定基石 ===============
{global_knowledge}

=============== 2. 全量实体生态 (当前所有角色与势力) ===============
{entities_context}

=============== 3. 全局故事线脉络 (历史 + 正在进行 + 未来规划) ===============
{full_storyline}

=============== 4. 当前大卷正文参考 (用于感受行文氛围) ===============
{current_volume_chapters}

=============== 🎯 当前任务与目标 ===============
【操作目标】：{target_desc}
【参考实体】：{ref_desc}

【主编(用户)的具体诉求】：
{user_prompt}
"""


def _build_full_storyline_tree(book_name: str) -> str:
    """提取全书完整故事线树（不做任何截断，包含未来规划）"""
    storylines = dao.list_storylines(book_name)
    if not storylines:
        return "暂无故事线规划。"

    lines = []
    for p in storylines:
        status = "✅已完结" if p.get('is_completed') else "🔄进行中/待推进"
        lines.append(f"【大卷：{p.get('name')}】 ({status})\n  核心脉络: {p.get('content', '暂无')}")
        for c in p.get('children', []):
            c_status = "✅已完结" if c.get('is_completed') else "🔄进行中/待推进"
            lines.append(f"    ▶ 【事件：{c.get('name')}】 ({c_status})\n      梗概: {c.get('content', '暂无')}")
    return "\n".join(lines)


def _get_current_volume_chapters(book_name: str) -> str:
    """提取当前正在进行的大卷下的所有已写章节正文"""
    storylines = dao.list_storylines(book_name)
    analyses = dao.list_chapter_analyses(book_name)

    # 找到当前未完结的大节点
    active_main_id = None
    for p in storylines:
        if not p.get('is_completed'):
            active_main_id = p['id']
            break

    if not active_main_id:
        return "（当前无活跃大卷或大纲已全部完结）"

    # 收集该大节点下绑定的章节正文
    bound_chapters = []
    for an in analyses:
        if an.get('bound_main_node_id') == active_main_id:
            cid = an.get('chapter_id')
            chap = dao.get_chapter(book_name, cid)
            if chap and chap.get('content'):
                bound_chapters.append(f"--- 第 {cid} 章 ---\n{chap.get('content')}")

    if not bound_chapters:
        return "（当前大卷尚未产生定稿章节正文）"

    return "\n\n".join(bound_chapters)


# ==========================================
# 核心业务：组装资料、支持预览或调用大模型
# ==========================================
def generate_entity_shaping(book_name: str, target_desc: str, ref_desc: str, user_prompt: str,
                            preview_only: bool = False):
    # 1. 拼装全知视角的资料包
    global_knowledge = build_global_knowledge(book_name)

    # 【无隔离实体】：传入 None 代表获取所有角色和势力，不传 max_chapter_id 代表不进行时光倒流
    entities_context = build_full_lifecycle_entities(book_name, char_names=None, faction_names=None,
                                                     max_chapter_id=None)

    # 【无隔离大纲】：获取整棵树
    full_storyline = _build_full_storyline_tree(book_name)

    # 获取当前大卷正文以供文风参考
    current_volume_chapters = _get_current_volume_chapters(book_name)

    # 2. 组装终极 User Prompt
    final_user_prompt = PROMPT_SHAPING_USER.format(
        global_knowledge=global_knowledge,
        entities_context=entities_context,
        full_storyline=full_storyline,
        current_volume_chapters=current_volume_chapters,
        target_desc=target_desc,
        ref_desc=ref_desc,
        user_prompt=user_prompt
    )

    # 3. 【极简代码核心】：拦截器模式！
    if preview_only:
        full_prompt_text = f"【System 指令】\n{PROMPT_SHAPING_SYSTEM}\n\n【User 提问】\n{final_user_prompt}"
        return {"status": "preview", "prompt": full_prompt_text}

    # 4. 正常调用大模型 (如果不是预览的话)
    ai_config = load_ai_config()
    response = ai_handler.chat(
        messages=[
            {"role": "system", "content": PROMPT_SHAPING_SYSTEM},
            {"role": "user", "content": final_user_prompt}
        ],
        model=ai_config.get('model', 'openai/gpt-4o-mini'),
        api_key=ai_config.get('api_key', ''),
        max_tokens=int(ai_config.get('max_tokens', 8192)),
        temperature=0.7,  # 创造性任务，温度适中
        top_p=float(ai_config.get('top_p', 1.0))
    )

    return {"status": "success", "content": response.choices[0].message.content}