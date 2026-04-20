// static/js/components/ActivityBar.js
import { appStore } from '../store.js';

export default {
    template: `
        <div class="activity-bar">
            <div class="activity-icon" :class="{ active: appStore.activePanel === 'chapters' }" @click="appStore.activePanel = 'chapters'">
                <span>📂</span><span>目录</span>
            </div>
            <div class="activity-icon" :class="{ active: appStore.activePanel === 'analysis' }" @click="appStore.activePanel = 'analysis'">
                <span>📊</span><span>分析</span>
            </div>
            <div class="activity-icon" :class="{ active: appStore.activePanel === 'knowledge' }" @click="appStore.activePanel = 'knowledge'">
                <span>📖</span><span>知识库</span>
            </div>
            <div class="activity-icon" :class="{ active: appStore.activePanel === 'characters' }" @click="appStore.activePanel = 'characters'">
                <span>👥</span><span>角色</span>
            </div>
            <div class="activity-icon" :class="{ active: appStore.activePanel === 'ai' }" @click="appStore.activePanel = 'ai'">
                <span>🤖</span><span>AI</span>
            </div>
            <div class="activity-icon">
                <span>⚙️</span><span>设置</span>
            </div>
        </div>
    `,
    setup() {
        return { appStore };
    }
};