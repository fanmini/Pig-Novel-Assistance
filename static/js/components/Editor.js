// static/js/components/Editor.js
const { watch } = Vue;
import { appStore, editorStore, toastStore } from '../store.js';
import { chapterApi } from '../api.js';

export default {
    template: `
        <div class="main-editor">
            <div v-if="editorStore.editMode === 'chapter'" class="editor-full">
                <div class="editor-container">
                    <input type="text" v-model="editorStore.editorTitle" class="chapter-title-input" placeholder="章节标题">
                    <textarea v-model="editorStore.editorContent" class="chapter-content-textarea" placeholder="正文内容..."></textarea>
                </div>
            </div>

            <div v-else class="editor-card-mode">
                <div class="editor-card">
                    <div class="editor-header">
                        <span>📄 数据编辑卡片</span>
                    </div>
                    <div class="editor-body">
                        <div style="text-align: center; color: #64748b; padding: 40px 0;">
                            这里是卡片编辑区（伏笔、记忆包、角色、故事线...）<br><br>
                            <button class="modal-btn secondary" @click="editorStore.editMode = 'chapter'">返回章节编辑</button>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    `,
    setup() {
        // 自动保存节流逻辑：监听标题和正文的变化
        let saveTimer;
        watch([() => editorStore.editorTitle, () => editorStore.editorContent], () => {
            if (editorStore.editMode !== 'chapter' || !editorStore.currentChapterId) return;
            clearTimeout(saveTimer);
            saveTimer = setTimeout(() => saveChapterSilently(), 800);
        });

        const saveChapterSilently = async () => {
            if (!appStore.currentBook || !editorStore.currentChapterId) return;
            const ch = editorStore.chapters.find(c => c.id === editorStore.currentChapterId);
            if (!ch) return;

            const newTitle = editorStore.editorTitle;
            const newContent = editorStore.editorContent;

            if (ch.title === newTitle && ch.content === newContent) return;

            const wordCount = newContent.replace(/[\\r\\n]/g, '').length;

            try {
                await chapterApi.update(appStore.currentBook, editorStore.currentChapterId, {
                    title: newTitle,
                    content: newContent
                });
                // 更新本地缓存
                ch.title = newTitle;
                ch.content = newContent;
                ch.word_count = wordCount;
            } catch (e) {
                // 静默失败，或者也可以打个 log
                console.error('自动保存失败');
            }
        };

        return {
            editorStore
        };
    }
};