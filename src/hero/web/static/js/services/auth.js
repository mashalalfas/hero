/* HERO Viewport — services/auth.js */
const STORAGE_KEY = 'hero_web_token';

export function setToken(token) {
  sessionStorage.setItem(STORAGE_KEY, token);
}

export function getToken() {
  return sessionStorage.getItem(STORAGE_KEY);
}

export function clearToken() {
  sessionStorage.removeItem(STORAGE_KEY);
}

export function hasToken() {
  return !!getToken();
}
