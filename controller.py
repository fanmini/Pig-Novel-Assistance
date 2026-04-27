import json
import uuid

from flask import Blueprint, request, jsonify, Response
from finalize_service import run_finalize_pipeline_stream, cleanup_chapter_data
from ai_handler import ai_handler, load_ai_config, save_ai_config
from base_dao import NovelModel
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
    dao.update_chapter(book_name, chapter_id, title=title, content=content, status=True)

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
    success = dao.add_or_update_chapter_analysis(
        book_name, chapter_id,
        summary=data.get('summary', ''),
        key_events=data.get('key_events', []),
        story_position=data.get('story_position', ''),
        emotion_intensity=data.get('emotion_intensity', 1),
        involved_characters=data.get('involved_characters', [])
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
    temperature = data.get('temperature', 0.7)
    max_tokens = data.get('max_tokens', 1024)
    top_p = data.get('top_p', 1.0)
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
    temperature = data.get('temperature', 0.7)
    max_tokens = data.get('max_tokens', 1024)
    top_p = data.get('top_p', 1.0)
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