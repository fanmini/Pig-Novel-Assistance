// static/js/store.js
const { ref, reactive, computed } = Vue; // 因为使用 CDN，直接从全局 Vue 获取

// 1. 提示框状态管理 (Toast)
export const toastStore = reactive({
    toasts: [],
    show(message, type = 'info') {
        const id = Date.now();
        this.toasts.push({ id, message, type });
        setTimeout(() => {
            this.toasts = this.toasts.filter(t => t.id !== id);
        }, 2500);
    }
});

// 2. 全局应用核心状态 (书籍、UI 面板)
export const appStore = reactive({
    books: [],
    currentBook: null,
    activePanel: 'chapters', // 'chapters', 'analysis', 'knowledge', 'characters', 'ai'
    showAiSidebar: true,
    deletingItemId: null // 用于确认删除状态 { type, key }
});

// 3. 章节与编辑器状态
export const editorStore = reactive({
    chapters: [],
    currentChapterId: null,
    editMode: 'chapter', // 'chapter', 'meta', 'character'
    editorTitle: '',
    editorContent: '',

    // 用于记录正在编辑的对象引用
    editingMeta: null,
    editingCharacter: null,
    editingStorylineNode: null,
});

// 4. 数据缓存库 (角色、分析、故事线、知识库)
export const dataStore = reactive({
    bookDetails: {},
    analysisCache: {}, // 格式: { [bookName]: [] }
    charactersList: [],
    factionsList: [],
    foreshadowsList: [],
    memoryPacksList: [],
    storylineNodes: [],

    get currentAnalyses() {
        return this.analysisCache[appStore.currentBook] || [];
    },
    get metaList() {
        return this.bookDetails.meta_list || [];
    },
    get sortedCharacters() {
        return [...this.charactersList].sort((a,b) => (b.importance_level || 0) - (a.importance_level || 0));
    }
});

// 5. AI 助手状态
export const aiStore = reactive({
    models: [],
    config: { model: 'openai/gpt-4o-mini', api_key: '', temperature: 0.7, max_tokens: 1024, top_p: 1.0 },
    messages: [{ role: 'assistant', content: '你好！我是你的写作AI～' }],
    input: '',
    mode: 'generate', // 'generate' | 'continue'
    inputExpanded: false,
    isTestingConnection: false
});

// 6. UI 弹窗状态 (分离各种 Modal 的可见性与表单数据)
export const modalStore = reactive({
    // 编辑章节分析
    analysisModal: { visible: false, title: '', field: '', value: '', chapterId: null, isTextarea: false },
    // 角色选择
    roleModal: { visible: false, chapterId: null, selectedRoles: [] },
    // 伏笔关联与选择
    fsModal: { visible: false, selected: [], newName: '' },
    // 查看伏笔详情
    viewingFsDetail: null,
    // 势力编辑
    factionModal: { visible: false, editingFaction: null },

    // 表单状态区
    factionForm: { name: '', description: '', history_log: '' },
    charForm: { name: '', importance_level: 1, change_log: '', relationships: '', profile: '' },
    foreshadowForm: { name: '', planted_chapter: 1, content: '', revealed_chapter: null, status: '埋设中' },
    memoryPackForm: { start_chapter_id: 1, end_chapter_id: 1, title: '', content: '' }
});