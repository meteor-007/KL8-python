/**
 * 🧬 K8-Quant Gemini 智能操盘大脑 (Web UI Widget)
 * 提供大屏右下角悬浮入口、自由对话、一键大白话量化分析与 API Key 快捷配置
 */

(function() {
    // 注入 CSS 样式
    const style = document.createElement('style');
    style.textContent = `
        /* AI 悬浮球 */
        .ai-fab-btn {
            position: fixed;
            bottom: 30px;
            right: 30px;
            width: 60px;
            height: 60px;
            border-radius: 50%;
            background: linear-gradient(135deg, #00f2fe 0%, #4facfe 50%, #6b11ff 100%);
            box-shadow: 0 0 20px rgba(0, 242, 254, 0.6), 0 0 40px rgba(107, 17, 255, 0.4);
            border: 2px solid rgba(255, 255, 255, 0.6);
            display: flex;
            align-items: center;
            justify-content: center;
            cursor: pointer;
            z-index: 9999;
            transition: all 0.3s cubic-bezier(0.175, 0.885, 0.32, 1.275);
            animation: ai-pulse 2.5s infinite;
        }
        .ai-fab-btn:hover {
            transform: scale(1.12) rotate(5deg);
            box-shadow: 0 0 30px rgba(0, 242, 254, 0.9), 0 0 60px rgba(107, 17, 255, 0.7);
        }
        .ai-fab-btn svg {
            width: 32px;
            height: 32px;
            fill: #ffffff;
            filter: drop-shadow(0 2px 4px rgba(0,0,0,0.3));
        }
        @keyframes ai-pulse {
            0% { box-shadow: 0 0 15px rgba(0, 242, 254, 0.5); }
            50% { box-shadow: 0 0 30px rgba(0, 242, 254, 0.8), 0 0 50px rgba(107, 17, 255, 0.5); }
            100% { box-shadow: 0 0 15px rgba(0, 242, 254, 0.5); }
        }

        /* AI 抽屉面板 */
        .ai-chat-drawer {
            position: fixed;
            bottom: 100px;
            right: 30px;
            width: 440px;
            max-width: calc(100vw - 40px);
            height: 620px;
            max-height: calc(100vh - 140px);
            background: rgba(13, 17, 28, 0.96);
            backdrop-filter: blur(20px);
            border: 1px solid rgba(0, 242, 254, 0.3);
            border-radius: 18px;
            box-shadow: 0 15px 50px rgba(0, 0, 0, 0.8), 0 0 30px rgba(0, 242, 254, 0.2);
            z-index: 9999;
            display: flex;
            flex-direction: column;
            overflow: hidden;
            transform-origin: bottom right;
            transform: scale(0.8) translateY(40px);
            opacity: 0;
            pointer-events: none;
            transition: all 0.3s cubic-bezier(0.2, 0.8, 0.2, 1);
        }
        .ai-chat-drawer.open {
            transform: scale(1) translateY(0);
            opacity: 1;
            pointer-events: auto;
        }

        /* 顶部 Header */
        .ai-drawer-header {
            padding: 14px 18px;
            background: linear-gradient(90deg, rgba(0, 242, 254, 0.15), rgba(107, 17, 255, 0.15));
            border-bottom: 1px solid rgba(0, 242, 254, 0.2);
            display: flex;
            align-items: center;
            justify-content: space-between;
        }
        .ai-header-title {
            display: flex;
            align-items: center;
            gap: 10px;
            font-size: 15px;
            font-weight: bold;
            color: #00f2fe;
            letter-spacing: 0.5px;
        }
        .ai-header-badge {
            font-size: 11px;
            padding: 2px 7px;
            border-radius: 10px;
            background: rgba(0, 242, 254, 0.2);
            border: 1px solid #00f2fe;
            color: #e0faff;
        }
        .ai-header-actions {
            display: flex;
            gap: 8px;
        }
        .ai-header-btn {
            background: none;
            border: none;
            color: #8fa0b5;
            cursor: pointer;
            padding: 4px;
            border-radius: 4px;
            transition: color 0.2s;
        }
        .ai-header-btn:hover {
            color: #ffffff;
            background: rgba(255, 255, 255, 0.1);
        }

        /* 快捷功能区 */
        .ai-quick-actions {
            padding: 10px 14px;
            background: rgba(6, 9, 17, 0.6);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            gap: 8px;
            overflow-x: auto;
            white-space: nowrap;
        }
        .ai-quick-btn {
            font-size: 12px;
            padding: 5px 10px;
            border-radius: 12px;
            background: rgba(0, 242, 254, 0.1);
            border: 1px solid rgba(0, 242, 254, 0.3);
            color: #6ee7b7;
            cursor: pointer;
            transition: all 0.2s;
            display: inline-flex;
            align-items: center;
            gap: 4px;
        }
        .ai-quick-btn:hover {
            background: rgba(0, 242, 254, 0.25);
            color: #ffffff;
            border-color: #00f2fe;
        }

        /* 消息列表区 */
        .ai-messages-container {
            flex: 1;
            padding: 16px;
            overflow-y: auto;
            display: flex;
            flex-direction: column;
            gap: 14px;
            font-size: 13.5px;
            line-height: 1.6;
        }
        .ai-msg-bubble {
            max-width: 90%;
            padding: 10px 14px;
            border-radius: 14px;
            word-break: break-word;
            animation: ai-msg-fade 0.2s ease-out;
        }
        @keyframes ai-msg-fade {
            from { opacity: 0; transform: translateY(6px); }
            to { opacity: 1; transform: translateY(0); }
        }
        .ai-msg-user {
            align-self: flex-end;
            background: linear-gradient(135deg, #1e3a8a 0%, #2563eb 100%);
            color: #ffffff;
            border-bottom-right-radius: 3px;
        }
        .ai-msg-assistant {
            align-self: flex-start;
            background: rgba(22, 30, 49, 0.9);
            color: #e2e8f0;
            border: 1px solid rgba(0, 242, 254, 0.2);
            border-bottom-left-radius: 3px;
        }
        .ai-msg-assistant strong {
            color: #38bdf8;
        }

        /* 底部输入框 */
        .ai-input-area {
            padding: 12px 14px;
            background: rgba(6, 9, 17, 0.8);
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            gap: 8px;
            align-items: center;
        }
        .ai-input-box {
            flex: 1;
            background: rgba(15, 23, 42, 0.9);
            border: 1px solid rgba(0, 242, 254, 0.25);
            border-radius: 8px;
            padding: 9px 12px;
            color: #f1f5f9;
            font-size: 13.5px;
            outline: none;
            transition: border-color 0.2s;
        }
        .ai-input-box:focus {
            border-color: #00f2fe;
            box-shadow: 0 0 10px rgba(0, 242, 254, 0.2);
        }
        .ai-send-btn {
            background: linear-gradient(135deg, #00f2fe 0%, #2563eb 100%);
            border: none;
            border-radius: 8px;
            color: #ffffff;
            padding: 9px 15px;
            font-size: 13.5px;
            font-weight: bold;
            cursor: pointer;
            transition: opacity 0.2s;
        }
        .ai-send-btn:hover {
            opacity: 0.9;
        }
        .ai-send-btn:disabled {
            background: #334155;
            cursor: not-allowed;
            opacity: 0.6;
        }

        /* 设置弹窗 */
        .ai-settings-modal {
            position: absolute;
            inset: 0;
            background: rgba(10, 14, 26, 0.95);
            z-index: 10;
            padding: 24px;
            display: none;
            flex-direction: column;
            gap: 16px;
        }
        .ai-settings-modal.show {
            display: flex;
        }
    `;
    document.head.appendChild(style);

    // 构建 DOM
    const fab = document.createElement('div');
    fab.className = 'ai-fab-btn';
    fab.id = 'aiFabBtn';
    fab.title = '打开 Gemini 智能操盘大脑';
    fab.innerHTML = `
        <svg viewBox="0 0 24 24">
            <path d="M12 2L14.4 7.6L20 10L14.4 12.4L12 18L9.6 12.4L4 10L9.6 7.6L12 2Z" />
            <path d="M19 16L20.2 18.8L23 20L20.2 21.2L19 24L17.8 21.2L15 20L17.8 18.8L19 16Z" />
            <path d="M5 16L6.2 18.8L9 20L6.2 21.2L5 24L3.8 21.2L1 20L3.8 18.8L5 16Z" />
        </svg>
    `;
    document.body.appendChild(fab);

    const drawer = document.createElement('div');
    drawer.className = 'ai-chat-drawer';
    drawer.id = 'aiChatDrawer';
    drawer.innerHTML = `
        <div class="ai-drawer-header">
            <div class="ai-header-title">
                <span>🤖 Gemini 量化操盘顾问</span>
                <span class="ai-header-badge" id="aiModelBadge">Gemini 1.5 Flash</span>
            </div>
            <div class="ai-header-actions">
                <button class="ai-header-btn" id="aiSettingsBtn" title="配置 API Key">⚙️</button>
                <button class="ai-header-btn" id="aiCloseBtn" title="收起">✕</button>
            </div>
        </div>

        <div class="ai-quick-actions">
            <button class="ai-quick-btn" id="aiQuickAnalyze">🌟 今日走势大白话解读</button>
            <button class="ai-quick-btn" data-query="今天推荐的金胆核心底气足不足？有哪些连带搭档关系？">🎯 问金胆底气</button>
            <button class="ai-quick-btn" data-query="有哪些号码憋冷了很久，今天有没有均值回归的机会？">❄️ 问冷号回补</button>
            <button class="ai-quick-btn" data-query="今天大盘整体偏向小号还是大号？大环境有变盘吗？">📊 问大环境变盘</button>
        </div>

        <div class="ai-messages-container" id="aiMessagesList">
            <div class="ai-msg-bubble ai-msg-assistant">
                老朋友你好！我是你的 <strong>Gemini 智能操盘助理</strong>。<br/>
                我已全面接入快乐8量化系统（含能量场、冷号回补、历史跟班与多维共振打分）。<br/>
                点击上方 <strong>“今日走势大白话解读”</strong> 或直接向我提问，我将用最接地气的大白话为您剖析盘面！
            </div>
        </div>

        <div class="ai-input-area">
            <input type="text" class="ai-input-box" id="aiInputText" placeholder="询问走势、形态规律、号码建议..." />
            <button class="ai-send-btn" id="aiSendBtn">发送</button>
        </div>

        <!-- 设置面板 -->
        <div class="ai-settings-modal" id="aiSettingsModal">
            <div style="display:flex; justify-content:space-between; align-items:center;">
                <h4 style="margin:0; color:#00f2fe;">⚙️ Gemini AI 配置</h4>
                <button class="ai-header-btn" id="aiCloseSettings">✕</button>
            </div>
            <p style="font-size:12.5px; color:#94a3b8; margin:0;">
                系统优先使用云端环境变量配置的 <code>GEMINI_API_KEY</code>。如果部署未配置，您可在此输入个人 API Key（仅保存在您的浏览器本地）：
            </p>
            <div>
                <label style="font-size:12px; color:#cbd5e1; display:block; margin-bottom:6px;">Google Gemini API Key:</label>
                <input type="password" id="aiCustomApiKey" class="ai-input-box" style="width:100%; box-sizing:border-box;" placeholder="AIzaSy..." />
            </div>
            <div>
                <label style="font-size:12px; color:#cbd5e1; display:block; margin-bottom:6px;">选择模型:</label>
                <select id="aiModelSelect" class="ai-input-box" style="width:100%;">
                    <option value="gemini-1.5-flash">Gemini 1.5 Flash (极速推荐)</option>
                    <option value="gemini-2.0-flash">Gemini 2.0 Flash (新一代)</option>
                    <option value="gemini-1.5-pro">Gemini 1.5 Pro (深度分析)</option>
                </select>
            </div>
            <button class="ai-send-btn" id="aiSaveSettings" style="margin-top:auto;">保存配置</button>
        </div>
    `;
    document.body.appendChild(drawer);

    // 交互逻辑
    const msgList = document.getElementById('aiMessagesList');
    const input = document.getElementById('aiInputText');
    const sendBtn = document.getElementById('aiSendBtn');
    const history = [];

    function getLocalApiKey() {
        return localStorage.getItem('k8_gemini_api_key') || '';
    }
    function getSelectedModel() {
        return localStorage.getItem('k8_gemini_model') || 'gemini-1.5-flash';
    }

    // 初始化设置值
    document.getElementById('aiCustomApiKey').value = getLocalApiKey();
    document.getElementById('aiModelSelect').value = getSelectedModel();

    fab.addEventListener('click', () => {
        drawer.classList.toggle('open');
    });

    document.getElementById('aiCloseBtn').addEventListener('click', () => {
        drawer.classList.remove('open');
    });

    document.getElementById('aiSettingsBtn').addEventListener('click', () => {
        document.getElementById('aiSettingsModal').classList.add('show');
    });

    document.getElementById('aiCloseSettings').addEventListener('click', () => {
        document.getElementById('aiSettingsModal').classList.remove('show');
    });

    document.getElementById('aiSaveSettings').addEventListener('click', () => {
        const key = document.getElementById('aiCustomApiKey').value.trim();
        const model = document.getElementById('aiModelSelect').value;
        localStorage.setItem('k8_gemini_api_key', key);
        localStorage.setItem('k8_gemini_model', model);
        document.getElementById('aiModelBadge').innerText = model;
        document.getElementById('aiSettingsModal').classList.remove('show');
        appendMessage('assistant', '✅ 配置已保存！后续问答将采用最新设置。');
    });

    function appendMessage(role, text) {
        const bubble = document.createElement('div');
        bubble.className = `ai-msg-bubble ${role === 'user' ? 'ai-msg-user' : 'ai-msg-assistant'}`;
        // 支持基础 markdown 换行和加粗
        let formatted = text.replace(/\n/g, '<br/>').replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        bubble.innerHTML = formatted;
        msgList.appendChild(bubble);
        msgList.scrollTop = msgList.scrollHeight;
    }

    async function sendChat(userText) {
        if (!userText.trim()) return;
        appendMessage('user', userText);
        input.value = '';
        sendBtn.disabled = true;
        sendBtn.innerText = '思考中...';

        const loadingBubble = document.createElement('div');
        loadingBubble.className = 'ai-msg-bubble ai-msg-assistant';
        loadingBubble.innerHTML = '<em>⚡ 操盘顾问正在快速演算走势数据...</em>';
        msgList.appendChild(loadingBubble);
        msgList.scrollTop = msgList.scrollHeight;

        try {
            const resp = await fetch('/api/v1/ai/chat', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: userText,
                    history: history,
                    api_key: getLocalApiKey() || null,
                    model: getSelectedModel()
                })
            });
            const data = await resp.json();
            msgList.removeChild(loadingBubble);

            if (data.success) {
                appendMessage('assistant', data.reply);
                history.push({ role: 'user', content: userText });
                history.push({ role: 'model', content: data.reply });
            } else {
                appendMessage('assistant', `⚠️ ${data.error || '请求失败，请稍后重试'}`);
            }
        } catch (e) {
            msgList.removeChild(loadingBubble);
            appendMessage('assistant', `❌ 网络请求发生错误: ${e.message}`);
        } finally {
            sendBtn.disabled = false;
            sendBtn.innerText = '发送';
        }
    }

    async function runAnalyzeToday() {
        sendBtn.disabled = true;
        appendMessage('user', '🌟 请为我做今日走势大白话全景解读！');
        
        const loadingBubble = document.createElement('div');
        loadingBubble.className = 'ai-msg-bubble ai-msg-assistant';
        loadingBubble.innerHTML = '<em>🔍 正在全面扫描今日金胆、跟班、空间分布与冷热指标...</em>';
        msgList.appendChild(loadingBubble);
        msgList.scrollTop = msgList.scrollHeight;

        try {
            const resp = await fetch('/api/v1/ai/analyze-today', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    api_key: getLocalApiKey() || null,
                    model: getSelectedModel()
                })
            });
            const data = await resp.json();
            msgList.removeChild(loadingBubble);

            if (data.success) {
                appendMessage('assistant', data.reply);
            } else {
                appendMessage('assistant', `⚠️ ${data.error || '解读失败'}`);
            }
        } catch (e) {
            msgList.removeChild(loadingBubble);
            appendMessage('assistant', `❌ 网络请求发生错误: ${e.message}`);
        } finally {
            sendBtn.disabled = false;
        }
    }

    sendBtn.addEventListener('click', () => sendChat(input.value));
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendChat(input.value);
    });

    document.getElementById('aiQuickAnalyze').addEventListener('click', runAnalyzeToday);

    document.querySelectorAll('.ai-quick-actions .ai-quick-btn[data-query]').forEach(btn => {
        btn.addEventListener('click', function() {
            const query = this.getAttribute('data-query');
            if (query) sendChat(query);
        });
    });
})();
