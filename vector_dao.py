import shutil

import chromadb
import os
import uuid
import hashlib


class VectorDAO:
    def __init__(self):
        db_path = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'data', 'vector_db')
        os.makedirs(db_path, exist_ok=True)
        self.client = chromadb.PersistentClient(path=db_path)

    def save_snippet_tags(self, book_name: str, chapter_id: int, snippet_content: str, tags: list):
        # 核心修复：把可能包含中文的书名，转换成 ChromaDB 绝对支持的纯英文数字组合
        safe_book_name = hashlib.md5(book_name.encode('utf-8')).hexdigest()
        collection_name = f"book_{safe_book_name}"

        # 使用安全的名称创建或获取集合
        collection = self.client.get_or_create_collection(name=collection_name)

        docs = []
        metadatas = []
        ids = []

        for tag in tags:
            docs.append(tag)
            metadatas.append({
                "chapter_id": chapter_id,
                "content": snippet_content
            })
            ids.append(str(uuid.uuid4()))

        if docs:
            collection.add(documents=docs, metadatas=metadatas, ids=ids)

    def delete_snippets_by_chapter(self, book_name: str, chapter_id: int):
        """核心新增：根据章节ID，精确删除 ChromaDB 中的旧片段，防止数据冗余"""
        safe_book_name = hashlib.md5(book_name.encode('utf-8')).hexdigest()
        collection_name = f"book_{safe_book_name}"
        try:
            collection = self.client.get_collection(name=collection_name)
            # 利用 ChromaDB 的 metadata 过滤功能进行精准删除
            collection.delete(where={"chapter_id": chapter_id})
            print(f"已清理向量库中《{book_name}》第 {chapter_id} 章的历史碎片。")
        except Exception:
            # 如果集合还没创建过，直接忽略即可
            pass

    def delete_collection(self, book_name: str):
        """核心新增：删除书籍时，彻底销毁 ChromaDB 中的对应集合"""
        safe_book_name = hashlib.md5(book_name.encode('utf-8')).hexdigest()
        collection_name = f"book_{safe_book_name}"
        try:
            # 只需要这一句！
            self.client.delete_collection(name=collection_name)
            print(f"已彻底删除向量库中《{book_name}》的全部数据。")
        except Exception as e:
            print(f"删除向量集合时忽略报错: {e}")
            pass

vector_dao = VectorDAO()