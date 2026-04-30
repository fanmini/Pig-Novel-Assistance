# vector_dao.py
import os
import chromadb
import hashlib
from chromadb.utils import embedding_functions

os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1"


class VectorDAO:
    def __init__(self):
        # 初始化 ChromaDB（这里默认存在本地目录 ./novel_vector_db）
        self.client = chromadb.PersistentClient(path="./data/vector_db")

        # 使用你默认的 Embedding 模型
        self.embedding_fn = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="BAAI/bge-small-zh-v1.5"
        )

    def _get_collection(self, book_name: str):
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

        res = collection.get()  # 取出集合中所有数据
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
        """
        【全新重构】：存储高光片段与结构化 Metadata 标签
        snippet_meta 包含了从 AI 提取的 8 个维度的字典
        """
        collection = self._get_collection(book_name)

        # 1. 构建合规的 Metadata (将列表扁平化为字符串)
        safe_metadata = {"chapter_id": chapter_id, "raw_content": content}

        for key, value in snippet_meta.items():
            if isinstance(value, list):
                # 【关键修复】：直接存数组！并且 ChromaDB 不允许存空数组，所以有值才存入
                if len(value) > 0:
                    safe_metadata[key] = value
            elif isinstance(value, (str, int, float, bool)) and value != "":
                safe_metadata[key] = value

        # 2. 复合文档构建
        # 为了不破坏语义纯净度，但又增加可搜性，我们在最开头简单拼接一下核心分类词汇
        scene = safe_metadata.get("scene_type", "")
        trope = safe_metadata.get("plot_trope", "")
        rich_document = f"【{scene} - {trope}】\n{content}"

        # 3. 生成唯一 ID
        doc_id = f"chap_{chapter_id}_{hashlib.md5(content.encode('utf-8')).hexdigest()[:10]}"

        # 4. 入库
        collection.add(
            documents=[rich_document],
            metadatas=[safe_metadata],  # 存入被扁平化的结构字典
            ids=[doc_id]
        )
        print(f"[VectorDB] 已存入第 {chapter_id} 章高光片段，元数据：{safe_metadata}")

    def query_snippets(self, book_name: str, query_text: str, n_results: int = 5, where_filter: dict = None):
        """
        【全新重构】：语义检索 + Metadata 过滤
        where_filter 例如：{"scene_type": {"$in": ["战斗"]}, "characters": {"$contains": "张三"}}
        (注：ChromaDB 支持丰富的 where 语法过滤)
        """
        collection = self._get_collection(book_name)

        # 防止空库报错
        if collection.count() == 0:
            return []

        fetch_count = min(n_results, collection.count())

        # 组装查询参数
        query_params = {
            "query_texts": [query_text],
            "n_results": fetch_count
        }

        # 如果传入了过滤条件，加入 where 子句
        if where_filter:
            query_params["where"] = where_filter

        results = collection.query(**query_params)

        # 解析结果，返回纯净的原始文本和它的元数据
        snippets = []
        if results['metadatas'] and len(results['metadatas'][0]) > 0:
            for meta in results['metadatas'][0]:
                if meta and 'raw_content' in meta:
                    # 把原本拍扁的 metadata 原样返回给前端展示
                    snippets.append({
                        "chapter_id": meta.get('chapter_id'),
                        "content": meta.get('raw_content'),
                        "metadata": meta  # 包含所有场景、角色等信息
                    })
        return snippets

    def delete_snippets_by_chapter(self, book_name: str, chapter_id: int):
        """时光倒流：清理某章的所有向量数据"""
        collection = self._get_collection(book_name)
        try:
            collection.delete(where={"chapter_id": chapter_id})
        except Exception as e:
            print(f"[VectorDB] 删除第 {chapter_id} 章向量数据失败: {e}")

    def delete_collection(self, book_name: str):
        """删除整本书的向量数据集合"""
        safe_name = hashlib.md5(book_name.encode('utf-8')).hexdigest()
        collection_name = f"book_{safe_name}"
        try:
            self.client.delete_collection(name=collection_name)
            print(f"[VectorDB] 已彻底删除书籍 {book_name} 的向量集合。")
        except ValueError:
            # ChromaDB 抛出 ValueError 通常是因为集合不存在，安全忽略即可
            print(f"[VectorDB] 书籍 {book_name} 的向量集合不存在，无需删除。")
        except Exception as e:
            print(f"[VectorDB] 删除书籍向量集合失败: {e}")


# 单例模式导出
vector_dao = VectorDAO()