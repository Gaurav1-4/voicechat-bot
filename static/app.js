let mediaRecorder;
let audioChunks = [];
let isRecording = false;

const recordBtn = document.getElementById('recordBtn');
const btnText = document.getElementById('btnText');
const chatContainer = document.getElementById('chat-container');
const audioPlayer = document.getElementById('audioPlayer');

// Request permissions
if (navigator.mediaDevices && navigator.mediaDevices.getUserMedia) {
    navigator.mediaDevices.getUserMedia({ audio: true })
        .then(stream => {
            let options = { mimeType: 'audio/webm' };
            let ext = 'webm';
            if (!MediaRecorder.isTypeSupported('audio/webm')) {
                options = { mimeType: 'audio/mp4' };
                ext = 'mp4';
            }
            
            mediaRecorder = new MediaRecorder(stream, options);
            
            mediaRecorder.ondataavailable = e => {
                if (e.data.size > 0) {
                    audioChunks.push(e.data);
                }
            };
            
            mediaRecorder.onstop = () => {
                const audioBlob = new Blob(audioChunks, { type: options.mimeType });
                audioChunks = [];
                sendToBackend(audioBlob, ext, null);
            };
        })
        .catch(err => {
            console.error("Error accessing mic:", err);
            addMessage("Error: Could not access microphone. Please allow mic permissions.", "system-msg");
            recordBtn.disabled = true;
        });
} else {
    console.error("MediaDevices API not supported.");
    addMessage("Error: Microphone access is not supported in this browser (HTTPS is required on mobile). You can still type text.", "system-msg");
    recordBtn.disabled = true;
}

// Mouse/Touch Events for Hold to Speak
recordBtn.addEventListener('mousedown', startRecording);
recordBtn.addEventListener('mouseup', stopRecording);
recordBtn.addEventListener('mouseleave', stopRecording);

recordBtn.addEventListener('touchstart', (e) => { e.preventDefault(); startRecording(); });
recordBtn.addEventListener('touchend', (e) => { e.preventDefault(); stopRecording(); });
recordBtn.addEventListener('touchcancel', (e) => { e.preventDefault(); stopRecording(); });

// Text Input Events
const askInput = document.getElementById('askInput');
const sendBtn = document.getElementById('sendBtn');
const uploadBtn = document.getElementById('uploadBtn');
const visualizer = document.getElementById('visualizer');

sendBtn.addEventListener('click', sendTextMessage);
askInput.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' || e.keyCode === 13) {
        sendTextMessage();
    }
});

uploadBtn.addEventListener('click', () => {
    addMessage("⚠️ Upload functionality is not yet implemented.", "system-msg");
});

// Suggestion Chips
document.querySelectorAll('.suggestion-chip').forEach(chip => {
    chip.addEventListener('click', () => {
        askInput.value = chip.textContent;
        sendTextMessage();
    });
});

let recordStartTime = 0;
let currentSentMsgDiv = null;
let audioUnlocked = false;

function unlockAudio() {
    if (!audioUnlocked) {
        audioPlayer.play().catch(e => { console.log('Audio unlock failed:', e); });
        audioPlayer.pause();
        audioPlayer.currentTime = 0;
        audioUnlocked = true;
    }
}

document.body.addEventListener('click', unlockAudio, { once: true });
document.body.addEventListener('touchstart', unlockAudio, { once: true });

function startRecording() {
    if (!mediaRecorder || isRecording) return;
    audioChunks = [];
    try {
        mediaRecorder.start();
    } catch (e) {
        console.error("Failed to start recording:", e);
        return;
    }
    isRecording = true;
    recordStartTime = Date.now();
    recordBtn.classList.add('recording');
    document.querySelector('.pill-text').textContent = 'Listening...';
    document.querySelector('.visualizer-text').textContent = "I'm listening...";
    visualizer.classList.add('active');
}

function stopRecording() {
    if (!mediaRecorder || !isRecording) return;
    
    let duration = Date.now() - recordStartTime;
    if (duration < 500) {
        // Tapped instead of holding
        try { mediaRecorder.stop(); } catch(e) {}
        isRecording = false;
        recordBtn.classList.remove('recording');
        document.querySelector('.pill-text').textContent = 'Hold to Speak';
        document.querySelector('.visualizer-text').textContent = "Ready.";
        visualizer.classList.remove('active');
        addMessage("⚠️ Please hold the microphone button down while speaking.", "system-msg");
        audioChunks = [];
        return;
    }

    try { mediaRecorder.stop(); } catch(e) {}
    isRecording = false;
    recordBtn.classList.remove('recording');
    document.querySelector('.pill-text').textContent = 'Hold to Speak';
    document.querySelector('.visualizer-text').textContent = "Processing...";
    visualizer.classList.remove('active');
    visualizer.classList.add('listening');
    recordBtn.disabled = true;
    currentSentMsgDiv = addMessage("🎙️ Processing audio...", "user-msg");
}

function sendTextMessage() {
    const text = askInput.value.trim();
    if (!text) return;
    
    askInput.value = '';
    sendBtn.disabled = true;
    recordBtn.disabled = true;
    document.querySelector('.visualizer-text').textContent = "Thinking...";
    visualizer.classList.add('listening');
    currentSentMsgDiv = addMessage(text, "user-msg");
    sendToBackend(null, null, text);
}

function addMessage(text, className) {
    const msgDiv = document.createElement('div');
    msgDiv.className = `message ${className}`;
    
    // Convert newlines to <br> for formatting
    msgDiv.innerHTML = text.replace(/\n/g, '<br>');
    
    chatContainer.appendChild(msgDiv);
    chatContainer.scrollTop = chatContainer.scrollHeight;
    return msgDiv;
}

function sendToBackend(audioBlob, ext, textInput) {
    const formData = new FormData();
    const voiceSelect = document.getElementById('voiceSelect');
    
    if (audioBlob) {
        formData.append('audio', audioBlob, 'recording.' + ext);
    }
    if (textInput) {
        formData.append('text', textInput);
    }
    if (voiceSelect) {
        formData.append('voice', voiceSelect.value);
    }
    
    fetch('/ask', {
        method: 'POST',
        body: formData
    })
    .then(async response => {
        const contentType = response.headers.get("content-type");
        if (contentType && contentType.includes("application/json")) {
            const data = await response.json();
            return { error: data.error };
        } else {
            const audioBlob = await response.blob();
            return {
                audioBlob: audioBlob,
                userText: decodeURIComponent(response.headers.get('X-User-Text') || ""),
                answerText: decodeURIComponent(response.headers.get('X-Answer-Text') || "")
            };
        }
    })
    .then(data => {
        recordBtn.disabled = false;
        sendBtn.disabled = false;
        visualizer.classList.remove('listening');
        
        if (data.error) {
            if (currentSentMsgDiv && !textInput) {
                currentSentMsgDiv.remove();
                currentSentMsgDiv = null;
            }
            document.querySelector('.visualizer-text').textContent = "Ready.";
            addMessage("Error: " + data.error, "system-msg");
            return;
        }
        
        if (data.userText && currentSentMsgDiv && !textInput) {
            currentSentMsgDiv.innerHTML = data.userText.replace(/\n/g, '<br>');
        }
        
        if (currentSentMsgDiv) {
            currentSentMsgDiv = null;
        }
        
        // Show text answer
        addMessage(data.answerText, "bot-msg");
        
        document.querySelector('.visualizer-text').textContent = "Speaking...";
        
        // Play audio answer directly from blob
        const audioUrl = URL.createObjectURL(data.audioBlob);
        audioPlayer.src = audioUrl;
        audioPlayer.play();
        
        audioPlayer.onended = () => {
            document.querySelector('.visualizer-text').textContent = "Ready.";
            URL.revokeObjectURL(audioUrl); // Clean up memory
        };
    })
    .catch(err => {
        console.error(err);
        recordBtn.disabled = false;
        sendBtn.disabled = false;
        document.querySelector('.visualizer-text').textContent = "Ready.";
        visualizer.classList.remove('listening');
        if (currentSentMsgDiv && !textInput) {
            currentSentMsgDiv.remove();
            currentSentMsgDiv = null;
        }
        addMessage("Error: Could not connect to server or request failed.", "system-msg");
    });
}
