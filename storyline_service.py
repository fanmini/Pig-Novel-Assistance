# storyline_service.py
import json
from base_dao import NovelModel
from ai_handler import ai_handler, load_ai_config
from context_builder import build_global_knowledge, build_full_lifecycle_entities

dao = NovelModel()

# ==========================================
# 专属 Prompts：故事线总结大模型设定
# ==========================================

# 针对【大节点/大卷】的总结 Prompt
PROMPT_MAIN_NODE_SYSTEM = """
=============== 身份 ===============
你是一位顶级的小说剧情架构师。你的任务是为AI写作系统提炼“大卷级别的故事脉络”。

=============== 写作铁律 ===============
1. 【宏观俯瞰】：不要纠结于某一场具体战斗的一招一式，要提炼这一大段剧情的“起承转合”。
2. 【流畅连贯】：这是一段连贯的、有大局观的故事梗概。严禁使用干巴巴的结构化条目（如“1.xx 2.xx”），要写成一篇流畅的总结文。
3. 【核心聚焦】：讲清楚这段剧情的核心矛盾是什么、经历了怎样的大波折、最终走向了什么结局，对整个世界观或主角有什么深远影响。
4. 【纯粹故事】：语言要求精炼、清晰，直接陈述发生的故事，不要加入“本章讲述了”、“总结来说”等废话。
"""

# 针对【小节点/单集事件】的总结 Prompt
PROMPT_SUB_NODE_SYSTEM = """
=============== 身份 ===============
你是一位专业的故事分集编剧。你的任务是为AI写作系统提炼“具体事件的详细梗概”。

=============== 写作铁律 ===============
1. 【微观聚焦】：专注把“当前这一个特定事件”完完整整地说清楚。起因是什么、发展过程中的关键动作/转折是什么、结果如何。
2. 【流畅连贯】：这是一段清晰流畅的事件纪实。严禁使用干巴巴的列表或条目，要像讲故事一样写出来。
3. 【清晰备忘】：你的总结将作为日后AI写作的“剧情导航仪”，必须明确指出主角在本次事件中干了什么具体的关键事情、获得了什么、失去了什么、或者与谁确立了什么关系。
4. 【纯粹故事】：直接平铺直叙地把事件讲明白，不掺杂任何分析性质的废话。
"""

PROMPT_STORYLINE_USER = """
=============== 1. 全书设定基石 ===============
{global_knowledge}

=============== 2. 实体档案 (已滤除未来剧透) ===============
{entities_context}

=============== 3. 前情提要 (历史结构化大纲) ===============
{previous_storylines}

=============== 4. 当前节点所属正文 ===============
【当前总结节点】：{node_name}
【正文内容如下】：
{chapter_contents}

=============== 任务 ===============
请根据上述所有正文，严格遵守我的系统设定，撰写一段流畅、清晰、连贯的故事脉络总结。
"""


# ==========================================
# 辅助函数：提取历史故事线和大纲
# ==========================================
def _build_previous_storylines(book_name: str, target_node_id: str) -> str:
    """
    遍历故事线树，提取目标节点【之前】的所有大节点和小节点的总结内容。
    用于给 AI 提供结构化的完美前情提要。
    """
    storylines = dao.list_storylines(book_name)
    lines = []

    for main_node in storylines:
        # 如果大节点本身就是目标，直接停止（不包含自己）
        if main_node['id'] == target_node_id:
            break

        main_content = main_node.get('content', '').strip()
        main_status = "✅已完结" if main_node.get('is_completed') else "🔄进行中"
        lines.append(f"【大节点：{main_node.get('name')}】 ({main_status})")
        if main_content:
            lines.append(f"  └─ 剧情梗概: {main_content}")

        target_found_in_sub = False
        for sub_node in main_node.get('children', []):
            if sub_node['id'] == target_node_id:
                target_found_in_sub = True
                break

            sub_content = sub_node.get('content', '').strip()
            if sub_content:
                lines.append(f"    ▶ 【小事件：{sub_node.get('name')}】")
                lines.append(f"      └─ 事件梗概: {sub_content}")

        if target_found_in_sub:
            break

    if not lines:
        return "（当前为故事起始阶段，暂无前情提要）"
    return "\n".join(lines)


# ==========================================
# 核心业务：生成故事线总结并回填
# ==========================================
def generate_storyline_summary(book_name: str, node_id: str, preview_only: bool = False):
    """
    主控流转：获取节点信息 -> 收集绑定章节 -> 时光倒流 -> 调用 AI -> 回填节点
    """
    storylines = dao.list_storylines(book_name)
    analyses = dao.list_chapter_analyses(book_name)

    # 1. 自动探测节点类型与节点名称
    node_type = None
    node_name = ""
    for main_node in storylines:
        if main_node['id'] == node_id:
            node_type = 'main'
            node_name = main_node.get('name', '')
            break
        for sub_node in main_node.get('children', []):
            if sub_node['id'] == node_id:
                node_type = 'sub'
                node_name = sub_node.get('name', '')
                break
        if node_type:
            break

    if not node_type:
        raise ValueError("未找到指定的故事线节点。")

    # 2. 收集当前节点绑定的所有章节正文
    bound_chapter_ids = []
    for an in analyses:
        if node_type == 'main' and an.get('bound_main_node_id') == node_id:
            bound_chapter_ids.append(an.get('chapter_id'))
        elif node_type == 'sub' and an.get('bound_sub_node_id') == node_id:
            bound_chapter_ids.append(an.get('chapter_id'))

    if not bound_chapter_ids:
        raise ValueError("当前节点尚未绑定任何已定稿章节，无需总结。")

    bound_chapter_ids.sort()
    max_chapter_id = bound_chapter_ids[-1]  # 用于“时光倒流”的边界

    chapter_contents_list = []
    for cid in bound_chapter_ids:
        chap = dao.get_chapter(book_name, cid)
        if chap and chap.get('content'):
            chapter_contents_list.append(f"--- 第 {cid} 章 ---\n{chap.get('content')}")
    chapter_contents_text = "\n\n".join(chapter_contents_list)

    # 3. 拼装核心资料
    global_knowledge = build_global_knowledge(book_name)
    # 【核心：时光倒流】只拿这批章节范围内及之前的档案！
    entities_context = build_full_lifecycle_entities(
        book_name,
        max_chapter_id=max_chapter_id + 1  # 加1是为了包含最后一章刚产生的变化
    )
    previous_storylines = _build_previous_storylines(book_name, node_id)

    # 4. 选择 Prompt
    system_prompt = PROMPT_MAIN_NODE_SYSTEM if node_type == 'main' else PROMPT_SUB_NODE_SYSTEM
    user_prompt = PROMPT_STORYLINE_USER.format(
        global_knowledge=global_knowledge,
        entities_context=entities_context,
        previous_storylines=previous_storylines,
        node_name=node_name,
        chapter_contents=chapter_contents_text
    )
    if preview_only:
        # 直接刹车，把组装好的终极 Prompt 吐出去！
        full_prompt = f"【System 指令】\n{system_prompt}\n\n【User 提问】\n{user_prompt}"
        return {"status": "preview", "prompt": full_prompt}
    # 5. 调用 AI 引擎
    ai_config = load_ai_config()
    response = ai_handler.chat(
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt}
        ],
        model=ai_config.get('model', 'openai/gpt-4o-mini'),
        api_key=ai_config.get('api_key', ''),
        max_tokens=int(ai_config.get('max_tokens', 8192)),
        temperature=0.4,  # 总结任务，温度可以稍微低一点，保证稳定和逻辑连贯
        top_p=float(ai_config.get('top_p', 1.0))
    )

    summary_result = response.choices[0].message.content.strip()

    # 6. 回填到 storylines.json
    for main_node in storylines:
        if main_node['id'] == node_id:
            main_node['content'] = summary_result
            break
        for sub_node in main_node.get('children', []):
            if sub_node['id'] == node_id:
                sub_node['content'] = summary_result
                break

    dao.update_storylines(book_name, storylines)

    return {"status": "success", "summary": summary_result}