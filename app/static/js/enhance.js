/**
 * 用户侧对话界面增强功能
 * 集成手势识别和语音播报功能
 */

(function() {
    'use strict';
    
    // 全局配置
    const ENHANCE_CONFIG = {
        enableGesture: true,      // 启用手势识别
        enableSpeech: true,       // 启用语音播报
        showGestureButton: true,  // 显示手势控制按钮
        showSpeechButton: true,   // 显示语音控制按钮
    };
    
    let gestureController = null;
    let speechController = null;
    let isGesturePanelOpen = false;
    
    // 获取全局存储键
    function getStorageKey(key) {
        return `enhance_global_${key}`;
    }
    
    // 从 localStorage 加载全局状态
    function loadPageState(key, defaultValue) {
        try {
            const value = localStorage.getItem(getStorageKey(key));
            return value !== null ? JSON.parse(value) : defaultValue;
        } catch (e) {
            return defaultValue;
        }
    }
    
    // 保存全局状态到 localStorage
    function savePageState(key, value) {
        try {
            localStorage.setItem(getStorageKey(key), JSON.stringify(value));
        } catch (e) {
            console.warn('保存状态失败:', e);
        }
    }
    
    /**
     * 初始化增强功能
     */
    async function initEnhancements() {
        console.log('初始化界面增强功能...');

        // 添加控制按钮（需要先创建按钮元素）
        addControlButtons();

        // 初始化语音控制器
        if (ENHANCE_CONFIG.enableSpeech) {
            initSpeechController();
        }

        // 初始化手势控制器
        if (ENHANCE_CONFIG.enableGesture) {
            await initGestureController();
        }

        // 监听手势行动
        setupGestureActions();

        // 监听页面操作并播报
        setupOperationNotifications();

        // 检查全局状态并初始化
        restoreGlobalState();

        console.log('界面增强功能初始化完成');
    }
    
    /**
     * 恢复全局状态
     */
    async function restoreGlobalState() {
        // 标记这是自动恢复，不显示提示
        window.isAutoRestore = true;

        // 恢复手势状态（首次登录默认关闭，但切换页面时保持状态）
        if (gestureController) {
            const gestureEnabled = loadPageState('gestureEnabled', false);
            if (gestureEnabled) {
                try {
                    await gestureController.start();
                    updateGestureButtonState('running');
                } catch (err) {
                    console.error('恢复手势识别失败:', err);
                    updateGestureButtonState('stopped');
                    savePageState('gestureEnabled', false);
                }
            } else {
                updateGestureButtonState('stopped');
            }
        }

        // 读取之前保存的语音状态并恢复
        const speechAutoSpeak = loadPageState('autoSpeak', false);
        const speechRate = loadPageState('speechRate', 1.0);
        const speechPitch = loadPageState('speechPitch', 1.0);
        const speechVolume = loadPageState('speechVolume', 1.0);
        
        if (speechController) {
            speechController.options.autoSpeak = speechAutoSpeak;
            speechController.setRate(speechRate);
            speechController.setPitch(speechPitch);
            speechController.setVolume(speechVolume);
            updateSpeechButtonState('idle');
        }

        // 重置标记
        setTimeout(() => {
            window.isAutoRestore = false;
        }, 1000);
        
        // 初始化导航按钮播报
        setupNavigationSpeak();
    }
    
    /**
     * 设置导航按钮点击播报
     */
    function setupNavigationSpeak() {
        // 为所有导航按钮添加点击事件
        const navButtons = document.querySelectorAll('.rail-tab, .nav-item, [data-tab]');
        
        navButtons.forEach(btn => {
            btn.addEventListener('click', function() {
                // 只有开启自动播报时才播报
                if (!speechController || !speechController.options.autoSpeak) return;
                
                // 获取按钮的标题或标签
                const title = this.getAttribute('title') || 
                             this.getAttribute('aria-label') ||
                             this.getAttribute('data-tab') ||
                             this.textContent.trim();
                
                if (title) {
                    speechController.speak(title);
                }
            });
        });
    }
    
    /**
     * 初始化语音控制器
     */
    function initSpeechController() {
        // 初始设置，播报功能默认关闭
        speechController = new SpeechController({
            rate: 1.0,
            pitch: 1.0,
            volume: 1.0,
            autoSpeak: false
        });

        // 监听语音事件
        speechController.on('start', () => {
            updateSpeechButtonState('speaking');
        });

        speechController.on('end', () => {
            updateSpeechButtonState('idle');
        });

        speechController.on('error', (data) => {
            console.error('语音播报错误:', data.error);
            updateSpeechButtonState('error');
        });

        window.speechController = speechController;

        // 初始化按钮状态为关闭
        updateSpeechButtonState('idle');

        // 监听 AI 回复完成事件，自动播报
        setupAutoSpeak();
    }
    
    /**
     * 设置自动播报功能
     */
    function setupAutoSpeak() {
        // 监听消息添加事件
        const chatList = document.getElementById('chatList');
        if (chatList) {
            const observer = new MutationObserver((mutations) => {
                mutations.forEach((mutation) => {
                    if (mutation.addedNodes.length > 0) {
                        mutation.addedNodes.forEach((node) => {
                            if (node.nodeType === 1 && node.classList && 
                                (node.classList.contains('message-item') || node.classList.contains('chat-item'))) {
                                // 检查是否是 AI 回复
                                const isAI = node.classList.contains('ai-message') || 
                                           node.classList.contains('assistant') ||
                                           node.querySelector('.ai-content, .assistant-content');
                                if (isAI) {
                                    // 延迟播报，等待内容完全渲染
                                    setTimeout(() => {
                                        speakAIMessage(node);
                                    }, 500);
                                }
                            }
                        });
                    }
                });
            });
            
            observer.observe(chatList, {
                childList: true,
                subtree: true
            });
        }
        
        // 也监听自定义事件
        window.addEventListener('ai-response-complete', (event) => {
            if (!speechController || !speechController.options.autoSpeak) return;
            if (event.detail && event.detail.content) {
                speechController.speak(event.detail.content);
            }
        });
    }
    
    /**
     * 播报 AI 消息
     */
    function speakAIMessage(messageNode) {
        if (!speechController || !speechController.options.autoSpeak) return;
        
        // 提取消息文本内容
        let text = '';
        const contentEl = messageNode.querySelector('.message-content, .chat-content, .ai-content, .assistant-content');
        if (contentEl) {
            text = contentEl.innerText || contentEl.textContent;
        } else {
            text = messageNode.innerText || messageNode.textContent;
        }
        
        // 清理文本（移除多余空白和特殊字符）
        text = text.replace(/\s+/g, ' ').trim();
        
        if (text && text.length > 5) {
            speechController.speak(text);
        }
    }
    
    /**
     * 初始化手势控制器
     */
    async function initGestureController() {
        try {
            gestureController = new GestureController({
                minDetectionConfidence: 0.7,
                minTrackingConfidence: 0.7,
                gestureDelay: 1500
            });
            
            await gestureController.init();
            
            // 监听手势事件
            gestureController.on('start', (data) => {
                if (data.success) {
                    updateGestureButtonState('running');
                    if (!window.isAutoRestore) {
                        showToast('手势识别已启动');
                    }
                } else {
                    showToast('启动手势识别失败：' + data.error, 'error');
                    updateGestureButtonState('stopped');
                }
            });
            
            gestureController.on('stop', () => {
                updateGestureButtonState('stopped');
                if (!window.isAutoRestore) {
                    showToast('手势识别已停止');
                }
            });
            
            gestureController.on('gesture', (data) => {
                console.log('识别到手势:', data.gestureName);
                // 只有开启自动播报时才播报手势名称
                if (speechController && speechController.options.autoSpeak) {
                    const cleanGestureName = data.gestureName.replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '').trim();
                    speechController.speak(cleanGestureName);
                }
                // 不显示重复的 toast，只显示右上角的 gesture feedback
            });
            
            window.gestureController = gestureController;
            
        } catch (error) {
            console.error('手势控制器初始化失败:', error);
            showToast('手势识别初始化失败：' + error.message, 'error');
        }
    }
    
    /**
     * 添加控制按钮
     */
    function addControlButtons() {
        // 创建控制容器
        const controlContainer = document.createElement('div');
        controlContainer.className = 'enhance-control-container';
        controlContainer.style.cssText = `
            position: fixed;
            top: 80px;
            right: 20px;
            display: flex;
            flex-direction: column;
            gap: 10px;
            z-index: 9998;
        `;
        
        // 手势控制按钮
        if (ENHANCE_CONFIG.showGestureButton) {
            const gestureBtn = createGestureButton();
            controlContainer.appendChild(gestureBtn);
        }
        
        // 语音控制按钮
        if (ENHANCE_CONFIG.showSpeechButton) {
            const speechBtn = createSpeechButton();
            controlContainer.appendChild(speechBtn);
        }
        
        // 帮助按钮
        const helpBtn = createHelpButton();
        controlContainer.appendChild(helpBtn);
        
        document.body.appendChild(controlContainer);
    }
    
    /**
     * 创建手势按钮
     */
    function createGestureButton() {
        const btn = document.createElement('button');
        btn.id = 'gesture-toggle-btn';
        btn.innerHTML = '🖐️';
        btn.title = '手势识别';
        btn.style.cssText = `
            width: 50px;
            height: 50px;
            border-radius: 12px;
            border: 2px solid rgba(0, 247, 255, 0.3);
            background: rgba(4, 20, 32, 0.8);
            color: white;
            font-size: 24px;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        `;
        
        btn.onmouseenter = function() {
            this.style.transform = 'scale(1.1)';
            this.style.boxShadow = '0 6px 20px rgba(0, 247, 255, 0.4)';
        };
        
        btn.onmouseleave = function() {
            this.style.transform = 'scale(1)';
            this.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)';
        };
        
        btn.onclick = () => toggleGesture();
        
        return btn;
    }
    
    /**
     * 创建语音按钮
     */
    function createSpeechButton() {
        const btn = document.createElement('button');
        btn.id = 'speech-toggle-btn';
        btn.innerHTML = '🔊';
        btn.title = '语音播报';
        btn.style.cssText = `
            width: 50px;
            height: 50px;
            border-radius: 12px;
            border: 2px solid rgba(0, 247, 255, 0.3);
            background: rgba(4, 20, 32, 0.8);
            color: white;
            font-size: 24px;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        `;
        
        btn.onmouseenter = function() {
            this.style.transform = 'scale(1.1)';
            this.style.boxShadow = '0 6px 20px rgba(0, 247, 255, 0.4)';
        };
        
        btn.onmouseleave = function() {
            this.style.transform = 'scale(1)';
            this.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)';
        };
        
        btn.onclick = () => {
            // 左键点击：切换自动播报
            if (!speechController) return;
            
            speechController.options.autoSpeak = !speechController.options.autoSpeak;
            savePageState('autoSpeak', speechController.options.autoSpeak);
            
            // 只有开启状态才显示提示，关闭时不显示任何提示
            if (speechController.options.autoSpeak) {
                showToast('🔊 自动播报已开启');
            }
            
            updateSpeechButtonState(speechController.isSpeakingNow() ? 'speaking' : 'idle');
        };
        
        // 右键点击：关闭自动播报，不显示任何提示
        btn.oncontextmenu = (e) => {
            e.preventDefault();
            if (!speechController) return;
            
            speechController.options.autoSpeak = false;
            savePageState('autoSpeak', false);
            updateSpeechButtonState('idle');
        };
        
        return btn;
    }
    
    /**
     * 创建帮助按钮
     */
    function createHelpButton() {
        const btn = document.createElement('button');
        btn.innerHTML = '❓';
        btn.title = '使用说明';
        btn.style.cssText = `
            width: 50px;
            height: 50px;
            border-radius: 12px;
            border: 2px solid rgba(0, 247, 255, 0.3);
            background: rgba(4, 20, 32, 0.8);
            color: white;
            font-size: 24px;
            cursor: pointer;
            transition: all 0.3s;
            box-shadow: 0 4px 12px rgba(0, 0, 0, 0.3);
        `;
        
        btn.onclick = showHelpPanel;
        
        return btn;
    }
    
    /**
     * 切换手势识别
     */
    function toggleGesture() {
        if (!gestureController) return;
        
        if (gestureController.isRunning) {
            gestureController.stop();
            savePageState('gestureEnabled', false);
        } else {
            gestureController.start().then(() => {
                savePageState('gestureEnabled', true);
            }).catch(err => {
                showToast('启动失败：' + err.message, 'error');
            });
        }
    }
    
    /**
     * 切换语音播报
     */
    function toggleSpeech() {
        if (!speechController) return;
        
        if (speechController.isSpeakingNow()) {
            speechController.stop();
        } else {
            // 播报最后一条 AI 消息
            speakLastAIMessage();
        }
    }
    
    /**
     * 播报最后一条 AI 消息
     */
    function speakLastAIMessage() {
        const messages = document.querySelectorAll('.message-item, .chat-item');
        if (messages.length > 0) {
            const lastMsg = messages[messages.length - 1];
            speakAIMessage(lastMsg);
        } else {
            // 如果没有消息，直接显示静音状态，不触发测试
            updateSpeechButtonState('idle');
            showToast('⚠️ 没有可播报的消息');
        }
    }
    
    /**
     * 切换自动播报
     */
    function toggleAutoSpeak() {
        if (!speechController) return;
        
        speechController.options.autoSpeak = !speechController.options.autoSpeak;
        // 保存到 localStorage
        savePageState('autoSpeak', speechController.options.autoSpeak);
        
        const status = speechController.options.autoSpeak ? '开启' : '关闭';
        showToast(`🔊 自动播报已${status}`);
        
        // 更新按钮状态
        updateSpeechButtonState(speechController.isSpeakingNow() ? 'speaking' : 'idle');
    }
    
    /**
     * 播报操作提示
     */
    function speakNotification(message, priority = 'normal') {
        if (!speechController || !speechController.options.autoSpeak) return;
        
        // 高优先级直接播报，低优先级排队
        if (priority === 'high') {
            speechController.stop();
            speechController.speak(message);
        } else {
            speechController.speak(message);
        }
    }
    
    /**
     * 监听页面操作并播报
     */
    function setupOperationNotifications() {
        // 监听发送按钮点击
        const sendBtn = document.getElementById('sendBtn');
        if (sendBtn) {
            sendBtn.addEventListener('click', () => {
                const input = document.getElementById('messageInput');
                if (input && input.value.trim()) {
                    speakNotification('已发送问题，正在思考中...');
                }
            });
        }
        
        // 监听新对话按钮
        const newChatBtn = document.querySelector('[onclick="startNewChat"]');
        if (newChatBtn) {
            newChatBtn.addEventListener('click', () => {
                speakNotification('已创建新对话');
            });
        }
        
        // 监听历史对话点击
        const historyList = document.getElementById('historyList');
        if (historyList) {
            historyList.addEventListener('click', (e) => {
                const item = e.target.closest('.history-item');
                if (item) {
                    const title = item.querySelector('.history-title');
                    if (title) {
                        speakNotification(`切换到对话：${title.textContent}`);
                    }
                }
            });
        }
        
        // 监听模型切换
        const modelSelect = document.getElementById('modelSelect');
        if (modelSelect) {
            modelSelect.addEventListener('change', () => {
                const selected = modelSelect.options[modelSelect.selectedIndex];
                if (selected) {
                    speakNotification(`已切换模型：${selected.textContent}`);
                }
            });
        }
        
        // 监听数字员工选择
        const employeePanel = document.getElementById('composerEmployees');
        if (employeePanel) {
            employeePanel.addEventListener('click', (e) => {
                const tag = e.target.closest('.employee-tag');
                if (tag) {
                    speakNotification(`已选择数字员工：${tag.textContent}`);
                }
            });
        }
    }
    
    /**
     * 更新手势按钮状态
     */
    function updateGestureButtonState(state) {
        const btn = document.getElementById('gesture-toggle-btn');
        if (!btn) return;
        
        switch (state) {
            case 'running':
                btn.innerHTML = '📹';
                btn.style.borderColor = 'rgba(0, 255, 100, 0.6)';
                btn.style.boxShadow = '0 0 20px rgba(0, 255, 100, 0.4)';
                break;
            case 'stopped':
                btn.innerHTML = '🖐️';
                btn.style.borderColor = 'rgba(0, 247, 255, 0.3)';
                btn.style.boxShadow = '0 4px 12px rgba(0, 0, 0, 0.3)';
                break;
            case 'error':
                btn.innerHTML = '⚠️';
                btn.style.borderColor = 'rgba(255, 100, 100, 0.6)';
                break;
        }
    }
    
    /**
     * 更新语音按钮状态
     */
    function updateSpeechButtonState(state) {
        const btn = document.getElementById('speech-toggle-btn');
        if (!btn) return;
        
        // 根据自动播报状态设置标题
        if (speechController) {
            btn.title = speechController.options.autoSpeak ? '语音播报（自动开启）' : '语音播报（右键切换自动）';
        }
        
        switch (state) {
            case 'speaking':
                btn.innerHTML = '🔊';
                btn.style.animation = 'pulse 1s infinite';
                btn.style.borderColor = 'rgba(0, 255, 100, 0.6)';
                break;
            case 'idle':
                btn.innerHTML = speechController && speechController.options.autoSpeak ? '🔊' : '🔇';
                btn.style.animation = '';
                btn.style.borderColor = speechController && speechController.options.autoSpeak ? 'rgba(0, 255, 100, 0.4)' : 'rgba(0, 247, 255, 0.3)';
                break;
            case 'error':
                btn.innerHTML = '⚠️';
                btn.style.borderColor = 'rgba(255, 100, 100, 0.6)';
                break;
        }
    }
    
    /**
     * 监听手势行动
     */
    function setupGestureActions() {
        window.addEventListener('gesture-action', (event) => {
            const action = event.detail.action;
            console.log('执行手势行动:', action);
            
            switch (action) {
                case 'switch_system':
                    switchSystem();
                    break;
                case 'upload_file':
                    uploadFile();
                    break;
                case 'send_message':
                    sendMessage();
                    break;
                case 'stop_response':
                    stopAIResponse();
                    break;
                case 'show_robot_panel':
                    showRobotPanel();
                    break;
                case 'screenshot':
                    takeScreenshot();
                    break;
                case 'send_love_message':
                    sendLoveMessage();
                    break;
            }
        });
    }
    
    /**
     * 截图功能
     */
    function takeScreenshot() {
        html2canvas(document.body).then(canvas => {
            const link = document.createElement('a');
            link.download = 'screenshot_' + Date.now() + '.png';
            link.href = canvas.toDataURL('image/png');
            link.click();
            showToast('📸 截图已保存！');
        }).catch(err => {
            showToast('截图失败：' + err.message, 'error');
        });
    }
    
    /**
     * 土味情话库
     */
    const loveMessages = [
        "你知道我最喜欢什么酒吗？和你天长地久。💕",
        "我最近学会了一门新技能，算命。掐指一算，你命里缺我。✨",
        "你是哪里人？我是你心上人。💖",
        "你累不累？你在我脑子里跑了一天了。🏃‍♀️",
        "我的手被划了一口子，你也划一下，这样我们就是两口子了。💑",
        "你猜我想吃什么？痴痴地望着你。👀",
        "我想你一定很忙，所以只看前三个字就好了。❤️",
        "你有地图吗？我在你的眼睛里迷路了。🗺️",
        "你的脸上有点东西，有点漂亮。🌟",
        "你知道我想喝什么吗？想呵护你。🥤",
        "你可以帮我洗个东西吗？喜欢我。💓",
        "你是年少的欢喜，倒过来念也是。🔄",
        "我最近一直在找一家店，什么店？你的来电。📞",
        "你猜我什么星座？为你量身定做。♌",
        "我喜欢冬天，因为冬天有你。❄️",
        "你知道你和星星有什么区别吗？星星在天上，你在我心里。⭐",
        "从今以后我只能称呼你为您了，因为你在我心上。👆",
        "我最近有点怕你，因为我怕老婆。👸",
        "你猜我想吃什么糖？你的胸膛。🍬",
        "你知道我最想成为什么人吗？成为你的人。👫"
    ];
    
    /**
     * 发送土味情话
     */
    function sendLoveMessage() {
        // 检查是否在聊天页面
        const path = window.location.pathname;
        if (!path.includes('im')) {
            showToast('请先到智能聊天页面发送土味情话！', 'info');
            return;
        }
        
        // 随机选择一条土味情话
        const randomIndex = Math.floor(Math.random() * loveMessages.length);
        const message = loveMessages[randomIndex];
        
        // 播报土味情话（去掉emoji）
        if (speechController) {
            const cleanMessage = message.replace(/[\u{1F300}-\u{1F9FF}\u{2600}-\u{26FF}\u{2700}-\u{27BF}]/gu, '');
            speechController.speak(cleanMessage);
        }
        
        // 找到输入框并填入消息
        const input = document.querySelector('.chat-input, #messageInput, [contenteditable]');
        if (input) {
            if (input.tagName === 'INPUT' || input.tagName === 'TEXTAREA') {
                input.value = message;
            } else {
                input.innerHTML = message;
            }
            
            // 尝试找到发送按钮并点击
            const sendBtn = document.querySelector('.send-btn, #sendBtn, [onclick*="send"]');
            if (sendBtn) {
                sendBtn.click();
                showToast('💕 已发送土味情话！');
            } else {
                showToast('请手动点击发送按钮！', 'info');
            }
        } else {
            showToast('未找到聊天输入框！', 'error');
        }
    }
    
    /**
     * 切换子系统（智能问数/智能聊天）
     */
    function switchSystem() {
        // 切换页面前保存手势和语音状态
        if (gestureController && gestureController.isRunning) {
            savePageState('gestureEnabled', true);
        }
        if (speechController) {
            savePageState('autoSpeak', speechController.options.autoSpeak);
        }
        
        const path = window.location.pathname;
        const isOnChatPage = path === '/im' || path.includes('im.html');
        
        if (isOnChatPage) {
            // 当前在聊天页面，切换到问数页面
            window.location.href = '/';
            showToast('✌️ 已切换到智能问数');
        } else {
            // 当前在问数页面，切换到聊天页面
            window.location.href = '/im';
            showToast('✌️ 已切换到智能聊天');
        }
    }
    
    /**
     * 上传文件
     */
    function uploadFile() {
        // 尝试多种方式查找文件上传按钮
        let fileBtn = null;
        
        // 1. 优先直接查找 fileInput 并触发（最直接的方式）
        const fileInput = document.querySelector('#fileInput, input[type="file"]');
        if (fileInput) {
            try {
                fileInput.click();
                return;
            } catch (e) {
                console.log('直接触发 fileInput 失败:', e);
            }
        }
        
        // 2. 查找 .tool-row 下的 .tool-btn 文件按钮
        const toolRow = document.querySelector('.tool-row');
        if (toolRow) {
            const toolBtns = toolRow.querySelectorAll('.tool-btn');
            toolBtns.forEach(btn => {
                if (!fileBtn && btn.textContent.trim() === '文件') {
                    fileBtn = btn;
                }
            });
        }
        
        // 3. 查找所有按钮中包含"文件"文字的
        if (!fileBtn) {
            const allBtns = document.querySelectorAll('button');
            allBtns.forEach(btn => {
                if (!fileBtn && btn.textContent.trim() === '文件') {
                    fileBtn = btn;
                }
            });
        }
        
        // 4. 查找带有 onclick 触发 fileInput 的按钮
        if (!fileBtn) {
            const btnsWithOnclick = document.querySelectorAll('[onclick*="fileInput"]');
            btnsWithOnclick.forEach(btn => {
                if (!fileBtn) fileBtn = btn;
            });
        }
        
        if (fileBtn) {
            try {
                // 先尝试直接调用 click()
                fileBtn.click();
            } catch (err) {
                showToast('打开文件选择失败：' + err.message, 'error');
            }
        } else {
            showToast('⚠️ 未找到文件上传按钮', 'error');
        }
    }
    
    /**
     * 发送消息
     */
    function sendMessage() {
        // 查找发送按钮并点击
        const sendBtn = document.querySelector('#sendBtn, .send-btn, [onclick*="sendTextMessage"]');
        if (sendBtn) {
            sendBtn.click();
            showToast('👌 已发送消息');
        } else {
            showToast('⚠️ 未找到发送按钮');
        }
    }
    
    /**
     * 停止 AI 响应
     */
    function stopAIResponse() {
        // 查找并点击停止按钮
        const stopBtn = document.querySelector('#stopBtn, .stop-btn, [data-action="stop"]');
        if (stopBtn) {
            stopBtn.click();
            showToast('⏹️ 已停止 AI 响应');
        } else {
            // 尝试通过事件停止
            const stopEvent = new CustomEvent('stop-ai-response');
            window.dispatchEvent(stopEvent);
            showToast('⏹️ 已发送停止指令');
        }
    }
    
    /**
     * 显示机器人面板
     */
    function showRobotPanel() {
        // 查找数字员工按钮
        const robotBtn = document.querySelector('[data-tab="employees"], .rail-tab[data-tab="employees"]');
        if (robotBtn) {
            robotBtn.click();
        } else {
            showToast('⚠️ 未找到机器人面板按钮');
        }
    }
    
    /**
     * 显示帮助面板
     */
    function showHelpPanel() {
        const helpHtml = `
            <div style="
                position: fixed;
                top: 50%;
                left: 50%;
                transform: translate(-50%, -50%);
                background: linear-gradient(135deg, rgba(4, 20, 32, 0.98), rgba(2, 10, 20, 0.98));
                border: 2px solid rgba(0, 247, 255, 0.3);
                border-radius: 16px;
                padding: 30px;
                max-width: 600px;
                max-height: 80vh;
                overflow-y: auto;
                z-index: 10001;
                box-shadow: 0 20px 60px rgba(0, 0, 0, 0.6);
                color: white;
                font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif;
            " id="help-panel">
                <h2 style="margin: 0 0 20px 0; font-size: 24px; color: #00f7ff;">🎮 手势识别说明</h2>
                
                <div style="margin-bottom: 20px;">
                    <h3 style="color: #00f7ff; margin: 15px 0 10px 0;">手势操作：</h3>
                    <ul style="line-height: 2; padding-left: 20px;">
                        <li>✌️ <strong>胜利手势</strong> - 切换子系统（智能问数/智能聊天）</li>
                        <li>1️⃣ <strong>数字1手势</strong> - 上传文件</li>
                        <li>👌 <strong>OK手势</strong> - 发送消息</li>
                        <li>✋ <strong>停止手势</strong> - 中断 AI 响应</li>
                        <li>🤙 <strong>呼叫手势</strong> - 打开机器人面板</li>
                        <li>🖐️🖐️ <strong>双手张开</strong> - 截图（需要两只手同时张开）</li>
                        <li>💕 <strong>双手爱心</strong> - 发送土味情话（需要两只手同时做）</li>
                    </ul>
                </div>
                
                <div style="margin-bottom: 20px;">
                    <h3 style="color: #00f7ff; margin: 15px 0 10px 0;">语音播报：</h3>
                    <ul style="line-height: 2; padding-left: 20px;">
                        <li>🔊 <strong>点击</strong> - 开启/关闭自动播报（开启时播报提示，关闭时无提示）</li>
                        <li>🔊 <strong>右键</strong> - 关闭自动播报（无任何提示）</li>
                        <li>支持语速、音调、音量调节</li>
                        <li>AI 回复自动朗读（需开启）</li>
                    </ul>
                    <div style="margin-top: 15px; padding: 10px; background: rgba(0, 247, 255, 0.1); border-radius: 8px;">
                        <label style="display: block; margin-bottom: 5px;">语速: <span id="rateValue">1.0</span></label>
                        <input type="range" id="rateSlider" min="0.1" max="2" step="0.1" value="1.0" onchange="setSpeechRate(this.value)" style="width: 100%;">
                        <label style="display: block; margin-bottom: 5px; margin-top: 10px;">音调: <span id="pitchValue">1.0</span></label>
                        <input type="range" id="pitchSlider" min="0" max="2" step="0.1" value="1.0" onchange="setSpeechPitch(this.value)" style="width: 100%;">
                        <label style="display: block; margin-bottom: 5px; margin-top: 10px;">音量: <span id="volumeValue">1.0</span></label>
                        <input type="range" id="volumeSlider" min="0" max="1" step="0.1" value="1.0" onchange="setSpeechVolume(this.value)" style="width: 100%;">
                    </div>
                </div>
                
                <div style="text-align: right; margin-top: 30px;">
                    <button onclick="closeHelpPanel()" style="
                        padding: 10px 30px;
                        background: linear-gradient(135deg, #00f7ff, #0096ff);
                        border: none;
                        border-radius: 8px;
                        color: white;
                        font-size: 16px;
                        cursor: pointer;
                        font-weight: bold;
                    ">关闭</button>
                </div>
            </div>
            <div style="
                position: fixed;
                top: 0;
                left: 0;
                right: 0;
                bottom: 0;
                background: rgba(0, 0, 0, 0.7);
                z-index: 10000;
            " id="help-overlay" onclick="closeHelpPanel()"></div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', helpHtml);
    }
    
    /**
     * 关闭帮助面板
     */
    function closeHelpPanel() {
        const panel = document.getElementById('help-panel');
        const overlay = document.getElementById('help-overlay');
        
        if (panel) panel.remove();
        if (overlay) overlay.remove();
    }
    
    // 将关闭函数暴露到全局作用域
    window.closeHelpPanel = closeHelpPanel;
    
    /**
     * 设置语速
     */
    function setSpeechRate(value) {
        const rateValue = document.getElementById('rateValue');
        if (rateValue) {
            rateValue.textContent = value;
        }
        if (speechController) {
            speechController.setRate(parseFloat(value));
            savePageState('speechRate', parseFloat(value));
        }
    }
    window.setSpeechRate = setSpeechRate;
    
    /**
     * 设置音调
     */
    function setSpeechPitch(value) {
        const pitchValue = document.getElementById('pitchValue');
        if (pitchValue) {
            pitchValue.textContent = value;
        }
        if (speechController) {
            speechController.setPitch(parseFloat(value));
            savePageState('speechPitch', parseFloat(value));
        }
    }
    window.setSpeechPitch = setSpeechPitch;
    
    /**
     * 设置音量
     */
    function setSpeechVolume(value) {
        const volumeValue = document.getElementById('volumeValue');
        if (volumeValue) {
            volumeValue.textContent = value;
        }
        if (speechController) {
            speechController.setVolume(parseFloat(value));
            savePageState('speechVolume', parseFloat(value));
        }
    }
    window.setSpeechVolume = setSpeechVolume;
    
    /**
     * 显示提示消息
     */
    function showToast(message, type = 'info') {
        // 如果已有提示元素，先移除
        const existingToast = document.getElementById('toast-message');
        if (existingToast) {
            existingToast.remove();
        }
        
        const toast = document.createElement('div');
        toast.id = 'toast-message';
        toast.textContent = message;
        toast.style.cssText = `
            position: fixed;
            top: 20px;
            right: 20px;
            background: ${type === 'error' ? 'rgba(255, 100, 100, 0.9)' : 'rgba(0, 247, 255, 0.9)'};
            color: white;
            padding: 12px 24px;
            border-radius: 8px;
            font-size: 14px;
            font-weight: bold;
            z-index: 10002;
            box-shadow: 0 4px 20px rgba(0, 0, 0, 0.4);
            animation: slideInRight 0.3s ease-out;
        `;
        
        document.body.appendChild(toast);
        
        setTimeout(() => {
            toast.style.animation = 'slideOutRight 0.3s ease-out';
            setTimeout(() => toast.remove(), 300);
        }, 3000);
    }
    
    // 添加 CSS 动画
    const style = document.createElement('style');
    style.textContent = `
        @keyframes slideDown {
            from { transform: translate(-50%, -100px); opacity: 0; }
            to { transform: translate(-50%, 0); opacity: 1; }
        }
        @keyframes slideUp {
            from { transform: translate(-50%, 0); opacity: 1; }
            to { transform: translate(-50%, -100px); opacity: 0; }
        }
        @keyframes slideIn {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOut {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
        @keyframes slideInRight {
            from { transform: translateX(100%); opacity: 0; }
            to { transform: translateX(0); opacity: 1; }
        }
        @keyframes slideOutRight {
            from { transform: translateX(0); opacity: 1; }
            to { transform: translateX(100%); opacity: 0; }
        }
        @keyframes pulse {
            0%, 100% { transform: scale(1); }
            50% { transform: scale(1.1); }
        }
    `;
    document.head.appendChild(style);
    
    // 页面加载完成后初始化
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initEnhancements);
    } else {
        initEnhancements();
    }
    
})();
