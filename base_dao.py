import os
import json
import shutil
from typing import List, Dict, Any, Optional


class NovelModel:
    """基于文件系统的小说数据管理层"""

    def __init__(self):
        current_dir = os.path.dirname(os.path.abspath(__file__))
        project_root = os.path.dirname(current_dir)
        if os.path.exists(os.path.join(current_dir, 'main.py')) or os.path.exists(
                os.path.join(current_dir, 'manage.py')):
            project_root = current_dir
        self.data_root = os.path.join(project_root, 'data')
        # 确保 data 目录存在
        if not os.path.exists(self.data_root):
            os.makedirs(self.data_root)

    # ==================== 书籍相关操作 ====================

    def list_books(self) -> List[str]:
        """返回所有书籍名称列表"""
        books = []
        for item in os.listdir(self.data_root):
            book_path = os.path.join(self.data_root, item)
            if os.path.isdir(book_path) and os.path.exists(os.path.join(book_path, "book.json")):
                books.append(item)
        return books

    def create_book(self, name: str, description: str = "", sort_order: int = 0,
                    meta_list: List[Dict[str, str]] = None) -> bool:
        """
        创建一本新书
        :param name: 书名（将作为文件夹名）
        :param description: 简介
        :param sort_order: 排序权重
        :param meta_list: 额外信息 [{"key":"author","value":"张三"}, ...]
        :return: 是否成功
        """
        book_folder = os.path.join(self.data_root, name)
        if os.path.exists(book_folder):
            return False  # 书籍已存在

        os.makedirs(book_folder)

        # 初始化 book.json
        book_data = {
            "name": name,
            "total_words": 0,
            "description": description,
            "sort_order": sort_order,
            "meta_list": meta_list or []
        }
        self._save_json(os.path.join(book_folder, "book.json"), book_data)

        # 初始化其他空文件
        self._save_json(os.path.join(book_folder, "chapters.json"), [])
        self._save_json(os.path.join(book_folder, "chapter_analysis.json"), [])
        self._save_json(os.path.join(book_folder, "characters.json"), [])
        self._save_json(os.path.join(book_folder, "foreshadows.json"), [])
        self._save_json(os.path.join(book_folder, "memory_packs.json"), [])

        return True

    def get_book(self, name: str) -> Optional[Dict[str, Any]]:
        """获取书籍基本信息"""
        book_path = os.path.join(self.data_root, name, "book.json")
        if not os.path.exists(book_path):
            return None
        return self._load_json(book_path)

    def update_book(self, name: str, **kwargs) -> bool:
        """
        更新书籍基本信息
        :param name: 书名（用于定位，不可修改）
        :param kwargs: 可更新字段：description, sort_order, meta_list
        :return: 是否成功
        """
        book_data = self.get_book(name)
        if not book_data:
            return False

        allowed = ["description", "sort_order", "meta_list"]
        for key, value in kwargs.items():
            if key in allowed:
                book_data[key] = value

        book_path = os.path.join(self.data_root, name, "book.json")
        self._save_json(book_path, book_data)
        return True

    def rename_book(self, old_name: str, new_name: str) -> bool:
        """
        重命名书籍（会同时修改文件夹名和 book.json 中的 name 字段）
        :param old_name: 原书名
        :param new_name: 新书名
        :return: 是否成功
        """
        old_path = os.path.join(self.data_root, old_name)
        new_path = os.path.join(self.data_root, new_name)
        if not os.path.exists(old_path) or os.path.exists(new_path):
            return False

        # 修改 book.json 中的 name
        book_data = self.get_book(old_name)
        book_data["name"] = new_name
        self._save_json(os.path.join(old_path, "book.json"), book_data)

        # 重命名文件夹
        os.rename(old_path, new_path)
        return True

    def delete_book(self, name: str) -> bool:
        """删除整本书（删除文件夹及其所有内容）"""
        book_folder = os.path.join(self.data_root, name)
        if not os.path.exists(book_folder):
            return False
        shutil.rmtree(book_folder)
        return True

    def update_total_words(self, name: str) -> int:
        """
        重新计算并更新书籍总字数（遍历所有已定稿章节）
        :return: 更新后的总字数
        """
        chapters = self.list_chapters(name)
        total = sum(ch.get("word_count", 0) for ch in chapters if ch.get("status") is True)
        book = self.get_book(name)
        if book:
            book["total_words"] = total
            self._save_json(os.path.join(self.data_root, name, "book.json"), book)
        return total

    # ==================== 章节相关操作 ====================

    def list_chapters(self, book_name: str) -> List[Dict[str, Any]]:
        """获取某本书的所有章节列表"""
        return self._load_json(os.path.join(self.data_root, book_name, "chapters.json"), [])

    def get_chapter(self, book_name: str, chapter_id: int) -> Optional[Dict[str, Any]]:
        """获取指定章节"""
        chapters = self.list_chapters(book_name)
        for ch in chapters:
            if ch.get("id") == chapter_id:
                return ch
        return None

    def add_chapter(self, book_name: str, chapter_id: int, title: str, content: str = "", status: bool = False) -> bool:
        """
        添加新章节（若 id 已存在则失败）
        """
        chapters = self.list_chapters(book_name)
        if any(ch.get("id") == chapter_id for ch in chapters):
            return False

        word_count = len(content)  # 纯文本字数（按字符数，可替换为更精确的中文分词计数）
        new_chapter = {
            "id": chapter_id,
            "title": title,
            "content": content,
            "status": status,
            "word_count": word_count
        }
        chapters.append(new_chapter)
        # 按 id 排序
        chapters.sort(key=lambda x: x["id"])
        self._save_json(os.path.join(self.data_root, book_name, "chapters.json"), chapters)

        # 若章节为定稿状态，更新总字数
        if status:
            self.update_total_words(book_name)
        return True

    def update_chapter(self, book_name: str, chapter_id: int, **kwargs) -> bool:
        """
        更新章节信息
        :param kwargs: title, content, status
        """
        chapters = self.list_chapters(book_name)
        target = None
        for ch in chapters:
            if ch.get("id") == chapter_id:
                target = ch
                break
        if not target:
            return False

        old_status = target.get("status")
        if "title" in kwargs:
            target["title"] = kwargs["title"]
        if "content" in kwargs:
            target["content"] = kwargs["content"]
            target["word_count"] = len(kwargs["content"])
        if "status" in kwargs:
            target["status"] = kwargs["status"]

        self._save_json(os.path.join(self.data_root, book_name, "chapters.json"), chapters)

        # 若状态发生变化（草稿<->定稿），需要重新计算总字数
        if "status" in kwargs and old_status != kwargs["status"]:
            self.update_total_words(book_name)
        elif "content" in kwargs:
            # 内容变化且当前是定稿状态，也需要更新总字数
            if target.get("status"):
                self.update_total_words(book_name)
        return True

    def delete_chapter(self, book_name: str, chapter_id: int) -> bool:
        """删除章节，同时删除对应的章节分析数据"""
        # 删除章节
        chapters = self.list_chapters(book_name)
        new_chapters = [ch for ch in chapters if ch.get("id") != chapter_id]
        if len(new_chapters) == len(chapters):
            return False  # 未找到
        self._save_json(os.path.join(self.data_root, book_name, "chapters.json"), new_chapters)

        # 删除对应的分析数据
        analysis_list = self.list_chapter_analyses(book_name)
        new_analysis = [an for an in analysis_list if an.get("chapter_id") != chapter_id]
        self._save_json(os.path.join(self.data_root, book_name, "chapter_analysis.json"), new_analysis)

        # 更新总字数
        self.update_total_words(book_name)
        return True

    # ==================== 章节分析相关操作 ====================

    def list_chapter_analyses(self, book_name: str) -> List[Dict[str, Any]]:
        """获取某本书所有章节的分析数据"""
        return self._load_json(os.path.join(self.data_root, book_name, "chapter_analysis.json"), [])

    def get_chapter_analysis(self, book_name: str, chapter_id: int) -> Optional[Dict[str, Any]]:
        """获取指定章节的分析数据"""
        analyses = self.list_chapter_analyses(book_name)
        for an in analyses:
            if an.get("chapter_id") == chapter_id:
                return an
        return None

    def add_or_update_chapter_analysis(self, book_name: str, chapter_id: int,
                                       summary: str = "",
                                       key_events: List[str] = None,
                                       story_position: str = "",
                                       emotion_intensity: int = 1,
                                       involved_characters: List[str] = None) -> bool:
        """
        添加或更新章节分析数据
        """
        analyses = self.list_chapter_analyses(book_name)
        key_events = key_events or []
        involved_characters = involved_characters or []

        existing = None
        for an in analyses:
            if an.get("chapter_id") == chapter_id:
                existing = an
                break

        data = {
            "chapter_id": chapter_id,
            "summary": summary,
            "key_events": key_events,
            "story_position": story_position,
            "emotion_intensity": max(1, min(10, emotion_intensity)),
            "involved_characters": involved_characters
        }

        if existing:
            existing.update(data)
        else:
            analyses.append(data)

        self._save_json(os.path.join(self.data_root, book_name, "chapter_analysis.json"), analyses)
        return True

    def delete_chapter_analysis(self, book_name: str, chapter_id: int) -> bool:
        """删除指定章节的分析数据"""
        analyses = self.list_chapter_analyses(book_name)
        new_analyses = [an for an in analyses if an.get("chapter_id") != chapter_id]
        if len(new_analyses) == len(analyses):
            return False
        self._save_json(os.path.join(self.data_root, book_name, "chapter_analysis.json"), new_analyses)
        return True

    # ==================== 角色相关操作 ====================

    def list_characters(self, book_name: str) -> List[Dict[str, Any]]:
        """获取所有角色列表"""
        return self._load_json(os.path.join(self.data_root, book_name, "characters.json"), [])

    def get_character(self, book_name: str, character_name: str) -> Optional[Dict[str, Any]]:
        """获取指定角色信息"""
        characters = self.list_characters(book_name)
        for ch in characters:
            if ch.get("character_name") == character_name:
                return ch
        return None

    def add_character(self, book_name: str, character_name: str,
                      importance_level: int = 1,
                      profile: str = "",
                      relationships: List[Dict[str, str]] = None,
                      change_log: str = "") -> bool:
        """添加新角色（若已存在则失败）"""
        if self.get_character(book_name, character_name):
            return False

        new_char = {
            "character_name": character_name,
            "importance_level": importance_level,
            "profile": profile,
            "relationships": relationships or [],
            "change_log": change_log
        }
        characters = self.list_characters(book_name)
        characters.append(new_char)
        self._save_json(os.path.join(self.data_root, book_name, "characters.json"), characters)
        return True

    def update_character(self, book_name: str, character_name: str, **kwargs) -> bool:
        """更新角色信息（不可更新主键）"""
        characters = self.list_characters(book_name)
        target = None
        for ch in characters:
            if ch.get("character_name") == character_name:
                target = ch
                break
        if not target:
            return False

        allowed = ["importance_level", "profile", "relationships", "change_log"]
        for key, value in kwargs.items():
            if key in allowed:
                target[key] = value

        self._save_json(os.path.join(self.data_root, book_name, "characters.json"), characters)
        return True

    def delete_character(self, book_name: str, character_name: str) -> bool:
        """删除角色"""
        characters = self.list_characters(book_name)
        new_chars = [ch for ch in characters if ch.get("character_name") != character_name]
        if len(new_chars) == len(characters):
            return False
        self._save_json(os.path.join(self.data_root, book_name, "characters.json"), new_chars)
        return True

    # ==================== 伏笔相关操作 ====================

    def list_foreshadows(self, book_name: str) -> List[Dict[str, Any]]:
        """获取所有伏笔列表"""
        return self._load_json(os.path.join(self.data_root, book_name, "foreshadows.json"), [])

    def get_foreshadow(self, book_name: str, name: str) -> Optional[Dict[str, Any]]:
        """根据伏笔名称获取"""
        foreshadows = self.list_foreshadows(book_name)
        for f in foreshadows:
            if f.get("name") == name:
                return f
        return None

    def add_foreshadow(self, book_name: str, name: str, planted_chapter: int,
                       content: str, revealed_chapter: int = None, status: str = "埋设中") -> bool:
        """添加新伏笔（名称唯一）"""
        if self.get_foreshadow(book_name, name):
            return False

        new_f = {
            "name": name,
            "planted_chapter": planted_chapter,
            "content": content,
            "revealed_chapter": revealed_chapter,
            "status": status
        }
        foreshadows = self.list_foreshadows(book_name)
        foreshadows.append(new_f)
        self._save_json(os.path.join(self.data_root, book_name, "foreshadows.json"), foreshadows)
        return True

    def update_foreshadow(self, book_name: str, name: str, **kwargs) -> bool:
        """更新伏笔信息"""
        foreshadows = self.list_foreshadows(book_name)
        target = None
        for f in foreshadows:
            if f.get("name") == name:
                target = f
                break
        if not target:
            return False

        allowed = ["planted_chapter", "content", "revealed_chapter", "status"]
        for key, value in kwargs.items():
            if key in allowed:
                target[key] = value

        self._save_json(os.path.join(self.data_root, book_name, "foreshadows.json"), foreshadows)
        return True

    def delete_foreshadow(self, book_name: str, name: str) -> bool:
        """删除伏笔"""
        foreshadows = self.list_foreshadows(book_name)
        new_fs = [f for f in foreshadows if f.get("name") != name]
        if len(new_fs) == len(foreshadows):
            return False
        self._save_json(os.path.join(self.data_root, book_name, "foreshadows.json"), new_fs)
        return True

    # ==================== 区间记忆包相关操作 ====================

    def list_memory_packs(self, book_name: str) -> List[Dict[str, Any]]:
        """获取所有记忆包列表"""
        return self._load_json(os.path.join(self.data_root, book_name, "memory_packs.json"), [])

    def get_memory_pack(self, book_name: str, title: str) -> Optional[Dict[str, Any]]:
        """根据标题获取记忆包"""
        packs = self.list_memory_packs(book_name)
        for p in packs:
            if p.get("title") == title:
                return p
        return None

    def add_memory_pack(self, book_name: str, start_chapter_id: int, end_chapter_id: int,
                        title: str, content: str) -> bool:
        """添加记忆包（标题唯一）"""
        if self.get_memory_pack(book_name, title):
            return False

        new_pack = {
            "start_chapter_id": start_chapter_id,
            "end_chapter_id": end_chapter_id,
            "title": title,
            "content": content
        }
        packs = self.list_memory_packs(book_name)
        packs.append(new_pack)
        self._save_json(os.path.join(self.data_root, book_name, "memory_packs.json"), packs)
        return True

    def update_memory_pack(self, book_name: str, title: str, **kwargs) -> bool:
        """更新记忆包"""
        packs = self.list_memory_packs(book_name)
        target = None
        for p in packs:
            if p.get("title") == title:
                target = p
                break
        if not target:
            return False

        allowed = ["start_chapter_id", "end_chapter_id", "content"]
        for key, value in kwargs.items():
            if key in allowed:
                target[key] = value

        self._save_json(os.path.join(self.data_root, book_name, "memory_packs.json"), packs)
        return True

    def delete_memory_pack(self, book_name: str, title: str) -> bool:
        """删除记忆包"""
        packs = self.list_memory_packs(book_name)
        new_packs = [p for p in packs if p.get("title") != title]
        if len(new_packs) == len(packs):
            return False
        self._save_json(os.path.join(self.data_root, book_name, "memory_packs.json"), new_packs)
        return True

    # ==================== 私有辅助方法 ====================

    def _load_json(self, file_path: str, default=None):
        """加载 JSON 文件，若不存在则返回默认值"""
        if not os.path.exists(file_path):
            return default if default is not None else {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default if default is not None else {}

    def _save_json(self, file_path: str, data: Any) -> None:
        """将数据保存为 JSON 文件"""
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

