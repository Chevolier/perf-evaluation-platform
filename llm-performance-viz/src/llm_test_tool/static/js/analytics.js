// Analytics module
import { getApiUrl } from './config.js';

export class Analytics {
    constructor() {
        this.clientId = window.CLIENT_ID || this.generateClientId();
        this.eventQueue = [];
        this.isOnline = navigator.onLine;
        
        // Set up basic event listeners
        this.setupEventListeners();
    }
    
    generateClientId() {
        // Simple client ID generation
        const clientId = 'client_' + Math.random().toString(36).substr(2, 16);
        return clientId;
    }
    
    setupEventListeners() {
        // Track online/offline status for event queue management
        window.addEventListener('online', () => {
            this.isOnline = true;
            this.flushEventQueue();
        });
        
        window.addEventListener('offline', () => {
            this.isOnline = false;
        });
    }
    
    async logEvent(eventType, data = {}) {
        const event = {
            event_type: eventType,
            data: {
                ...data,
                timestamp: new Date().toISOString(),
                client_id: this.clientId
            }
        };
        
        if (this.isOnline) {
            try {
                await fetch(getApiUrl('/api/analytics'), {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Client-ID': this.clientId
                    },
                    body: JSON.stringify(event)
                });
            } catch (error) {
                console.warn('Failed to send analytics event:', error);
                this.eventQueue.push(event);
            }
        } else {
            this.eventQueue.push(event);
        }
    }
    
    async flushEventQueue() {
        if (!this.isOnline || this.eventQueue.length === 0) return;
        
        const events = [...this.eventQueue];
        this.eventQueue = [];
        
        for (const event of events) {
            try {
                await fetch(getApiUrl('/api/analytics'), {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json',
                        'X-Client-ID': this.clientId
                    },
                    body: JSON.stringify(event)
                });
            } catch (error) {
                console.warn('Failed to flush analytics event:', error);
                this.eventQueue.push(event);
                break;
            }
        }
    }
}