/* HERO Viewport — services/state.js */
/* Singleton state store — exports direct methods and factory */

function _createStore(initial = {}) {
  let state = { ...initial };
  const listeners = new Map();

  return {
    getState: () => state,

    setState: (partial) => {
      const prev = { ...state };
      state = { ...state, ...partial };
      listeners.forEach((cbs) => {
        cbs.forEach((cb) => cb(state, prev));
      });
    },

    subscribe: (cb) => {
      const key = `_cb_${Date.now()}_${Math.random()}`;
      if (!listeners.has(key)) listeners.set(key, new Set());
      listeners.get(key).add(cb);
      return () => listeners.get(key)?.delete(cb);
    },

    getSnapshot: () => ({ ...state }),
  };
}

// Singleton store instance
let _instance = null;
function _getInstance() {
  if (!_instance) _instance = _createStore({
    trees: [],
    summary: null,
    sandboxes: {},
    selectedSandbox: null,
    expanded: {},
    isConnected: false,
    tokenHistory: [0],
    errorCount: 0,
    burnRate: 0,
  });
  return _instance;
}

// Named exports for singleton access (used by components)
export function getState() { return _getInstance().getState(); }
export function setState(partial) { return _getInstance().setState(partial); }
export function subscribe(cb) { return _getInstance().subscribe(cb); }
export function getSnapshot() { return _getInstance().getSnapshot(); }

// Factory export for app.js (returns singleton)
export function createStore(initial) {
  const inst = _getInstance();
  // Override initial state if provided
  if (initial) inst.setState(initial);
  return inst;
}
