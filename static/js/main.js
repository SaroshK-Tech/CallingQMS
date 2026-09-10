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
        const series = ticketNumber.charAt(0);
        const digits = ticketNumber.slice(1);
        
        // Build audio file list
        if (lang === 'en') {
            files.push(`/static/audio/en_ticket.mp3`);
            files.push(`/static/audio/en_${series}.mp3`);
            for (const d of digits) {
                files.push(`/static/audio/en_${d}.mp3`);
            }
            files.push(`/static/audio/en_please_proceed_to.mp3`);
            files.push(`/static/audio/en_counter_${this.slug(counterName)}.mp3`);
        } else {
            files.push(`/static/audio/ur_ticket.mp3`);
            files.push(`/static/audio/ur_${series}.mp3`);
            for (const d of digits) {
                files.push(`/static/audio/ur_${d}.mp3`);
            }
            files.push(`/static/audio/ur_please_proceed_to.mp3`);
            files.push(`/static/audio/ur_counter_${this.slug(counterName)}.mp3`);
        }

        return files;
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
