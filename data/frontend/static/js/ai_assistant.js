/**
 * K8-Quant AI 智能操盘大脑客户端 (Mobile & Desktop Dual-Adaptive)
 * 对接企业专线中继 (DeepSeek)，手机端免翻墙秒级直连，结合快乐8实时量化数据进行大白话答疑。
 */
(function () {
    // 注入专用样式 (自动适配 6 大主题与移动端)
    const style = document.createElement('style');
    style.innerHTML = `
        .ai-fab-btn {
            position: fixed;
            bottom: 22px;
            right: 18px;
            z-index: 980;
            width: 52px;
            height: 52px;
            border-radius: 50%;
            background: linear-gradient(135deg, #06b6d4, #3b82f6, #8b5cf6);
            border: 2px solid rgba(255, 255, 255, 0.4);
            box-shadow: 0 4px 22px rgba(6, 182, 212, 0.5), inset 0 2px 4px rgba(255,255,255,0.4);
            color: #fff;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 24px;
            cursor: pointer;
            transition: all 0.25s cubic-bezier(0.34, 1.56, 0.64, 1);
            user-select: none;
            -webkit-tap-highlight-color: transparent;
        }
        .ai-fab-btn:hover {
            transform: scale(1.08) translateY(-2px);
            box-shadow: 0 8px 28px rgba(6, 182, 212, 0.7);
        }
        .ai-fab-btn:active {
            transform: scale(0.94);
        }
        .ai-fab-badge {
            position: absolute;
            top: -2px;
            right: -2px;
            background: #10b981;
            width: 13px;
            height: 13px;
            border-radius: 50%;
            border: 2px solid #0b1020;
            box-shadow: 0 0 8px #10b981;
        }
        .ai-typing-cursor {
            display: inline-block;
            width: 6px;
            height: 14px;
            background: #06b6d4;
            margin-left: 2px;
            vertical-align: middle;
            animation: ai-cursor-blink 0.7s infinite;
        }
        @keyframes ai-cursor-blink {
            0%, 100% { opacity: 1; }
            50% { opacity: 0; }
        }

        /* 遮罩层 */
        .ai-drawer-backdrop {
            position: fixed;
            inset: 0;
            background: rgba(0, 0, 0, 0.5);
            backdrop-filter: blur(4px);
            -webkit-backdrop-filter: blur(4px);
            z-index: 998;
            opacity: 0;
            visibility: hidden;
            transition: all 0.25s ease;
        }
        .ai-drawer-backdrop.show {
            opacity: 1;
            visibility: visible;
        }

        /* 对话抽屉容器 */
        .ai-drawer {
            position: fixed;
            top: 0;
            right: 0;
            bottom: 0;
            width: min(440px, 100vw);
            background: rgba(11, 16, 32, 0.94);
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
            border-left: 1px solid rgba(56, 189, 248, 0.25);
            box-shadow: -10px 0 40px rgba(0, 0, 0, 0.7);
            z-index: 999;
            display: flex;
            flex-direction: column;
            transform: translateX(100%);
            transition: transform 0.3s cubic-bezier(0.16, 1, 0.3, 1);
            font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, "PingFang SC", "Microsoft YaHei", sans-serif;
            color: #e2e8f0;
        }
        .ai-drawer.open {
            transform: translateX(0);
        }

        /* 移动端抽屉全宽适配 */
        @media (max-width: 640px) {
            .ai-drawer {
                width: 100vw !important;
                border-left: none !important;
            }
        }

        /* 抽屉头部 */
        .ai-drawer-header {
            padding: 14px 16px;
            background: rgba(15, 23, 42, 0.85);
            border-bottom: 1px solid rgba(56, 189, 248, 0.2);
            display: flex;
            align-items: center;
            justify-content: space-between;
            flex-shrink: 0;
        }
        .ai-header-title {
            display: flex;
            align-items: center;
            gap: 10px;
        }
        .ai-header-icon {
            width: 36px;
            height: 36px;
            border-radius: 10px;
            background: linear-gradient(135deg, rgba(6, 182, 212, 0.2), rgba(139, 92, 246, 0.2));
            border: 1px solid rgba(56, 189, 248, 0.4);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 20px;
        }
        .ai-header-text h3 {
            margin: 0;
            font-size: 14px;
            font-weight: 700;
            color: #f8fafc;
            display: flex;
            align-items: center;
            gap: 6px;
        }
        .ai-header-text p {
            margin: 2px 0 0;
            font-size: 11px;
            color: #94a3b8;
            font-family: monospace;
        }
        .ai-close-btn {
            background: rgba(255, 255, 255, 0.08);
            border: 1px solid rgba(255, 255, 255, 0.15);
            color: #94a3b8;
            width: 32px;
            height: 32px;
            border-radius: 8px;
            cursor: pointer;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 14px;
            transition: all 0.2s;
        }
        .ai-close-btn:hover {
            color: #fff;
            background: rgba(244, 63, 94, 0.2);
            border-color: rgba(244, 63, 94, 0.4);
        }

        /* 快捷提问横条 (Quick Chips) */
        .ai-chips-bar {
            padding: 8px 12px;
            background: rgba(15, 23, 42, 0.5);
            border-bottom: 1px solid rgba(255, 255, 255, 0.05);
            display: flex;
            gap: 8px;
            overflow-x: auto;
            -webkit-overflow-scrolling: touch;
            scrollbar-width: none;
            flex-shrink: 0;
        }
        .ai-chips-bar::-webkit-scrollbar { display: none; }
        .ai-chip-btn {
            white-space: nowrap;
            padding: 5px 10px;
            border-radius: 20px;
            background: rgba(6, 182, 212, 0.12);
            border: 1px solid rgba(6, 182, 212, 0.3);
            color: #38bdf8;
            font-size: 11.5px;
            font-weight: 600;
            cursor: pointer;
            transition: all 0.2s;
            flex-shrink: 0;
        }
        .ai-chip-btn:hover {
            background: rgba(6, 182, 212, 0.25);
            border-color: #00f0ff;
            color: #fff;
            transform: translateY(-1px);
        }

        /* 消息滚动区 */
        .ai-messages-container {
            flex: 1;
            overflow-y: auto;
            -webkit-overflow-scrolling: touch;
            padding: 16px 14px;
            display: flex;
            flex-direction: column;
            gap: 14px;
        }
        .ai-msg-row {
            display: flex;
            gap: 10px;
            align-items: flex-start;
            max-width: 90%;
        }
        .ai-msg-row.user {
            align-self: flex-end;
            flex-direction: row-reverse;
        }
        .ai-msg-avatar {
            width: 30px;
            height: 30px;
            border-radius: 50%;
            background: rgba(6, 182, 212, 0.2);
            border: 1px solid rgba(6, 182, 212, 0.4);
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: 15px;
            flex-shrink: 0;
        }
        .ai-msg-row.user .ai-msg-avatar {
            background: rgba(245, 158, 11, 0.2);
            border-color: rgba(245, 158, 11, 0.4);
        }
        .ai-bubble {
            padding: 10px 14px;
            border-radius: 12px;
            font-size: 13px;
            line-height: 1.6;
            word-break: break-word;
        }
        .ai-msg-row.assistant .ai-bubble {
            background: rgba(30, 41, 59, 0.75);
            border: 1px solid rgba(56, 189, 248, 0.2);
            color: #f1f5f9;
            box-shadow: 0 2px 10px rgba(0, 0, 0, 0.2);
        }
        .ai-msg-row.assistant .ai-bubble strong {
            color: #38bdf8;
        }
        .ai-msg-row.user .ai-bubble {
            background: linear-gradient(135deg, #0284c7, #2563eb);
            color: #ffffff;
            box-shadow: 0 2px 12px rgba(37, 99, 235, 0.35);
        }
        .ai-bubble em {
            color: #94a3b8;
            font-style: italic;
        }

        /* 底部输入框区 */
        .ai-input-wrapper {
            padding: 12px 14px calc(12px + env(safe-area-inset-bottom, 0px));
            background: rgba(15, 23, 42, 0.9);
            border-top: 1px solid rgba(255, 255, 255, 0.08);
            display: flex;
            gap: 8px;
            align-items: center;
            flex-shrink: 0;
        }
        .ai-input-box {
            flex: 1;
            padding: 10px 14px;
            border-radius: 10px;
            background: rgba(11, 16, 32, 0.8);
            border: 1px solid rgba(56, 189, 248, 0.25);
            color: #fff;
            font-size: 16px !important; /* 核心：防止 iOS 聚焦自动放大 */
            outline: none;
            transition: all 0.2s;
            -webkit-text-size-adjust: 100%;
        }
        .ai-input-box:focus {
            border-color: #38bdf8;
            box-shadow: 0 0 0 2px rgba(56, 189, 248, 0.2);
        }
        .ai-send-action-btn {
            padding: 10px 16px;
            border-radius: 10px;
            background: linear-gradient(135deg, #06b6d4, #0284c7);
            border: none;
            color: #fff;
            font-size: 13px;
            font-weight: 700;
            cursor: pointer;
            transition: all 0.2s;
            flex-shrink: 0;
            user-select: none;
        }
        .ai-send-action-btn:hover {
            opacity: 0.9;
            transform: translateY(-1px);
        }
        .ai-send-action-btn:disabled {
            opacity: 0.45;
            cursor: not-allowed;
            transform: none;
        }
    `;
    document.head.appendChild(style);

    // 1. 创建悬浮球
    const fab = document.createElement('button');
    fab.className = 'ai-fab-btn';
    fab.title = '打开 AI 智能操盘私教 (企业专线)';
    fab.innerHTML = `
        <span>🤖</span>
        <span class="ai-fab-badge" title="专线在线"></span>
    `;
    document.body.appendChild(fab);

    // 2. 创建遮罩与抽屉 DOM
    const backdrop = document.createElement('div');
    backdrop.className = 'ai-drawer-backdrop';
    document.body.appendChild(backdrop);

    const drawer = document.createElement('div');
    drawer.className = 'ai-drawer';
    drawer.innerHTML = `
        <div class="ai-drawer-header">
            <div class="ai-header-title">
                <div class="ai-header-icon">🧬</div>
                <div class="ai-header-text">
                    <h3>AI 智能操盘顾问 <span style="font-size:10px; padding:2px 6px; border-radius:4px; background:rgba(16,185,129,0.2); color:#34d399; font-weight:normal;">DeepSeek专线</span></h3>
                    <p>老派操盘手大白话 · 实时量化记忆</p>
                </div>
            </div>
            <button class="ai-close-btn" id="aiCloseBtn" title="收起助手">✕</button>
        </div>

        <!-- 快捷问答芯片条 -->
        <div class="ai-chips-bar">
            <button class="ai-chip-btn" id="aiChipToday">🌟 今日大白话全景解读</button>
            <button class="ai-chip-btn" data-query="请帮我大白话拆解今天的 Top 5 核心金胆，哪个底气最足？">👑 Top5金胆底气</button>
            <button class="ai-chip-btn" data-query="今天的极简选2黄金搭档号码有什么连带规律？">💎 黄金选2搭档</button>
            <button class="ai-chip-btn" data-query="从遗漏和均值回归角度，今天有哪些冷号需要重点防回补？">❄️ 冷号防回补</button>
            <button class="ai-chip-btn" data-query="作为老派操盘手，今天的仓位和风险如何控制？">🛡️ 操盘手风控</button>
        </div>

        <!-- 消息流容器 -->
        <div class="ai-messages-container" id="aiMsgContainer">
            <div class="ai-msg-row assistant">
                <div class="ai-msg-avatar">🤖</div>
                <div class="ai-bubble">
                    老朋友，您好！我是您的<strong>专属量化操盘顾问</strong>。<br/>
                    我已经实时同步了系统今天最新的<strong>核心金胆、推荐5码、冷热遗漏和走势矩阵</strong>。绝不跟您讲假大空的神棍套话，咱们全凭数据大白话论英雄！<br/>
                    您可以直接点击上方快捷按钮，或在下方直接问我！
                </div>
            </div>
        </div>

        <!-- 底部输入栏 -->
        <div class="ai-input-wrapper">
            <input type="text" class="ai-input-box" id="aiInput" placeholder="输入您想咨询的号码、形态或规律..." autocomplete="off" />
            <button class="ai-send-action-btn" id="aiSendBtn">发送</button>
        </div>
    `;
    document.body.appendChild(drawer);

    // 状态与逻辑
    const msgContainer = document.getElementById('aiMsgContainer');
    const input = document.getElementById('aiInput');
    const sendBtn = document.getElementById('aiSendBtn');
    const history = [];

    const openDrawer = () => {
        backdrop.classList.add('show');
        drawer.classList.add('open');
        input.focus();
    };

    const closeDrawer = () => {
        backdrop.classList.remove('show');
        drawer.classList.remove('open');
    };

    fab.addEventListener('click', openDrawer);
    backdrop.addEventListener('click', closeDrawer);
    document.getElementById('aiCloseBtn').addEventListener('click', closeDrawer);

    function appendMessage(role, text) {
        const row = document.createElement('div');
        row.className = `ai-msg-row ${role === 'user' ? 'user' : 'assistant'}`;
        const avatar = document.createElement('div');
        avatar.className = 'ai-msg-avatar';
        avatar.innerText = role === 'user' ? '👤' : '🤖';

        const bubble = document.createElement('div');
        bubble.className = 'ai-bubble';
        // 格式化文本
        let formatted = text
            .replace(/\n/g, '<br/>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
        bubble.innerHTML = formatted;

        row.appendChild(avatar);
        row.appendChild(bubble);
        msgContainer.appendChild(row);
        msgContainer.scrollTop = msgContainer.scrollHeight;
    }

    function formatMessageText(text) {
        return text
            .replace(/\n/g, '<br/>')
            .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    }

    async function sendQuery(queryText) {
        if (!queryText || !queryText.trim()) return;
        const text = queryText.trim();
        appendMessage('user', text);
        input.value = '';
        sendBtn.disabled = true;
        sendBtn.innerText = '推演中...';

        // 创建 Assistant 气泡，准备流式打字输出
        const assistantRow = document.createElement('div');
        assistantRow.className = 'ai-msg-row assistant';
        const avatar = document.createElement('div');
        avatar.className = 'ai-msg-avatar';
        avatar.innerText = '🤖';
        const bubble = document.createElement('div');
        bubble.className = 'ai-bubble';
        bubble.innerHTML = '<em>⚡ 操盘手正在结合最新量化快照推演中...</em><span class="ai-typing-cursor"></span>';
        assistantRow.appendChild(avatar);
        assistantRow.appendChild(bubble);
        msgContainer.appendChild(assistantRow);
        msgContainer.scrollTop = msgContainer.scrollHeight;

        let accumulatedText = '';
        let hasStartedStreaming = false;

        try {
            const resp = await fetch('/api/v1/ai/chat-stream', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    message: text,
                    history: history
                })
            });

            if (!resp.ok) {
                throw new Error(`HTTP ${resp.status}`);
            }

            const reader = resp.body.getReader();
            const decoder = new TextDecoder('utf-8');
            let buffer = '';

            while (true) {
                const { done, value } = await reader.read();
                if (done) break;
                buffer += decoder.decode(value, { stream: true });

                const lines = buffer.split('\n');
                buffer = lines.pop(); // 保留最后一个可能未完整的行

                for (const line of lines) {
                    const trimmed = line.trim();
                    if (!trimmed || !trimmed.startsWith('data: ')) continue;
                    const dataStr = trimmed.slice(6).trim();
                    if (dataStr === '[DONE]') {
                        break;
                    }
                    try {
                        const parsed = JSON.parse(dataStr);
                        if (parsed.error) {
                            bubble.innerHTML = `<span style="color:#f87171;">⚠️ ${parsed.error}</span>`;
                            break;
                        }
                        if (parsed.content) {
                            if (!hasStartedStreaming) {
                                hasStartedStreaming = true;
                                bubble.innerHTML = '';
                            }
                            accumulatedText += parsed.content;
                            bubble.innerHTML = formatMessageText(accumulatedText) + '<span class="ai-typing-cursor"></span>';
                            msgContainer.scrollTop = msgContainer.scrollHeight;
                        }
                    } catch (e) {
                        // 忽略分片截断异常
                    }
                }
            }

            // 完成流式传输，去除光标
            if (accumulatedText) {
                bubble.innerHTML = formatMessageText(accumulatedText);
                history.push({ role: 'user', content: text });
                history.push({ role: 'assistant', content: accumulatedText });
            } else if (!hasStartedStreaming) {
                bubble.innerHTML = '<span style="color:#f87171;">⚠️ 操盘大脑未返回有效回复</span>';
            }
        } catch (err) {
            console.warn('流式接口异常，尝试平滑回退至普通通道:', err);
            try {
                const fallbackResp = await fetch('/api/v1/ai/chat', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ message: text, history: history })
                });
                const fallbackData = await fallbackResp.json();
                if (fallbackData.success) {
                    bubble.innerHTML = formatMessageText(fallbackData.reply);
                    history.push({ role: 'user', content: text });
                    history.push({ role: 'assistant', content: fallbackData.reply });
                } else {
                    bubble.innerHTML = `<span style="color:#f87171;">⚠️ ${fallbackData.error || '请求响应异常'}</span>`;
                }
            } catch (fallbackErr) {
                bubble.innerHTML = `<span style="color:#f87171;">❌ 接口调用失败: ${fallbackErr.message}</span>`;
            }
        } finally {
            sendBtn.disabled = false;
            sendBtn.innerText = '发送';
            msgContainer.scrollTop = msgContainer.scrollHeight;
        }
    }

    async function runAnalyzeToday() {
        await sendQuery('🌟 请为我做今日走势大白话全景解读！');
    }

    sendBtn.addEventListener('click', () => sendQuery(input.value));
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter') sendQuery(input.value);
    });

    document.getElementById('aiChipToday').addEventListener('click', runAnalyzeToday);

    document.querySelectorAll('.ai-chips-bar .ai-chip-btn[data-query]').forEach(btn => {
        btn.addEventListener('click', function () {
            const q = this.getAttribute('data-query');
            if (q) sendQuery(q);
        });
    });
})();
