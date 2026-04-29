# context_builder.py
import re

from base_dao import NovelModel

dao = NovelModel()

def _filter_future_logs(log_str: str, max_chapter_id: int) -> str:
    """辅助：滤除大于等于 max_chapter_id 的历史记录"""
    if not log_str: return ""
    lines = log_str.split('\n')
    valid_lines = []
    for line in lines:
        match = re.search(r'【第(\d+)章', line)
        if match and int(match.group(1)) >= max_chapter_id:
            continue
        valid_lines.append(line)
    return '\n'.join(valid_lines)

def _filter_future_list(log_list: list, max_chapter_id: int) -> list:
    """辅助：滤除大于等于 max_chapter_id 的列表形式记录"""
    valid_lines = []
    for line in log_list:
        match = re.search(r'【第(\d+)章', line)
        if match and int(match.group(1)) >= max_chapter_id:
            continue
        valid_lines.append(line)
    return valid_lines

def build_global_knowledge(book_name: str) -> str:
    """公共基座 1：全书基础知识库 (世界观、简介、核心设定)"""
    book = dao.get_book(book_name) or {}
    lines = [f"【书籍简介】: {book.get('description', '暂无简介')}"]
    for meta in book.get('meta_list', []):
        lines.append(f"【{meta.get('key', '未知设定')}】: {meta.get('value', '')}")
    return "\n".join(lines)


def build_macro_storyline(book_name: str, active_main_id: str) -> str:
    """公共基座 2：宏观金字塔大纲 (从头遍历到当前活跃大节点)"""
    storylines = dao.list_storylines(book_name)
    lines = []

    for p in storylines:
        status_str = "✅已完结" if p.get('is_completed') else "🔄进行中"
        lines.append(f"【大节点：{p.get('name')}】 {status_str}")
        lines.append(f"  └─ 核心内容: {p.get('content', '暂无描述')}")

        # 只有当到达“当前正在进行的大节点”时，才展开内部的小节点详情
        if p['id'] == active_main_id:
            for c in p.get('children', []):
                c_status = "✅已完结" if c.get('is_completed') else "🔄进行中"
                lines.append(f"    ▶ 【当前大节点下的子节点：{c.get('name')}】 {c_status}")
                lines.append(f"      └─ 核心内容: {c.get('content', '暂无描述')}")
            break  # 不再透传未来的大节点，防止 AI 剧透或混淆

    return "\n".join(lines) if lines else "暂无宏观大纲"


def build_micro_details(book_name: str, current_chapter_id: int, history_limit: int = 10) -> str:
    """
    公共基座 3：微观细节 (最近 N 章的具体详情)。
    完美解决痛点：包含了摘要、事件、情绪，以及最重要的——【伏笔的具体内容】。
    也同时替代了以前废柴的 prev_summary。
    """
    analyses = dao.list_chapter_analyses(book_name)
    foreshadows = dao.list_foreshadows(book_name)

    # 筛选出最近的 N 章分析记录
    recent_analyses = [an for an in analyses if an.get('chapter_id', 0) < current_chapter_id]
    recent_analyses = sorted(recent_analyses, key=lambda x: x['chapter_id'])[-history_limit:]

    if not recent_analyses:
        return "暂无近期章节记录（当前为故事起始阶段）。"

    lines = []
    for an in recent_analyses:
        cid = an['chapter_id']
        lines.append(f"【第 {cid} 章】:")
        lines.append(f"  - 摘要: {an.get('summary', '')}")
        lines.append(f"  - 情绪值: {an.get('emotion_intensity', 1)}")
        if an.get('key_events'):
            lines.append(f"  - 核心事件: {', '.join(an.get('key_events', []))}")

        # 【关键修复】查出在这一章埋设的所有伏笔的具体内容！
        planted_fs = [f for f in foreshadows if f.get("planted_chapter") == cid]
        if planted_fs:
            fs_details = [f"[{f.get('name')}]: {f.get('content')}" for f in planted_fs]
            lines.append(f"  - 本章埋设伏笔: {' | '.join(fs_details)}")

    return "\n".join(lines)


def build_full_lifecycle_entities(book_name: str, char_names: list = None, faction_names: list = None,
                                  max_chapter_id: int = None) -> str:
    """公共基座 4：出场实体的全生命周期完整档案 (已支持时光倒流，自动剥离未来剧透)"""
    all_chars = dao.list_characters(book_name)
    all_factions = dao.list_factions(book_name)

    involved_chars = [c for c in all_chars if (char_names is None or c['character_name'] in char_names)]
    involved_factions = [f for f in all_factions if (faction_names is None or f['name'] in faction_names)]

    lines = []
    if involved_chars:
        lines.append("【出场角色完整编年史】:")
        for c in involved_chars:
            # 时光倒流：如果这章之前他还没出场，直接隐身，不给AI投喂
            first_appear = None
            if c.get('arc_history'):
                first_appear = c['arc_history'][0].get('chapter_id')
            if max_chapter_id and first_appear and first_appear >= max_chapter_id:
                continue

            lines.append(f"  ▶ 角色:【{c['character_name']}】(重要度: {c.get('importance_level', 1)})")
            lines.append(f"    - 基础画像: {c.get('profile', '暂无')}")

            change_log = c.get('change_log', '')
            if max_chapter_id:
                change_log = _filter_future_logs(change_log, max_chapter_id)

            if change_log:
                lines.append(f"    - 历史演变:\n      {change_log.replace(chr(10), chr(10) + '      ')}")

            rels = c.get('relationships', [])
            if rels:
                rel_lines = []
                for r in rels:
                    target = r.get('target')
                    history = r.get('history', [])
                    if max_chapter_id:
                        history = _filter_future_list(history, max_chapter_id)
                    if history:
                        rel_lines.append(f"{target}: {history[-1]}")
                if rel_lines:
                    lines.append(f"    - 核心关系:\n      " + "\n      ".join(rel_lines))

    if involved_factions:
        lines.append("【出场势力完整编年史】:")
        for f in involved_factions:
            history_log = f.get('history_log', [])
            if max_chapter_id:
                history_log = _filter_future_list(history_log, max_chapter_id)

            if max_chapter_id and not history_log and f.get('history_log'):
                continue  # 时光倒流：此时势力尚未暴露

            lines.append(f"  ▶ 势力:【{f['name']}】")
            lines.append(f"    - 宗旨底色: {f.get('description', '暂无')}")
            if history_log:
                lines.append(f"    - 势力动态:\n      " + "\n      ".join(history_log))

    return "\n".join(lines) if lines else "未提供或未检索到相关实体档案。"