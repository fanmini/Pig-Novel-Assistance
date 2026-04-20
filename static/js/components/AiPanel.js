// static/js/components/AiPanel.js
const { ref, nextTick, watch } = Vue;
import { appStore, aiStore, toastStore } from '../store.js';

export default {
    template: `
        <div class="ai-sidebar" v-show="appStore.showAiSidebar">
            <div class="ai-header">
                <span>🤖 文形小助手</span>
            </div>
            <div class="ai-messages">
                <div v-for="(msg, idx) in aiStore.messages" :key="idx" class="message" :class="msg.role">
                    <div class="message-bubble">{{ msg.content }}</div>
                </div>
            </div>
            <div class="ai-input-area">
                <div class="mode-switch">
                    <div class="mode-btn" :class="{ active: aiStore.mode === 'generate' }" @click="aiStore.mode = 'generate'">章节生成</div>
                    <div class="mode-btn" :class="{ active: aiStore.mode === 'continue' }" @click="aiStore.mode = 'continue'">章节续写</div>
                    <button class="expand-toggle" @click="aiStore.inputExpanded = !aiStore.inputExpanded" :title="aiStore.inputExpanded ? '收起' : '展开'" style="margin-left: auto; background: none; border: none; font-size: 16px; cursor: pointer; color: #64748b; width: 28px; height: 28px; display: flex; align-items: center; justify-content: center; border-radius: 20px;">
                        {{ aiStore.inputExpanded ? '▲' : '▼' }}
                    </button>
                </div>
                <div class="input-wrapper">
                    <textarea ref="aiTextareaRef" v-model="aiStore.input" class="ai-textarea" :class="{ expanded: aiStore.inputExpanded }" placeholder="输入提示词..." @input="adjustHeight"></textarea>
                    <button class="send-btn" @click="sendMessage">发送</button>
                </div>
            </div>
        </div>
    `,
    setup() {
        const aiTextareaRef = ref(null);

        // 文本框高度自适应
        const adjustHeight = () => {
            const el = aiTextareaRef.value;
            if (!el) return;
            el.style.height = 'auto';
            const maxH = aiStore.inputExpanded ? 400 : 130;
            let newH = el.scrollHeight;
            if (newH > maxH) newH = maxH;
            el.style.height = newH + 'px';
        };

        watch(() => aiStore.input, () => nextTick(adjustHeight));
        watch(() => aiStore.inputExpanded, () => nextTick(adjustHeight));

        // 滚动到底部
        const scrollToBottom = () => {
            nextTick(() => {
                const el = document.querySelector('.ai-messages');
                if(el) el.scrollTop = el.scrollHeight;
            });
        };

        // 发送消息
        const sendMessage = async () => {
            const msg = aiStore.input.trim();
            if (aiStore.mode === 'continue' && !msg) {
                toastStore.show('续写模式下不能为空', 'error');
                return;
            }
            if (!msg) return;

            aiStore.messages.push({ role: 'user', content: msg });
            aiStore.input = '';

            // 模拟回复延迟 (你可以替换成真实的后端 API 请求)
            setTimeout(() => {
                aiStore.messages.push({ role: 'assistant', content: \`🤖 收到：关于“\${msg}”，建议记录到伏笔或角色弧光中～\` });
                scrollToBottom();
            }, 500);

            nextTick(adjustHeight);
        };

        return {
            appStore,
            aiStore,
            aiTextareaRef,
            adjustHeight,
            sendMessage
        };
    }
};