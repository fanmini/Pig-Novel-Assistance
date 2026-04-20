# finalize_service.py
import json
import queue
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from base_dao import NovelModel
from ai_handler import ai_handler, load_ai_config
from vector_dao import vector_dao
from prompts.chapter_analysis import PROMPT_CHAPTER_ANALYSIS_COLD_START, PROMPT_CHAPTER_ANALYSIS_NORMAL, \
    PROMPT_VECTOR_TAGS

dao = NovelModel()
executor = ThreadPoolExecutor(max_workers=5)


def clean_json_string(text: str) -> dict:
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def task_knowledge_analysis(book_name: str, chapter_id: int, content: str):
    book = dao.get_book(book_name)
    storylines = dao.list_storylines(book_name)
    characters = dao.list_characters(book_name)
    analyses = dao.list_chapter_analyses(book_name)
    ai_config = load_ai_config()

    if chapter_id == 1:
        prompt = PROMPT_CHAPTER_ANALYSIS_COLD_START.format(
            book_desc=book.get('description', '暂无简介'),
            content=content
        )
        response = ai_handler.chat(
            messages=[{"role": "user", "content": prompt}],
            model=ai_config.get('model', 'openai/gpt-4o-mini'),
            api_key=ai_config.get('api_key', ''),
            temperature=0.2
        )
        ai_json = clean_json_string(response.choices[0].message.content)
        if not ai_json: return

        action_data = ai_json.get('storyline_action', {})
        main_id = storylines[0]['id'] if storylines else "p_" + str(int(time.time() * 1000))
        sub_id = "c_" + str(int(time.time() * 1000) + 1)

        if storylines:
            storylines[0]['content'] = action_data.get('main_node_content', '初始起因')
            storylines[0]['children'] = [{
                "id": sub_id,
                "name": action_data.get('sub_node_name', '初始事件'),
                "content": action_data.get('sub_node_content', '事件起因'),
                "foreshadows": [],
                "is_completed": False
            }]
        dao.update_storylines(book_name, storylines)
        _save_analysis_and_entities(book_name, chapter_id, ai_json, characters, main_id, sub_id,
                                    action_data.get('progress_desc', ''))
        return

    # === 寻找当前活跃节点 ===
    active_main = None
    active_sub = None
    active_main_idx = -1
    active_sub_idx = -1

    for i, p in enumerate(storylines):
        if not p.get('is_completed'):
            active_main = p
            active_main_idx = i
            for j, c in enumerate(p.get('children', [])):
                if not c.get('is_completed'):
                    active_sub = c
                    active_sub_idx = j
                    break
            break

    if not active_main and storylines:
        active_main = storylines[-1]
        active_main_idx = len(storylines) - 1
        if active_main.get('children'):
            active_sub = active_main['children'][-1]
            active_sub_idx = len(active_main['children']) - 1

    active_main_id = active_main['id'] if active_main else ""
    active_sub_id = active_sub['id'] if active_sub else ""

    # === 提取宏观主干 ===
    macro_storyline_lines = []
    for p in storylines:
        macro_storyline_lines.append(f"卷/大节点：【{p.get('name')}】 - 背景事实：{p.get('content')}")
        for c in p.get('children', []):
            macro_storyline_lines.append(f"  小节点：【{c.get('name')}】 - 核心事实：{c.get('content')}")
            if c.get('id') == active_sub_id:
                break
        if p.get('id') == active_main_id:
            break
    macro_storyline_text = "\n".join(macro_storyline_lines)

    # === 提取未来预设视野（作者提前规划的大纲） ===
    upcoming_lines = []
    if active_main:
        # 当前大节点下的剩余预设小节点
        for c in active_main.get('children', [])[active_sub_idx + 1:]:
            upcoming_lines.append(f"  预设小节点：【{c.get('name')}】")
        # 之后的预设大节点
        for p in storylines[active_main_idx + 1:]:
            upcoming_lines.append(f"预设大卷：【{p.get('name')}】")
            for c in p.get('children', []):
                upcoming_lines.append(f"  预设小节点：【{c.get('name')}】")
            # 为防爆，只提取未来最近的2个大节点即可
            if len(upcoming_lines) > 6:
                break
    upcoming_storyline_text = "\n".join(upcoming_lines) if upcoming_lines else "（暂无作者预设的未来节点）"

    # === 提取局部进度与摘要 ===
    current_node_progress_lines = []
    for an in sorted(analyses, key=lambda x: x.get('chapter_id', 0)):
        if an.get('bound_sub_node_id') == active_sub_id:
            current_node_progress_lines.append(f"第{an['chapter_id']}章进度：{an.get('story_position', '')}")
    current_node_progress_text = "\n".join(
        current_node_progress_lines) if current_node_progress_lines else "（该节点刚刚开启，暂无前置进度）"

    prev_summary = "暂无"
    prev_an = dao.get_chapter_analysis(book_name, chapter_id - 1)
    if prev_an and prev_an.get('summary'):
        prev_summary = prev_an['summary']

    prompt = PROMPT_CHAPTER_ANALYSIS_NORMAL.format(
        macro_storyline=macro_storyline_text,
        current_main_name=active_main.get('name') if active_main else "未知",
        current_sub_name=active_sub.get('name') if active_sub else "未知",
        current_node_progress=current_node_progress_text,
        upcoming_storyline=upcoming_storyline_text,
        prev_summary=prev_summary,
        characters=", ".join([c['character_name'] for c in characters]) or "暂无已知角色",
        current_main_id=active_main_id,
        current_sub_id=active_sub_id,
        content=content
    )

    response = ai_handler.chat(
        messages=[{"role": "user", "content": prompt}],
        model=ai_config.get('model', 'openai/gpt-4o-mini'),
        api_key=ai_config.get('api_key', ''),
        temperature=0.2
    )
    ai_json = clean_json_string(response.choices[0].message.content)
    if not ai_json: return

    action_data = ai_json.get('storyline_action', {})
    action = action_data.get('action', 'MATCH')

    bound_main_id = active_main_id
    bound_sub_id = active_sub_id
    new_content = action_data.get('new_node_content') or ai_json.get('summary', '事件推进')
    new_name = action_data.get('new_node_name') or f"新事件(第{chapter_id}章)"

    # === 状态机推演：新增 NEXT_PREPLANNED 兼容预设大纲 ===
    if action == 'NEXT_PREPLANNED':
        if active_sub: active_sub['is_completed'] = True

        # 寻找作者预设的下一个未完成节点
        next_sub = None
        if active_main:
            for c in active_main.get('children', []):
                if not c.get('is_completed'):
                    next_sub = c
                    break

        if next_sub:
            bound_sub_id = next_sub['id']
            # 如果预设节点之前没有内容，把AI分析的起因填充进去
            if not next_sub.get('content'):
                next_sub['content'] = new_content
        else:
            # 当前大节点所有预设小节点都完成了
            if active_main: active_main['is_completed'] = True
            next_main = None
            for p in storylines:
                if not p.get('is_completed'):
                    next_main = p
                    break

            if next_main:
                bound_main_id = next_main['id']
                if not next_main.get('content'): next_main['content'] = new_content
                if next_main.get('children'):
                    bound_sub_id = next_main['children'][0]['id']
                else:
                    # 如果下一个预设大卷是空的，自动建一个起始事件
                    bound_sub_id = 'c_' + str(int(time.time() * 1000))
                    next_main['children'] = [{
                        "id": bound_sub_id, "name": "起始事件", "content": new_content,
                        "foreshadows": [], "is_completed": False
                    }]
            else:
                # 极端兜底：作者的预设大纲用光了，那就自动降级为 NEW_MAIN 新建逻辑
                action = 'NEW_MAIN'

    # 原有的 NEW_MAIN 和 NEW_SUB 逻辑（在没有预设大纲时触发）
    if action == 'NEW_MAIN':
        if active_main: active_main['is_completed'] = True
        if active_sub: active_sub['is_completed'] = True
        bound_main_id = 'p_' + str(int(time.time() * 1000))
        bound_sub_id = 'c_' + str(int(time.time() * 1000) + 1)
        storylines.append({
            "id": bound_main_id, "name": new_name, "content": new_content,
            "foreshadows": [], "is_completed": False,
            "children": [{
                "id": bound_sub_id, "name": "起始事件", "content": new_content,
                "foreshadows": [], "is_completed": False
            }]
        })
        dao.update_storylines(book_name, storylines)

    elif action == 'NEW_SUB':
        if active_sub: active_sub['is_completed'] = True
        bound_sub_id = 'c_' + str(int(time.time() * 1000))
        if active_main:
            active_main['children'].append({
                "id": bound_sub_id, "name": new_name, "content": new_content,
                "foreshadows": [], "is_completed": False
            })
            dao.update_storylines(book_name, storylines)

    # 如果是 NEXT_PREPLANNED 但上面提前更新了节点属性，这里统一落盘
    if action == 'NEXT_PREPLANNED':
        dao.update_storylines(book_name, storylines)

    # 伏笔自动绑定逻辑
    fs_names_to_bind = []
    for fs in ai_json.get('planted_foreshadows', []):
        if isinstance(fs, dict) and fs.get('name'): fs_names_to_bind.append(fs['name'])
    for fs_name in ai_json.get('revealed_foreshadows', []):
        if fs_name: fs_names_to_bind.append(fs_name)

    if fs_names_to_bind:
        for p in storylines:
            if p.get('id') == bound_main_id:
                for c in p.get('children', []):
                    if c.get('id') == bound_sub_id:
                        c['foreshadows'] = c.get('foreshadows', [])
                        for name in fs_names_to_bind:
                            if name not in c['foreshadows']:
                                c['foreshadows'].append(name)
                        break
                break
        dao.update_storylines(book_name, storylines)

    _save_analysis_and_entities(book_name, chapter_id, ai_json, characters, bound_main_id, bound_sub_id,
                                action_data.get('progress_desc', ''))


def _save_analysis_and_entities(book_name, chapter_id, ai_json, existing_characters, bound_main_id, bound_sub_id,
                                progress_desc):
    dao.add_or_update_chapter_analysis(
        book_name, chapter_id,
        summary=ai_json.get('summary', ''),
        key_events=ai_json.get('key_events', []),
        story_position=progress_desc or ai_json.get('summary', ''),
        emotion_intensity=ai_json.get('emotion_intensity', 1),
        involved_characters=ai_json.get('involved_characters', []),
        bound_main_node_id=bound_main_id,
        bound_sub_node_id=bound_sub_id
    )

    existing_char_names = [c['character_name'] for c in existing_characters]
    for char_name in ai_json.get('involved_characters', []):
        if char_name not in existing_char_names:
            dao.add_character(book_name, char_name, change_log=f"首次出现于第{chapter_id}章")

    for fs in ai_json.get('planted_foreshadows', []):
        if fs.get('name') and fs.get('content'):
            dao.add_foreshadow(book_name, fs['name'], chapter_id, fs['content'], status="埋设中")

    for fs_name in ai_json.get('revealed_foreshadows', []):
        if fs_name:
            dao.update_foreshadow(book_name, fs_name, revealed_chapter=chapter_id, status="已揭示")


def task_vector_storage(book_name: str, chapter_id: int, content: str):
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


def cleanup_chapter_data(book_name: str, chapter_id: int):
    dao.delete_chapter_analysis(book_name, chapter_id)
    vector_dao.delete_snippets_by_chapter(book_name, chapter_id)


def run_finalize_pipeline(book_name: str, chapter_id: int, content: str, is_re_final: bool = False):
    if is_re_final: cleanup_chapter_data(book_name, chapter_id)
    executor.submit(task_knowledge_analysis, book_name, chapter_id, content)
    executor.submit(task_vector_storage, book_name, chapter_id, content)


def run_finalize_pipeline_stream(book_name: str, chapter_id: int, content: str, is_re_final: bool = False):
    q = queue.Queue()

    def log_msg(msg):
        q.put(msg)

    def worker():
        try:
            if is_re_final:
                log_msg("🧹 正在清理当前章节的历史残留数据...")
                cleanup_chapter_data(book_name, chapter_id)
                log_msg("✨ 历史数据清理完毕！")

            log_msg("🚀 正在启动后台双轨 AI 引擎...")

            def task_a():
                log_msg(
                    f"🧠 知识分析引擎：{'正在进行第1章冷启动推演...' if chapter_id == 1 else '正在提取动态上下文与大纲防爆包装...'}")
                task_knowledge_analysis(book_name, chapter_id, content)
                log_msg("✅ 知识分析引擎：分析完毕，本章已与故事线完成节点强绑定！")

            def task_b():
                log_msg("🔪 向量切片引擎：开始寻找高光片段并打标...")
                task_vector_storage(book_name, chapter_id, content)
                log_msg("✅ 向量切片引擎：所有切片入库完毕！")

            future_a = executor.submit(task_a)
            future_b = executor.submit(task_b)

            wait([future_a, future_b])
            q.put("DONE")
        except Exception as e:
            log_msg(f"❌ 引擎运行出现错误: {str(e)}")
            q.put("DONE")

    threading.Thread(target=worker).start()

    while True:
        msg = q.get()
        if msg == "DONE":
            yield f"data: {json.dumps({'content': '🎉 章节定稿全部完成，故事线已推进，你可以继续创作啦！'})}\n\n"
            yield "data: [DONE]\n\n"
            break
        else:
            yield f"data: {json.dumps({'content': msg})}\n\n"