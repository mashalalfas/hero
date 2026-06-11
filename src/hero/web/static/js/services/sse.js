/* HERO Viewport — services/sse.js */

class SSEManager {
  constructor(url = '/api/v1/events') {
    this.url = url;
    this.eventSource = null;
    this.handlers = new Map(); // event → Set<callback>
    this.lastEventId = null;
    this.reconnectAttempt = 0;
    this.reconnectMax = 16000;
    this.reconnectBase = 1000;
    this._disconnected = false;
    this._token = null;
  }

  connect(token) {
    this._disconnected = false;
    this.reconnectAttempt = 0;
    this._token = token;
    this._createConnection(token);
  }

  _createConnection(token) {
    const url = new URL(this.url, window.location.origin);
    if (token) url.searchParams.set('token', token);

    this.eventSource = new EventSource(url.toString());

    if (this.lastEventId !== null) {
      // Browsers pick this up automatically via EventSource.lastEventId,
      // but we explicitly store it for reference.
    }

    this.eventSource.addEventListener('open', () => {
      this.reconnectAttempt = 0;
    });

    this.eventSource.addEventListener('message', (e) => {
      if (e.lastEventId) this.lastEventId = e.lastEventId;
      this._emit('message', e.data);
    });

    // Forward named events
    this.handlers.forEach((_, event) => {
      if (event === 'message') return;
      this.eventSource.addEventListener(event, (e) => {
        if (e.lastEventId) this.lastEventId = e.lastEventId;
        this._emit(event, e.data ? JSON.parse(e.data) : null);
      });
    });

    this.eventSource.addEventListener('error', () => {
      if (this._disconnected) return;
      this.eventSource.close();
      this._reconnect();
    });
  }

  on(event, callback) {
    if (!this.handlers.has(event)) this.handlers.set(event, new Set());
    this.handlers.get(event).add(callback);

    // If already connected, attach listener directly
    if (this.eventSource && event !== 'message') {
      this.eventSource.addEventListener(event, (e) => {
        if (e.lastEventId) this.lastEventId = e.lastEventId;
        this._emit(event, e.data ? JSON.parse(e.data) : null);
      });
    }
    return () => this.handlers.get(event)?.delete(callback);
  }

  disconnect() {
    this._disconnected = true;
    this.reconnectAttempt = 0;
    this._token = null;
    if (this.eventSource) {
      this.eventSource.close();
      this.eventSource = null;
    }
  }

  _emit(event, data) {
    const cbs = this.handlers.get(event);
    if (cbs) cbs.forEach(cb => cb(data));
  }

  _reconnect() {
    if (this._disconnected) return;
    const delay = Math.min(
      this.reconnectBase * Math.pow(2, this.reconnectAttempt),
      this.reconnectMax
    );
    this.reconnectAttempt++;
    setTimeout(() => {
      if (!this._disconnected) this._createConnection(this._token);
    }, delay);
  }
}

export { SSEManager };
