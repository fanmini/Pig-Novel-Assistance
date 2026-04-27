# finalize_service.py
import json
import os
import queue
import re
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from base_dao import NovelModel
from ai_handler import ai_handler, load_ai_config
from vector_dao import vector_dao
from prompts.chapter_analysis import (
    PROMPT_PLOT_ENGINE_COLD_START, PROMPT_PLOT_ENGINE,
    PROMPT_ENTITY_ENGINE, PROMPT_VECTOR_TAGS
)

dao = NovelModel()
executor = ThreadPoolExecutor(max_workers=3)


def clean_json_string(text: str) -> dict:
    """清理并解析 AI 返回的 JSON 字符串"""
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


# =====================================================================
# 深度上下文拼装工具箱 (精准投喂控制)
# =====================================================================

def build_global_knowledge(book_name: str) -> str:
    """公共基座1：全书基础知识库"""
    book = dao.get_book(book_name) or {}
    lines = [f"【书籍简介】: {book.get('description', '暂无简介')}"]
    for meta in book.get('meta_list', []):
        lines.append(f"【{meta.get('key', '未知条目')}】: {meta.get('value', '')}")
    return "\n".join(lines)


def build_macro_storyline_with_span(storylines: list, analyses: list, active_main_id: str) -> str:
    """公共基座2：宏观大纲，带章节跨度"""
    main_spans = {}
    for an in analyses:
        mid = an.get('bound_main_node_id')
        if mid:
            main_spans.setdefault(mid, []).append(an.get('chapter_id'))

    lines = []
    for p in storylines:
        span = main_spans.get(p['id'], [])
        span_str = f"(第{min(span)}章 - 第{max(span)}章)" if span else "(尚无章节)"
        lines.append(f"【卷/大节点: {p.get('name')}】 {span_str} - 核心起因: {p.get('content')}")
        if p['id'] == active_main_id:
            break
    return "\n".join(lines) if lines else "暂无宏观大纲"


def get_prev_summary(book_name: str, current_chapter_id: int) -> str:
    """公共基座3：严格且独立的“上一章摘要”"""
    if current_chapter_id <= 1:
        return "无（当前为第一章，故事刚开始）"
    prev_an = dao.get_chapter_analysis(book_name, current_chapter_id - 1)
    return prev_an.get('summary', '暂无上一章摘要数据') if prev_an else "暂无上一章摘要数据"


def get_micro_details_with_fallback(book_name: str, current_chapter_id: int, active_main_id: str,
                                    detail_level: str = 'full') -> str:
    """
    微观细节与 10 章强制保底溯源机制
    :param detail_level: 'full' (一轨专用) 或 'lite' (二/三轨专用，不含事实/伏笔/情绪)
    """
    analyses = dao.list_chapter_analyses(book_name)
    foreshadows = dao.list_foreshadows(book_name)

    past_analyses = sorted(
        [a for a in analyses if a.get('chapter_id', 0) < current_chapter_id],
        key=lambda x: x['chapter_id']
    )

    if not past_analyses:
        return "暂无近期微观细节（可能是第一章或前文数据缺失）"

    # 逻辑核心：合并【当前大节点的所有章】和【最近的10章】去重
    current_node_analyses = [a for a in past_analyses if a.get('bound_main_node_id') == active_main_id]
    recent_10_analyses = past_analyses[-10:]

    merged_dict = {a['chapter_id']: a for a in recent_10_analyses}
    for a in current_node_analyses:
        merged_dict[a['chapter_id']] = a

    final_analyses = sorted(merged_dict.values(), key=lambda x: x['chapter_id'])

    lines = []
    for an in final_analyses:
        cid = an.get('chapter_id')

        # 严格的时间线排版
        lines.append(f"【第 {cid} 章】")
        lines.append(f" - 摘要: {an.get('summary', '无')}")
        lines.append(f" - 故事进度: {an.get('story_position', '无')}")

        # 根据 detail_level 控制输出深度
        if detail_level == 'full':
            fs_list = [f for f in foreshadows if f.get('planted_chapter') == cid]
            fs_str = "、".join([f"{f['name']}({f['status']})" for f in fs_list]) if fs_list else "无"
            events = "、".join(an.get('key_events', [])) or "无"

            lines.append(f" - 情绪值: {an.get('emotion_intensity', 1)}")
            lines.append(f" - 事实条目: {events}")
            lines.append(f" - 埋设伏笔: {fs_str}")

        lines.append("")  # 加空行为了美观排版

    return "\n".join(lines).strip()


def build_full_lifecycle_entities(book_name: str, content: str) -> tuple:
    """提取本章出场实体的全生命周期完整档案"""
    all_chars = dao.list_characters(book_name)
    all_factions = dao.list_factions(book_name)

    involved_chars = [c for c in all_chars if c['character_name'] in content]
    involved_factions = [f for f in all_factions if f['name'] in content]

    lines = []
    if involved_chars:
        lines.append("【出场角色完整编年史】:")
        for c in involved_chars:
            lines.append(f"  ▶ 角色:【{c['character_name']}】(重要度: {c.get('importance_level', 1)})")
            lines.append(f"    - 基础画像: {c.get('profile', '暂无')}")

            arc_hist = c.get('arc_history', [])
            if arc_hist:
                lines.append("    - 弧光演变史:")
                for arc in arc_hist:
                    lines.append(f"      * {arc.get('arc_detail')}")
            else:
                lines.append("    - 弧光演变史: 暂无")

            rels = c.get('relationships', [])
            if rels:
                lines.append("    - 人际关系史:")
                for r in rels:
                    hist_str = " -> ".join(r.get('history', []))
                    lines.append(f"      * 对【{r.get('target', '未知')}】: {hist_str}")
            else:
                lines.append("    - 人际关系史: 暂无人际互动")

    if involved_factions:
        lines.append("【出场势力完整编年史】:")
        for f in involved_factions:
            lines.append(f"  ▶ 势力:【{f['name']}】")
            lines.append(f"    - 宗旨底色: {f.get('description', '暂无')}")

            logs = f.get('history_log', [])
            if logs:
                lines.append("    - 历史动态:")
                for log in logs:
                    lines.append(f"      * {log}")

    entities_text = "\n".join(lines) if lines else "本章未发现已知角色或势力。"
    return entities_text, involved_chars, involved_factions


# =====================================================================
# 核心三轨引擎
# =====================================================================

def task_plot_engine(book_name: str, chapter_id: int, content: str, global_knowledge: str, prev_summary: str,
                     ai_config: dict):
    """第一轨：剧情推演引擎 (Full 版资料)"""
    storylines = dao.list_storylines(book_name)
    analyses = dao.list_chapter_analyses(book_name)

    # 获取出场实体的生命周期
    entities_text, _, _ = build_full_lifecycle_entities(book_name, content)

    if chapter_id == 1:
        prompt = PROMPT_PLOT_ENGINE_COLD_START.format(
            global_knowledge=global_knowledge,
            entities_context=entities_text,
            content=content
        )
    else:
        active_main, active_sub = None, None
        active_main_idx = -1
        for i, p in enumerate(storylines):
            if not p.get('is_completed'):
                active_main, active_main_idx = p, i
                for c in p.get('children', []):
                    if not c.get('is_completed'):
                        active_sub = c
                        break
                break

        if not active_main and storylines:
            active_main, active_main_idx = storylines[-1], len(storylines) - 1
            if active_main.get('children'):
                active_sub = active_main['children'][-1]

        active_main_id = active_main['id'] if active_main else ""
        active_sub_id = active_sub['id'] if active_sub else ""

        macro_span_storyline = build_macro_storyline_with_span(storylines, analyses, active_main_id)
        # 第一轨提取 full 级详细微观历史
        micro_details_full = get_micro_details_with_fallback(book_name, chapter_id, active_main_id, detail_level='full')

        prompt = PROMPT_PLOT_ENGINE.format(
            global_knowledge=global_knowledge,
            macro_storyline=macro_span_storyline,
            entities_context=entities_text,
            prev_summary=prev_summary,
            micro_details=micro_details_full,
            current_main_name=active_main.get('name') if active_main else "未知",
            current_sub_name=active_sub.get('name') if active_sub else "未知",
            current_main_id=active_main_id,
            current_sub_id=active_sub_id,
            content=content
        )

    response = ai_handler.chat(
        [{"role": "user", "content": prompt}],
        model=ai_config.get('model', 'openai/gpt-4o-mini'),
        api_key=ai_config.get('api_key', ''),
        max_tokens=int(ai_config.get('max_tokens', 8192)),
        top_p=ai_config.get('top_p', 1.0),
        temperature=0.2
    )
    raw_content = response.choices[0].message.content
    return clean_json_string(raw_content), {"prompt": prompt, "response": raw_content}


def task_entity_engine(book_name: str, chapter_id: int, content: str, global_knowledge: str, prev_summary: str,
                       entities_context: str, ai_config: dict):
    """第二轨：生灵与势力引擎 (Lite 版资料，专攻心理与关系)"""
    storylines = dao.list_storylines(book_name)
    analyses = dao.list_chapter_analyses(book_name)

    active_main_id = ""
    for p in storylines:
        if not p.get('is_completed'):
            active_main_id = p['id']
            break

    macro_span_storyline = build_macro_storyline_with_span(storylines, analyses, active_main_id)
    # 第二轨提取 lite 级精简微观历史
    micro_details_lite = get_micro_details_with_fallback(book_name, chapter_id, active_main_id, detail_level='lite')

    prompt = PROMPT_ENTITY_ENGINE.format(
        global_knowledge=global_knowledge,
        macro_storyline=macro_span_storyline,
        entities_context=entities_context,
        prev_summary=prev_summary,
        micro_details=micro_details_lite,
        content=content
    )

    response = ai_handler.chat(
        [{"role": "user", "content": prompt}],
        model=ai_config.get('model', 'openai/gpt-4o-mini'),
        api_key=ai_config.get('api_key', ''),
        max_tokens=int(ai_config.get('max_tokens', 8192)),
        top_p=ai_config.get('top_p', 1.0),
        temperature=0.3
    )
    raw_content = response.choices[0].message.content
    return clean_json_string(raw_content), {"prompt": prompt, "response": raw_content}


def task_vector_engine(book_name: str, chapter_id: int, content: str, plot_result: dict, global_knowledge: str,
                       prev_summary: str, updated_entities_context: str, ai_config: dict):
    """第三轨：高光与向量引擎 (接收轨一轨二落盘后的最新档案)"""
    storylines = dao.list_storylines(book_name)
    active_main_id = ""
    for p in storylines:
        if not p.get('is_completed'):
            active_main_id = p['id']
            break

    analyses = dao.list_chapter_analyses(book_name)
    macro_span_storyline = build_macro_storyline_with_span(storylines, analyses, active_main_id)
    # 第三轨同样只需要 lite 级精简微观历史
    micro_details_lite = get_micro_details_with_fallback(book_name, chapter_id, active_main_id, detail_level='lite')

    action_data = plot_result.get('storyline_action', {}) if plot_result else {}
    main_name = action_data.get('new_node_name', '当前主线')
    sub_name = action_data.get('new_node_name', '当前事件')

    prompt = PROMPT_VECTOR_TAGS.format(
        global_knowledge=global_knowledge,
        macro_storyline=macro_span_storyline,
        entities_context=updated_entities_context,
        prev_summary=prev_summary,
        micro_details=micro_details_lite,
        current_main_name=main_name,
        current_sub_name=sub_name,
        content=content
    )

    response = ai_handler.chat(
        [{"role": "user", "content": prompt}],
        model=ai_config.get('model', 'openai/gpt-4o-mini'),
        api_key=ai_config.get('api_key', ''),
        max_tokens=int(ai_config.get('max_tokens', 8192)),
        top_p=ai_config.get('top_p', 1.0),
        temperature=0.3
    )

    raw_content = response.choices[0].message.content
    ai_json = clean_json_string(raw_content)

    for item in ai_json.get('snippets', []):
        if item.get('content') and item.get('tags'):
            vector_dao.save_snippet_tags(book_name, chapter_id, item['content'], item['tags'])

    return {"prompt": prompt, "response": raw_content}


# =====================================================================
# 落盘处理中心
# =====================================================================

def _process_and_save_results(book_name: str, chapter_id: int, plot_json: dict, entity_json: dict,
                              known_involved_chars: list):
    """处理并合并一二轨数据，执行状态机推进、伏笔回收和日志追加"""
    storylines = dao.list_storylines(book_name)
    action_data = plot_json.get('storyline_action', {})
    action = action_data.get('action', 'MATCH')

    bound_main_id = action_data.get('current_main_node_id', '')
    bound_sub_id = action_data.get('current_sub_node_id', '')
    new_content = action_data.get('new_node_content') or plot_json.get('summary', '事件推进')
    new_name = action_data.get('new_node_name') or f"新事件(第{chapter_id}章)"

    # ================= 1. 故事线状态机运转 =================
    if action == 'INIT':
        bound_main_id = storylines[0]['id'] if storylines else "p_" + str(int(time.time() * 1000))
        bound_sub_id = "c_" + str(int(time.time() * 1000) + 1)
        if storylines:
            storylines[0]['content'] = action_data.get('main_node_content', '初始起因')
            storylines[0]['children'] = [{
                "id": bound_sub_id, "name": action_data.get('sub_node_name', '初始事件'),
                "content": action_data.get('sub_node_content', '起因'), "foreshadows": [], "is_completed": False
            }]
    else:
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
            if active_sub:
                active_sub['is_completed'] = True
                active_sub['completed_by_chapter'] = chapter_id  # 盖章：本章完结了它

            next_sub = next((c for c in active_main.get('children', []) if not c.get('is_completed')),
                            None) if active_main else None

            if next_sub:
                bound_sub_id = next_sub['id']
                if not next_sub.get('content'): next_sub['content'] = new_content
            else:
                if active_main:
                    active_main['is_completed'] = True
                    active_main['completed_by_chapter'] = chapter_id  # 盖章：本章完结了它
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
                             "is_completed": False, "created_by_chapter": chapter_id}]
                else:
                    action = 'NEW_MAIN'

        if action == 'NEW_MAIN':
            if active_main:
                active_main['is_completed'] = True
                active_main['completed_by_chapter'] = chapter_id
            if active_sub:
                active_sub['is_completed'] = True
                active_sub['completed_by_chapter'] = chapter_id

            bound_main_id = 'p_' + str(int(time.time() * 1000))
            bound_sub_id = 'c_' + str(int(time.time() * 1000) + 1)
            storylines.append({
                "id": bound_main_id, "name": new_name, "content": new_content,
                "foreshadows": [], "is_completed": False, "created_by_chapter": chapter_id,  # 盖章：本章创建
                "children": [{"id": bound_sub_id, "name": "起始事件", "content": new_content, "foreshadows": [],
                              "is_completed": False, "created_by_chapter": chapter_id}]
            })

        elif action == 'NEW_SUB':
            if active_sub:
                active_sub['is_completed'] = True
                active_sub['completed_by_chapter'] = chapter_id
            bound_sub_id = 'c_' + str(int(time.time() * 1000))
            if active_main:
                active_main['children'].append(
                    {"id": bound_sub_id, "name": new_name, "content": new_content, "foreshadows": [],
                     "is_completed": False, "created_by_chapter": chapter_id})  # 盖章：本章创建

    fs_to_bind = [fs['name'] for fs in plot_json.get('planted_foreshadows', []) if fs.get('name')] + \
                 [fs for fs in plot_json.get('revealed_foreshadows', []) if fs]
    if fs_to_bind:
        for p in storylines:
            if p.get('id') == bound_main_id:
                for c in p.get('children', []):
                    if c.get('id') == bound_sub_id:
                        c['foreshadows'] = list(set(c.get('foreshadows', []) + fs_to_bind))
                        break
                break

    dao.update_storylines(book_name, storylines)

    # ================= 2. 统筹角色出场大名单 =================
    discoveries = entity_json.get('new_discoveries', {}) if entity_json else {}
    known_char_names = [c['character_name'] for c in known_involved_chars]
    new_char_names = [nc.get('name') for nc in discoveries.get('new_characters', []) if nc.get('name')]

    changed_char_names = []
    if entity_json:
        for arc in entity_json.get('arc_changes', []):
            if arc.get('character_name'): changed_char_names.append(arc['character_name'])
        for rel in entity_json.get('relationship_changes', []):
            if rel.get('subject'): changed_char_names.append(rel['subject'])

    final_involved_characters = list(set(known_char_names + new_char_names + changed_char_names))
    for pc in plot_json.get('involved_characters', []):
        if pc in [c['character_name'] for c in dao.list_characters(book_name)] and pc not in final_involved_characters:
            final_involved_characters.append(pc)

    # ================= 3. 写入章节分析数据 =================
    dao.add_or_update_chapter_analysis(
        book_name, chapter_id,
        summary=plot_json.get('summary', ''),
        key_events=plot_json.get('key_events', []),
        story_position=action_data.get('progress_desc', plot_json.get('summary', '')),
        emotion_intensity=plot_json.get('emotion_intensity', 1),
        involved_characters=final_involved_characters,
        bound_main_node_id=bound_main_id,
        bound_sub_node_id=bound_sub_id
    )

    # ================= 4. 伏笔落盘 =================
    for fs in plot_json.get('planted_foreshadows', []):
        if fs.get('name') and fs.get('content'):
            dao.add_foreshadow(book_name, fs['name'], chapter_id, fs['content'], status="埋设中")

    for fs_name in plot_json.get('revealed_foreshadows', []):
        if fs_name:
            dao.update_foreshadow(book_name, fs_name, revealed_chapter=chapter_id, status="已揭示")

    # ================= 5. 实体全生命周期演变落盘 =================
    if entity_json:
        current_chars = dao.list_characters(book_name)
        current_factions = dao.list_factions(book_name)
        is_char_changed, is_faction_changed = False, False

        for arc in entity_json.get('arc_changes', []):
            if arc.get('character_name') and arc.get('arc_detail'):
                target = next((c for c in current_chars if c['character_name'] == arc['character_name']), None)
                if target:
                    if 'arc_history' not in target: target['arc_history'] = []
                    new_arc_detail = f"【第{chapter_id}章】：{arc['arc_detail']}"
                    target['arc_history'].append({"chapter_id": chapter_id, "arc_summary": arc.get('arc_summary', ''),
                                                  "arc_detail": new_arc_detail})
                    old_log = target.get('change_log', '')
                    target['change_log'] = f"{old_log}\n{new_arc_detail}".strip() if old_log else new_arc_detail
                    is_char_changed = True

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

        for nc in discoveries.get('new_characters', []):
            if nc.get('name') and not next((c for c in current_chars if c['character_name'] == nc['name']), None):
                init_rels = [
                    {"target": r.get('target'), "history": [f"【第{chapter_id}章初见】：{r.get('relation_detail')}"]} for r
                    in nc.get('initial_relationships', []) if r.get('target') and r.get('relation_detail')]
                init_arc = []
                change_log_text = f"第{chapter_id}章首次登场"
                if nc.get('initial_arc'):
                    change_log_text = f"【第{chapter_id}章登场】：{nc.get('initial_arc')}"
                    init_arc.append(
                        {"chapter_id": chapter_id, "arc_summary": "初始登场状态", "arc_detail": change_log_text})

                current_chars.append(
                    {"character_name": nc['name'], "importance_level": 1, "profile": nc.get('profile', ''),
                     "relationships": init_rels, "change_log": change_log_text, "arc_history": init_arc})
                is_char_changed = True

        for nf in discoveries.get('new_factions', []):
            if nf.get('name') and not next((f for f in current_factions if f['name'] == nf['name']), None):
                current_factions.append(
                    {"name": nf['name'], "description": nf.get('description', ''), "key_figures": [], "history_log": [
                        f"【第{chapter_id}章首次显露】：{nf.get('initial_status', nf.get('description', ''))}"]})
                is_faction_changed = True

        if is_char_changed:
            dao._save_json(os.path.join(dao.data_root, book_name, "characters.json"), current_chars)
        if is_faction_changed:
            dao._save_json(os.path.join(dao.data_root, book_name, "factions.json"), current_factions)


def cleanup_chapter_data(book_name: str, chapter_id: int):
    # 清理章节分析
    dao.delete_chapter_analysis(book_name, chapter_id)
    # 清理向量高光切片
    vector_dao.delete_snippets_by_chapter(book_name, chapter_id)
    # 彻底清理本章埋设/揭示的伏笔及其级联数据
    dao.clean_foreshadows_by_chapter(book_name, chapter_id)
    # 故事线时光倒流：抹除本章对故事线节点的创建与完结记录
    dao.clean_storylines_by_chapter(book_name, chapter_id)


# =====================================================================
# 主流程串联 (彻底贯彻双轨并发 + 单轨串行的时序逻辑)
# =====================================================================

def run_finalize_pipeline_stream(book_name: str, chapter_id: int, content: str, is_re_final: bool = False):
    """带时序控制与状态刷新的流水线核心"""
    q = queue.Queue()
    ai_config = load_ai_config()

    def log_step(engine, status, msg, debug=None):
        step_data = {"type": "step", "engine": engine, "status": status, "msg": msg}
        if debug: step_data["debug"] = debug
        q.put(step_data)

    def worker():
        try:
            log_step("系统清理", "processing", "🧹 正在清理当前章节的历史残留数据...")
            cleanup_chapter_data(book_name, chapter_id)
            log_step("系统清理", "success", "🧹 残留数据清理完成。")

            log_step("主控中心", "processing", "🔍 正在拉取全局公共基座与实体档案...")
            # 1. 提取全书公共基座（基础知识 + 严格上一章摘要）
            global_knowledge = build_global_knowledge(book_name)
            prev_summary = get_prev_summary(book_name, chapter_id)

            # 2. 提取本章出场角色的生命周期完整档案（轨一轨二共用）
            entities_text, involved_chars, _ = build_full_lifecycle_entities(book_name, content)

            log_step("第一轨 (剧情)", "processing", "⏳ 剧情推演引擎正在运算中...")
            plot_future = executor.submit(task_plot_engine, book_name, chapter_id, content, global_knowledge,
                                          prev_summary, ai_config)

            log_step("第二轨 (生灵)", "processing", "⏳ 实体生命周期引擎正在运算中...")
            entity_future = executor.submit(task_entity_engine, book_name, chapter_id, content, global_knowledge,
                                            prev_summary, entities_text, ai_config)

            # --- 等待一、二轨并发完成 ---
            plot_result, plot_debug = plot_future.result()
            log_step("第一轨 (剧情)", "success", "✅ 剧情演进与伏笔推演完毕！", debug=plot_debug)

            entity_result, entity_debug = entity_future.result()
            log_step("第二轨 (生灵)", "success", "✅ 实体演化与新血肉挖掘完毕！", debug=entity_debug)

            # --- 数据统筹合并落盘 ---
            log_step("主控中心", "processing", "💾 正在统筹合并各维度数据，执行安全落盘...")
            _process_and_save_results(book_name, chapter_id, plot_result, entity_result, involved_chars)
            log_step("主控中心", "success", "💾 数据安全落盘完毕！")

            # --- 第三轨：串行启动，拉取最新档案 ---
            log_step("第三轨 (向量)", "processing", "⏳ 正在拉取【落盘后】的最新档案进行打标...")
            # 此时的档案绝对包含了刚刚轨二落盘的新角色和轨一的新角色
            updated_entities_text, _, _ = build_full_lifecycle_entities(book_name, content)

            vector_result = task_vector_engine(book_name, chapter_id, content, plot_result, global_knowledge,
                                               prev_summary, updated_entities_text, ai_config)
            log_step("第三轨 (向量)", "success", "✅ 高光片段已打标并存入知识库！", debug=vector_result)

            q.put("DONE")

        except Exception as e:
            import traceback
            traceback.print_exc()
            log_step("主控中心", "error", f"❌ 引擎运行出现致命错误: {str(e)}")
            q.put("DONE")

    threading.Thread(target=worker).start()

    while True:
        msg = q.get()
        if msg == "DONE":
            yield f"data: {json.dumps({'type': 'step', 'engine': '完成', 'status': 'success', 'msg': '🎉 核心定稿全线跑通！'})}\n\n"
            yield "data: [DONE]\n\n"
            break
        else:
            yield f"data: {json.dumps(msg)}\n\n"