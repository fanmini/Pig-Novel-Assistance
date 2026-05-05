import json
import uuid

from flask import Blueprint, request, jsonify, Response

from entity_shaping_service import generate_entity_shaping
from finalize_service import run_finalize_pipeline_stream, cleanup_chapter_data
from ai_handler import ai_handler, load_ai_config, save_ai_config
from base_dao import NovelModel
from generate_service import generate_chapter_plan, query_vector_knowledge, generate_chapter_content_stream
from prompt_manager import prompt_manager
from storyline_service import generate_storyline_summary
from vector_dao import vector_dao

api_bp = Blueprint('api', __name__)
dao = NovelModel()


# ---------- 书籍 ----------
@api_bp.route('/books', methods=['GET'])
def list_books():
    return jsonify(dao.list_books())

@api_bp.route('/books', methods=['POST'])
def create_book():
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'error': '书名不能为空'}), 400
    success = dao.create_book(name, description=data.get('description', ''),
                              sort_order=data.get('sort_order', 0),
                              meta_list=data.get('meta_list', []))
    if success:
        return jsonify({'message': '创建成功'}), 201
    return jsonify({'error': '书籍已存在'}), 409

@api_bp.route('/books/<name>', methods=['GET'])
def get_book(name):
    book = dao.get_book(name)
    if book:
        return jsonify(book)
    return jsonify({'error': '书籍不存在'}), 404

@api_bp.route('/books/<name>', methods=['PUT'])
def update_book(name):
    data = request.json
    success = dao.update_book(name, **data)
    if success:
        return jsonify({'message': '更新成功'})
    return jsonify({'error': '更新失败'}), 400

@api_bp.route('/books/<name>', methods=['DELETE'])
def delete_book(name):
    success = dao.delete_book(name)
    if success:
        vector_dao.delete_collection(name)
        return jsonify({'message': '删除成功'})
    return jsonify({'error': '删除失败'}), 400

# ---------- 章节 ----------
@api_bp.route('/books/<book_name>/chapters', methods=['GET'])
def list_chapters(book_name):
    chapters = dao.list_chapters(book_name)
    return jsonify(chapters)

@api_bp.route('/books/<book_name>/chapters', methods=['POST'])
def add_chapter(book_name):
    data = request.json
    chap_id = data.get('id')
    if not chap_id:
        return jsonify({'error': '缺少章节id'}), 400
    success = dao.add_chapter(book_name, chap_id, data.get('title', ''),
                              data.get('content', ''), data.get('status', False))
    if success:
        return jsonify({'message': '添加成功'}), 201
    return jsonify({'error': '章节id已存在'}), 409

@api_bp.route('/books/<book_name>/chapters/<int:chapter_id>', methods=['PUT'])
def update_chapter(book_name, chapter_id):
    data = request.json
    success = dao.update_chapter(book_name, chapter_id, **data)
    if success:
        return jsonify({'message': '更新成功'})
    return jsonify({'error': '章节不存在'}), 404

@api_bp.route('/books/<book_name>/chapters/<int:chapter_id>', methods=['DELETE'])
def delete_chapter(book_name, chapter_id):
    # 1. 核心修复：在删除章节物理文件之前，先触发时光倒流机制
    # 把这章产出的：伏笔、故事线推演、角色弧光、新势力、向量数据库 全部洗刷干净
    try:
        cleanup_chapter_data(book_name, chapter_id)
    except Exception as e:
        print(f"执行章节时光倒流清理失败: {e}")

    # 2. 最后再删除章节自身的基础信息
    success = dao.delete_chapter(book_name, chapter_id)

    if success:
        return jsonify({'message': '删除及关联数据清理成功'})
    return jsonify({'error': '删除失败'}), 400


@api_bp.route('/books/<book_name>/chapters/<int:chapter_id>/finalize', methods=['POST'])
def finalize_chapter(book_name, chapter_id):
    data = request.json
    title = data.get('title', '')
    content = data.get('content', '')
    is_re_final = data.get('is_re_final', False)

    # 状态强行标记为 true (已定稿)
    dao.update_chapter(book_name, chapter_id, title=title, content=content)

    # 【核心修改】：不再直接返回 JSON，而是返回流式事件，唤醒前端的小助手
    return Response(
        run_finalize_pipeline_stream(book_name, chapter_id, content, is_re_final),
        mimetype='text/event-stream'
    )

# ---------- 角色 ----------
@api_bp.route('/books/<book_name>/characters', methods=['GET'])
def list_characters(book_name):
    return jsonify(dao.list_characters(book_name))

@api_bp.route('/books/<book_name>/characters', methods=['POST'])
def add_character(book_name):
    data = request.json
    name = data.get('character_name')
    if not name:
        return jsonify({'error': '角色名不能为空'}), 400
    success = dao.add_character(book_name, name,
                                importance_level=data.get('importance_level', 1),
                                personal_info=data.get('personal_info', ''), # 【新增】接收个人资料
                                profile=data.get('profile', ''),
                                relationships=data.get('relationships', []),
                                change_log=data.get('change_log', ''))
    if success:
        return jsonify({'message': '添加成功'}), 201
    return jsonify({'error': '角色已存在'}), 409

@api_bp.route('/books/<book_name>/characters/<character_name>', methods=['PUT'])
def update_character(book_name, character_name):
    data = request.json
    success = dao.update_character(book_name, character_name, **data)
    if success:
        return jsonify({'message': '更新成功'})
    return jsonify({'error': '角色不存在'}), 404

@api_bp.route('/books/<book_name>/characters/<character_name>', methods=['DELETE'])
def delete_character(book_name, character_name):
    success = dao.delete_character(book_name, character_name)
    if success:
        return jsonify({'message': '删除成功'})
    return jsonify({'error': '删除失败'}), 400

# ---------- 伏笔 ----------
@api_bp.route('/books/<book_name>/foreshadows', methods=['GET'])
def list_foreshadows(book_name):
    return jsonify(dao.list_foreshadows(book_name))

@api_bp.route('/books/<book_name>/foreshadows', methods=['POST'])
def add_foreshadow(book_name):
    data = request.json
    name = data.get('name')
    if not name:
        return jsonify({'error': '伏笔名称不能为空'}), 400
    success = dao.add_foreshadow(book_name, name, data.get('planted_chapter', 1),
                                 data.get('content', ''),
                                 data.get('revealed_chapter', None),
                                 data.get('status', '埋设中'))
    if success:
        return jsonify({'message': '添加成功'}), 201
    return jsonify({'error': '伏笔名称已存在'}), 409

@api_bp.route('/books/<book_name>/foreshadows/<name>', methods=['PUT'])
def update_foreshadow(book_name, name):
    data = request.json
    success = dao.update_foreshadow(book_name, name, **data)
    if success:
        return jsonify({'message': '更新成功'})
    return jsonify({'error': '伏笔不存在'}), 404

@api_bp.route('/books/<book_name>/foreshadows/<name>', methods=['DELETE'])
def delete_foreshadow(book_name, name):
    success = dao.delete_foreshadow(book_name, name)
    if success:
        return jsonify({'message': '删除成功'})
    return jsonify({'error': '删除失败'}), 400

# ---------- 记忆包 ----------
@api_bp.route('/books/<book_name>/memory_packs', methods=['GET'])
def list_memory_packs(book_name):
    return jsonify(dao.list_memory_packs(book_name))

@api_bp.route('/books/<book_name>/memory_packs', methods=['POST'])
def add_memory_pack(book_name):
    data = request.json
    title = data.get('title')
    if not title:
        return jsonify({'error': '记忆包标题不能为空'}), 400
    success = dao.add_memory_pack(book_name, data.get('start_chapter_id', 0),
                                  data.get('end_chapter_id', 0), title,
                                  data.get('content', ''))
    if success:
        return jsonify({'message': '添加成功'}), 201
    return jsonify({'error': '标题已存在'}), 409

@api_bp.route('/books/<book_name>/memory_packs/<title>', methods=['PUT'])
def update_memory_pack(book_name, title):
    data = request.json
    success = dao.update_memory_pack(book_name, title, **data)
    if success:
        return jsonify({'message': '更新成功'})
    return jsonify({'error': '记忆包不存在'}), 404

@api_bp.route('/books/<book_name>/memory_packs/<title>', methods=['DELETE'])
def delete_memory_pack(book_name, title):
    success = dao.delete_memory_pack(book_name, title)
    if success:
        return jsonify({'message': '删除成功'})
    return jsonify({'error': '删除失败'}), 400

# ---------- 章节分析 ----------
@api_bp.route('/books/<book_name>/chapter_analyses', methods=['GET'])
def list_chapter_analyses(book_name):
    return jsonify(dao.list_chapter_analyses(book_name))


@api_bp.route('/books/<book_name>/chapter_analyses/<int:chapter_id>', methods=['PUT'])
def update_chapter_analysis(book_name, chapter_id):
    data = request.json
    existing = dao.get_chapter_analysis(book_name, chapter_id) or {}

    success = dao.add_or_update_chapter_analysis(
        book_name, chapter_id,
        summary=data.get('summary', existing.get('summary', '')),
        key_events=data.get('key_events', existing.get('key_events', [])),
        emotion_intensity=data.get('emotion_intensity', existing.get('emotion_intensity', 1)),
        involved_characters=data.get('involved_characters', existing.get('involved_characters', [])),
        bound_main_node_id=data.get('bound_main_node_id', existing.get('bound_main_node_id', '')),
        bound_sub_node_id=data.get('bound_sub_node_id', existing.get('bound_sub_node_id', ''))
    )
    if success:
        return jsonify({'message': '更新成功'})
    return jsonify({'error': '更新失败'}), 400

# ---------- 故事线 ----------
@api_bp.route('/books/<book_name>/storylines', methods=['GET'])
def list_storylines(book_name):
    return jsonify(dao.list_storylines(book_name))

@api_bp.route('/books/<book_name>/storylines', methods=['PUT'])
def update_storylines(book_name):
    data = request.json
    nodes = data.get('nodes', [])
    success = dao.update_storylines(book_name, nodes)
    if success:
        return jsonify({'message': '更新成功'})
    return jsonify({'error': '更新失败'}), 400

@api_bp.route('/books/<book_name>/storylines/summarize/<node_id>', methods=['POST'])
def summarize_storyline_node(book_name, node_id):
    """触发 AI 对指定的故事线节点进行智能总结并回填"""
    data = request.json or {}
    preview_only = data.get('preview_only', False)  # 获取前端是否只要预览
    try:
        result = generate_storyline_summary(book_name, node_id, preview_only=preview_only)
        return jsonify(result)
    except ValueError as ve:
        # 捕获我们在 Service 里主动抛出的没找到节点或没绑定章节的错误
        return jsonify({'error': str(ve)}), 400
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'error': f'总结失败: {str(e)}'}), 500



# ==================== 势力相关接口 (新增) ====================
@api_bp.route('/books/<book_name>/factions', methods=['GET'])
def get_factions(book_name):
    return jsonify(dao.list_factions(book_name))

@api_bp.route('/books/<book_name>/factions', methods=['POST'])
def add_faction(book_name):
    data = request.json
    if not data or 'name' not in data:
        return jsonify({"success": False, "msg": "势力名不能为空"})
    success = dao.add_faction(book_name, data['name'], data.get('description', ''), data.get('key_figures', []), data.get('history_log', []))
    return jsonify({"success": success})

@api_bp.route('/books/<book_name>/factions/<faction_name>', methods=['PUT'])
def update_faction(book_name, faction_name):
    data = request.json
    success = dao.update_faction(book_name, faction_name, **data)
    return jsonify({"success": success})

@api_bp.route('/books/<book_name>/factions/<faction_name>', methods=['DELETE'])
def delete_faction(book_name, faction_name):
    success = dao.delete_faction(book_name, faction_name)
    return jsonify({"success": success})


# ---------- AI相关 ----------
@api_bp.route('/ai/models', methods=['GET'])
def get_ai_models():
    return jsonify(ai_handler.get_available_models())

@api_bp.route('/ai/chat', methods=['POST'])
def ai_chat():
    data = request.json
    messages = data.get('messages', [])
    model = data.get('model', 'openai/gpt-4o-mini')
    # 👇 加上强制类型转换 👇
    temperature = float(data.get('temperature', 0.7))
    max_tokens = int(data.get('max_tokens', 1024))
    top_p = float(data.get('top_p', 1.0))
    api_key = data.get('api_key')
    session_id = data.get('session_id', str(uuid.uuid4()))
    try:
        response = ai_handler.chat(
            messages=messages, model=model, temperature=temperature,
            max_tokens=max_tokens, top_p=top_p, stream=False, api_key=api_key
        )
        assistant_content = response.choices[0].message.content
        ai_handler.save_conversation_log(
            session_id=session_id, user_message=messages[-1]['content'],
            assistant_message=assistant_content, model=model,
            params={"temperature": temperature, "max_tokens": max_tokens, "top_p": top_p}
        )
        return jsonify({"session_id": session_id, "content": assistant_content, "model": model})
    except Exception as e:
        return jsonify({"error": str(e)}), 500

@api_bp.route('/ai/chat/stream', methods=['POST'])
def ai_chat_stream():
    data = request.json
    messages = data.get('messages', [])
    model = data.get('model', 'openai/gpt-4o-mini')
    temperature = float(data.get('temperature', 0.7))
    max_tokens = int(data.get('max_tokens', 1024))
    top_p = float(data.get('top_p', 1.0))
    api_key = data.get('api_key')
    session_id = data.get('session_id', str(uuid.uuid4()))

    def generate():
        full_response = ""
        try:
            response = ai_handler.chat(
                messages=messages, model=model, temperature=temperature,
                max_tokens=max_tokens, top_p=top_p, stream=True, api_key=api_key
            )
            for chunk in response:
                if ai_handler._stop_event.is_set(): break
                content = chunk.choices[0].delta.content or ""
                full_response += content
                yield f"data: {json.dumps({'content': content})}\n\n"
            ai_handler.save_conversation_log(
                session_id=session_id, user_message=messages[-1]['content'],
                assistant_message=full_response, model=model,
                params={"temperature": temperature, "max_tokens": max_tokens, "top_p": top_p}
            )
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    return Response(generate(), mimetype='text/event-stream')

@api_bp.route('/ai/stop', methods=['POST'])
def ai_stop():
    ai_handler.stop_generation()
    return jsonify({"status": "stopped"})

@api_bp.route('/ai/config', methods=['GET'])
def get_ai_config():
    return jsonify(load_ai_config())

@api_bp.route('/ai/config', methods=['POST'])
def update_ai_config():
    data = request.json
    save_ai_config(data)
    return jsonify({"status": "ok"})

# --------- 章节生成-------------
@api_bp.route('/ai/generate_plan', methods=['POST'])
def ai_generate_plan():
    """接口A：生成规划与检索词"""
    data = request.json
    book_name = data.get('book_name')
    chapter_id = data.get('chapter_id')
    user_draft = data.get('user_draft', '')

    if not book_name or not chapter_id:
        return jsonify({"error": "缺少参数"}), 400

    plan_data = generate_chapter_plan(book_name, chapter_id, user_draft)
    return jsonify(plan_data)


@api_bp.route('/ai/query_vectors', methods=['POST'])
def ai_query_vectors():
    """接口B：执行向量检索试看"""
    data = request.json
    book_name = data.get('book_name')
    tags = data.get('tags', [])

    if not book_name or not tags:
        return jsonify({"error": "缺少查询词"}), 400

    results = query_vector_knowledge(book_name, tags)
    return jsonify(results)

@api_bp.route('/books/<book_name>/vector_snippets', methods=['GET'])
def get_vector_snippets(book_name):
    """获取整本书的所有向量片段"""
    return jsonify(vector_dao.get_all_snippets(book_name))

@api_bp.route('/books/<book_name>/vector_tags', methods=['GET'])
def get_vector_tags(book_name):
    return jsonify(dao.list_vector_tags(book_name))


@api_bp.route('/ai/generate_content/stream', methods=['POST'])
@api_bp.route('/ai/generate_content/stream', methods=['POST'])
def ai_generate_content_stream():
    """接口C：最后一步，打字机流式生成正文（带兜底保护机制）"""
    data = request.json
    book_name = data.get('book_name')
    chapter_id = data.get('chapter_id')
    content_plan = data.get('content_plan', '')
    selected_chars = data.get('selected_chars', [])
    retrieved_snippets = data.get('retrieved_snippets', [])

    def generate():
        full_text = ""  # 用于在后端缓存正在生成的每一滴文字
        try:
            stream, prompt_text = generate_chapter_content_stream(
                book_name, chapter_id, content_plan,
                selected_chars, retrieved_snippets
            )

            debug_data = {
                "type": "debug_info",
                "data": {
                    "engine": "章节生成 - 第三阶段：正式执笔",
                    "debug": {
                        "prompt": prompt_text,
                        "response": "（当前为流式输出，正文正实时打印在编辑器中...）"
                    }
                }
            }
            yield f"data: {json.dumps(debug_data)}\n\n"

            for chunk in stream:
                if ai_handler._stop_event.is_set(): break
                content = chunk.choices[0].delta.content or ""
                full_text += content  # 后端同步积攒文字
                yield f"data: {json.dumps({'content': content})}\n\n"

        except GeneratorExit:
            # 【关键捕获】：这是前端切换界面、断开连接时必然触发的异常
            # 我们捕获它，啥也不用做，让代码平稳滑到 finally 里面去保存
            pass
        except Exception as e:
            yield f"data: {json.dumps({'error': str(e)})}\n\n"
        finally:
            # 【终极兜底机制】：只要有了文字，不管前端死活，统统落盘！
            if full_text:
                try:
                    chapter = dao.get_chapter(book_name, chapter_id)
                    if chapter:
                        existing_content = chapter.get('content', '')
                        if existing_content and not existing_content.endswith('\n\n'):
                            new_content = existing_content + '\n\n' + full_text
                        else:
                            new_content = existing_content + full_text
                        dao.update_chapter(book_name, chapter_id, content=new_content)
                except Exception as e:
                    print(f"流式兜底保存发生错误: {e}")

            yield "data: [DONE]\n\n"

    return Response(generate(), mimetype='text/event-stream')


@api_bp.route('/ai/entity_shape', methods=['POST'])
def ai_entity_shape():
    """右侧AI助手：全知视角的角色/势力塑造与补全"""
    data = request.json
    book_name = data.get('book_name')
    target_desc = data.get('target_desc', '未指定目标')
    ref_desc = data.get('ref_desc', '无参考实体')
    user_prompt = data.get('user_prompt', '')
    preview_only = data.get('preview_only', False)

    if not book_name or not user_prompt:
        return jsonify({"error": "书籍名称和诉求不能为空"}), 400

    try:
        result = generate_entity_shaping(
            book_name=book_name,
            target_desc=target_desc,
            ref_desc=ref_desc,
            user_prompt=user_prompt,
            preview_only=preview_only
        )
        return jsonify(result)
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({"error": f"塑造生成失败: {str(e)}"}), 500


# --------- 提示词管理-------------
@api_bp.route('/prompts', methods=['GET'])
def get_prompts():
    """获取所有提示词列表（包含默认与自定义）"""
    return jsonify(prompt_manager.get_all_prompts())

@api_bp.route('/prompts', methods=['PUT'])
def update_prompts():
    """保存前端自定义的提示词"""
    data = request.json
    if not isinstance(data, list):
        return jsonify({"error": "格式错误，期望收到列表"}), 400
    prompt_manager.save_prompts(data)
    return jsonify({"status": "success", "message": "提示词保存成功"})