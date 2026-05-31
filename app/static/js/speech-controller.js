/**
 * 语音播报控制器
 * 使用 Web Speech API 实现语音合成
 * 支持多音色、语速、音量调节
 */

class SpeechController {
    constructor(options = {}) {
        this.options = {
            rate: 1.0,      // 语速 0.1-10
            pitch: 1.0,     // 音调 0-2
            volume: 1.0,    // 音量 0-1
            lang: 'zh-CN',  // 语言
            autoSpeak: false, // 是否自动播报
            ...options
        };
        
        this.synth = window.speechSynthesis;
        this.voices = [];
        this.currentVoice = null;
        this.isSpeaking = false;
        this.isPaused = false;
        this.speechQueue = [];
        this.currentUtterance = null;
        this.callbacks = {};
        
        // 初始化
        this.init();
    }
    
    /**
     * 初始化语音合成
     */
    init() {
        if (!this.synth) {
            console.warn('浏览器不支持 Web Speech API');
            return;
        }
        
        // 加载语音列表
        this.loadVoices();
        
        // 监听语音列表变化
        if (speechSynthesis.onvoiceschanged !== undefined) {
            speechSynthesis.onvoiceschanged = this.loadVoices.bind(this);
        }
        
        console.log('语音播报初始化完成');
    }
    
    /**
     * 加载语音列表
     */
    loadVoices() {
        this.voices = this.synth.getVoices() || [];
        
        // 过滤中文语音
        const zhVoices = this.voices.filter(voice => 
            voice.lang.includes('zh') || voice.lang.includes('CN')
        );
        
        if (zhVoices.length > 0) {
            // 优先选择 Google 中文语音
            this.currentVoice = zhVoices.find(v => v.name.includes('Google')) || zhVoices[0];
        } else if (this.voices.length > 0) {
            this.currentVoice = this.voices[0];
        }
        
        console.log(`加载了 ${this.voices.length} 个语音，当前语音：${this.currentVoice ? this.currentVoice.name : '无'}`);
        this.triggerCallback('voicesLoaded', {voices: this.voices, currentVoice: this.currentVoice});
    }
    
    /**
     * 播报文本
     */
    speak(text, options = {}) {
        if (!this.synth) {
            console.warn('浏览器不支持语音播报');
            return Promise.reject(new Error('不支持语音播报'));
        }
        
        if (!text || text.trim() === '') {
            return Promise.resolve();
        }
        
        return new Promise((resolve, reject) => {
            const utterance = new SpeechSynthesisUtterance(text);
            
            // 应用配置
            utterance.rate = options.rate || this.options.rate;
            utterance.pitch = options.pitch || this.options.pitch;
            utterance.volume = options.volume || this.options.volume;
            utterance.lang = options.lang || this.options.lang;
            
            // 设置语音
            if (options.voice || this.currentVoice) {
                utterance.voice = options.voice || this.currentVoice;
            }
            
            // 事件处理
            utterance.onstart = () => {
                this.isSpeaking = true;
                this.isPaused = false;
                this.currentUtterance = utterance;
                this.triggerCallback('start', {text});
            };
            
            utterance.onend = () => {
                this.isSpeaking = false;
                this.isPaused = false;
                this.currentUtterance = null;
                this.triggerCallback('end', {text});
                resolve();
                
                // 播放队列中的下一条
                this.playNextFromQueue();
            };
            
            utterance.onerror = (event) => {
                this.isSpeaking = false;
                this.isPaused = false;
                this.currentUtterance = null;
                console.error('语音播报错误:', event);
                this.triggerCallback('error', {error: event});
                reject(event);
                
                // 继续播放队列
                this.playNextFromQueue();
            };
            
            utterance.onpause = () => {
                this.isPaused = true;
                this.triggerCallback('pause', {});
            };
            
            utterance.onresume = () => {
                this.isPaused = false;
                this.triggerCallback('resume', {});
            };
            
            // 添加到队列或直接播放
            if (this.isSpeaking) {
                this.speechQueue.push(utterance);
            } else {
                this.synth.speak(utterance);
            }
        });
    }
    
    /**
     * 播放队列中的下一条
     */
    playNextFromQueue() {
        if (this.speechQueue.length > 0) {
            const nextUtterance = this.speechQueue.shift();
            this.synth.speak(nextUtterance);
        }
    }
    
    /**
     * 暂停播报
     */
    pause() {
        if (this.isSpeaking && !this.isPaused) {
            this.synth.pause();
        }
    }
    
    /**
     * 继续播报
     */
    resume() {
        if (this.isPaused) {
            this.synth.resume();
        }
    }
    
    /**
     * 停止播报
     */
    stop() {
        this.synth.cancel();
        this.isSpeaking = false;
        this.isPaused = false;
        this.speechQueue = [];
        this.currentUtterance = null;
        this.triggerCallback('stop', {});
    }
    
    /**
     * 设置语音
     */
    setVoice(voice) {
        this.currentVoice = voice;
        this.triggerCallback('voiceChanged', {voice});
    }
    
    /**
     * 获取所有语音
     */
    getVoices() {
        return this.voices;
    }
    
    /**
     * 获取中文语音列表
     */
    getChineseVoices() {
        return this.voices.filter(voice => 
            voice.lang.includes('zh') || voice.lang.includes('CN')
        );
    }
    
    /**
     * 设置语速
     */
    setRate(rate) {
        this.options.rate = Math.max(0.1, Math.min(10, rate));
        this.triggerCallback('rateChanged', {rate: this.options.rate});
    }
    
    /**
     * 设置音调
     */
    setPitch(pitch) {
        this.options.pitch = Math.max(0, Math.min(2, pitch));
        this.triggerCallback('pitchChanged', {pitch: this.options.pitch});
    }
    
    /**
     * 设置音量
     */
    setVolume(volume) {
        this.options.volume = Math.max(0, Math.min(1, volume));
        this.triggerCallback('volumeChanged', {volume: this.options.volume});
    }
    
    /**
     * 设置自动播报
     */
    setAutoSpeak(auto) {
        this.options.autoSpeak = auto;
        this.triggerCallback('autoSpeakChanged', {auto});
    }
    
    /**
     * 检查是否正在播报
     */
    isSpeakingNow() {
        return this.isSpeaking;
    }
    
    /**
     * 检查是否暂停
     */
    isPausedNow() {
        return this.isPaused;
    }
    
    /**
     * 注册回调
     */
    on(event, callback) {
        if (!this.callbacks[event]) {
            this.callbacks[event] = [];
        }
        this.callbacks[event].push(callback);
    }
    
    /**
     * 触发回调
     */
    triggerCallback(event, data) {
        if (this.callbacks[event]) {
            this.callbacks[event].forEach(callback => {
                try {
                    callback(data);
                } catch (error) {
                    console.error(`回调执行错误 [${event}]:`, error);
                }
            });
        }
    }
    
    /**
     * 测试语音
     */
    test() {
        return this.speak('您好，这是一个语音播报测试。如果您能听到这段声音，说明语音播报功能正常工作。');
    }
    
    /**
     * 播报 AI 回复（支持 Markdown 清理）
     */
    speakAIResponse(markdownText) {
        // 简单的 Markdown 清理
        let text = markdownText
            .replace(/```[\s\S]*?```/g, '')  // 移除代码块
            .replace(/`([^`]+)`/g, '$1')     // 移除行内代码
            .replace(/!\[([^\]]*)\]\([^)]+\)/g, '$1')  // 移除图片
            .replace(/\[([^\]]+)\]\([^)]+\)/g, '$1')   // 移除链接
            .replace(/[#*_~]/g, '')          // 移除格式符号
            .replace(/\n+/g, ' ')            // 换行转空格
            .trim();
        
        if (this.options.autoSpeak && text) {
            return this.speak(text);
        }
        return Promise.resolve();
    }
}

// 导出全局
window.SpeechController = SpeechController;
