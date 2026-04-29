# generate_service.py
import json
import re
from context_builder import *
from vector_dao import vector_dao
from ai_handler import ai_handler, load_ai_config
from prompts.chapter_generation import PROMPT_PLAN_AND_QUERY, PROMPT_GENERATE_CONTENT


def clean_json_string(text: str) -> dict:
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match: text = match.group(1)
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {}


def generate_chapter_plan(book_name: str, chapter_id: int, user_draft: str) -> dict:
    """阶段一：接收用户草稿，生成【规划】与【检索词】"""
    ai_config = load_ai_config()
    global_knowledge = build_global_knowledge(book_name)

    # 【时光倒流1】：如果这章以前定稿过，强行找回它的老节点，屏蔽后续大纲
    storylines = dao.list_storylines(book_name)
    analyses = dao.list_chapter_analyses(book_name)
    existing_analysis = next((an for an in analyses if an.get("chapter_id") == chapter_id), None)
    active_main_id = existing_analysis.get("bound_main_node_id") if existing_analysis else ""

    if not active_main_id:
        active_main_id = next((p['id'] for p in storylines if not p.get('is_completed')), "")

    macro_storyline = build_macro_storyline(book_name, active_main_id)
    micro_details = build_micro_details(book_name, chapter_id)

    all_chars = dao.list_characters(book_name)
    all_factions = dao.list_factions(book_name)
    involved_chars = [c['character_name'] for c in all_chars if c['character_name'] in user_draft]
    involved_factions = [f['name'] for f in all_factions if f['name'] in user_draft]

    # 【时光倒流2】：传 max_chapter_id 屏蔽未来的人物和势力档案
    entities_context = build_full_lifecycle_entities(
        book_name, char_names=involved_chars,
        faction_names=involved_factions, max_chapter_id=chapter_id
    )

    # 2. 组装 Prompt (将新增的变量填入格式化字符串)
    prompt = PROMPT_PLAN_AND_QUERY.format(
        global_knowledge=global_knowledge,
        entities_context=entities_context,
        macro_storyline=macro_storyline,
        micro_details=micro_details,
        user_draft=user_draft
    )

    # 3. 调用 AI (非流式，要求严格 JSON)
    response = ai_handler.chat(
        messages=[{"role": "user", "content": prompt}],
        model=ai_config.get('model', 'openai/gpt-4o-mini'),
        api_key=ai_config.get('api_key', ''),
        max_tokens=2048,
        temperature=0.3
    )

    raw_content = response.choices[0].message.content
    parsed = clean_json_string(raw_content)

    # 将调试信息打包进 JSON 返回给前端
    parsed['debug_info'] = {
        "engine": "章节生成 - 第一阶段：意图解析",
        "debug": {
            "prompt": prompt,
            "response": raw_content
        }
    }
    return parsed

def query_vector_knowledge(book_name: str, tags: list) -> list:
    """阶段二：去向量数据库查询片段"""
    return vector_dao.query_snippets(book_name, tags, n_results=2)


def generate_chapter_content_stream(book_name: str, chapter_id: int, content_plan: str,
                                    selected_chars: list, retrieved_snippets: list):
    """阶段三：大模型正式流式打字生成正文"""
    ai_config = load_ai_config()

    global_knowledge = build_global_knowledge(book_name)

    # 【核心：Context Control】只投喂前端用户打勾选中的角色和势力！
    entities_context = build_full_lifecycle_entities(book_name, char_names=selected_chars, max_chapter_id=chapter_id)

    # 拼装从知识库搜出来的结果文本
    snippets_text = "暂无相关历史片段。"
    if retrieved_snippets:
        lines = []
        for item in retrieved_snippets:
            query = item.get('query')
            for snip in item.get('snippets', []):
                lines.append(
                    f"[针对'{query}'查到的资料 (来源第{snip.get('chapter_id')}章)]:\n{snip.get('original_text')}\n")
        snippets_text = "\n".join(lines)

    prompt = PROMPT_GENERATE_CONTENT.format(
        global_knowledge=global_knowledge,
        entities_context=entities_context,
        retrieved_snippets=snippets_text,
        content_plan=content_plan
    )

    # 返回流式 Generator 供 Flask 推送 SSE
    stream = ai_handler.chat(
        [{"role": "user", "content": prompt}],
        model=ai_config.get('model', 'openai/gpt-4o-mini'),
        api_key=ai_config.get('api_key', ''),
        max_tokens=int(ai_config.get('max_tokens', 8192)),
        top_p=ai_config.get('top_p', 1.0),
        temperature=ai_config.get('temperature', 0.8),  # 生成正文，温度稍微高一点以增加文采
        stream=True
    )

    return stream, prompt