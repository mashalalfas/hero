# HERO Dashboard Kill Button — MiniMax Analysis & Fix

**Agent:** MiniMax RESEARCHER (M2.7)
**Date:** 2026-05-27
**Status:** FIXED & VERIFIED

---

## Problem Statement

The kill button (☠️ Kill) on the HERO dashboard at `http://192.168.8.149:8765` does nothing when tapped on a mobile phone, despite:
- The Melody_MD sandbox showing as "working" (kill button rendered)
- The kill button being visible (red background, 13px font)
- Previous fixes to CSS, modal, and kill endpoint
- It working in headless Playwright tests (desktop Chromium)

## Root Cause Analysis

I identified **5 distinct bugs**, 3 of which were critical to the mobile failure:

---

### 🔴 BUG 1 (Critical): Missing `confirmation_token` in kill API call

**Files:** `static/js/components/controls.js` → `static/js/services/api.js`

**What happened:**
```js
// controls.js (line 38)
await killSandbox(sbName);

// api.js expects TWO arguments:
export function killSandbox(name, confirmToken) {
  return apiFetch(`.../kill`, {
    body: JSON.stringify({ confirmation_token: confirmToken }),
  });
}
```

`killSandbox(sbName)` was called with only the sandbox name. The `confirmToken` parameter was `undefined`. `JSON.stringify({ confirmation_token: undefined })` produces `{}` (undefined values are dropped by JSON serialization). The backend then checks `if not confirmation_token:` and raises HTTP 400.

**Why this seemed to work:** On desktop Playwright tests, the modal would still *appear* (that part worked). But the Confirm button would silently fail with the API returning 400, showing an error toast that may have been missed or dismissed.

**Fix:** Pass sandbox name as confirmation token:
```js
await killSandbox(sbName, sbName);
```

---

### 🔴 BUG 2 (Critical): Card click handler fires for kill button clicks, triggering full re-render

**File:** `static/js/components/sandbox-card.js` (lines 24-30)

```js
container.addEventListener('click', (e) => {
  const card = e.target.closest('[data-sandbox-name]'); // ← matches card!
  if (!card) return;
  setState({ selectedSandbox: name }); // ← triggers STATE CHANGE → RE-RENDER
});
```

The kill button is **inside** the card div (which has `data-sandbox-name`). When the user taps the kill button:
1. Event bubbles up → kill handler fires → `showModal()` creates the modal
2. Event continues bubbling to the sandbox-grid container
3. Card click handler fires → `e.target.closest('[data-sandbox-name]')` matches the **card**
4. `setState({ selectedSandbox: name })` fires → **synchronous re-render** of ALL cards
5. The re-render replaces `container.innerHTML`, destroying and recreating DOM elements

**Why this breaks on mobile specifically:** On mobile browsers (especially iOS Safari), a DOM mutation during event processing can interfere with the synthesized click event chain. The `requestAnimationFrame` callback (which adds `show` class to the modal) fires after the re-render completes, potentially in a different paint cycle where the event context has been invalidated.

**Fix:** Skip kill clicks in the card click handler:
```js
if (e.target.closest('.kill-btn-container, [data-action="kill"]')) return;
```

---

### 🔴 BUG 3 (High): No mobile touch optimization (CSS)

**File:** `static/css/components.css`

**Issues found:**
1. `.btn-kill` had `min-height: 36px` — below Apple's 44pt HIG minimum touch target
2. No `touch-action: manipulation` — mobile browsers may delay click event for double-tap detection
3. No `-webkit-tap-highlight-color` — no visual feedback on tap
4. No `user-select: none` — text could be accidentally selected on long-press
5. `.modal-btn` CSS class **was entirely missing** — the modal's confirm/cancel buttons had no styling, falling back to bare HTML buttons
6. Modal overlay had no `touch-action: none` or `overscroll-behavior: contain` — allowing background content to scroll on mobile while modal is open

**Fixes applied:**

| Property | Before | After | Why |
|----------|--------|-------|-----|
| `.btn-kill`` min-height` | 36px | 44px | Apple HIG touch target |
| `.btn-kill` touch-action | auto | manipulation | Eliminate 300ms tap delay |
| `.btn-kill` -webkit-tap-highlight-color | auto | transparent | Disable grey highlight box |
| `.btn-kill` padding | 6px 14px | 8px 16px | Better tap area |
| `.btn-kill` font-size | 13px | 14px | Readability |
| `.modal-btn` styles | **missing** | Full styling (padding, touch-action, min-height: 44px, colors) | Buttons were invisible/unstyled |
| `.modal-btn-confirm.danger` | **missing** | Red background, white text | Kill confirmation needs visual urgency |
| `.modal-overlay` touch-action | auto | none | Prevent background scroll |
| `.modal-overlay` overscroll-behavior | auto | contain | Prevent elastic scroll on iOS |
| `.modal-footer` flex-wrap | nowrap | wrap | Prevent button overflow on small screens |
| `.modal-close-btn` touch-action | auto | manipulation | Ensure tap reliability |

---

### 🟡 BUG 4 (Medium): `removeEventListener` passes `null`

**File:** `static/js/components/sandbox-card.js` (line 33)

```js
destroy: () => {
  if (unsubscribe) unsubscribe();
  container.removeEventListener('click', null); // ← null removes nothing!
}
```

Passing `null` as the handler function to `removeEventListener` silently does nothing. The event listener is never cleaned up. If the component is re-created, stale listeners accumulate.

**Fix:** Removed the broken cleanup — the listener uses event delegation on the persistent `#sandbox-grid` container, so it doesn't need per-instance cleanup (the `unsubscribe` already handles state subscription cleanup).

---

### 🟡 BUG 5 (Low): No `:active` state on kill button

**File:** `static/css/components.css`

The `.btn-kill` had no `:active` state, meaning no visual feedback when the button is pressed on mobile. Added:

```css
.btn-kill:active { background: #FEE2E2; transform: scale(0.97); }
```

---

## Why Playwright Desktop Tests Passed But Mobile Failed

| Factor | Desktop (Playwright headless Chromium) | Mobile (iPhone Safari) |
|--------|---------------------------------------|----------------------|
| Event model | Mouse events directly | Touch→click synthesis |
| Tap delay | None | 300ms (without `touch-action: manipulation`) |
| DOM mutation during event | Handled gracefully | Can interrupt click chain |
| Touch target size | Mouse always hits | Small targets miss on touch |
| Visual feedback | `:hover` works | No hover on touch; needs `touch-action` |
| Button styling | Visible by default | Bare buttons invisible without `.modal-btn` CSS |

The combination of Bug 2 (re-render on kill click) + Bug 3 (missing mobile CSS) explains why nothing appeared to happen on mobile: the click event was either dropped during the DOM mutation race or the modal was visually broken.

---

## Files Changed

### `static/js/components/controls.js`
- Pass `sbName` as confirmation token to `killSandbox(sbName, sbName)`

### `static/js/components/sandbox-card.js`
- Skip kill clicks in card click handler: `if (e.target.closest('.kill-btn-container, [data-action="kill"]')) return;`
- Remove broken `removeEventListener('click', null)` from destroy cleanup

### `static/css/components.css`
- `.btn-kill`: Increased min-height to 44px, added `touch-action: manipulation`, `-webkit-tap-highlight-color: transparent`, `user-select: none`, `:active` state
- `.modal-overlay`: Added `touch-action: none`, `overscroll-behavior: contain`
- `.modal-close-btn`: Added `touch-action: manipulation`
- `.modal-footer`: Added `flex-wrap: wrap`
- **New**: `.modal-btn`, `.modal-btn-cancel`, `.modal-btn-confirm`, `.modal-btn-confirm.danger` — full styling for modal action buttons

---

## Verification

### Playwright Test (mobile emulation)
All tests pass with mobile emulation (iPhone 14 Pro, touch events enabled):

```
✅ Kill button rendered
   touch-action: manipulation ✅
   min-height: 44px ✅
✅ Modal appeared after kill button tap
   Modal title: "Kill Sandbox" ✅
✅ Confirm button visible (85x44, touch-friendly)
✅ Success toast appeared
✅ Modal closed after confirm
✅ Escape closes modal with cancel toast
```

Run with:
```bash
NODE_PATH=/home/max/.openclaw/workspace/node_modules node test-kill-fix.spec.js
```

---

## Recommendations

1. **Test on a real iPhone** — the Playwright touch emulation is close but not identical to real iOS Safari. The fix should work, but real-device testing is always the gold standard.
2. **Add CSP headers** — The dashboard currently allows inline styles; adding a Content Security Policy would improve security.
3. **Consider `FastClick` or similar** — If further mobile issues arise, a lightweight tap library could normalize touch→click across all browsers, though modern browsers make this largely unnecessary with `touch-action: manipulation`.
