// ─── State ───
let profile = null;
let ws = null;

// ─── Init ───
document.addEventListener('DOMContentLoaded', async () => {
    try {
        const res = await fetch('/api/profile');
        if (res.ok) {
            profile = await res.json();
            showChat();
        } else {
            showSetup();
        }
    } catch (e) {
        showSetup();
    }
    registerServiceWorker();
});

// ─── View Management ───
function showView(id) {
    document.querySelectorAll('.view').forEach(v => v.classList.add('hidden'));
    document.getElementById(id).classList.remove('hidden');
}

function showSetup() {
    showView('setup-view');
}

function showChat() {
    showView('chat-view');
    if (profile) {
        document.getElementById('header-baby-name').textContent = profile.baby_name || 'Baby';
        document.getElementById('header-week').textContent = `Week ${profile.week} · ${profile.weeks_remaining} weeks to go`;
    }
    loadMessages();
    connectWebSocket();
    document.getElementById('chat-input').focus();
}

function showInfo() {
    showView('info-view');
    loadWeekInfo();
    loadMoodTrend();
}

// ─── Setup Form ───
document.getElementById('setup-form').addEventListener('submit', async (e) => {
    e.preventDefault();
    const btn = document.querySelector('.setup-submit');
    btn.textContent = 'Connecting to baby...';
    btn.disabled = true;

    const data = {
        name: document.getElementById('mom-name').value.trim(),
        baby_name: document.getElementById('baby-name').value.trim(),
        due_date: document.getElementById('due-date').value,
        baby_gender: document.querySelector('.gender-btn.active')?.dataset.gender || 'surprise',
    };

    try {
        const res = await fetch('/api/setup', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data),
        });
        const result = await res.json();
        profile = {
            name: data.name,
            baby_name: data.baby_name,
            due_date: data.due_date,
            baby_gender: data.baby_gender,
            week: result.week,
            weeks_remaining: 40 - result.week,
        };
        showChat();
    } catch (err) {
        btn.textContent = 'Start Talking';
        btn.disabled = false;
        alert('Something went wrong. Please try again.');
    }
});

// Gender button toggle
document.querySelectorAll('.gender-btn').forEach(btn => {
    btn.addEventListener('click', () => {
        document.querySelectorAll('.gender-btn').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
    });
});

// ─── Chat ───
async function loadMessages() {
    try {
        const res = await fetch('/api/messages');
        const data = await res.json();
        const container = document.getElementById('chat-messages');
        container.innerHTML = '';

        let lastDate = '';
        for (const msg of data.messages) {
            const msgDate = formatDate(msg.created_at);
            if (msgDate !== lastDate) {
                lastDate = msgDate;
                const sep = document.createElement('div');
                sep.className = 'date-separator';
                sep.textContent = msgDate;
                container.appendChild(sep);
            }
            appendBubble(msg.role, msg.content, msg.created_at, false);
        }
        scrollToBottom();
    } catch (e) {
        console.error('Failed to load messages:', e);
    }
}

function appendBubble(role, content, timestamp, animate = true) {
    const container = document.getElementById('chat-messages');

    const bubble = document.createElement('div');
    bubble.className = role === 'baby' ? 'bubble-baby' : 'bubble-mom';
    bubble.textContent = content;
    if (!animate) bubble.style.animation = 'none';
    container.appendChild(bubble);

    if (timestamp) {
        const time = document.createElement('div');
        time.className = `bubble-time ${role === 'baby' ? 'bubble-time-left' : 'bubble-time-right'}`;
        time.textContent = formatTime(timestamp);
        container.appendChild(time);
    }
}

function scrollToBottom() {
    const container = document.getElementById('chat-messages');
    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
    });
}

async function sendMessage() {
    const input = document.getElementById('chat-input');
    const text = input.value.trim();
    if (!text) return;

    input.value = '';
    appendBubble('mom', text, new Date().toISOString());
    scrollToBottom();
    showTyping();

    try {
        const res = await fetch('/api/chat', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ message: text }),
        });
        const data = await res.json();
        hideTyping();
        appendBubble('baby', data.reply, new Date().toISOString());
        scrollToBottom();
    } catch (err) {
        hideTyping();
        appendBubble('baby', "Hmm, I got a little sleepy there... try again? I'm here.", new Date().toISOString());
        scrollToBottom();
    }
}

// Send on enter
document.getElementById('chat-input').addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
});

document.getElementById('send-btn').addEventListener('click', sendMessage);

// Typing indicator
function showTyping() {
    document.getElementById('typing').classList.remove('hidden');
    scrollToBottom();
}

function hideTyping() {
    document.getElementById('typing').classList.add('hidden');
}

// ─── WebSocket ───
function connectWebSocket() {
    if (ws) {
        try { ws.close(); } catch (e) {}
    }

    const protocol = location.protocol === 'https:' ? 'wss:' : 'ws:';
    ws = new WebSocket(`${protocol}//${location.host}/ws`);

    ws.onmessage = (event) => {
        try {
            const data = JSON.parse(event.data);
            if (data.type === 'baby_message') {
                appendBubble('baby', data.content, new Date().toISOString());
                scrollToBottom();
                if (navigator.vibrate) navigator.vibrate(200);
            }
        } catch (e) {}
    };

    ws.onclose = () => {
        setTimeout(connectWebSocket, 5000);
    };
}

// ─── Info View ───
document.getElementById('info-btn').addEventListener('click', showInfo);
document.getElementById('back-btn').addEventListener('click', showChat);

const SIZE_EMOJIS = {
    'poppy seed': '\u{1F33C}', 'sesame seed': '\u{1F330}', 'lentil': '\u{1F7E4}',
    'blueberry': '\u{1FAD0}', 'kidney bean': '\u{1FAD8}', 'grape': '\u{1F347}',
    'kumquat': '\u{1F34A}', 'fig': '\u{1F95D}', 'lime': '\u{1F34B}',
    'peach': '\u{1F351}', 'lemon': '\u{1F34B}', 'apple': '\u{1F34E}',
    'avocado': '\u{1F951}', 'turnip': '\u{1F955}', 'bell pepper': '\u{1FAD1}',
    'mango': '\u{1F96D}', 'banana': '\u{1F34C}', 'carrot': '\u{1F955}',
    'papaya': '\u{1F350}', 'grapefruit': '\u{1F34A}', 'ear of corn': '\u{1F33D}',
    'cauliflower': '\u{1F966}', 'lettuce': '\u{1F96C}', 'broccoli': '\u{1F966}',
    'eggplant': '\u{1F346}', 'butternut squash': '\u{1F33D}', 'cabbage': '\u{1F96C}',
    'coconut': '\u{1F965}', 'squash': '\u{1F33D}', 'pineapple': '\u{1F34D}',
    'cantaloupe': '\u{1F348}', 'honeydew': '\u{1F348}', 'watermelon': '\u{1F349}',
};

async function loadWeekInfo() {
    try {
        const res = await fetch('/api/week');
        const data = await res.json();
        const info = data.info;

        document.getElementById('info-week-title').textContent = `Week ${data.week}`;
        document.getElementById('info-size').textContent = `The size of ${info.size}`;
        document.getElementById('info-dimensions').textContent = `${info.length} · ${info.weight}`;

        // Find matching emoji
        const sizeKey = Object.keys(SIZE_EMOJIS).find(k => info.size.includes(k));
        document.getElementById('info-size-emoji').textContent = sizeKey ? SIZE_EMOJIS[sizeKey] : '\u{1F476}';

        populateList('info-developing', info.developing);
        populateList('info-can-do', info.baby_can);
        populateList('info-mom-feeling', info.mom_might_feel);
        document.getElementById('info-fun-fact').textContent = info.fun_fact;
    } catch (e) {
        console.error('Failed to load week info:', e);
    }
}

async function loadMoodTrend() {
    try {
        const res = await fetch('/api/mood/trend');
        const data = await res.json();

        const trendText = {
            improving: "You've been feeling better lately \u{2728}",
            stable: "Your mood has been steady",
            declining: "It's been a tough stretch. I'm here with you \u{1F49B}",
        };
        document.getElementById('mood-trend').textContent = trendText[data.trend] || 'Start chatting to track your mood';

        const dotsContainer = document.getElementById('mood-dots');
        dotsContainer.innerHTML = '';
        for (const entry of data.entries) {
            const dot = document.createElement('div');
            dot.className = `mood-dot ${entry.mood_score >= 3.5 ? 'high' : entry.mood_score >= 2.5 ? 'mid' : 'low'}`;
            dot.textContent = Math.round(entry.mood_score);
            dot.title = `${entry.mood} — ${formatDate(entry.created_at)}`;
            dotsContainer.appendChild(dot);
        }
    } catch (e) {}
}

function populateList(id, items) {
    const ul = document.getElementById(id);
    ul.innerHTML = '';
    for (const item of items) {
        const li = document.createElement('li');
        li.textContent = item;
        ul.appendChild(li);
    }
}

// ─── Helpers ───
function formatTime(isoStr) {
    try {
        const d = new Date(isoStr);
        return d.toLocaleTimeString([], { hour: 'numeric', minute: '2-digit' });
    } catch {
        return '';
    }
}

function formatDate(isoStr) {
    try {
        const d = new Date(isoStr);
        const today = new Date();
        if (d.toDateString() === today.toDateString()) return 'Today';
        const yesterday = new Date(today);
        yesterday.setDate(yesterday.getDate() - 1);
        if (d.toDateString() === yesterday.toDateString()) return 'Yesterday';
        return d.toLocaleDateString([], { month: 'short', day: 'numeric' });
    } catch {
        return '';
    }
}

// ─── PWA ───
async function registerServiceWorker() {
    if ('serviceWorker' in navigator) {
        try {
            await navigator.serviceWorker.register('/sw.js');
        } catch (e) {
            console.log('SW registration failed:', e);
        }
    }
}
