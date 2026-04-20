// static/js/main.js
const { createApp, watch } = Vue;

// 引入我们刚才拆分出来的 Store 和 API
import { appStore, editorStore, dataStore, toastStore } from './store.js';
import { bookApi } from './api.js';

// 引入组件
import TopBar from './components/TopBar.js';
import ActivityBar from './components/ActivityBar.js';
import SidebarPanel from './components/Sidebar.js';
import AiPanel from './components/AiPanel.js';
import Editor from './components/Editor.js';

const app = createApp({
    // 由于我们在 index.html 里还有一些全局的 Toast，这里暂时保留 delimiters，但在独立的 js 组件中可以用 {{ }}
    delimiters: ['[[', ']]'],
    components: {
        TopBar,
        ActivityBar,
        SidebarPanel,
        AiPanel,
        Editor
    },
    setup() {
        // 全局初始化逻辑：加载书籍列表
        async function initApp() {
            try {
                const books = await bookApi.getList();
                appStore.books = books;
                if (books.length > 0 && !appStore.currentBook) {
                    appStore.currentBook = books[0];
                }
            } catch (e) {
                toastStore.show(e.message || '加载书籍失败', 'error');
            }
        }

        // 监听当前书籍变化，书籍改变时重置各种状态
        watch(() => appStore.currentBook, (newBook) => {
            if (newBook) {
                // 这里后续会触发加载章节、故事线、角色等逻辑
                console.log(`切换到了书籍: ${newBook}`);
                editorStore.currentChapterId = null;
                editorStore.editMode = 'chapter';
            }
        });

        // 启动初始化
        initApp();

        return {
            toastStore,
            appStore
        };
    }
});

// 挂载应用
app.mount('#app');