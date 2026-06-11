# Ideas by me — Army Tree Viewport

> A live terminal dashboard that shows HERO's work as a **command hierarchy tree** — branches of work flowing from root to leaves, errors sprouting retry branches, all converging back to deliver results.

---

## Core Concept

Instead of a flat table, the viewport becomes a **live tree** rooted at the user request, branching down through army roles, with every soldier visible as a leaf node. Work flows down the tree, errors fork into retry branches, and the whole thing updates every 2 seconds.

```
                              ┌──────────┐
                              │  USER    │
                              │  Request │
                              └────┬─────┘
                                   │
                              ┌────▼─────┐
                              │ COMM  ●  │  "Fix theme switcher"
                              │ Active   │
                              └────┬─────┘
                                   │
                              ┌────▼─────┐
                              │ LEAD  ✓  │  Breakdown into 4 subtasks
                              │ Done     │
                              └────┬─────┘
                                   │
                          ┌────────┼────────────────┐
                          │        │                 │
                     ┌────▼──┐ ┌──▼────┐      ┌─────▼───┐
                     │ARCH ✓ │ │ARCH ✓ │      │ ARCH ✓  │
                     │Done   │ │Done   │      │ Done    │
                     └───┬───┘ └───┬───┘      └──┬───┬───┘
                         │         │              │   │
              ┌──────────┤    ┌────┤      ┌───────┘   │
              │          │    │    │      │           │
         ┌────▼───┐ ┌───▼──┐ │ ┌──▼──┐┌─▼────┐ ┌────▼───┐
         │SOLDER1 │ │SOLDER│ │ │SOLDR││SOLDR │ │ SOLDER  │
         │● Active│ │● Idle│ │ │●Run ││●Run  │ │ ◌Queued │
         │step-3.5│ │deepsk│ │ │st3.5││st3.5 │ │deepseek │
         └───┬────┘ └──────┘ │ └─────┘└──────┘ └────────┘
             │               │
        ✗──Timeout───┐      │
                     │      │
                ┌────▼──┐   │
                │RETRY 1│   │
                │● fixing│  │
                │Kimi K26│  │
                └────────┘  │
                            │
               ┌────────────┘
               ▼
          ┌──────────┐
          │ VERIFY   │
          │ ◌ Queued │
          └────┬─────┘
               │
          ┌────▼─────┐
          │ARCHIVIST │
          │ ◌ Queued │
          └────┬─────┘
               │
          ┌────▼─────┐
          │  COMM    │
          │ ● Report │
          │ Pending  │
          └──────────┘
```

---

## Node Anatomy

Each node is a fixed-width box:

```
┌──────────┐
│ ROLE     │    ← Role name (COMM, LEAD, ARCH, SOLDIER, VERIFY, ARCHIVIST)
│ ● Active │    ← Status icon + text
│ step-3.5 │    ← Model assigned (soldiers only)
└──────────┘
```

**Status icons + colors:**

| Icon | Status | Color | Meaning |
|------|--------|-------|---------|
| ● | Active | Cyan | Currently processing |
| ✓ | Done | Green | Completed successfully |
| ◌ | Queued | Grey/Yellow | Waiting for upstream |
| ✗ | Failed | Red | Errored out |
| 🔄 | Retry | Yellow | Fallback model retrying |

**Node width = fixed 10 chars** so the tree aligns perfectly regardless of content.

---

## How Data Flows

### Downstream (request → execution)

```
USER ──► COMM ──► LEAD ──► ARCH ──► SOLDIERS
                                      │
                            ┌─────────┼─────────┐
                            │         │         │
                        soldier_1  soldier_2  soldier_3
```

The tree grows deeper as work progresses:
- **COMM** receives user request → passes to **LEAD**
- **LEAD** breaks task into subtasks → multiple **ARCH** nodes (one per subtask)
- Each **ARCH** produces a spec → children become **SOLDIER** nodes executing the spec
- Multiple **SOLDIER** siblings = parallel execution

### Upstream (results → delivery)

```
SOLDIERS ──► VERIFY ──► ARCHIVIST ──► COMM ──► USER
```

Results converge back up:
- **VERIFY** checks all soldier outputs
- **ARCHIVIST** documents what was done
- **COMM** formats and delivers to **USER**

---

## Error Forking

When a soldier fails, the tree grows a **retry branch** right at the point of failure:

```
         │
    ┌────▼───┐    
    │SOLDER  │ ✗ Timeout
    └───┬────┘    
        │
   ┌────▼────┐    
   │ RETRY 1 │ ● Fixing (Kimi K2.6)
   └─────────┘    
        │
   ┌────▼────┐    
   │ RETRY 2 │ ◌ Queued (deepseek)
   └─────────┘    
```

If all retries fail, the error propagates up to the parent (ARCH → LEAD → COMM → USER). Each level gets a red ✗ badge with an error count.

---

## Multiple Pipelines

When multiple sandboxes have active pipelines, they appear as **sibling root trees**, each rooted at its own COMM node:

```
sook_pro ── fix theme switcher
═══════════════════════════════
USER ──► COMM ──► LEAD ──► ...

Freya ── add search bar
═══════════════════════
USER ──► COMM ──► LEAD ──► ...

qlearner ── optimize solver
════════════════════════════
USER ──► COMM ──► LEAD ──► ...
```

---

## Keyboard Navigation

| Key | Action |
|-----|--------|
| `↑↓` | Move selection up/down the tree |
| `←→` | Collapse/expand subtree at current node |
| `Enter` | Select node → show detail panel (task, model, time, errors) |
| `/` | Search — filter nodes by name/task |
| `Tab` | Jump between pipelines |
| `e` | Toggle: show only errored nodes |
| `r` | Force refresh |
| `q` | Quit |

---

## Layout Modes

### Full tree (wide terminal)
The full tree occupies the center. Multiple pipelines side by side if the terminal is wide enough.

### Compact tree (narrow terminal)
Single pipeline at a time. `←→` arrows or `Tab` to switch between active pipelines. Collapsed nodes show only parent + child count:

```
USER ──► COMM ──► LEAD ──► [+]3 children
```

### Minimal tree (idle state)
When no pipelines are active, show a collapsed sandbox summary with idle indicators:

```
sook_pro    ○ idle   Freya    ○ idle   qlearner   90% ██████████
```

---

## Why Tree Over Flow

| Aspect | Flow (horizontal) | Tree (vertical) |
|--------|-------------------|-----------------|
| Parallelism | Stacked horizontally, limited width | Unlimited siblings, scroll vertically |
| Error forking | Side panels or zig-zag arrows | Natural child node off failed parent |
| Multiple pipelines | Stack vertically | Side by side or tabbed |
| Depth | Shallow (6 stages max) | Deep — shows nested subtask breakdown |
| Intuition | Assembly line | Command hierarchy / org chart |
| Scrolling | May need horizontal scroll | Natural vertical scroll (terminal strength) |

The tree maps naturally to how HERO actually works: one Lead sends work to many Soldiers, failures spawn retries, results converge back up. It's a living org chart of the work itself.

---

*Idea by Mashal — tree viewport for HERO army operations*

---

# Android DeX Alternative — Desktop OS Phone App

> A Samsung DeX-like desktop experience from **any** Android phone. Plug into HDMI (wired) or cast wirelessly (WebRTC/Miracast) to a monitor/TV. Phone becomes a full PC with taskbar, windows, file manager, browser, terminal.

---

## The Goal

One Android APK that turns your phone into a desktop computer:
- **Wired**: USB-C to HDMI cable (if phone has DP Alt Mode) OR DisplayLink USB adapter (~$30, works on literally any Android 5+ phone)
- **Wireless**: Miracast (if OEM supports) or WebRTC stream to Android TV / Chromecast / web browser / Pi dongle
- **Same desktop UI** on both: taskbar, start menu, resizable windows, file manager, browser, terminal, settings
- **Phone screen** becomes touchpad/remote while monitor shows the desktop
- **Bluetooth keyboard + mouse** for input

---

## Architecture

```
Phone App ──── VirtualDisplay (1920×1080) ──── Desktop UI (Compose)
    │                                                  │
    ├── Wired: DisplayLink adapter or USB-C HDMI       │
    └── Wireless: WebRTC (H.265) → TV/receiver         │
                                                       │
Phone screen shows touchpad ────────── Monitor shows desktop
```

### Key Android APIs (all public, no root/ADB):

| API | Purpose | Min API |
|---|---|---|
| `MediaProjection` | Screen capture permission | 21 (5.0) |
| `VirtualDisplay` | Secondary display for desktop | 17 (4.2) |
| `MediaCodec` | HW video encoding (H.264/H.265) | 16 (4.1) |
| `Presentation` | Separate UI on external display | 17 (4.2) |
| `DisplayManager` | Detect display connections | 17 (4.2) |
| `AccessibilityService` | Input injection | 18 (4.3) |

---

## How DisplayLink Works (USB 2.0 → HDMI)

DisplayLink compresses the screen before sending over USB:

```
Phone screen → MediaProjection → H.264/H.265 hardware encode (10-20 Mbps)
    → USB 2.0 (480 Mbps, 20x headroom) → DisplayLink adapter decodes → HDMI
```

This is why it works on **any** phone — even USB 2.0 budget phones. The phone's hardware encoder handles compression.

---

## Transport Comparison

| Method | Devices | Latency | Extra Hardware |
|---|---|---|---|
| USB-C to HDMI (DP Alt Mode) | Mid-range+ phones | <10ms | Cable only |
| DisplayLink adapter | **Any Android 5+** | 30-50ms | $30 adapter |
| Android TV APK (WebRTC) | **200M+ TVs** | 30-80ms | Nothing (TV) |
| Web PWA (WebRTC) | Any browser | 50-100ms | Nothing |
| Miracast | OEM-dependent | 50-150ms | Wireless HDMI adapter |
| Wi-Fi Direct P2P | Any phone | 40-80ms | Pi/FireStick receiver |

---

## Build Phases

### Phase 0 — Foundation (1-2 weeks)
- VirtualDisplay creation + MediaProjection consent
- Compose desktop UI rendering on secondary display
- Proof of concept: colored shape streams wirelessly to browser

### Phase 1 — Wired Desktop MVP (2 weeks)
- DesktopWindowManager: taskbar, start menu, window manager
- Built-in apps: File Manager, Terminal, Settings, Browser (WebView)
- DisplayLink detection + wired output
- Bluetooth keyboard + mouse

### Phase 2 — Wireless (2 weeks)
- WebRTC streaming (H.265 hardware encode)
- Android TV receiver APK
- Web receiver (PWA)
- Network discovery + QR code pairing

### Phase 3 — Native Android Apps (2 weeks)
- Freeform window launcher for third-party Android apps
- Keyboard shortcuts (Alt+Tab, Ctrl+C, etc.)
- Window snapping

### Phase 4 — Polish (2 weeks)
- Adaptive bitrate for wireless
- Wi-Fi Direct P2P fallback
- Audio streaming
- Clipboard sync
- Multi-display

**Total:** ~10-12 weeks for v1.0

---

## Prior Art & References

| Project | Relevance |
|---|---|
| **[scrcpy](https://github.com/Genymobile/scrcpy)** | `--new-display` creates VirtualDisplay + streams. Closest existing project. |
| **[Taskbar](https://github.com/farmerbb/Taskbar)** | Open-source Android desktop launcher with freeform. |
| **[DisplayLink for Android](https://www.synaptics.com/products/displaylink-graphics/downloads/android)** | Screen mirroring to HDMI via USB adapter. Works Android 5+. |
| **[Samsung DeX](https://www.samsung.com/us/explore/dex/)** | The gold standard. Wired only (DP Alt Mode). Requires Samsung flagship. |
| **[Motorola Ready For](https://www.motorola.com/us/smart-connect)** | Motorola's DeX alternative. Wired only. |
| **Google Connected Displays (Android 16)** | Native desktop mode in AOSP. Wired DP Alt Mode only. |

---

## Key Technical Notes

### Limitation: DisplayLink mirrors only
DisplayLink Presenter mirrors the **primary** display. For separate screens (phone=touchpad, monitor=desktop):
- **With DP Alt Mode**: Use `Presentation` API or `setLaunchDisplayId()` — works great
- **With DisplayLink**: More complex — need to pipe VirtualDisplay output to DisplayLink's capture surface
- **MVP**: Desktop shows same UI as phone but optimized for big screen (desktop launcher mode)

### Limitation: WebRTC latency
- Target: <60ms for productivity (excellent), <100ms acceptable
- H.265 hardware encode saves 30-50% bandwidth over H.264 at same quality
- No frame buffering on receiver
- Adaptive bitrate 5-20 Mbps based on WiFi quality

### Limitation: Input injection
- For **built-in desktop apps**: Works perfectly — our Compose UI handles all input natively
- For **third-party Android apps**: Needs freeform support + AccessibilityService for injection
- **Easiest UX**: User connects Bluetooth keyboard/mouse directly to phone (works on any phone)

---

*Research gathered 2026-06-08 by Claw. Architectures researched by DeepSeek V4 Flash. Covers wired (DisplayLink + USB-C HDMI) and wireless (WebRTC + Miracast) paths.*
