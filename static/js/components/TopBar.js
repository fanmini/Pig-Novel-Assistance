// static/js/components/TopBar.js
const { ref } = Vue;
import { appStore, toastStore } from '../store.js';
import { bookApi } from '../api.js';

export default {
    template: `
        <div class="top-bar">
            <div class="left-group">
                <div class="book-manager">
                    <template v-if="isEditingBookName">
                        <input v-model="newBookName" class="book-name-input" placeholder="输入书名" @keyup.enter="createBook" autofocus>
                        <div class="book-edit-actions">
                            <button class="book-action-btn" style="color:#10b981;" @click="createBook">✓</button>
                            <button class="book-action-btn" style="color:#ef4444;" @click="isEditingBookName = false; newBookName = ''">✕</button>
                        </div>
                    </template>
                    <template v-else>
                        <div class="book-selector">
                            <span>📚</span>
                            <select v-model="appStore.currentBook">
                                <option v-for="b in appStore.books" :key="b" :value="b">{{ b }}</option>
                                <option v-if="!appStore.books.length" disabled>暂无书籍</option>
                            </select>
                        </div>
                        <button class="delete-book-btn" v-if="appStore.currentBook" @click="deleteBook">✕</button>
                        <button class="new-book-btn" @click="isEditingBookName = true">➕</button>
                    </template>
                </div>
            </div>

            <div class="center-title">{{ appStore.currentBook || '未选择书籍' }}</div>

            <div class="right-group">
                <div class="save-dropdown" @click.stop="toggleSaveDropdown">
                    <button class="save-btn">💾 保存 <span class="arrow">▼</span></button>
                    <div v-if="showSaveDropdown" class="dropdown-menu">
                        <div class="dropdown-item" @click.stop="handleSave('final')">定稿保存</div>
                        <div class="dropdown-item" @click.stop="handleSave('reFinal')">重新定稿</div>
                    </div>
                </div>
                <div class="ai-icon" @click="appStore.showAiSidebar = !appStore.showAiSidebar">✨</div>
            </div>
        </div>
    `,
    setup() {
        const isEditingBookName = ref(false);
        const newBookName = ref('');
        const showSaveDropdown = ref(false);

        // 创建新书
        const createBook = async () => {
            const name = newBookName.value.trim();
            if (!name) return toastStore.show('书名不能为空', 'error');
            try {
                await bookApi.create(name);
                newBookName.value = '';
                isEditingBookName.value = false;

                // 刷新书籍列表并选中新书
                const books = await bookApi.getList();
                appStore.books = books;
                appStore.currentBook = name;
                toastStore.show('创建成功', 'success');
            } catch (e) {
                toastStore.show(e.message, 'error');
            }
        };

        // 删除书籍
        const deleteBook = async () => {
            if (!appStore.currentBook) return;
            if (!confirm(\`确定删除“\${appStore.currentBook}”？\`)) return;
            try {
                await bookApi.delete(appStore.currentBook);
                const books = await bookApi.getList();
                appStore.books = books;
                appStore.currentBook = books[0] || null;
                toastStore.show('删除成功', 'success');
            } catch (e) {
                toastStore.show('删除失败', 'error');
            }
        };

        // 触发保存与定稿（这里先通过抛出事件或调用 store 方法，后续会接入你的定稿流）
        const toggleSaveDropdown = () => {
            showSaveDropdown.value = !showSaveDropdown.value;
        };
        const handleSave = (type) => {
            showSaveDropdown.value = false;
            toastStore.show('正在调用 AI 定稿流...', 'info');
            // 此处后续会整合你的 triggerFinalize 逻辑
        };

        // 监听全局点击事件，关闭下拉菜单
        window.addEventListener('click', (e) => {
            if (!e.target.closest('.save-dropdown')) showSaveDropdown.value = false;
        });

        return {
            appStore,
            isEditingBookName,
            newBookName,
            showSaveDropdown,
            createBook,
            deleteBook,
            toggleSaveDropdown,
            handleSave
        };
    }
};