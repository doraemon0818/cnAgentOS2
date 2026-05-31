/**
 * 手势识别控制器
 * 使用 MediaPipe Hands 实现手势识别
 * 支持 5 种以上手势交互
 */

class GestureController {
    constructor(options = {}) {
        this.options = {
            cameraWidth: 640,
            cameraHeight: 480,
            minDetectionConfidence: 0.8,
            minTrackingConfidence: 0.8,
            gestureDelay: 2500, // 手势识别延迟（毫秒）- 降低灵敏度
            ...options
        };
        
        this.hands = null;
        this.camera = null;
        this.canvas = null;
        this.ctx = null;
        this.isRunning = false;
        this.lastGestureTime = 0;
        this.currentGesture = null;
        this.callbacks = {};
        this.gestureHistory = [];
        
        // 手势映射
        this.gestureMap = {
            'victory': '✌️ 切换子系统',
            'one': '1️⃣ 上传文件',
            'ok': '👌 发送消息',
            'open_palm': '✋ 停止AI',
            'call': '🤙 机器人面板',
            'double_fist': '🖐️🖐️ 截图',
            'heart': '💕 发送土味情话'
        };
        
        // 是否自动执行手势动作（用户端需要，管理员端不需要）
        this.autoExecuteActions = options.autoExecuteActions !== false;
        
        // 是否显示手势反馈提示（用户端需要，管理员端不需要）
        this.showGestureTips = options.showGestureTips !== false;
    }
    
    /**
     * 初始化手势识别
     */
    async init() {
        try {
            // 动态加载 MediaPipe Hands
            await this.loadMediaPipe();
            
            // 创建 canvas
            this.createCanvas();
            
            // 初始化 Hands
            this.hands = new Hands({
                locateFile: (file) => {
                    return `https://cdn.jsdelivr.net/npm/@mediapipe/hands/${file}`;
                }
            });
            
            this.hands.setOptions({
                maxNumHands: 2,
                modelComplexity: 1,
                minDetectionConfidence: this.options.minDetectionConfidence,
                minTrackingConfidence: this.options.minTrackingConfidence
            });
            
            this.hands.onResults(this.onHandsResults.bind(this));
            
            console.log('手势识别初始化完成');
            return true;
        } catch (error) {
            console.error('手势识别初始化失败:', error);
            return false;
        }
    }
    
    /**
     * 加载 MediaPipe 库
     */
    async loadMediaPipe() {
        return new Promise((resolve, reject) => {
            if (window.Hands && window.Camera) {
                resolve();
                return;
            }
            
            let loadedCount = 0;
            const totalScripts = 2;
            
            const checkLoaded = () => {
                loadedCount++;
                if (loadedCount === totalScripts) {
                    resolve();
                }
            };
            
            // 加载 Hands
            const handsScript = document.createElement('script');
            handsScript.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/hands/hands.js';
            handsScript.onload = checkLoaded;
            handsScript.onerror = () => reject(new Error('MediaPipe Hands 加载失败'));
            document.head.appendChild(handsScript);
            
            // 加载 Camera
            const cameraScript = document.createElement('script');
            cameraScript.src = 'https://cdn.jsdelivr.net/npm/@mediapipe/camera_utils/camera_utils.js';
            cameraScript.onload = checkLoaded;
            cameraScript.onerror = () => reject(new Error('MediaPipe Camera 加载失败'));
            document.head.appendChild(cameraScript);
        });
    }
    
    /**
     * 创建 Canvas
     */
    createCanvas() {
        this.canvas = document.createElement('canvas');
        this.canvas.width = this.options.cameraWidth;
        this.canvas.height = this.options.cameraHeight;
        this.canvas.style.position = 'fixed';
        this.canvas.style.top = '10px';
        this.canvas.style.left = 'calc(50% + 100px)';
        this.canvas.style.width = '113px';
        this.canvas.style.height = '113px';
        this.canvas.style.borderRadius = '12px';
        this.canvas.style.border = '2px solid rgba(0, 247, 255, 0.3)';
        this.canvas.style.boxShadow = '0 0 20px rgba(0, 247, 255, 0.2)';
        this.canvas.style.zIndex = '9999';
        this.canvas.style.display = 'none';
        this.canvas.id = 'gesture-canvas';
        
        document.body.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
    }
    
    /**
     * 启动摄像头和手势识别
     */
    async start() {
        if (this.isRunning) {
            console.log('手势识别已在运行');
            return;
        }
        
        try {
            const video = document.createElement('video');
            video.width = this.options.cameraWidth;
            video.height = this.options.cameraHeight;
            video.style.display = 'none';
            document.body.appendChild(video);
            
            const stream = await navigator.mediaDevices.getUserMedia({
                video: {
                    width: this.options.cameraWidth,
                    height: this.options.cameraHeight,
                    facingMode: 'user'
                }
            });
            
            video.srcObject = stream;
            await video.play();
            
            this.camera = new Camera(video, {
                onFrame: async () => {
                    await this.hands.send({image: video});
                },
                width: this.options.cameraWidth,
                height: this.options.cameraHeight
            });
            
            this.camera.start();
            this.isRunning = true;
            this.canvas.style.display = 'block';
            
            console.log('手势识别已启动');
            this.triggerCallback('start', {success: true});
            
        } catch (error) {
            console.error('启动手势识别失败:', error);
            this.triggerCallback('start', {success: false, error: error.message});
            throw error;
        }
    }
    
    /**
     * 停止手势识别
     */
    stop() {
        if (!this.isRunning) return;
        
        if (this.camera) {
            this.camera.stop();
            this.camera = null;
        }
        
        if (this.hands) {
            this.hands.close();
        }
        
        const video = document.querySelector('#gesture-canvas + video');
        if (video && video.srcObject) {
            video.srcObject.getTracks().forEach(track => track.stop());
            video.remove();
        }
        
        this.canvas.style.display = 'none';
        this.isRunning = false;
        this.currentGesture = null;
        
        console.log('手势识别已停止');
        this.triggerCallback('stop', {});
    }
    
    /**
     * 处理手部识别结果
     */
    async onHandsResults(results) {
        if (!this.ctx) return;
        
        // 清空 canvas
        this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);
        
        if (results.multiHandLandmarks && results.multiHandLandmarks.length > 0) {
            let gesture = null;
            
            // 绘制所有手部骨架
            for (let i = 0; i < results.multiHandLandmarks.length; i++) {
                const landmarks = results.multiHandLandmarks[i];
                this.drawHand(landmarks);
            }
            
            // 如果有两只手，检测爱心手势和双手握拳手势
                if (results.multiHandLandmarks.length >= 2) {
                    const leftHand = results.multiHandLandmarks[0];
                    const rightHand = results.multiHandLandmarks[1];
                    
                    gesture = this.recognizeHeartGesture(leftHand, rightHand);
                    
                    if (!gesture) {
                        gesture = this.recognizeDoubleFistGesture(leftHand, rightHand);
                    }
                }
            
            // 如果没有检测到爱心手势，则检测单手势
            if (!gesture && results.multiHandLandmarks.length > 0) {
                gesture = this.recognizeGesture(results.multiHandLandmarks[0]);
            }
            
            if (gesture && gesture !== this.currentGesture) {
                const now = Date.now();
                if (now - this.lastGestureTime > this.options.gestureDelay) {
                    this.currentGesture = gesture;
                    this.lastGestureTime = now;
                    this.gestureHistory.push({
                        gesture: gesture,
                        time: new Date().toISOString()
                    });
                    
                    console.log('识别到手势:', this.gestureMap[gesture]);
                    
                    // 只有在用户端才显示手势反馈提示
                    if (this.showGestureTips) {
                        this.showGestureFeedback(gesture);
                    }
                    
                    this.triggerCallback('gesture', {
                        gesture: gesture,
                        gestureName: this.gestureMap[gesture]
                    });
                    
                    // 只有在用户端才自动执行手势动作（管理员端通过回调自行处理）
                    if (this.autoExecuteActions) {
                        this.executeGestureAction(gesture);
                    }
                }
            }
        } else {
            this.currentGesture = null;
        }
    }
    
    /**
     * 绘制手部骨架
     */
    drawHand(landmarks) {
        const connections = [
            [0, 1], [1, 2], [2, 3], [3, 4],
            [0, 5], [5, 6], [6, 7], [7, 8],
            [0, 9], [9, 10], [10, 11], [11, 12],
            [0, 13], [13, 14], [14, 15], [15, 16],
            [0, 17], [17, 18], [18, 19], [19, 20],
            [5, 9], [9, 13], [13, 17]
        ];
        
        this.ctx.strokeStyle = 'rgba(0, 247, 255, 0.8)';
        this.ctx.lineWidth = 2;
        
        connections.forEach(([i, j]) => {
            this.ctx.beginPath();
            this.ctx.moveTo(landmarks[i].x * this.canvas.width, landmarks[i].y * this.canvas.height);
            this.ctx.lineTo(landmarks[j].x * this.canvas.width, landmarks[j].y * this.canvas.height);
            this.ctx.stroke();
        });
        
        // 绘制关键点
        landmarks.forEach((landmark, index) => {
            this.ctx.beginPath();
            this.ctx.arc(
                landmark.x * this.canvas.width,
                landmark.y * this.canvas.height,
                4,
                0,
                2 * Math.PI
            );
            this.ctx.fillStyle = 'rgba(0, 247, 255, 1)';
            this.ctx.fill();
        });
    }
    
    /**
     * 识别手势
     */
    recognizeGesture(landmarks) {
        // 获取关键点
        const thumbTip = landmarks[4];
        const indexTip = landmarks[8];
        const middleTip = landmarks[12];
        const ringTip = landmarks[16];
        const pinkyTip = landmarks[20];
        const thumbIp = landmarks[3];
        const thumbMcp = landmarks[1];
        const indexPip = landmarks[6];
        const indexMcp = landmarks[5];
        const middlePip = landmarks[10];
        const middleMcp = landmarks[9];
        const ringPip = landmarks[14];
        const ringMcp = landmarks[13];
        const pinkyPip = landmarks[18];
        const pinkyMcp = landmarks[17];
        const wrist = landmarks[0];
        
        // 计算手指伸直程度（适中的判断）
        const getFingerLength = (tip, mcp) => Math.sqrt(
            Math.pow(tip.x - mcp.x, 2) + Math.pow(tip.y - mcp.y, 2)
        );
        
        const getFingerExtension = (tip, pip, mcp) => {
            const totalLength = getFingerLength(tip, mcp);
            const tipToPip = Math.sqrt(Math.pow(tip.x - pip.x, 2) + Math.pow(tip.y - pip.y, 2));
            // 伸直程度：tip到pip的距离 / 总长度 > 0.5 就算伸直（适中）
            return tip.y < pip.y && tipToPip / totalLength > 0.5;
        };
        
        // 判断手指是否弯曲（适中）
        const isFingerBent = (tip, pip) => {
            // 弯曲程度：指尖在第二关节下方即可
            return tip.y > pip.y + 0.015;
        };
        
        const indexExtended = getFingerExtension(indexTip, indexPip, indexMcp);
        const middleExtended = getFingerExtension(middleTip, middlePip, middleMcp);
        const ringExtended = getFingerExtension(ringTip, ringPip, ringMcp);
        const pinkyExtended = getFingerExtension(pinkyTip, pinkyPip, pinkyMcp);
        
        const indexBent = isFingerBent(indexTip, indexPip);
        const middleBent = isFingerBent(middleTip, middlePip);
        const ringBent = isFingerBent(ringTip, ringPip);
        const pinkyBent = isFingerBent(pinkyTip, pinkyPip);
        
        // 拇指伸直判断（适中）
        const thumbExtended = getFingerExtension(thumbTip, thumbIp, thumbMcp);
        
        // 简单的手指伸直判断（兼容旧逻辑）
        const isSimpleExtended = (tip, pip) => tip.y < pip.y;
        const indexSimpleExtended = isSimpleExtended(indexTip, indexPip);
        const middleSimpleExtended = isSimpleExtended(middleTip, middlePip);
        const ringSimpleExtended = isSimpleExtended(ringTip, ringPip);
        const pinkySimpleExtended = isSimpleExtended(pinkyTip, pinkyPip);
        
        // 胜利手势（V 字）：食指和中指伸直，无名指和小指弯曲（适中）
        if (indexSimpleExtended && middleSimpleExtended && !ringSimpleExtended && !pinkySimpleExtended) {
            return 'victory';
        }
        
        // 数字1手势：只有食指伸直，其他手指弯曲（适中）
        if (indexSimpleExtended && !middleSimpleExtended && !ringSimpleExtended && !pinkySimpleExtended) {
            return 'one';
        }
        
        // OK手势：拇指和食指形成圆圈，其他手指伸直
        const thumbIndexDistance = Math.sqrt(
            Math.pow(thumbTip.x - indexTip.x, 2) + 
            Math.pow(thumbTip.y - indexTip.y, 2)
        );
        // 适中：拇指和食指距离小于 0.08
        if (thumbIndexDistance < 0.08 && middleSimpleExtended && ringSimpleExtended && pinkySimpleExtended) {
            return 'ok';
        }
        
        // 停止（手掌张开）：所有手指伸直
        if (indexSimpleExtended && middleSimpleExtended && ringSimpleExtended && pinkySimpleExtended) {
            return 'open_palm';
        }
        
        // 呼叫：拇指和小指伸直
        if (thumbTip.y < wrist.y && pinkySimpleExtended && !indexSimpleExtended && !middleSimpleExtended && !ringSimpleExtended) {
            return 'call';
        }
        
        return null;
    }
    
    /**
     * 识别双手爱心手势
     */
    recognizeHeartGesture(leftHand, rightHand) {
        // 获取两只手的关键点
        const leftThumbTip = leftHand[4];
        const leftIndexTip = leftHand[8];
        const leftThumbIp = leftHand[3];
        const leftIndexPip = leftHand[6];
        const leftWrist = leftHand[0];

        const rightThumbTip = rightHand[4];
        const rightIndexTip = rightHand[8];
        const rightThumbIp = rightHand[3];
        const rightIndexPip = rightHand[6];
        const rightWrist = rightHand[0];

        // 计算拇指和食指之间的距离
        const thumbDistance = Math.sqrt(
            Math.pow(leftThumbTip.x - rightThumbTip.x, 2) +
            Math.pow(leftThumbTip.y - rightThumbTip.y, 2)
        );

        const indexDistance = Math.sqrt(
            Math.pow(leftIndexTip.x - rightIndexTip.x, 2) +
            Math.pow(leftIndexTip.y - rightIndexTip.y, 2)
        );

        // 计算指尖到手腕的距离（判断手指是否伸出）
        const getFingerLength = (tip, wrist) => Math.sqrt(
            Math.pow(tip.x - wrist.x, 2) + Math.pow(tip.y - wrist.y, 2)
        );
        
        const leftThumbLength = getFingerLength(leftThumbTip, leftWrist);
        const leftIndexLength = getFingerLength(leftIndexTip, leftWrist);
        const rightThumbLength = getFingerLength(rightThumbTip, rightWrist);
        const rightIndexLength = getFingerLength(rightIndexTip, rightWrist);

        // 检查拇指和食指是否伸出（距离手腕足够远）
        const thumbExtended = (length) => length > 0.1;
        const indexExtended = (length) => length > 0.15;
        
        const leftThumbOk = thumbExtended(leftThumbLength);
        const leftIndexOk = indexExtended(leftIndexLength);
        const rightThumbOk = thumbExtended(rightThumbLength);
        const rightIndexOk = indexExtended(rightIndexLength);

        // 爱心手势条件：
        // 1. 拇指和食指都伸出
        // 2. 两只手的拇指尖距离要近
        // 3. 两只手的食指尖距离要近
        if (leftThumbOk && leftIndexOk && rightThumbOk && rightIndexOk) {
            if (thumbDistance < 0.18 && indexDistance < 0.18) {
                return 'heart';
            }
        }

        return null;
    }

    /**
     * 识别双手张开手势
     */
    recognizeDoubleFistGesture(leftHand, rightHand) {
        // 检查左手是否张开（所有手指都伸直）
        const leftIndexTip = leftHand[8];
        const leftIndexPip = leftHand[6];
        const leftMiddleTip = leftHand[12];
        const leftMiddlePip = leftHand[10];
        const leftRingTip = leftHand[16];
        const leftRingPip = leftHand[14];
        const leftPinkyTip = leftHand[20];
        const leftPinkyPip = leftHand[18];
        
        // 检查右手是否张开
        const rightIndexTip = rightHand[8];
        const rightIndexPip = rightHand[6];
        const rightMiddleTip = rightHand[12];
        const rightMiddlePip = rightHand[10];
        const rightRingTip = rightHand[16];
        const rightRingPip = rightHand[14];
        const rightPinkyTip = rightHand[20];
        const rightPinkyPip = rightHand[18];
        
        // 手指伸直判断：指尖在关节上方
        const isExtended = (tip, pip) => tip.y < pip.y;
        
        // 左手张开：食指、中指、无名指、小指都伸直
        const leftOpen = isExtended(leftIndexTip, leftIndexPip) && 
                        isExtended(leftMiddleTip, leftMiddlePip) && 
                        isExtended(leftRingTip, leftRingPip) && 
                        isExtended(leftPinkyTip, leftPinkyPip);
        
        // 右手张开
        const rightOpen = isExtended(rightIndexTip, rightIndexPip) && 
                         isExtended(rightMiddleTip, rightMiddlePip) && 
                         isExtended(rightRingTip, rightRingPip) && 
                         isExtended(rightPinkyTip, rightPinkyPip);
        
        // 两只手都张开
        if (leftOpen && rightOpen) {
            return 'double_fist';
        }
        
        return null;
    }
    
    /**
     * 显示手势反馈
     */
    showGestureFeedback(gesture) {
        // 如果已有反馈元素，先移除
        const existingFeedback = document.getElementById('gesture-feedback');
        if (existingFeedback) {
            existingFeedback.remove();
        }
        
        // 创建反馈元素
        const feedback = document.createElement('div');
        feedback.id = 'gesture-feedback';
        feedback.style.position = 'fixed';
        feedback.style.top = '20px';
        feedback.style.right = '20px';
        feedback.style.padding = '12px 24px';
        feedback.style.background = 'linear-gradient(135deg, rgba(0, 247, 255, 0.9), rgba(0, 150, 255, 0.9))';
        feedback.style.color = 'white';
        feedback.style.borderRadius = '8px';
        feedback.style.fontSize = '16px';
        feedback.style.fontWeight = 'bold';
        feedback.style.boxShadow = '0 4px 20px rgba(0, 247, 255, 0.4)';
        feedback.style.zIndex = '10000';
        feedback.style.animation = 'slideIn 0.3s ease-out';
        feedback.textContent = this.gestureMap[gesture];
        
        document.body.appendChild(feedback);
        
        // 2 秒后移除
        setTimeout(() => {
            feedback.style.animation = 'slideOut 0.3s ease-out';
            setTimeout(() => feedback.remove(), 300);
        }, 2000);
    }
    
    /**
     * 执行手势对应的动作
     */
    executeGestureAction(gesture) {
        switch (gesture) {
            case 'victory':
                // 切换子系统（智能问数/智能聊天）
                this.triggerAction('switch_system');
                break;
            case 'one':
                // 上传文件
                this.triggerAction('upload_file');
                break;
            case 'ok':
                // 发送消息
                this.triggerAction('send_message');
                break;
            case 'open_palm':
                // 停止 AI 响应
                this.triggerAction('stop_response');
                break;
            case 'call':
                // 打开机器人面板
                this.triggerAction('show_robot_panel');
                break;
            case 'double_fist':
                // 截图
                this.triggerAction('screenshot');
                break;
            case 'heart':
                // 发送土味情话
                this.triggerAction('send_love_message');
                break;
        }
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
            this.callbacks[event].forEach(callback => callback(data));
        }
    }
    
    /**
     * 触发行动
     */
    triggerAction(action) {
        const event = new CustomEvent('gesture-action', {detail: {action}});
        window.dispatchEvent(event);
    }
    
    /**
     * 获取手势历史
     */
    getGestureHistory() {
        return this.gestureHistory;
    }
    
    /**
     * 清除手势历史
     */
    clearGestureHistory() {
        this.gestureHistory = [];
    }
}

// 导出全局
window.GestureController = GestureController;
