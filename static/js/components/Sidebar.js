// static/js/components/Sidebar.js
const { ref, computed } = Vue;
import { appStore, editorStore, dataStore, toastStore, modalStore, aiStore } from '../store.js';
import { chapterApi, kbApi, entityApi, aiApi } from '../api.js';

export default {
    template: `
        <div class="sidebar-wrapper" style="display: flex; height: 100%;">

            <div class="sidebar-panel" v-show="appStore.activePanel === 'chapters'">
                <div class="panel-header">
                    <span>📑 章节列表</span>
                    <div class="panel-header-actions">
                        <span class="icon-btn" @click="loadChapters">🔄</span>
                        <span class="icon-btn" @click="createChapter">➕</span>
                    </div>
                </div>
                <div class="panel-content">
                    <div v-if="!editorStore.chapters.length" style="padding:12px;text-align:center;color:#94a3b8;">暂无章节</div>
                    <div v-for="ch in editorStore.chapters" :key="ch.id" class="chapter-item" :class="{ active: editorStore.currentChapterId === ch.id }" @click="selectChapter(ch.id)">
                        <div class="chapter-info">
                            <span class="chapter-index">第{{ ch.id }}章</span>
                            <span class="chapter-title-text">{{ ch.title || '无标题' }}</span>
                            <span class="chapter-wordcount">{{ ch.word_count }}字</span>
                            <span v-if="ch.status" class="chapter-status">定稿</span>
                        </div>
                        <span class="chapter-delete" @click.stop="deleteChapter(ch.id)">✕</span>
                    </div>
                </div>
            </div>

            <div class="sidebar-panel" v-show="appStore.activePanel === 'analysis'">
                <div class="panel-header">
                    <span>📊 章节分析</span>
                    <div class="panel-header-actions">
                        <span class="icon-btn" @click="loadAnalysisData">🔄</span>
                    </div>
                </div>
                <div class="panel-content">
                    <div v-for="ch in editorStore.chapters" :key="ch.id" class="analysis-chapter-item">
                        <div class="analysis-chapter-header" @click="toggleExpand(ch.id)">
                            <span class="expand-icon">{{ expandedChapters.has(ch.id) ? '▼' : '▶' }}</span>
                            <span>第{{ ch.id }}章 {{ ch.title }}</span>
                        </div>
                        <div v-if="expandedChapters.has(ch.id)" class="analysis-detail">
                            <div class="analysis-field-row">
                                <span class="field-label-text">摘要</span>
                                <div class="field-content">
                                    <span>{{ getAnalysis(ch.id).summary || '暂无' }}</span>
                                    <span class="edit-pencil" @click.stop="openEditModal(ch.id, 'summary', getAnalysis(ch.id).summary)">✎</span>
                                </div>
                            </div>
                            <div class="analysis-field-row">
                                <span class="field-label-text">角色</span>
                                <div class="field-content">
                                    <span>{{ getAnalysis(ch.id).involved_characters?.join('、') || '暂无' }}</span>
                                    <span class="edit-pencil" @click.stop="openRoleModal(ch.id)">✎</span>
                                </div>
                            </div>
                            </div>
                    </div>
                </div>
            </div>

            <div class="sidebar-panel" v-show="appStore.activePanel === 'knowledge'">
                <div class="panel-header">
                    <span>📖 知识库</span>
                    <div class="panel-header-actions">
                        <span class="icon-btn" @click="loadAllKb">🔄</span>
                        <span class="icon-btn" @click="handleKbAdd">➕</span>
                    </div>
                </div>
                <div class="kb-tabs">
                    <div class="kb-tab" :class="{ active: kbActiveTab === 'book' }" @click="kbActiveTab = 'book'">书籍知识</div>
                    <div class="kb-tab" :class="{ active: kbActiveTab === 'foreshadow' }" @click="kbActiveTab = 'foreshadow'">伏笔信息</div>
                    <div class="kb-tab" :class="{ active: kbActiveTab === 'memory' }" @click="kbActiveTab = 'memory'">区间记忆包</div>
                    <div class="kb-tab" :class="{ active: kbActiveTab === 'storyline' }" @click="kbActiveTab = 'storyline'">故事线</div>
                </div>
                <div class="panel-content">
                    <div v-if="kbActiveTab === 'book'">
                        <div class="kb-item fixed-kb-item" @click="editBookDesc">
                            <span class="kb-item-key">简介</span>
                            <span style="margin-left:12px;color:#64748b;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{{ dataStore.bookDetails.description || '暂无' }}</span>
                        </div>
                        <div v-for="meta in dataStore.metaList" :key="meta.key" class="kb-item" @click="editMeta(meta)">
                            <span class="kb-item-key">{{ meta.key }}</span>
                            <span class="kb-item-delete" @click.stop="startDelete('meta', meta.key)">✕</span>
                        </div>
                    </div>
                    <div v-if="kbActiveTab === 'storyline'">
                         <div style="text-align:center; margin-top:10px;"><button class="add-event-btn" @click="addParentStoryline">+ 新增主线大节点</button></div>
                    </div>
                </div>
            </div>

            <div class="sidebar-panel" v-show="appStore.activePanel === 'characters'">
                <div class="panel-header" style="flex-direction: column; align-items: stretch; padding: 0;">
                    <div style="display: flex; justify-content: space-between; align-items: center; padding: 10px 12px; border-bottom: 1px solid #e2e8f0;">
                        <span>👥 实体档案</span>
                        <div class="panel-header-actions">
                            <span class="icon-btn" @click="roleActiveTab === 'characters' ? loadCharacters() : loadFactions()">🔄</span>
                            <span class="icon-btn" @click="roleActiveTab === 'characters' ? newCharacter() : openFactionModal()">➕</span>
                        </div>
                    </div>
                    <div class="kb-tabs" style="border-bottom: none;">
                        <div class="kb-tab" :class="{active: roleActiveTab === 'characters'}" @click="roleActiveTab = 'characters'">👤 角色档案</div>
                        <div class="kb-tab" :class="{active: roleActiveTab === 'factions'}" @click="roleActiveTab = 'factions'">🏛️ 势力分布</div>
                    </div>
                </div>
                <div class="panel-content">
                    <div v-show="roleActiveTab === 'characters'">
                        <div v-for="char in dataStore.sortedCharacters" :key="char.character_name" class="character-card" @click="editCharacter(char)">
                            <div class="character-info">
                                <div class="character-name">{{ char.character_name }}</div>
                                <div class="character-stars">{{ '★'.repeat(char.importance_level || 1) }}</div>
                            </div>
                            <span class="character-delete" style="margin-left: auto; cursor: pointer; color: #94a3b8; padding: 4px;" @click.stop="startDelete('character', char.character_name)">✕</span>
                        </div>
                    </div>
                    </div>
            </div>

            <div class="sidebar-panel" v-show="appStore.activePanel === 'ai'">
                <div class="panel-header">
                    <span>🤖 AI 助手设置</span>
                    <div class="panel-header-actions"><span class="icon-btn" @click="loadAIModels">🔄</span></div>
                </div>
                <div class="panel-content">
                    <div class="setting-group"><label>选择模型</label>
                        <select v-model="aiStore.config.model">
                            <option v-for="m in aiStore.models" :key="m.id" :value="m.id">{{ m.name }} ({{ m.provider }})</option>
                        </select>
                    </div>
                    <div class="setting-group"><label>API Key (留空则使用环境变量)</label><input type="password" v-model="aiStore.config.api_key" placeholder="sk-..."></div>
                    <div class="setting-group"><label>Temperature: {{ aiStore.config.temperature }}</label><input type="range" min="0" max="2" step="0.1" v-model="aiStore.config.temperature"></div>
                    <div class="config-actions" style="display: flex; gap: 10px; justify-content: flex-end;">
                        <button class="modal-btn secondary" @click="testAiConnection" :disabled="aiStore.isTestingConnection">
                            {{ aiStore.isTestingConnection ? '⏳ 测试中...' : '🔌 测试连接' }}
                        </button>
                        <button class="modal-btn primary" @click="saveAIConfig">💾 保存配置</button>
                    </div>
                </div>
            </div>

            </div>
    `,
    setup() {
        const expandedChapters = ref(new Set());
        const kbActiveTab = ref('book');
        const roleActiveTab = ref('characters');

        // ==== 章节相关逻辑 ====
        const loadChapters = async () => {
            if (!appStore.currentBook) return;
            try {
                const data = await chapterApi.getList(appStore.currentBook);
                editorStore.chapters = data.sort((a,b) => a.id - b.id);
            } catch (e) {
                toastStore.show('加载章节失败', 'error');
            }
        };

        const createChapter = async () => {
            if (!appStore.currentBook) return toastStore.show('请先选择书籍', 'error');
            const newId = editorStore.chapters.length ? Math.max(...editorStore.chapters.map(c=>c.id)) + 1 : 1;
            try {
                await chapterApi.create(appStore.currentBook, { id: newId, title: \`第\${newId}章\`, content: '', status: false });
                await loadChapters();
                editorStore.currentChapterId = newId;
                toastStore.show('章节已创建', 'success');
            } catch (e) {
                toastStore.show('创建失败', 'error');
            }
        };

        const deleteChapter = async (id) => { /* 删除逻辑 */ };
        const selectChapter = (id) => {
            editorStore.editMode = 'chapter';
            editorStore.currentChapterId = id;
        };

        // ==== 分析相关逻辑 ====
        const loadAnalysisData = async () => {
             if (!appStore.currentBook) return;
             try {
                 const data = await chapterApi.getAnalyses(appStore.currentBook);
                 dataStore.analysisCache[appStore.currentBook] = data;
             } catch(e) {}
        };
        const toggleExpand = (id) => {
            expandedChapters.value.has(id) ? expandedChapters.value.delete(id) : expandedChapters.value.add(id);
            expandedChapters.value = new Set(expandedChapters.value);
        };
        const getAnalysis = (id) => {
            return dataStore.currentAnalyses.find(a => a.chapter_id === id) || { chapter_id: id, summary: '' };
        };

        // ==== 其他所有的方法都可以平滑移植到这里 ====
        const loadAllKb = () => { /* 刷新知识库 */ };
        const handleKbAdd = () => { /* 新增知识库条目 */ };
        const editBookDesc = () => { /* 编辑简介 */ };
        const editMeta = (meta) => { /* 编辑元数据 */ };
        const startDelete = (type, key) => { /* 删除确认逻辑 */ };
        const loadCharacters = () => { /* 加载角色 */ };
        const loadFactions = () => { /* 加载势力 */ };
        const newCharacter = () => { /* 新建角色 */ };
        const openFactionModal = () => { /* 打开势力弹窗 */ };
        const editCharacter = (char) => { /* 编辑角色 */ };
        const loadAIModels = async () => { /* 加载模型 */ };
        const testAiConnection = async () => { /* 测试AI */ };
        const saveAIConfig = async () => { /* 保存配置 */ };

        return {
            appStore,
            editorStore,
            dataStore,
            modalStore,
            aiStore,
            expandedChapters,
            kbActiveTab,
            roleActiveTab,

            // 方法
            loadChapters, createChapter, deleteChapter, selectChapter,
            loadAnalysisData, toggleExpand, getAnalysis,
            loadAllKb, handleKbAdd, editBookDesc, editMeta, startDelete,
            loadCharacters, loadFactions, newCharacter, openFactionModal, editCharacter,
            loadAIModels, testAiConnection, saveAIConfig
        };
    }
};