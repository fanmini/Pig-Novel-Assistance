# finalize_service.py
import json
import re
from concurrent.futures import ThreadPoolExecutor
from base_dao import NovelModel
from ai_handler import ai_handler, load_ai_config
from vector_dao import vector_dao
from prompts.chapter_analysis import PROMPT_CHAPTER_ANALYSIS, PROMPT_VECTOR_TAGS

dao = NovelModel()
# 创建一个全局线程池
executor = ThreadPoolExecutor(max_workers=5)


def clean_json_string(text: str) -> dict:
    """清理大模型可能带有的 markdown 代码块，并解析为字典"""
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def task_knowledge_analysis(book_name: str, chapter_id: int, content: str):
    """线程A：分析摘要、角色、情感、故事线状态机"""
    book = dao.get_book(book_name)
    chapters = dao.list_chapters(book_name)
    storylines = dao.list_storylines(book_name)
    characters = dao.list_characters(book_name)

    # 1. 获取上一章摘要（解决盲区：如果是第1章则为空）
    prev_summary = "（这是本书第一章，暂无前情提要，请重点分析开局设定。）"
    if chapter_id > 1:
        prev_analysis = dao.get_chapter_analysis(book_name, chapter_id - 1)
        if prev_analysis and prev_analysis.get('summary'):
            prev_summary = prev_analysis['summary']

    # 2. 提取当前未完成的故事线
    uncompleted_nodes = []
    for p in storylines:
        if not p.get('is_completed'):
            uncompleted_nodes.append(f"大节点: {p.get('name')}")
            for c in p.get('children', []):
                if not c.get('is_completed'):
                    uncompleted_nodes.append(f"  - 小节点: {c.get('name')}")

    # 3. 组装 Prompt 并调用 AI
    prompt = PROMPT_CHAPTER_ANALYSIS.format(
        book_desc=book.get('description', ''),
        prev_summary=prev_summary,
        characters=", ".join([c['character_name'] for c in characters]),
        uncompleted_storyline="\n".join(
            uncompleted_nodes) if uncompleted_nodes else "（空，请直接创建第一个大节点和小节点）",
        content=content
    )

    # 读取用户在前端保存的 AI 配置
    ai_config = load_ai_config()

    response = ai_handler.chat(
        messages=[{"role": "user", "content": prompt}],
        model=ai_config.get('model', 'openai/gpt-4o-mini'),
        api_key=ai_config.get('api_key', ''),
        temperature=0.3  # 分析类任务建议把温度调低，避免 AI 瞎编
    )
    ai_json = clean_json_string(response.choices[0].message.content)

    if not ai_json:
        return

    # 4. 数据落盘：保存分析数据
    dao.add_or_update_chapter_analysis(
        book_name, chapter_id,
        summary=ai_json.get('summary', ''),
        key_events=ai_json.get('key_events', []),
        story_position=ai_json.get('story_position', ''),
        emotion_intensity=ai_json.get('emotion_intensity', 1),
        involved_characters=ai_json.get('involved_characters', [])
    )

    # 5. 自动注册新出场角色
    existing_char_names = [c['character_name'] for c in characters]
    for char_name in ai_json.get('involved_characters', []):
        if char_name not in existing_char_names:
            dao.add_character(book_name, char_name, change_log=f"首次出现于第{chapter_id}章")

    # 6. 故事线 A/B/C 状态机逻辑（仅限最新章节，防止修改历史章节）
    import time

    # 【核心逻辑 1：剧情前沿判定 (Frontier Check)】
    # 只要当前章的“后面”没有任何已经生成过摘要的章节，当前章就是“剧情前沿”！
    # 这样就算作者预建了 100 个空章节，然后按序录入，也能完美触发故事线生长。
    is_frontier = True
    analyses = dao.list_chapter_analyses(book_name)
    for an in analyses:
        # 如果存在比当前 ID 大的章节，并且它已经有了 summary，说明是在修文（历史编辑）
        if an.get('chapter_id', 0) > chapter_id and an.get('summary'):
            is_frontier = False
            break

    if is_frontier:
        action_data = ai_json.get('storyline_action', {})
        action = action_data.get('action', 'MATCH')

        # 【核心逻辑 2：活跃锚点追踪 (Active Anchor)】
        # 寻找目前排在最前面的“未完成大节点”作为当前的活跃锚点
        active_main_idx = -1
        for i, p in enumerate(storylines):
            if not p.get('is_completed'):
                active_main_idx = i
                break

        if action == 'NEW_MAIN':
            # 如果 AI 判定开启了完全不在大纲里的新卷
            # 1. 把当前的活跃大节点标记完结
            if active_main_idx != -1:
                storylines[active_main_idx]['is_completed'] = True

            # 2. 在末尾追加全新的大卷和起始小节点
            new_p = {
                "id": 'p_' + str(int(time.time() * 1000)),
                "name": action_data.get('new_main_name', '新大节点'),
                "content": "", "foreshadows": [], "is_completed": False,
                "children": [{
                    "id": 'c_' + str(int(time.time() * 1000) + 1),
                    "name": action_data.get('new_sub_name', '新小节点'),
                    "content": "", "foreshadows": [], "is_completed": False
                }]
            }
            storylines.append(new_p)
            dao.update_storylines(book_name, storylines)

        elif action == 'NEW_SUB':
            # 如果 AI 判定发生了计划外的小事件
            if active_main_idx != -1:
                # 直接挂在当前的“活跃大节点”下面，作为新支线
                p = storylines[active_main_idx]
                p['children'] = p.get('children', [])
                p['children'].append({
                    "id": 'c_' + str(int(time.time() * 1000)),
                    "name": action_data.get('new_sub_name', '新支线事件'),
                    "content": "", "foreshadows": [], "is_completed": False
                })
                dao.update_storylines(book_name, storylines)
            else:
                # 连大节点都没有，直接兜底建一个
                new_p = {
                    "id": 'p_' + str(int(time.time() * 1000)),
                    "name": "未命名初始剧情",
                    "content": "", "foreshadows": [], "is_completed": False,
                    "children": [{
                        "id": 'c_' + str(int(time.time() * 1000) + 1),
                        "name": action_data.get('new_sub_name', '新小节点'),
                        "content": "", "foreshadows": [], "is_completed": False
                    }]
                }
                storylines.append(new_p)
                dao.update_storylines(book_name, storylines)

        elif action == 'MATCH':
            # 完美命中作者的预设大纲节点，或者仍在当前节点发展。
            # 什么都不需要新建，维持树状结构不动。
            pass


def task_vector_storage(book_name: str, chapter_id: int, content: str):
    """线程B：提取片段、打标签、存入向量数据库"""
    prompt = PROMPT_VECTOR_TAGS.format(content=content)
    ai_config = load_ai_config()

    response = ai_handler.chat(
        messages=[{"role": "user", "content": prompt}],
        model=ai_config.get('model', 'openai/gpt-4o-mini'),
        api_key=ai_config.get('api_key', ''),
        temperature=0.3
    )
    ai_json = clean_json_string(response.choices[0].message.content)

    snippets = ai_json.get('snippets', [])
    for item in snippets:
        snippet_content = item.get('content')
        tags = item.get('tags', [])
        if snippet_content and tags:
            vector_dao.save_snippet_tags(book_name, chapter_id, snippet_content, tags)


def run_finalize_pipeline(book_name: str, chapter_id: int, content: str):
    """触发并发流水线"""
    executor.submit(task_knowledge_analysis, book_name, chapter_id, content)
    executor.submit(task_vector_storage, book_name, chapter_id, content)