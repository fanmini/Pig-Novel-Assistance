# vector_dao.py
import os
import chromadb
import hashlib
from chromadb.utils import embedding_functions
os.environ["HF_ENDPOINT"] = "https://hf-mirror.com"
os.environ["HF_HUB_DISABLE_SYMLINKS_WARNING"] = "1" # 顺便消灭一个烦人的警告

class VectorDAO:
    def __init__(self):
        # 数据库持久化路径
        self.persist_directory = os.path.join(os.path.dirname(__file__), 'data', 'vector_db')
        os.makedirs(self.persist_directory, exist_ok=True)

        self.client = chromadb.PersistentClient(path=self.persist_directory)

        # 【核心优化 1：替换中文 Embedding 模型】
        # 使用 BAAI 的 bge-small-zh-v1.5，这是目前极其优秀的开源中文向量模型
        # 第一次运行会自动下载（约100MB），之后都在本地极速运行
        self.ef = embedding_functions.SentenceTransformerEmbeddingFunction(
            model_name="BAAI/bge-small-zh-v1.5"
        )

    def _get_collection(self, book_name: str):
        safe_name = hashlib.md5(book_name.encode('utf-8')).hexdigest()
        collection_name = f"book_{safe_name}"

        return self.client.get_or_create_collection(
            name=collection_name,
            embedding_function=self.ef,
            metadata={"hnsw:space": "cosine"}  # 使用余弦相似度，对长文本更友好
        )

    def save_snippet_tags(self, book_name: str, chapter_id: int, content: str, tags: list):
        """存储高光片段与标签"""
        collection = self._get_collection(book_name)

        # 【核心优化 2：复合文档构建】
        # 将标签和正文拼接成极其丰富的语境，让模型深刻理解这个片段的“核心要素”
        tags_str = "，".join(tags)
        rich_document = f"【核心要素标签】：{tags_str}\n【详细剧情内容】：{content}"

        doc_id = f"chap_{chapter_id}_{hash(content)}"

        collection.add(
            documents=[rich_document],  # 存入复合文档用于强大的语义检索
            metadatas=[{
                "chapter_id": chapter_id,
                "tags_str": tags_str,  # 将标签存入元数据，留给精准查询备用
                "raw_content": content  # 原始干净的文本
            }],
            ids=[doc_id]
        )
        print(f"[VectorDB] 已存入第 {chapter_id} 章高光片段，标签：{tags_str}")

    def query_snippets(self, book_name: str, query_text: str, n_results: int = 5):
        """语义检索片段"""
        collection = self._get_collection(book_name)

        # 防止空库报错
        if collection.count() == 0:
            return []

        # 限制返回数量不超过库中总数
        fetch_count = min(n_results, collection.count())

        results = collection.query(
            query_texts=[query_text],
            n_results=fetch_count
        )

        # 解析结果，返回纯净的原始文本
        snippets = []
        if results['metadatas'] and len(results['metadatas'][0]) > 0:
            for meta in results['metadatas'][0]:
                if meta and 'raw_content' in meta:
                    snippets.append({
                        "chapter_id": meta.get('chapter_id'),
                        "content": meta.get('raw_content'),
                        "tags_str": meta.get('tags_str')
                    })
        return snippets

    def delete_snippets_by_chapter(self, book_name: str, chapter_id: int):
        """时光倒流：清理某章的所有向量数据"""
        collection = self._get_collection(book_name)
        # ChromaDB 支持直接通过 Metadata 的条件进行删除
        collection.delete(
            where={"chapter_id": chapter_id}
        )


# 单例模式导出
vector_dao = VectorDAO()