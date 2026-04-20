// static/js/api.js
const API_BASE = '/api';

/**
 * 基础封装的 Fetch 函数，统一处理错误
 */
export async function apiFetch(url, options = {}) {
    const res = await fetch(url, options);
    if (!res.ok) {
        const errData = await res.json().catch(() => ({}));
        throw new Error(errData.error || '请求失败');
    }
    return res.json();
}

/**
 * 书籍相关接口
 */
export const bookApi = {
    getList: () => apiFetch(`${API_BASE}/books`),
    create: (name) => apiFetch(`${API_BASE}/books`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ name })
    }),
    getDetails: (bookName) => apiFetch(`${API_BASE}/books/${bookName}`),
    update: (bookName, data) => apiFetch(`${API_BASE}/books/${bookName}`, {
        method: 'PUT',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(data)
    }),
    delete: (bookName) => apiFetch(`${API_BASE}/books/${bookName}`, { method: 'DELETE' })
};

/**
 * 章节与分析相关接口
 */
export const chapterApi = {
    getList: (bookName) => apiFetch(`${API_BASE}/books/${bookName}/chapters`),
    create: (bookName, data) => apiFetch(`${API_BASE}/books/${bookName}/chapters`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    }),
    update: (bookName, chapterId, data) => apiFetch(`${API_BASE}/books/${bookName}/chapters/${chapterId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    }),
    delete: (bookName, chapterId) => apiFetch(`${API_BASE}/books/${bookName}/chapters/${chapterId}`, { method: 'DELETE' }),

    // 章节分析
    getAnalyses: (bookName) => apiFetch(`${API_BASE}/books/${bookName}/chapter_analyses`),
    updateAnalysis: (bookName, chapterId, data) => apiFetch(`${API_BASE}/books/${bookName}/chapter_analyses/${chapterId}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    })
};

/**
 * 角色与势力相关接口
 */
export const entityApi = {
    // 角色
    getCharacters: (bookName) => apiFetch(`${API_BASE}/books/${bookName}/characters`),
    createCharacter: (bookName, data) => apiFetch(`${API_BASE}/books/${bookName}/characters`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    }),
    updateCharacter: (bookName, charName, data) => apiFetch(`${API_BASE}/books/${bookName}/characters/${charName}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    }),
    deleteCharacter: (bookName, charName) => apiFetch(`${API_BASE}/books/${bookName}/characters/${charName}`, { method: 'DELETE' }),

    // 势力
    getFactions: (bookName) => apiFetch(`${API_BASE}/books/${bookName}/factions`),
    createFaction: (bookName, data) => apiFetch(`${API_BASE}/books/${bookName}/factions`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    }),
    updateFaction: (bookName, factionName, data) => apiFetch(`${API_BASE}/books/${bookName}/factions/${factionName}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    }),
    deleteFaction: (bookName, factionName) => apiFetch(`${API_BASE}/books/${bookName}/factions/${factionName}`, { method: 'DELETE' })
};

/**
 * 知识库 (伏笔、记忆包、故事线) 相关接口
 */
export const kbApi = {
    // 伏笔
    getForeshadows: (bookName) => apiFetch(`${API_BASE}/books/${bookName}/foreshadows`),
    createForeshadow: (bookName, data) => apiFetch(`${API_BASE}/books/${bookName}/foreshadows`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    }),
    updateForeshadow: (bookName, name, data) => apiFetch(`${API_BASE}/books/${bookName}/foreshadows/${name}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    }),
    deleteForeshadow: (bookName, name) => apiFetch(`${API_BASE}/books/${bookName}/foreshadows/${name}`, { method: 'DELETE' }),

    // 记忆包
    getMemoryPacks: (bookName) => apiFetch(`${API_BASE}/books/${bookName}/memory_packs`),
    createMemoryPack: (bookName, data) => apiFetch(`${API_BASE}/books/${bookName}/memory_packs`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    }),
    updateMemoryPack: (bookName, title, data) => apiFetch(`${API_BASE}/books/${bookName}/memory_packs/${title}`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    }),
    deleteMemoryPack: (bookName, title) => apiFetch(`${API_BASE}/books/${bookName}/memory_packs/${title}`, { method: 'DELETE' }),

    // 故事线
    getStorylines: (bookName) => apiFetch(`${API_BASE}/books/${bookName}/storylines`),
    updateStorylines: (bookName, nodes) => apiFetch(`${API_BASE}/books/${bookName}/storylines`, {
        method: 'PUT', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ nodes })
    })
};

/**
 * AI 相关接口
 */
export const aiApi = {
    getModels: () => apiFetch(`${API_BASE}/ai/models`),
    getConfig: () => apiFetch(`${API_BASE}/ai/config`),
    saveConfig: (data) => apiFetch(`${API_BASE}/ai/config`, {
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    }),
    chat: (data) => fetch(`${API_BASE}/ai/chat`, {  // chat 特殊处理，因为有时候涉及 stream
        method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(data)
    })
};