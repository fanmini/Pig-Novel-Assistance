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
        # 【新增】：判断是否启用，未设置(旧数据)默认视为True启用
        if meta.get('enabled', True):
            lines.append(f"【{meta.get('key', '未知设定')}】: {meta.get('value', '')}")
    return "\n".join(lines)


def build_macro_storyline(book_name: str, active_main_id: str) -> str:
    """公共基座 2：宏观金字塔大纲 (从头遍历到当前活跃大节点，并增加章节顺序感)"""
    storylines = dao.list_storylines(book_name)
    analyses = dao.list_chapter_analyses(book_name)

    # 统计每个节点绑定的章节范围
    node_chapters = {}
    for an in analyses:
        cid = an.get('chapter_id')
        main_id = an.get('bound_main_node_id')
        sub_id = an.get('bound_sub_node_id')
        if main_id:
            node_chapters.setdefault(main_id, []).append(cid)
        if sub_id:
            node_chapters.setdefault(sub_id, []).append(cid)

    lines = []
    for p in storylines:
        p_chaps = node_chapters.get(p['id'], [])
        range_str = f" (第{min(p_chaps)}-{max(p_chaps)}章)" if p_chaps else ""
        status_str = "✅已完结" if p.get('is_completed') else "🔄进行中"

        lines.append(f"【大节点：{p.get('name')}】{range_str} {status_str}")
        lines.append(f"  └─ 核心内容: {p.get('content', '暂无描述')}")

        if p['id'] == active_main_id:
            for c in p.get('children', []):
                c_chaps = node_chapters.get(c['id'], [])
                c_range_str = f" (第{min(c_chaps)}-{max(c_chaps)}章)" if c_chaps else ""
                c_status = "✅已完结" if c.get('is_completed') else "🔄进行中"
                lines.append(f"    ▶ 【当前大节点下的子节点：{c.get('name')}】{c_range_str} {c_status}")
                lines.append(f"      └─ 核心内容: {c.get('content', '暂无描述')}")
            break

    return "\n".join(lines) if lines else "暂无宏观大纲"


def build_micro_details(book_name: str, current_chapter_id: int, history_limit: int = 10) -> str:
    """公共基座 3：微观细节 (最近 N 章的具体详情)。"""
    analyses = dao.list_chapter_analyses(book_name)

    # 筛选出最近的 N 章分析记录
    recent_analyses = [an for an in analyses if an.get('chapter_id', 0) < current_chapter_id]
    recent_analyses = sorted(recent_analyses, key=lambda x: x['chapter_id'])[-history_limit:]

    if not recent_analyses:
        return "暂无近期章节记录（当前为故事起始阶段）。"

    lines = []
    for an in recent_analyses:
        cid = an['chapter_id']
        lines.append(f"【第 {cid} 章】:")

        # 针对上一章（前一章）：去摘要，给完整正文
        if cid == current_chapter_id - 1:
            events = an.get('key_events', [])
            if events:
                lines.append(f"  - 核心事件: {', '.join(events)}")
            else:
                lines.append(f"  - 核心事件: 暂无记录")

            # 抓取上一章的完整正文
            prev_chapter = dao.get_chapter(book_name, cid)
            if prev_chapter and prev_chapter.get('content', '').strip():
                lines.append(f"  - 完整正文:\n{prev_chapter.get('content')}\n")
            else:
                lines.append("  - 完整正文: (暂无内容)\n")

        # 针对更早的历史章节：给摘要和核心事件
        else:
            summary = an.get('summary', '').strip()
            lines.append(f"  - 摘要: {summary if summary else '暂无摘要'}")

            events = an.get('key_events', [])
            if events:
                lines.append(f"  - 核心事件: {', '.join(events)}")
            else:
                lines.append(f"  - 核心事件: 暂无记录")

    return "\n".join(lines)


def build_full_lifecycle_entities(book_name: str, char_names: list = None, faction_names: list = None,
                                  max_chapter_id: int = None) -> str:
    """公共基座 4：出场实体的全生命周期完整档案"""
    all_chars = dao.list_characters(book_name)
    all_factions = dao.list_factions(book_name)

    involved_chars = [c for c in all_chars if (char_names is None or c['character_name'] in char_names)]
    involved_factions = [f for f in all_factions if (faction_names is None or f['name'] in faction_names)]

    lines = []
    if involved_chars:
        lines.append("【出场角色完整编年史】:")
        for c in involved_chars:
            first_appear = None
            if c.get('arc_history'):
                first_appear = c['arc_history'][0].get('chapter_id')
            if max_chapter_id and first_appear and first_appear >= max_chapter_id:
                continue


            # 基础画像兜底
            profile = c.get('profile', '').strip()
            lines.append(f"  ▶ 角色:【{c['character_name']}】(重要度: {c.get('importance_level', 1)})")
            lines.append(f"    - 基础画像: {profile if profile else '暂无基础画像'}")

            # 个人信息
            personal_info = c.get('personal_info', '').strip()
            lines.append(f"    - 个人信息: {personal_info if personal_info else '暂无个人信息'}")

            # 历史演变兜底
            change_log = c.get('change_log', '')
            if max_chapter_id:
                change_log = _filter_future_logs(change_log, max_chapter_id)

            if change_log.strip():
                lines.append(f"    - 历史演变:\n      {change_log.replace(chr(10), chr(10) + '      ')}")
            else:
                lines.append("    - 历史演变: 暂无记录")

            # 核心关系兜底
            rels = c.get('relationships', [])
            rel_lines = []
            if rels:
                for r in rels:
                    target = r.get('target')
                    history = r.get('history', [])
                    if max_chapter_id:
                        history = _filter_future_list(history, max_chapter_id)
                    if history:
                        rel_lines.append(f"{target}: {history[-1]}")

            if rel_lines:
                lines.append(f"    - 核心关系:\n      " + "\n      ".join(rel_lines))
            else:
                lines.append("    - 核心关系: 暂无记录")

    if involved_factions:
        lines.append("【出场势力完整编年史】:")
        for f in involved_factions:
            history_log = f.get('history_log', [])
            if max_chapter_id:
                history_log = _filter_future_list(history_log, max_chapter_id)

            if max_chapter_id and not history_log and f.get('history_log'):
                continue

            desc = f.get('description', '').strip()
            lines.append(f"  ▶ 势力:【{f['name']}】")
            lines.append(f"    - 宗旨底色: {desc if desc else '暂无说明'}")

            # 势力动态兜底
            if history_log:
                lines.append(f"    - 势力动态:\n      " + "\n      ".join(history_log))
            else:
                lines.append("    - 势力动态: 暂无记录")

    return "\n".join(lines) if lines else "未提供或未检索到相关实体档案。"