class EQMSWebSocket {
    constructor(group, onMessage) {
        this.group = group;
        this.onMessage = onMessage;
        this.ws = null;
        this.reconnectAttempts = 0;
        this.maxReconnectAttempts = 10;
        this.reconnectDelay = 1000;
        this.connect();
    }

    connect() {
        const protocol = window.location.protocol === 'https:' ? 'wss://' : 'ws://';
        const url = `${protocol}${window.location.host}/ws/${this.group}/`;
        
        this.ws = new WebSocket(url);

        this.ws.onopen = () => {
            console.log(`WebSocket connected to ${this.group}`);
            this.reconnectAttempts = 0;
        };

        this.ws.onmessage = (e) => {
            const data = JSON.parse(e.data);
            this.onMessage(data);
        };

        this.ws.onclose = (e) => {
            console.log(`WebSocket closed for ${this.group}`);
            if (this.reconnectAttempts < this.maxReconnectAttempts) {
                setTimeout(() => {
                    this.reconnectAttempts++;
                    this.connect();
                }, this.reconnectDelay * Math.pow(2, this.reconnectAttempts));
            }
        };

        this.ws.onerror = (e) => {
            console.error('WebSocket error:', e);
        };
    }

    send(data) {
        if (this.ws && this.ws.readyState === WebSocket.OPEN) {
            this.ws.send(JSON.stringify(data));
        }
    }

    close() {
        if (this.ws) {
            this.ws.close();
        }
    }
}

class AudioAnnouncer {
    constructor() {
        this.queue = [];
        this.playing = false;
    }

    enqueue(files) {
        this.queue.push(files);
        this.processQueue();
    }

    async processQueue() {
        if (this.playing) return;
        this.playing = true;
        while (this.queue.length > 0) {
            const files = this.queue.shift();
            await this.playSequence(files);
        }
        this.playing = false;
    }

    playChime() {
        this.enqueue(['/static/audio/chime.wav']);
    }

    playAnnouncement(ticketNumber, counterName, lang = 'en') {
        this.enqueue(this.buildFileList(ticketNumber, counterName, lang));
    }

    buildFileList(ticketNumber, counterName, lang) {
        const files = [];
        const match = /^([A-Za-z]*)(\d+)$/.exec(ticketNumber || '');
        const series = match ? match[1] : (ticketNumber || '').slice(0, 1);
        const digits = match ? match[2] : (ticketNumber || '').slice(1);

        // The numeric part is spoken as a whole number (mirrors core/number_words.py).
        const prefix = [`/static/audio/${lang}_ticket.mp3`];
        if (series) prefix.push(`/static/audio/${lang}_${series}.mp3`);
        for (const token of this.numberTokens(digits, lang)) {
            prefix.push(`/static/audio/${lang}_n_${token}.mp3`);
        }

        files.push(...prefix);

        if (lang === 'en') {
            files.push(`/static/audio/en_please_proceed_to.mp3`);
            files.push(`/static/audio/en_counter_${this.slug(counterName)}.mp3`);
        } else {
            files.push(`/static/audio/ur_please_proceed_to.mp3`);
            files.push(`/static/audio/ur_counter_${this.slug(counterName)}.mp3`);
            files.push(`/static/audio/ur_go_to.mp3`);
        }

        return files;
    }

    numberTokens(number, lang) {
        const n = parseInt(number, 10);
        if (!Number.isFinite(n) || n <= 0) return ['0'];
        return lang === 'ur' ? this.urduTokens(n) : this.englishTokens(n);
    }

    englishTokens(n) {
        const tokens = [];
        if (n >= 1000) {
            tokens.push(...this.englishTokens(Math.floor(n / 1000)), '1000');
            n %= 1000;
            if (n && n < 100) tokens.push('and');
        }
        if (n >= 100) {
            tokens.push(...this.englishTokens(Math.floor(n / 100)), '100');
            n %= 100;
            if (n) tokens.push('and');
        }
        if (n >= 20) {
            tokens.push(String(Math.floor(n / 10) * 10));
            n %= 10;
        }
        if (n) tokens.push(String(n));
        return tokens;
    }

    urduTokens(n) {
        const tokens = [];
        if (n >= 1000) {
            tokens.push(...this.urduTokens(Math.floor(n / 1000)), '1000');
            n %= 1000;
        }
        if (n >= 100) {
            tokens.push(String(Math.floor(n / 100)), '100');
            n %= 100;
        }
        if (n) tokens.push(String(n));
        return tokens;
    }

    slug(name) {
        return name.toLowerCase().replace(/[^a-z0-9]+/g, '_');
    }

    async playSequence(files) {
        for (const file of files) {
            try {
                const audio = new Audio(file);
                await new Promise((resolve, reject) => {
                    audio.onended = resolve;
                    audio.onerror = () => {
                        console.warn(`Audio file not found: ${file}`);
                        resolve();
                    };
                    audio.play().catch(resolve);
                });
            } catch (e) {
                console.warn(`Failed to play ${file}:`, e);
            }
        }
    }
}

// Shared instances
const announcer = new AudioAnnouncer();
