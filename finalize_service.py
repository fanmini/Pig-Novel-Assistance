# finalize_service.py
import json
import os
import queue
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor, wait
from base_dao import NovelModel
from ai_handler import ai_handler, load_ai_config
from vector_dao import vector_dao
from prompts.chapter_analysis import (
    PROMPT_PLOT_ENGINE_COLD_START, PROMPT_PLOT_ENGINE,
    PROMPT_ENTITY_ENGINE, PROMPT_VECTOR_TAGS
)

dao = NovelModel()
# 定义 3 个并发线程，完美适配我们的“三驾马车”
executor = ThreadPoolExecutor(max_workers=3)


def clean_json_string(text: str) -> dict:
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# =====================================================================
# 预扫描与上下文组装模块 (极速本地处理)
# =====================================================================
def build_entities_context(book_name: str, content: str) -> tuple:
    """词法预过滤：极速扫描本章出现的已知角色和势力，并打包快照"""
    all_chars = dao.list_characters(book_name)
    all_factions = dao.list_factions(book_name)

    involved_chars = [c for c in all_chars if c['character_name'] in content]
    involved_factions = [f for f in all_factions if f['name'] in content]

    context_lines = []

    # 打包角色快照（摘要缓冲压缩法）
    if involved_chars:
        context_lines.append("【出场已知角色状态】:")
        for c in involved_chars:
            name = c['character_name']
            arc_history = c.get('arc_history', [])
            if not arc_history:
                arc_str = "暂无弧光记录"
            else:
                arc_parts = [f"[阶段{i + 1}]{arc.get('arc_summary', '')}" for i, arc in enumerate(arc_history[:-1])]
                arc_parts.append(f"[当前最新状态]{arc_history[-1].get('arc_summary', '')}")
                arc_str = " -> ".join(arc_parts)

            rels = c.get('relationships', [])
            rel_str_parts = []
            for r in rels:
                latest_rel = r.get('history', [''])[-1] if isinstance(r.get('history'), list) and r.get(
                    'history') else "暂无细节"
                rel_str_parts.append(f"对【{r.get('target', '未知')}】: {latest_rel}")
            rel_str = " | ".join(rel_str_parts) if rel_str_parts else "暂无人际互动"

            context_lines.append(f"  - 角色【{name}】 | 弧光演进: {arc_str} | 人际互动: {rel_str}")

    # 打包势力快照
    if involved_factions:
        context_lines.append("【涉及已知势力状态】:")
        for f in involved_factions:
            name = f['name']
            latest_log = f.get('history_log', [''])[-1] if f.get('history_log') else "暂无历史波动"
            context_lines.append(f"  - 势力【{name}】 | 宗旨底色: {f.get('description', '')} | 近期态势: {latest_log}")

    entities_context_text = "\n".join(context_lines) if context_lines else "本章未发现已知的角色或势力。"

    return entities_context_text, involved_chars, involved_factions


# =====================================================================
# 三轨并发引擎任务 (独立且纯粹)
# =====================================================================
def task_plot_engine(book_name: str, chapter_id: int, content: str, ai_config: dict):
    """第一轨：剧情推演引擎"""
    book = dao.get_book(book_name)
    storylines = dao.list_storylines(book_name)
    analyses = dao.list_chapter_analyses(book_name)

    if chapter_id == 1:
        prompt = PROMPT_PLOT_ENGINE_COLD_START.format(book_desc=book.get('description', '暂无简介'), content=content)
    else:
        # === 寻找当前活跃节点 ===
        active_main, active_sub = None, None
        active_main_idx, active_sub_idx = -1, -1
        for i, p in enumerate(storylines):
            if not p.get('is_completed'):
                active_main, active_main_idx = p, i
                for j, c in enumerate(p.get('children', [])):
                    if not c.get('is_completed'):
                        active_sub, active_sub_idx = c, j
                        break
                break
        if not active_main and storylines:
            active_main, active_main_idx = storylines[-1], len(storylines) - 1
            if active_main.get('children'):
                active_sub, active_sub_idx = active_main['children'][-1], len(active_main['children']) - 1

        active_main_id = active_main['id'] if active_main else ""
        active_sub_id = active_sub['id'] if active_sub else ""

        # === 提取宏观主干与局部细节 ===
        macro_lines = []
        for p in storylines:
            macro_lines.append(f"卷:【{p.get('name')}】 - 背景:{p.get('content')}")
            for c in p.get('children', []):
                macro_lines.append(f"  节点:【{c.get('name')}】 - 事实:{c.get('content')}")
                if c.get('id') == active_sub_id: break
            if p.get('id') == active_main_id: break

        upcoming_lines = []
        if active_main:
            for c in active_main.get('children', [])[active_sub_idx + 1:]: upcoming_lines.append(
                f"预设小节点:【{c.get('name')}】")
            for p in storylines[active_main_idx + 1: active_main_idx + 3]:
                upcoming_lines.append(f"预设大卷:【{p.get('name')}】")
                for c in p.get('children', []): upcoming_lines.append(f"  预设小节点:【{c.get('name')}】")

        progress_lines = [f"第{an['chapter_id']}章: {an.get('story_position', '')}" for an in
                          sorted(analyses, key=lambda x: x.get('chapter_id', 0)) if
                          an.get('bound_sub_node_id') == active_sub_id]

        prev_an = dao.get_chapter_analysis(book_name, chapter_id - 1)

        prompt = PROMPT_PLOT_ENGINE.format(
            macro_storyline="\n".join(macro_lines),
            current_main_name=active_main.get('name') if active_main else "未知",
            current_sub_name=active_sub.get('name') if active_sub else "未知",
            current_node_progress="\n".join(progress_lines) if progress_lines else "暂无",
            upcoming_storyline="\n".join(upcoming_lines) if upcoming_lines else "暂无",
            prev_summary=prev_an.get('summary', '暂无') if prev_an else "暂无",
            current_main_id=active_main_id,
            current_sub_id=active_sub_id,
            content=content
        )

    response = ai_handler.chat([{"role": "user", "content": prompt}],
                               model=ai_config.get('model', 'openai/gpt-4o-mini'), api_key=ai_config.get('api_key', ''),
                               temperature=0.2)
    return clean_json_string(response.choices[0].message.content)


def task_entity_engine(book_name: str, content: str, entities_context_text: str, ai_config: dict):
    """第二轨：生灵与势力引擎 (专注实体状态演进与挖掘)"""
    prompt = PROMPT_ENTITY_ENGINE.format(entities_context=entities_context_text, content=content)
    response = ai_handler.chat([{"role": "user", "content": prompt}],
                               model=ai_config.get('model', 'openai/gpt-4o-mini'), api_key=ai_config.get('api_key', ''),
                               temperature=0.3)
    return clean_json_string(response.choices[0].message.content)


def task_vector_engine(book_name: str, chapter_id: int, content: str, plot_result: dict, ai_config: dict):
    """第三轨：高光与向量引擎"""
    action_data = plot_result.get('storyline_action', {}) if plot_result else {}
    main_name = action_data.get('new_node_name', '当前主线')
    sub_name = action_data.get('new_node_name', '当前事件')

    prompt = PROMPT_VECTOR_TAGS.format(current_main_name=main_name, current_sub_name=sub_name, content=content)
    response = ai_handler.chat([{"role": "user", "content": prompt}],
                               model=ai_config.get('model', 'openai/gpt-4o-mini'), api_key=ai_config.get('api_key', ''),
                               temperature=0.3)
    ai_json = clean_json_string(response.choices[0].message.content)

    for item in ai_json.get('snippets', []):
        if item.get('content') and item.get('tags'):
            vector_dao.save_snippet_tags(book_name, chapter_id, item['content'], item['tags'])


# =====================================================================
# 流水线总控与数据落盘 (统一协调)
# =====================================================================
def _process_and_save_results(book_name: str, chapter_id: int, plot_json: dict, entity_json: dict,
                              involved_chars: list):
    """处理并合并三个引擎的数据，执行状态机推进和日志追加"""
    storylines = dao.list_storylines(book_name)
    action_data = plot_json.get('storyline_action', {})
    action = action_data.get('action', 'MATCH')

    bound_main_id = action_data.get('current_main_node_id', '')
    bound_sub_id = action_data.get('current_sub_node_id', '')
    new_content = action_data.get('new_node_content') or plot_json.get('summary', '事件推进')
    new_name = action_data.get('new_node_name') or f"新事件(第{chapter_id}章)"

    # --- 1. 处理剧情状态机 (NEXT_PREPLANNED, NEW_MAIN, NEW_SUB, INIT) ---
    if action == 'INIT':
        bound_main_id = storylines[0]['id'] if storylines else "p_" + str(int(time.time() * 1000))
        bound_sub_id = "c_" + str(int(time.time() * 1000) + 1)
        if storylines:
            storylines[0]['content'] = action_data.get('main_node_content', '初始起因')
            storylines[0]['children'] = [{"id": bound_sub_id, "name": action_data.get('sub_node_name', '初始事件'),
                                          "content": action_data.get('sub_node_content', '起因'), "foreshadows": [],
                                          "is_completed": False}]
    else:
        # 寻找指针
        active_main, active_sub = None, None
        for p in storylines:
            if p['id'] == bound_main_id:
                active_main = p
                for c in p.get('children', []):
                    if c['id'] == bound_sub_id:
                        active_sub = c
                        break
                break

        if action == 'NEXT_PREPLANNED':
            if active_sub: active_sub['is_completed'] = True
            next_sub = next((c for c in active_main.get('children', []) if not c.get('is_completed')),
                            None) if active_main else None
            if next_sub:
                bound_sub_id = next_sub['id']
                if not next_sub.get('content'): next_sub['content'] = new_content
            else:
                if active_main: active_main['is_completed'] = True
                next_main = next((p for p in storylines if not p.get('is_completed')), None)
                if next_main:
                    bound_main_id = next_main['id']
                    if not next_main.get('content'): next_main['content'] = new_content
                    if next_main.get('children'):
                        bound_sub_id = next_main['children'][0]['id']
                    else:
                        bound_sub_id = 'c_' + str(int(time.time() * 1000))
                        next_main['children'] = [
                            {"id": bound_sub_id, "name": "起始事件", "content": new_content, "foreshadows": [],
                             "is_completed": False}]
                else:
                    action = 'NEW_MAIN'  # 兜底

        if action == 'NEW_MAIN':
            if active_main: active_main['is_completed'] = True
            if active_sub: active_sub['is_completed'] = True
            bound_main_id, bound_sub_id = 'p_' + str(int(time.time() * 1000)), 'c_' + str(int(time.time() * 1000) + 1)
            storylines.append({"id": bound_main_id, "name": new_name, "content": new_content, "foreshadows": [],
                               "is_completed": False, "children": [
                    {"id": bound_sub_id, "name": "起始事件", "content": new_content, "foreshadows": [],
                     "is_completed": False}]})
        elif action == 'NEW_SUB':
            if active_sub: active_sub['is_completed'] = True
            bound_sub_id = 'c_' + str(int(time.time() * 1000))
            if active_main: active_main['children'].append(
                {"id": bound_sub_id, "name": new_name, "content": new_content, "foreshadows": [],
                 "is_completed": False})

    # 伏笔自动绑定
    fs_to_bind = [fs['name'] for fs in plot_json.get('planted_foreshadows', []) if fs.get('name')] + [fs for fs in
                                                                                                      plot_json.get(
                                                                                                          'revealed_foreshadows',
                                                                                                          []) if fs]
    if fs_to_bind:
        for p in storylines:
            if p.get('id') == bound_main_id:
                for c in p.get('children', []):
                    if c.get('id') == bound_sub_id:
                        c['foreshadows'] = list(set(c.get('foreshadows', []) + fs_to_bind))
                        break
                break
    dao.update_storylines(book_name, storylines)

    # --- 2. 写入分析数据与伏笔 ---
    dao.add_or_update_chapter_analysis(
        book_name, chapter_id, summary=plot_json.get('summary', ''), key_events=plot_json.get('key_events', []),
        story_position=action_data.get('progress_desc', plot_json.get('summary', '')),
        emotion_intensity=plot_json.get('emotion_intensity', 1),
        involved_characters=plot_json.get('involved_characters', [c['character_name'] for c in involved_chars]),
        bound_main_node_id=bound_main_id, bound_sub_node_id=bound_sub_id
    )
    for fs in plot_json.get('planted_foreshadows', []):
        if fs.get('name') and fs.get('content'): dao.add_foreshadow(book_name, fs['name'], chapter_id, fs['content'],
                                                                    status="埋设中")
    for fs_name in plot_json.get('revealed_foreshadows', []):
        if fs_name: dao.update_foreshadow(book_name, fs_name, revealed_chapter=chapter_id, status="已揭示")

    # --- 3. 处理实体状态变动 (追加日志与新发现) ---
    if entity_json:
        current_chars = dao.list_characters(book_name)
        current_factions = dao.list_factions(book_name)
        is_char_changed, is_faction_changed = False, False

        # 弧光追加
        for arc in entity_json.get('arc_changes', []):
            if arc.get('character_name') and arc.get('arc_detail'):
                target = next((c for c in current_chars if c['character_name'] == arc['character_name']), None)
                if target:
                    if 'arc_history' not in target: target['arc_history'] = []
                    target['arc_history'].append({"chapter_id": chapter_id, "arc_summary": arc.get('arc_summary', ''),
                                                  "arc_detail": f"【第{chapter_id}章】：{arc['arc_detail']}"})
                    is_char_changed = True

        # 关系追加
        for rel in entity_json.get('relationship_changes', []):
            if rel.get('subject') and rel.get('target') and rel.get('relation_detail'):
                subj = next((c for c in current_chars if c['character_name'] == rel['subject']), None)
                if subj:
                    if 'relationships' not in subj: subj['relationships'] = []
                    t_rel = next((r for r in subj['relationships'] if r.get('target') == rel['target']), None)
                    if not t_rel:
                        t_rel = {"target": rel['target'], "history": []}
                        subj['relationships'].append(t_rel)
                    t_rel['history'].append(f"【第{chapter_id}章】：{rel['relation_detail']}")
                    is_char_changed = True

        # 势力态势追加
        for f_change in entity_json.get('faction_changes', []):
            if f_change.get('faction_name') and f_change.get('change_detail'):
                fac = next((f for f in current_factions if f['name'] == f_change['faction_name']), None)
                if fac:
                    if 'history_log' not in fac: fac['history_log'] = []
                    fac['history_log'].append(f"【第{chapter_id}章】：{f_change['change_detail']}")
                    is_faction_changed = True

        # 挖掘新角色与势力
        discoveries = entity_json.get('new_discoveries', {})
        for nc in discoveries.get('new_characters', []):
            if nc.get('name') and not next((c for c in current_chars if c['character_name'] == nc['name']), None):
                current_chars.append(
                    {"character_name": nc['name'], "importance_level": 1, "profile": nc.get('profile', ''),
                     "relationships": [], "change_log": f"第{chapter_id}章首次登场", "arc_history": []})
                is_char_changed = True
        for nf in discoveries.get('new_factions', []):
            if nf.get('name') and not next((f for f in current_factions if f['name'] == nf['name']), None):
                current_factions.append(
                    {"name": nf['name'], "description": nf.get('description', ''), "key_figures": [],
                     "history_log": [f"【第{chapter_id}章首次显露】：{nf.get('description', '')}"]})
                is_faction_changed = True

        if is_char_changed: dao._save_json(os.path.join(dao.data_root, book_name, "characters.json"), current_chars)
        if is_faction_changed: dao._save_json(os.path.join(dao.data_root, book_name, "factions.json"), current_factions)


def cleanup_chapter_data(book_name: str, chapter_id: int):
    dao.delete_chapter_analysis(book_name, chapter_id)
    vector_dao.delete_snippets_by_chapter(book_name, chapter_id)


def run_finalize_pipeline_stream(book_name: str, chapter_id: int, content: str, is_re_final: bool = False):
    """【终极架构】带预扫描和三轨并发的定稿流水线"""
    q = queue.Queue()
    ai_config = load_ai_config()

    def log_msg(msg):
        q.put(msg)

    def worker():
        try:
            if is_re_final:
                log_msg("🧹 正在清理当前章节的历史残留数据...")
                cleanup_chapter_data(book_name, chapter_id)

            log_msg("🔍 [主控] 正在极速扫描本章登场实体，打包专属记忆库...")
            entities_context_text, involved_chars, _ = build_entities_context(book_name, content)

            log_msg("🚀 [主控] 启动【三轨并发 AI 引擎】...")

            # --- 并发启动三驾马车 ---
            plot_future = executor.submit(task_plot_engine, book_name, chapter_id, content, ai_config)
            entity_future = executor.submit(task_entity_engine, book_name, content, entities_context_text, ai_config)

            # 等待剧情引擎完成，拿到结构数据再跑向量打标会更准
            plot_result = plot_future.result()
            log_msg("✅ [轨一] 剧情世界观引擎推演完毕！")

            vector_future = executor.submit(task_vector_engine, book_name, chapter_id, content, plot_result, ai_config)

            entity_result = entity_future.result()
            log_msg("✅ [轨二] 生灵势力引擎状态结算与挖掘完毕！")

            vector_future.result()
            log_msg("✅ [轨三] 高光片段向量存储与打标完毕！")

            log_msg("💾 [主控] 正在统筹合并所有维度数据，执行安全落盘...")
            _process_and_save_results(book_name, chapter_id, plot_result, entity_result, involved_chars)

            q.put("DONE")
        except Exception as e:
            log_msg(f"❌ 引擎运行出现错误: {str(e)}")
            q.put("DONE")

    threading.Thread(target=worker).start()

    while True:
        msg = q.get()
        if msg == "DONE":
            yield f"data: {json.dumps({'content': '🎉 三轨定稿全部完成！大纲、人设、势力全面推进！'})}\n\n"
            yield "data: [DONE]\n\n"
            break
        else:
            yield f"data: {json.dumps({'content': msg})}\n\n"