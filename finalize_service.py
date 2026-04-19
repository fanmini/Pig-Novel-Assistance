# finalize_service.py
import json
import queue
import re
import threading
from concurrent.futures import ThreadPoolExecutor, wait
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

    # 【新增解析 1】：获取故事线进展描述，绑定节点进度
    action_data = ai_json.get('storyline_action', {})
    progress_desc = action_data.get('progress_desc', '')
    if not progress_desc:
        progress_desc = ai_json.get('story_position', '')  # 兼容兜底

    # 4. 数据落盘：保存分析数据 (写入与节点绑定的进度)
    dao.add_or_update_chapter_analysis(
        book_name, chapter_id,
        summary=ai_json.get('summary', ''),
        key_events=ai_json.get('key_events', []),
        story_position=progress_desc,
        emotion_intensity=ai_json.get('emotion_intensity', 1),
        involved_characters=ai_json.get('involved_characters', [])
    )

    # 5. 自动注册新出场角色
    existing_char_names = [c['character_name'] for c in characters]
    for char_name in ai_json.get('involved_characters', []):
        if char_name not in existing_char_names:
            dao.add_character(book_name, char_name, change_log=f"首次出现于第{chapter_id}章")

    # 【新增逻辑：5.5 自动提取与更新伏笔】
    planted_fs_list = ai_json.get('planted_foreshadows', [])
    for fs in planted_fs_list:
        fs_name = fs.get('name')
        fs_content = fs.get('content')
        if fs_name and fs_content:
            dao.add_foreshadow(book_name, fs_name, chapter_id, fs_content, status="埋设中")

    revealed_fs_list = ai_json.get('revealed_foreshadows', [])
    for fs_name in revealed_fs_list:
        if fs_name:
            # 自动将前文的旧伏笔更新为“已揭示”
            dao.update_foreshadow(book_name, fs_name, revealed_chapter=chapter_id, status="已揭示")

    # 6. 故事线状态机逻辑（融合了严密的进度推进）
    import time
    is_frontier = True
    analyses = dao.list_chapter_analyses(book_name)
    for an in analyses:
        if an.get('chapter_id', 0) > chapter_id and an.get('summary'):
            is_frontier = False
            break

    if is_frontier:
        action = action_data.get('action', 'MATCH')

        active_main_idx = -1
        for i, p in enumerate(storylines):
            if not p.get('is_completed'):
                active_main_idx = i
                break

        if action == 'NEW_MAIN':
            # 开启新卷：把旧卷打上完成标签
            if active_main_idx != -1:
                storylines[active_main_idx]['is_completed'] = True
                for c in storylines[active_main_idx].get('children', []):
                    c['is_completed'] = True

            new_p = {
                "id": 'p_' + str(int(time.time() * 1000)),
                "name": action_data.get('new_main_name', '初始剧情/新大卷'),
                "content": "", "foreshadows": [], "is_completed": False,
                "children": [{
                    "id": 'c_' + str(int(time.time() * 1000) + 1),
                    "name": action_data.get('new_sub_name', '起始事件'),
                    "content": "", "foreshadows": [], "is_completed": False
                }]
            }
            storylines.append(new_p)
            dao.update_storylines(book_name, storylines)

        elif action == 'NEW_SUB':
            if active_main_idx != -1:
                p = storylines[active_main_idx]
                # 有新事件发生，说明上一个未完成的事件走完了，将其闭环
                if p.get('children'):
                    for c in reversed(p['children']):
                        if not c.get('is_completed'):
                            c['is_completed'] = True
                            break

                p['children'] = p.get('children', [])
                p['children'].append({
                    "id": 'c_' + str(int(time.time() * 1000)),
                    "name": action_data.get('new_sub_name', '新支线事件'),
                    "content": "", "foreshadows": [], "is_completed": False
                })
                dao.update_storylines(book_name, storylines)
            else:
                # 兜底：如果没有大节点，新建一个
                new_p = {
                    "id": 'p_' + str(int(time.time() * 1000)),
                    "name": "初始剧情",
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
            # 精确匹配节点：使用提取到的 current_node
            matched_name = action_data.get('current_node', '')
            if active_main_idx != -1 and matched_name:
                p = storylines[active_main_idx]
                state_changed = False

                # 自动填补跳过的节点状态
                for c in p.get('children', []):
                    if c.get('name') == matched_name:
                        break  # 找到了现在的位置，停止标记
                    if not c.get('is_completed'):
                        c['is_completed'] = True
                        state_changed = True

                if state_changed:
                    dao.update_storylines(book_name, storylines)


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


def cleanup_chapter_data(book_name: str, chapter_id: int):
    """大清洗方法：清除当前章节的所有旧分析数据和向量碎片"""
    # 1. 清理本地 JSON 中的本章分析数据
    dao.delete_chapter_analysis(book_name, chapter_id)
    # 2. 清理向量数据库中的本章碎片
    vector_dao.delete_snippets_by_chapter(book_name, chapter_id)


def run_finalize_pipeline(book_name: str, chapter_id: int, content: str, is_re_final: bool = False):
    """触发并发流水线"""
    if is_re_final:
        # 如果是重新定稿，必须先在主线程把旧数据清理干净！
        cleanup_chapter_data(book_name, chapter_id)

    executor.submit(task_knowledge_analysis, book_name, chapter_id, content)
    executor.submit(task_vector_storage, book_name, chapter_id, content)


def run_finalize_pipeline_stream(book_name: str, chapter_id: int, content: str, is_re_final: bool = False):
    """【感知系统核心】带流式反馈的并发定稿流水线"""
    q = queue.Queue()

    def log_msg(msg):
        """向前端小助手推送消息"""
        q.put(msg)

    def worker():
        try:
            if is_re_final:
                log_msg("🧹 正在清理当前章节的历史残留数据...")
                cleanup_chapter_data(book_name, chapter_id)  # 这里的 cleanup 必须是你刚才加过的那个
                log_msg("✨ 历史数据清理完毕！")

            log_msg("🚀 正在启动后台双轨 AI 引擎...")

            # 包装一下原有的两个任务，加上状态汇报
            def task_a():
                log_msg("🧠 知识分析引擎：开始提取摘要、角色与伏笔...")
                task_knowledge_analysis(book_name, chapter_id, content)
                log_msg("✅ 知识分析引擎：分析完毕，故事线已同步推演！")

            def task_b():
                log_msg("🔪 向量切片引擎：开始寻找高光片段并打标...")
                task_vector_storage(book_name, chapter_id, content)
                log_msg("✅ 向量切片引擎：所有切片入库完毕！")

            future_a = executor.submit(task_a)
            future_b = executor.submit(task_b)

            # 等待两个并发任务全部完成
            wait([future_a, future_b])
            q.put("DONE")
        except Exception as e:
            log_msg(f"❌ 引擎运行出现错误: {str(e)}")
            q.put("DONE")

    # 启动后台主控线程
    threading.Thread(target=worker).start()

    # 持续向前端吐出状态
    while True:
        msg = q.get()
        if msg == "DONE":
            yield f"data: {json.dumps({'content': '🎉 章节定稿全部完成，你可以继续创作啦！'})}\n\n"
            yield "data: [DONE]\n\n"
            break
        else:
            yield f"data: {json.dumps({'content': msg})}\n\n"