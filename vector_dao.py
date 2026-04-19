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


vector_dao = VectorDAO()