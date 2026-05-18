# vector_dao.py
import os
import chromadb
import hashlib
import threading  # 【新增】引入线程模块
from chromadb.utils import embedding_functions

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"


class VectorDAO:
    def __init__(self):
        # 【修改】初始化为空
        self.client = None
        self.embedding_fn = None
        self._ready_event = threading.Event()
        if os.environ.get('WERKZEUG_RUN_MAIN') != 'true' and os.environ.get('FLASK_DEBUG') == '1':
            pass
        else:
            print("[VectorDB] 🚀 正在后台启动加载向量数据库与模型...")
            threading.Thread(target=self._init_in_background, daemon=True).start()

    def _init_in_background(self):
        """真正在后台执行的耗时加载操作"""
        try:
            # 加载 ChromaDB 和 Embedding 模型（这里是最耗时的步骤）
            self.client = chromadb.PersistentClient(path="./data/vector_db")
            self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
                model_name="BAAI/bge-small-zh-v1.5"
            )

            # 加载完成！将事件锁设置为 True，变成绿灯
            self._ready_event.set()
            print("[VectorDB] ✅ 后台加载完成，向量检索服务已就绪！")
        except Exception as e:
            print(f"[VectorDB] ❌ 后台加载向量模型失败: {e}")

    def _ensure_ready(self):
        """【新增】在使用数据库之前，检查这盏绿灯亮了没"""
        if not self._ready_event.is_set():
            print("[VectorDB] ⏳ 等待后台向量模型加载完毕，请稍候...")
            # 如果还没加载完，调用这个方法的线程就会在这里停住等一下，直到 set() 被调用
            self._ready_event.wait()

    def _get_collection(self, book_name: str):
        # 【修改】每次获取集合前，都确保后台加载已经完成
        self._ensure_ready()

        safe_name = hashlib.md5(book_name.encode('utf-8')).hexdigest()
        collection_name = f"book_{safe_name}"

        return self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.embedding_fn,
            metadata={"hnsw:space": "cosine"}  # 使用余弦相似度，对长文本更友好
        )

    def get_all_snippets(self, book_name: str):
        """获取全书所有向量片段及 Metadata，供前端可视化展示"""
        collection = self._get_collection(book_name)
        if collection.count() == 0:
            return []

        res = collection.get()
        snippets = []
        if res and res.get('metadatas'):
            for i, meta in enumerate(res['metadatas']):
                if meta:
                    snippets.append({
                        "id": res['ids'][i],
                        "chapter_id": meta.get('chapter_id', 0),
                        "content": meta.get('raw_content', ''),
                        "metadata": meta
                    })
        return snippets

    def save_structured_snippet(self, book_name: str, chapter_id: int, content: str, snippet_meta: dict):
        collection = self._get_collection(book_name)

        safe_metadata = {"chapter_id": chapter_id, "raw_content": content}

        # 提取动态标签和摘要
        intent_summary = snippet_meta.get("intent_summary", "无摘要")
        dynamic_tags = snippet_meta.get("dynamic_tags", [])

        safe_metadata["intent_summary"] = intent_summary
        if isinstance(dynamic_tags, list) and len(dynamic_tags) > 0:
            safe_metadata["dynamic_tags"] = ",".join(str(v) for v in dynamic_tags)

        # 处理其他实体列表 (characters, factions, items, locations)
        for key, value in snippet_meta.items():
            if key not in ["intent_summary", "dynamic_tags", "content"]:
                if isinstance(value, list):
                    if len(value) > 0:
                        safe_metadata[key] = ",".join(str(v) for v in value)
                elif isinstance(value, (str, int, float, bool)) and value != "":
                    safe_metadata[key] = value

        # 【核心爆改：构建超级词向量文本】
        # 让 ChromaDB 记住摘要和标签的语义
        tag_str = safe_metadata.get("dynamic_tags", "无标签")
        rich_document = f"【检索特征摘要】：{intent_summary}\n【关联标签】：{tag_str}\n【原文内容】：\n{content}"

        import hashlib
        doc_id = f"chap_{chapter_id}_{hashlib.md5(content.encode('utf-8')).hexdigest()[:10]}"

        collection.add(
            documents=[rich_document],
            metadatas=[safe_metadata],
            ids=[doc_id]
        )
        print(f"[VectorDB] 已存入第 {chapter_id} 章高光片段，摘要：{intent_summary}")

    def query_snippets(self, book_name: str, query_text: str, n_results: int = 5, where_filter: dict = None):
        collection = self._get_collection(book_name)

        if collection.count() == 0:
            return []

        fetch_count = min(n_results, collection.count())

        query_params = {
            "query_texts": [query_text],
            "n_results": fetch_count
        }

        if where_filter:
            query_params["where"] = where_filter

        results = collection.query(**query_params)

        snippets = []
        if results['metadatas'] and len(results['metadatas'][0]) > 0:
            for meta in results['metadatas'][0]:
                if meta and 'raw_content' in meta:
                    snippets.append({
                        "chapter_id": meta.get('chapter_id'),
                        "content": meta.get('raw_content'),
                        "metadata": meta
                    })
        return snippets

    def delete_snippets_by_chapter(self, book_name: str, chapter_id: int):
        collection = self._get_collection(book_name)
        try:
            collection.delete(where={"chapter_id": chapter_id})
        except Exception as e:
            print(f"[VectorDB] 删除第 {chapter_id} 章向量数据失败: {e}")

    def delete_collection(self, book_name: str):
        # 【修改】这步操作没用到 _get_collection，但也需要等 client 加载完毕
        self._ensure_ready()

        safe_name = hashlib.md5(book_name.encode('utf-8')).hexdigest()
        collection_name = f"book_{safe_name}"
        try:
            self.client.delete_collection(name=collection_name)
            print(f"[VectorDB] 已彻底删除书籍 {book_name} 的向量集合。")
        except ValueError:
            print(f"[VectorDB] 书籍 {book_name} 的向量集合不存在，无需删除。")
        except Exception as e:
            print(f"[VectorDB] 删除书籍向量集合失败: {e}")


# 单例模式导出
vector_dao = VectorDAO()