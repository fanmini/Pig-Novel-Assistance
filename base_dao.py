import os
import json
import shutil
import time
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
        if not os.path.exists(self.data_root):
            os.makedirs(self.data_root)

    # ==================== 书籍相关操作 ====================
    def list_books(self) -> List[str]:
        books = []
        for item in os.listdir(self.data_root):
            book_path = os.path.join(self.data_root, item)
            if os.path.isdir(book_path) and os.path.exists(os.path.join(book_path, "book.json")):
                books.append(item)
        return books

    def create_book(self, name: str, description: str = "", sort_order: int = 0,
                    meta_list: List[Dict[str, str]] = None) -> bool:
        book_folder = os.path.join(self.data_root, name)
        if os.path.exists(book_folder):
            return False

        os.makedirs(book_folder)

        book_data = {
            "name": name,
            "total_words": 0,
            "description": description,
            "sort_order": sort_order,
            "meta_list": meta_list or []
        }
        self._save_json(os.path.join(book_folder, "book.json"), book_data)

        # 初始化各模块文件
        self._save_json(os.path.join(book_folder, "chapters.json"), [])
        self._save_json(os.path.join(book_folder, "chapter_analysis.json"), [])
        self._save_json(os.path.join(book_folder, "characters.json"), [])
        self._save_json(os.path.join(book_folder, "foreshadows.json"), [])
        self._save_json(os.path.join(book_folder, "memory_packs.json"), [])
        self._save_json(os.path.join(book_folder, "factions.json"), [])  # 【新增】势力分布存储

        # 【故事线冷启动初始化】
        default_storylines = [{
            "id": "p_" + str(int(time.time() * 1000)),
            "name": "故事开始",
            "content": "",
            "foreshadows": [],
            "is_completed": False,
            "children": []
        }]
        self._save_json(os.path.join(book_folder, "storylines.json"), default_storylines)

        return True

    def get_book(self, name: str) -> Optional[Dict[str, Any]]:
        book_path = os.path.join(self.data_root, name, "book.json")
        if not os.path.exists(book_path): return None
        return self._load_json(book_path)

    def update_book(self, name: str, **kwargs) -> bool:
        book_data = self.get_book(name)
        if not book_data: return False
        allowed = ["description", "sort_order", "meta_list"]
        for key, value in kwargs.items():
            if key in allowed: book_data[key] = value
        self._save_json(os.path.join(self.data_root, name, "book.json"), book_data)
        return True

    def rename_book(self, old_name: str, new_name: str) -> bool:
        old_path = os.path.join(self.data_root, old_name)
        new_path = os.path.join(self.data_root, new_name)
        if not os.path.exists(old_path) or os.path.exists(new_path): return False
        book_data = self.get_book(old_name)
        book_data["name"] = new_name
        self._save_json(os.path.join(old_path, "book.json"), book_data)
        os.rename(old_path, new_path)
        return True

    def delete_book(self, name: str) -> bool:
        book_folder = os.path.join(self.data_root, name)
        if not os.path.exists(book_folder): return False
        shutil.rmtree(book_folder)
        return True

    def update_total_words(self, name: str) -> int:
        chapters = self.list_chapters(name)
        total = sum(ch.get("word_count", 0) for ch in chapters if ch.get("status") is True)
        book = self.get_book(name)
        if book:
            book["total_words"] = total
            self._save_json(os.path.join(self.data_root, name, "book.json"), book)
        return total

    # ==================== 章节与分析相关操作 ====================
    def list_chapters(self, book_name: str) -> List[Dict[str, Any]]:
        return self._load_json(os.path.join(self.data_root, book_name, "chapters.json"), [])

    def get_chapter(self, book_name: str, chapter_id: int) -> Optional[Dict[str, Any]]:
        for ch in self.list_chapters(book_name):
            if ch.get("id") == chapter_id: return ch
        return None

    def add_chapter(self, book_name: str, chapter_id: int, title: str, content: str = "", status: bool = False) -> bool:
        chapters = self.list_chapters(book_name)
        if any(ch.get("id") == chapter_id for ch in chapters): return False
        word_count = len(content.replace('\r', '').replace('\n', ''))
        chapters.append(
            {"id": chapter_id, "title": title, "content": content, "status": status, "word_count": word_count})
        chapters.sort(key=lambda x: x["id"])
        self._save_json(os.path.join(self.data_root, book_name, "chapters.json"), chapters)
        if status: self.update_total_words(book_name)
        return True

    def update_chapter(self, book_name: str, chapter_id: int, **kwargs) -> bool:
        chapters = self.list_chapters(book_name)
        target = next((ch for ch in chapters if ch.get("id") == chapter_id), None)
        if not target: return False
        old_status = target.get("status")
        if "title" in kwargs: target["title"] = kwargs["title"]
        if "content" in kwargs:
            target["content"] = kwargs["content"]
            target["word_count"] = len(kwargs["content"].replace('\r', '').replace('\n', ''))
        if "status" in kwargs: target["status"] = kwargs["status"]
        self._save_json(os.path.join(self.data_root, book_name, "chapters.json"), chapters)
        if "status" in kwargs and old_status != kwargs["status"]:
            self.update_total_words(book_name)
        elif "content" in kwargs and target.get("status"):
            self.update_total_words(book_name)
        return True

    def delete_chapter(self, book_name: str, chapter_id: int) -> bool:
        chapters = self.list_chapters(book_name)
        new_chapters = [ch for ch in chapters if ch.get("id") != chapter_id]
        if len(new_chapters) == len(chapters): return False
        self._save_json(os.path.join(self.data_root, book_name, "chapters.json"), new_chapters)
        self.delete_chapter_analysis(book_name, chapter_id)
        self.update_total_words(book_name)
        return True

    def list_chapter_analyses(self, book_name: str) -> List[Dict[str, Any]]:
        return self._load_json(os.path.join(self.data_root, book_name, "chapter_analysis.json"), [])

    def get_chapter_analysis(self, book_name: str, chapter_id: int) -> Optional[Dict[str, Any]]:
        for an in self.list_chapter_analyses(book_name):
            if an.get("chapter_id") == chapter_id: return an
        return None

    def add_or_update_chapter_analysis(self, book_name: str, chapter_id: int,
                                       summary: str = "", key_events: List[str] = None,
                                       story_position: str = "", emotion_intensity: int = 1,
                                       involved_characters: List[str] = None,
                                       bound_main_node_id: str = "", bound_sub_node_id: str = "") -> bool:
        analyses = self.list_chapter_analyses(book_name)
        existing = next((an for an in analyses if an.get("chapter_id") == chapter_id), None)
        data = {
            "chapter_id": chapter_id, "summary": summary, "key_events": key_events or [],
            "story_position": story_position, "emotion_intensity": max(1, min(10, emotion_intensity)),
            "involved_characters": involved_characters or [],
            "bound_main_node_id": bound_main_node_id, "bound_sub_node_id": bound_sub_node_id
        }
        if existing:
            existing.update(data)
        else:
            analyses.append(data)
        self._save_json(os.path.join(self.data_root, book_name, "chapter_analysis.json"), analyses)
        return True

    def delete_chapter_analysis(self, book_name: str, chapter_id: int) -> bool:
        analyses = self.list_chapter_analyses(book_name)
        new_analyses = [an for an in analyses if an.get("chapter_id") != chapter_id]
        if len(new_analyses) == len(analyses): return False
        self._save_json(os.path.join(self.data_root, book_name, "chapter_analysis.json"), new_analyses)
        return True

    # ==================== 角色相关操作 (含级联删除与重命名) ====================
    def list_characters(self, book_name: str) -> List[Dict[str, Any]]:
        return self._load_json(os.path.join(self.data_root, book_name, "characters.json"), [])

    def get_character(self, book_name: str, character_name: str) -> Optional[Dict[str, Any]]:
        for ch in self.list_characters(book_name):
            if ch.get("character_name") == character_name: return ch
        return None

    def add_character(self, book_name: str, character_name: str,
                      importance_level: int = 1, profile: str = "",
                      relationships: List[Dict[str, Any]] = None, change_log: str = "") -> bool:
        if self.get_character(book_name, character_name): return False
        new_char = {
            "character_name": character_name, "importance_level": importance_level,
            "profile": profile, "relationships": relationships or [],
            "change_log": change_log, "arc_history": []  # 弧光历史记录表
        }
        characters = self.list_characters(book_name)
        characters.append(new_char)
        self._save_json(os.path.join(self.data_root, book_name, "characters.json"), characters)
        return True

    def update_character(self, book_name: str, character_name: str, **kwargs) -> bool:
        characters = self.list_characters(book_name)
        target = next((ch for ch in characters if ch.get("character_name") == character_name), None)
        if not target: return False
        allowed = ["importance_level", "profile", "relationships", "change_log", "arc_history"]
        for key, value in kwargs.items():
            if key in allowed: target[key] = value

        new_name = kwargs.get("new_character_name")
        if new_name and new_name != character_name:
            target["character_name"] = new_name
            analyses = self.list_chapter_analyses(book_name)
            is_changed = False
            for an in analyses:
                involved = an.get("involved_characters", [])
                if character_name in involved:
                    involved.remove(character_name)
                    if new_name not in involved: involved.append(new_name)
                    is_changed = True
            if is_changed: self._save_json(os.path.join(self.data_root, book_name, "chapter_analysis.json"), analyses)

        self._save_json(os.path.join(self.data_root, book_name, "characters.json"), characters)
        return True

    def delete_character(self, book_name: str, character_name: str) -> bool:
        characters = self.list_characters(book_name)
        new_chars = [ch for ch in characters if ch.get("character_name") != character_name]
        if len(new_chars) == len(characters): return False
        self._save_json(os.path.join(self.data_root, book_name, "characters.json"), new_chars)

        analyses = self.list_chapter_analyses(book_name)
        is_changed = False
        for an in analyses:
            involved = an.get("involved_characters", [])
            if character_name in involved:
                involved.remove(character_name)
                is_changed = True
        if is_changed: self._save_json(os.path.join(self.data_root, book_name, "chapter_analysis.json"), analyses)
        return True

    # ==================== 势力分布相关操作 (新增) ====================
    def list_factions(self, book_name: str) -> List[Dict[str, Any]]:
        return self._load_json(os.path.join(self.data_root, book_name, "factions.json"), [])

    def get_faction(self, book_name: str, name: str) -> Optional[Dict[str, Any]]:
        for f in self.list_factions(book_name):
            if f.get("name") == name: return f
        return None

    def add_faction(self, book_name: str, name: str, description: str = "",
                    key_figures: List[str] = None, history_log: List[str] = None) -> bool:
        if self.get_faction(book_name, name): return False
        factions = self.list_factions(book_name)
        factions.append({
            "name": name,
            "description": description,
            "key_figures": key_figures or [],
            "history_log": history_log or []  # 势力动态编年史
        })
        self._save_json(os.path.join(self.data_root, book_name, "factions.json"), factions)
        return True

    def update_faction(self, book_name: str, name: str, **kwargs) -> bool:
        factions = self.list_factions(book_name)
        target = next((f for f in factions if f.get("name") == name), None)
        if not target: return False

        allowed = ["description", "key_figures", "history_log"]
        for key, value in kwargs.items():
            if key in allowed: target[key] = value

        new_name = kwargs.get("new_name")
        if new_name and new_name != name:
            target["name"] = new_name

        self._save_json(os.path.join(self.data_root, book_name, "factions.json"), factions)
        return True

    def delete_faction(self, book_name: str, name: str) -> bool:
        factions = self.list_factions(book_name)
        new_factions = [f for f in factions if f.get("name") != name]
        if len(new_factions) == len(factions): return False
        self._save_json(os.path.join(self.data_root, book_name, "factions.json"), new_factions)
        return True

    # ==================== 伏笔、记忆包、故事线 ====================
    def clean_storylines_by_chapter(self, book_name: str, chapter_id: int) -> bool:
        """【新增】撤销指定章节对故事线造成的改变（时光倒流机制）"""
        storylines = self.list_storylines(book_name)
        is_changed = False

        # 逆序遍历，方便在遍历时安全删除元素
        for i in range(len(storylines) - 1, -1, -1):
            main_node = storylines[i]

            # 1. 如果这个大节点是本章新建的，连根拔起直接删掉
            if main_node.get("created_by_chapter") == chapter_id:
                del storylines[i]
                is_changed = True
                continue

            # 2. 如果这个大节点是本章宣告完结的，撤销它的完结状态！
            if main_node.get("completed_by_chapter") == chapter_id:
                main_node["is_completed"] = False
                main_node["completed_by_chapter"] = None
                is_changed = True

            # 3. 处理大节点里面的小节点（子节点）
            if "children" in main_node:
                children = main_node["children"]
                for j in range(len(children) - 1, -1, -1):
                    sub_node = children[j]

                    # 如果小节点是本章新建的，删掉
                    if sub_node.get("created_by_chapter") == chapter_id:
                        del children[j]
                        is_changed = True
                        continue

                    # 如果小节点是本章完结的，撤销完结状态
                    if sub_node.get("completed_by_chapter") == chapter_id:
                        sub_node["is_completed"] = False
                        sub_node["completed_by_chapter"] = None
                        is_changed = True

        if is_changed:
            self.update_storylines(book_name, storylines)

        return is_changed

    def clean_foreshadows_by_chapter(self, book_name: str, chapter_id: int) -> bool:
        """【新增】清理指定章节产生的伏笔数据（重定稿时使用）"""
        foreshadows = self.list_foreshadows(book_name)
        new_fs = []
        is_changed = False
        deleted_names = []

        for f in foreshadows:
            # 情况 1：如果是本章刚“埋设”的伏笔 -> 直接将其删除（不加入新列表）
            if f.get("planted_chapter") == chapter_id:
                deleted_names.append(f.get("name"))
                is_changed = True
                continue

            # 情况 2：如果是本章“揭示(填坑)”的伏笔 -> 撤销揭示状态，退回“埋设中”
            if f.get("revealed_chapter") == chapter_id:
                f["revealed_chapter"] = None
                f["status"] = "埋设中"
                is_changed = True

            new_fs.append(f)

        # 1. 保存清理后的伏笔文件
        if is_changed:
            self._save_json(os.path.join(self.data_root, book_name, "foreshadows.json"), new_fs)

        # 2. 级联清理：如果彻底删除了某些伏笔，需要把故事线节点上绑定的对应名字也洗掉
        if deleted_names:
            storylines = self.list_storylines(book_name)
            story_changed = False
            for p in storylines:
                for c in p.get("children", []):
                    old_len = len(c.get("foreshadows", []))
                    c["foreshadows"] = [name for name in c.get("foreshadows", []) if name not in deleted_names]
                    if len(c["foreshadows"]) != old_len:
                        story_changed = True
            if story_changed:
                self.update_storylines(book_name, storylines)

        return is_changed

    def list_foreshadows(self, book_name: str) -> List[Dict[str, Any]]:
        return self._load_json(os.path.join(self.data_root, book_name, "foreshadows.json"), [])

    def get_foreshadow(self, book_name: str, name: str) -> Optional[Dict[str, Any]]:
        for f in self.list_foreshadows(book_name):
            if f.get("name") == name: return f
        return None

    def add_foreshadow(self, book_name: str, name: str, planted_chapter: int,
                       content: str, revealed_chapter: int = None, status: str = "埋设中") -> bool:
        if self.get_foreshadow(book_name, name): return False
        foreshadows = self.list_foreshadows(book_name)
        foreshadows.append(
            {"name": name, "planted_chapter": planted_chapter, "content": content, "revealed_chapter": revealed_chapter,
             "status": status})
        self._save_json(os.path.join(self.data_root, book_name, "foreshadows.json"), foreshadows)
        return True

    def update_foreshadow(self, book_name: str, name: str, **kwargs) -> bool:
        foreshadows = self.list_foreshadows(book_name)
        target = next((f for f in foreshadows if f.get("name") == name), None)
        if not target: return False
        for key, value in kwargs.items():
            if key in ["planted_chapter", "content", "revealed_chapter", "status"]: target[key] = value
        self._save_json(os.path.join(self.data_root, book_name, "foreshadows.json"), foreshadows)
        return True

    def delete_foreshadow(self, book_name: str, name: str) -> bool:
        foreshadows = self.list_foreshadows(book_name)
        new_fs = [f for f in foreshadows if f.get("name") != name]
        if len(new_fs) == len(foreshadows): return False
        self._save_json(os.path.join(self.data_root, book_name, "foreshadows.json"), new_fs)
        return True

    def list_memory_packs(self, book_name: str) -> List[Dict[str, Any]]:
        return self._load_json(os.path.join(self.data_root, book_name, "memory_packs.json"), [])

    def get_memory_pack(self, book_name: str, title: str) -> Optional[Dict[str, Any]]:
        for p in self.list_memory_packs(book_name):
            if p.get("title") == title: return p
        return None

    def add_memory_pack(self, book_name: str, start_chapter_id: int, end_chapter_id: int,
                        title: str, content: str) -> bool:
        if self.get_memory_pack(book_name, title): return False
        packs = self.list_memory_packs(book_name)
        packs.append({"start_chapter_id": start_chapter_id, "end_chapter_id": end_chapter_id, "title": title,
                      "content": content})
        self._save_json(os.path.join(self.data_root, book_name, "memory_packs.json"), packs)
        return True

    def update_memory_pack(self, book_name: str, title: str, **kwargs) -> bool:
        packs = self.list_memory_packs(book_name)
        target = next((p for p in packs if p.get("title") == title), None)
        if not target: return False
        for key, value in kwargs.items():
            if key in ["start_chapter_id", "end_chapter_id", "content"]: target[key] = value
        self._save_json(os.path.join(self.data_root, book_name, "memory_packs.json"), packs)
        return True

    def delete_memory_pack(self, book_name: str, title: str) -> bool:
        packs = self.list_memory_packs(book_name)
        new_packs = [p for p in packs if p.get("title") != title]
        if len(new_packs) == len(packs): return False
        self._save_json(os.path.join(self.data_root, book_name, "memory_packs.json"), new_packs)
        return True

    def list_storylines(self, book_name: str) -> List[Dict[str, Any]]:
        return self._load_json(os.path.join(self.data_root, book_name, "storylines.json"), [])

    def update_storylines(self, book_name: str, nodes: List[Dict[str, Any]]) -> bool:
        self._save_json(os.path.join(self.data_root, book_name, "storylines.json"), nodes)
        return True

    def _load_json(self, file_path: str, default=None):
        if not os.path.exists(file_path): return default if default is not None else {}
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            return default if default is not None else {}

    def _save_json(self, file_path: str, data: Any) -> None:
        with open(file_path, 'w', encoding='utf-8') as f: json.dump(data, f, ensure_ascii=False, indent=2)