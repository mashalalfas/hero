/**
 * HERO OS — Reactive State Store
 * Minimal pub/sub with deep equality checks
 */

const _stores = new Map();

function createStore(key, initial = {}) {
  let state = { ...initial };
  const listeners = new Set();

  const store = {
    get() {
      return state;
    },
    set(patch) {
      const next = { ...state, ...patch };
      const changed = !_deepEqual(state, next);
      if (changed) {
        state = next;
        listeners.forEach((fn) => {
          try { fn(state); } catch (e) { console.error('store listener error:', e); }
        });
      }
      return changed;
    },
    subscribe(fn) {
      listeners.add(fn);
      fn(state); // immediate call
      return () => listeners.delete(fn);
    },
  };

  _stores.set(key, store);
  return store;
}

function getStore(key) {
  return _stores.get(key);
}

function _deepEqual(a, b) {
  if (a === b) return true;
  if (typeof a !== 'object' || typeof b !== 'object' || a == null || b == null) return false;
  const keysA = Object.keys(a);
  const keysB = Object.keys(b);
  if (keysA.length !== keysB.length) return false;
  for (const k of keysA) {
    if (!keysB.includes(k)) return false;
    if (!_deepEqual(a[k], b[k])) return false;
  }
  return true;
}

export { createStore, getStore };
