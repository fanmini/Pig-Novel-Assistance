# context_builder.py
from base_dao import NovelModel

dao = NovelModel()

def build_global_knowledge(book_name: str) -> str:
    """公共基座1：全书基础知识库 (世界观、简介、条目)"""
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
    """公共基座3：上一章摘要"""
    if current_chapter_id <= 1:
        return "无（当前为第一章，故事刚开始）"
    prev_an = dao.get_chapter_analysis(book_name, current_chapter_id - 1)
    return prev_an.get('summary', '暂无上一章摘要数据') if prev_an else "暂无上一章摘要数据"

def get_micro_details_with_fallback(book_name: str, current_chapter_id: int, active_main_id: str, detail_level: str = 'full') -> str:
    """公共基座4：微观细节与 10 章保底溯源 (原样保留)"""
    # ... (这里粘贴你原来 finalize_service.py 里的 get_micro_details_with_fallback 代码) ...
    pass # 篇幅原因省略，直接剪切过来即可

def build_full_lifecycle_entities(book_name: str, char_names: list = None, faction_names: list = None) -> str:
    """
    公共基座5：出场实体的全生命周期完整档案。
    【优化说明】：增加了参数过滤。如果是定稿，传嗅探到的名字；
    如果是章节生成，传用户在面板【打勾】选中的名字。如果不传，则返回空或全量。
    """
    all_chars = dao.list_characters(book_name)
    all_factions = dao.list_factions(book_name)

    involved_chars = [c for c in all_chars if (char_names is None or c['character_name'] in char_names)]
    involved_factions = [f for f in all_factions if (faction_names is None or f['name'] in faction_names)]

    lines = []
    if involved_chars:
        lines.append("【出场角色完整编年史】:")
        for c in involved_chars:
            lines.append(f"  ▶ 角色:【{c['character_name']}】(重要度: {c.get('importance_level', 1)})")
            lines.append(f"    - 基础画像: {c.get('profile', '暂无')}")
            # ... (把原来拼装弧光、关系网的代码复制过来) ...

    if involved_factions:
        lines.append("【出场势力完整编年史】:")
        for f in involved_factions:
            lines.append(f"  ▶ 势力:【{f['name']}】")
            lines.append(f"    - 宗旨底色: {f.get('description', '暂无')}")
            # ... (把原来拼装势力历史的代码复制过来) ...

    return "\n".join(lines) if lines else "未提供实体档案。"