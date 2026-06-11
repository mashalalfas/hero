# HERO Teach Skill — Build Brief

> **Companion to:** `TEACH_SKILL_DESIGN.md`
> **Audience:** the developer (or agent) implementing the site
> **Goal:** a step-by-step recipe that, followed top to bottom, produces a deployed `hero-teach` site on Cloudflare Pages.
> **Estimated effort:** 4–6 focused working days for one developer.

---

## 0. Pre-flight checklist

Before you write a single file, confirm:

- [ ] Node.js ≥ 20 installed (`node -v`)
- [ ] pnpm installed (`npm i -g pnpm && pnpm -v`) — or substitute npm/yarn in every command below
- [ ] Cloudflare account (free tier is enough) — https://dash.cloudflare.com/sign-up
- [ ] Wrangler CLI (`pnpm add -g wrangler` and `wrangler login`)
- [ ] GitHub repo for the site (e.g. `max/hero-teach`)
- [ ] HERO source checked out at `/home/max/Development/HERO/` (already true)
- [ ] Read `TEACH_SKILL_DESIGN.md` end to end

If any item is missing, fix it before continuing. The build assumes all of these are true.

---

## 1. Scaffold the project

```bash
mkdir -p ~/Development/hero-teach
cd ~/Development/hero-teach

pnpm create vite@latest . -- --template react-ts
pnpm install

# Core dependencies
pnpm add react-router-dom reactflow lucide-react fuse.js \
         @mdx-js/rollup @mdx-js/react remark-gfm rehype-slug \
         gray-matter reading-time shiki
pnpm add -D tailwindcss@3 postcss autoprefixer \
            @types/node tsx

pnpm dlx tailwindcss init -p
```

### `package.json` scripts

Replace the `scripts` block with:

```json
{
  "scripts": {
    "dev": "vite",
    "build": "tsc --noEmit && vite build",
    "preview": "vite preview --port 4173",
    "extract": "tsx scripts/extract-commands.mjs && tsx scripts/extract-roles.mjs",
    "deploy": "wrangler pages deploy dist --project-name hero-teach --branch main",
    "deploy:preview": "wrangler pages deploy dist --project-name hero-teach"
  }
}
```

### `tsconfig.json` (replace the generated one)

```json
{
  "compilerOptions": {
    "target": "ES2022",
    "lib": ["ES2022", "DOM", "DOM.Iterable"],
    "module": "ESNext",
    "moduleResolution": "Bundler",
    "jsx": "react-jsx",
    "strict": true,
    "noUncheckedIndexedAccess": true,
    "skipLibCheck": true,
    "esModuleInterop": true,
    "resolveJsonModule": true,
    "isolatedModules": true,
    "allowSyntheticDefaultImports": true,
    "forceConsistentCasingInFileNames": true,
    "useDefineForClassFields": true,
    "types": ["vite/client", "node"]
  },
  "include": ["src", "scripts", "vite.config.ts"]
}
```

### `vite.config.ts`

```ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import mdx from "@mdx-js/rollup";
import remarkGfm from "remark-gfm";
import rehypeSlug from "rehype-slug";

export default defineConfig({
  plugins: [
    { enforce: "pre", ...mdx({ remarkPlugins: [remarkGfm], rehypePlugins: [rehypeSlug] }) },
    react(),
  ],
  resolve: {
    alias: { "~": "/src" },
  },
  build: {
    target: "es2020",
    sourcemap: true,
    rollupOptions: {
      output: {
        manualChunks: {
          reactflow: ["reactflow"],
          mdx: ["@mdx-js/react"],
        },
      },
    },
  },
});
```

### `tailwind.config.ts`

```ts
import type { Config } from "tailwindcss";

export default {
  content: ["./index.html", "./src/**/*.{ts,tsx,mdx}"],
  darkMode: "class",
  theme: {
    extend: {
      colors: {
        // See TEACH_SKILL_DESIGN.md §6.2 — paste the full token set
        base: "#0b1020",
        "elev-1": "#11172a",
        "elev-2": "#161d36",
        "border-subtle": "#1f2a44",
        "border-active": "#22d3ee",
        accent: "#22d3ee",
        pass: "#34d399",
        warn: "#fbbf24",
        fail: "#f43f5e",
        quarantine: "#9f1239",
      },
      fontFamily: {
        sans: ["Inter", "system-ui", "sans-serif"],
        mono: ["JetBrains Mono", "ui-monospace", "monospace"],
      },
      maxWidth: { container: "1200px" },
    },
  },
  plugins: [],
} satisfies Config;
```

### `src/styles/globals.css`

```css
@tailwind base;
@tailwind components;
@tailwind utilities;

@layer base {
  :root {
    color-scheme: dark;
  }
  html {
    @apply bg-base text-slate-100 antialiased;
    font-family: "Inter", system-ui, sans-serif;
  }
  body {
    @apply min-h-screen;
  }
  code, pre, kbd, samp {
    font-family: "JetBrains Mono", ui-monospace, monospace;
  }
  ::selection { @apply bg-cyan-400/30 text-white; }
  a { @apply text-cyan-300 hover:text-cyan-200 transition-colors; }

  @media (prefers-reduced-motion: reduce) {
    *, *::before, *::after {
      animation-duration: 0.001ms !important;
      transition-duration: 0.001ms !important;
    }
  }
}

@layer components {
  .container-prose { @apply mx-auto w-full max-w-container px-6; }
  .card { @apply rounded-md border border-border-subtle bg-elev-1; }
  .pill { @apply inline-flex items-center gap-2 rounded-md border border-border-subtle bg-elev-1 px-3 py-1.5 font-mono text-sm; }
}
```

---

## 2. Folder skeleton

Run this once to create the structure:

```bash
cd ~/Development/hero-teach
mkdir -p src/components src/pages src/data src/lib src/data/examples \
         public public/img scripts
```

Final layout (matches `TEACH_SKILL_DESIGN.md` §5.4):

```
hero-teach/
├── public/
│   ├── favicon.svg
│   └── img/                    # terminal screenshots
├── scripts/
│   ├── extract-commands.mjs
│   └── extract-roles.mjs
├── src/
│   ├── App.tsx
│   ├── main.tsx
│   ├── components/             # 10 components, see §3
│   ├── pages/                  # 14 pages, see §4
│   ├── data/
│   │   ├── commands.json       # generated
│   │   ├── roles.json          # generated
│   │   ├── pipeline.json       # hand-authored
│   │   └── examples/*.mdx
│   ├── lib/
│   │   ├── shiki.ts
│   │   └── mdx.tsx
│   ├── styles/globals.css
│   └── types.ts
├── index.html
├── package.json
├── tailwind.config.ts
├── tsconfig.json
└── vite.config.ts
```

---

## 3. Component architecture

The site has 10 components. Build them in this order — each one is small and self-contained.

### 3.1 `src/lib/mdx.tsx` — MDX components map

```tsx
import { MDXProvider } from "@mdx-js/react";
import type { MDXComponents } from "mdx/types";
import { CodeBlock } from "~/components/CodeBlock";
import { Callout } from "~/components/Callout";
import { ScoreBadge } from "~/components/ScoreBadge";

export const mdxComponents: MDXComponents = {
  pre: (props) => <CodeBlock {...(props as any)} />,
  Callout,
  Score: ScoreBadge,
};

export function MDXLayout({ children }: { children: React.ReactNode }) {
  return <MDXProvider components={mdxComponents}>{children}</MDXProvider>;
}
```

### 3.2 `src/lib/shiki.ts` — code highlighter

```ts
import { createHighlighter, type Highlighter } from "shiki";

const LANGS = ["bash", "python", "yaml", "json", "toon", "diff", "typescript"];
const THEMES = { dark: "github-dark", light: "github-light" };

let hl: Promise<Highlighter> | null = null;
export function getHighlighter() {
  if (!hl) hl = createHighlighter({ themes: [...Object.values(THEMES)], langs: LANGS });
  return hl;
}
```

### 3.3 `src/components/CodeBlock.tsx`

```tsx
import { useEffect, useState } from "react";
import { getHighlighter } from "~/lib/shiki";

type Props = { children: string; lang?: string; title?: string };

export function CodeBlock({ children, lang = "bash", title }: Props) {
  const [html, setHtml] = useState<string>("");
  useEffect(() => {
    let cancelled = false;
    getHighlighter().then((h) => {
      if (cancelled) return;
      setHtml(h.codeToHtml(children, { lang, theme: "github-dark" }));
    });
    return () => { cancelled = true; };
  }, [children, lang]);

  return (
    <figure className="card my-4 overflow-hidden">
      {title && <figcaption className="border-b border-border-subtle px-4 py-2 font-mono text-xs text-slate-400">{title}</figcaption>}
      <div className="overflow-x-auto p-4 text-sm" dangerouslySetInnerHTML={{ __html: html || `<pre><code>${children}</code></pre>` }} />
    </figure>
  );
}
```

### 3.4 `src/components/ScoreBadge.tsx`

```tsx
export function ScoreBadge({ value, size = "sm" }: { value: number; size?: "sm" | "md" }) {
  const tone = value >= 70 ? "pass" : value >= 50 ? "warn" : "fail";
  const cls = size === "md" ? "text-base px-2.5 py-1" : "text-xs px-1.5 py-0.5";
  return (
    <span className={`rounded font-mono font-semibold tabular-nums ${cls} bg-${tone}/10 text-${tone} border border-${tone}/30`}>
      {value}
    </span>
  );
}
```

(Note: Tailwind's JIT can't resolve dynamic class names; for production, expand the `${tone}` switch into explicit class strings.)

### 3.5 `src/components/Callout.tsx`

```tsx
import type { ReactNode } from "react";
import { Info, AlertTriangle, CheckCircle2, XCircle } from "lucide-react";

const STYLES = {
  info:    { icon: Info,           border: "border-cyan-500/40",     bg: "bg-cyan-500/5",     icon_cls: "text-cyan-400" },
  success: { icon: CheckCircle2,   border: "border-emerald-500/40",  bg: "bg-emerald-500/5",  icon_cls: "text-emerald-400" },
  warn:    { icon: AlertTriangle,  border: "border-amber-500/40",    bg: "bg-amber-500/5",    icon_cls: "text-amber-400" },
  danger:  { icon: XCircle,        border: "border-rose-500/40",     bg: "bg-rose-500/5",     icon_cls: "text-rose-400" },
};

export function Callout({ kind = "info", title, children }: { kind?: keyof typeof STYLES; title?: string; children: ReactNode }) {
  const s = STYLES[kind];
  const Icon = s.icon;
  return (
    <aside className={`my-4 flex gap-3 rounded-md border ${s.border} ${s.bg} p-4`}>
      <Icon className={`mt-0.5 h-5 w-5 shrink-0 ${s.icon_cls}`} />
      <div className="text-sm leading-6 text-slate-200">
        {title && <p className="mb-1 font-semibold">{title}</p>}
        <div>{children}</div>
      </div>
    </aside>
  );
}
```

### 3.6 `src/components/ThemeToggle.tsx`

```tsx
import { Moon, Sun } from "lucide-react";
import { useEffect, useState } from "react";

const KEY = "hero-teach-theme";
type Theme = "dark" | "light";

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>("dark");

  useEffect(() => {
    const stored = (localStorage.getItem(KEY) as Theme | null);
    const initial = stored ?? (window.matchMedia("(prefers-color-scheme: light)").matches ? "light" : "dark");
    setTheme(initial);
    document.documentElement.classList.toggle("light", initial === "light");
  }, []);

  const toggle = () => {
    const next: Theme = theme === "dark" ? "light" : "dark";
    setTheme(next);
    localStorage.setItem(KEY, next);
    document.documentElement.classList.toggle("light", next === "light");
  };

  return (
    <button onClick={toggle} aria-label="Toggle theme" className="rounded p-2 text-slate-300 hover:bg-elev-2">
      {theme === "dark" ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </button>
  );
}
```

### 3.7 `src/components/Nav.tsx` and `Footer.tsx`

Standard responsive nav with these links: `architecture · pipeline · exchange · commands · roles · getting started`. `Footer.tsx` mirrors them plus a "GitHub ↗" link and a copyright line.

### 3.8 `src/components/PipelineMap.tsx` (the centerpiece)

The `PipelineMap` component:

- Reads `src/data/pipeline.json` and renders nodes + edges via React Flow.
- Uses a custom node type `NodePill` for every node.
- Listens to `onNodeClick` and bubbles up to set a `selectedNode` state.
- The `NodePanel` slides in from the right when a node is selected.
- The `Replay` button resets all nodes to `idle` and animates them through `running` → `passed` in pipeline order over 12s.

Skeleton:

```tsx
import { useCallback, useEffect, useMemo, useState } from "react";
import ReactFlow, { Background, Controls, MiniMap, type Node, type Edge } from "reactflow";
import "reactflow/dist/style.css";
import pipeline from "~/data/pipeline.json";
import { NodePill } from "./NodePill";
import { NodePanel } from "./NodePanel";

const nodeTypes = { pill: NodePill };

export function PipelineMap({ scope = "full", height = 520 }: { scope?: "full" | "execution" | "summary"; height?: number }) {
  const [selectedId, setSelectedId] = useState<string | null>(null);

  const { nodes, edges } = useMemo(() => buildGraph(pipeline, scope), [scope]);

  return (
    <div className="relative grid grid-cols-1 gap-4 lg:grid-cols-[1fr_320px]">
      <div className="card overflow-hidden" style={{ height }}>
        <ReactFlow
          nodes={nodes}
          edges={edges.map((e) => ({ ...e, animated: true }))}
          nodeTypes={nodeTypes}
          onNodeClick={(_, n) => setSelectedId(n.id)}
          fitView
          proOptions={{ hideAttribution: true }}
        >
          <Background gap={20} color="#1f2a44" />
          <Controls position="bottom-right" showInteractive={false} />
          <MiniMap nodeColor="#22d3ee" maskColor="rgba(11,16,32,0.7)" pannable zoomable />
        </ReactFlow>
      </div>
      <NodePanel nodeId={selectedId} onClose={() => setSelectedId(null)} />
    </div>
  );
}
```

### 3.9 `src/components/NodePill.tsx`

```tsx
import { Handle, Position } from "reactflow";
import type { PipelineNode } from "~/types";

const TONES = {
  idle:    "border-border-subtle",
  running: "border-cyan-400 shadow-[0_0_20px_rgba(34,211,238,0.35)] animate-pulse",
  passed:  "border-emerald-500",
  warn:    "border-amber-500",
  failed:  "border-rose-500",
};

export function NodePill({ data }: { data: PipelineNode }) {
  const tone = TONES[data.status ?? "idle"];
  return (
    <div className={`rounded-md border ${tone} bg-elev-1 px-4 py-2 font-mono text-sm text-slate-100 min-w-[180px]`}>
      <Handle type="target" position={Position.Left} className="!bg-border-subtle" />
      <div className="flex items-center justify-between gap-3">
        <span className="font-semibold">{data.label}</span>
        {typeof data.score === "number" && <span className="text-xs text-slate-400 tabular-nums">{data.score}</span>}
      </div>
      {data.subtitle && <div className="mt-1 text-[11px] text-slate-500">{data.subtitle}</div>}
      <Handle type="source" position={Position.Right} className="!bg-border-subtle" />
    </div>
  );
}
```

### 3.10 `src/components/NodePanel.tsx`

Side panel that looks up the selected node in `pipeline.json` and shows:
- What it does (markdown body)
- Who runs it (model + role)
- Score formula
- Example output (code block)
- Link to source file on GitHub

Skeleton left to the implementer — it's a simple `AnimatePresence` slide-in from the right.

### 3.11 `src/components/ToonVsJson.tsx`

Two-column widget showing the same payload in TOON and JSON, with a footer note: "TOON uses ~40% fewer tokens."

### 3.12 `src/components/SearchBar.tsx`

Fuse.js-backed fuzzy search over `commands.json`. The Commands page calls `<SearchBar onChange={setQuery} />` and filters the list locally.

---

## 4. Pages

The 14 pages live in `src/pages/`. Each is a React component that:

- Exports a `default` component.
- Sets `<title>` and `<meta>` via `react-helmet-async`.
- Pulls content from MDX files in `src/data/` where appropriate.

### 4.1 `src/pages/Home.tsx`

The landing page described in `TEACH_SKILL_DESIGN.md` §4.1. Above-the-fold: headline, subhead, hero `<PipelineMap scope="summary" />`, two CTAs. Below: 3-column "What it does", TOON vs JSON widget, full-width code block, footer.

### 4.2 `src/pages/Architecture.tsx`

Full interactive `<PipelineMap scope="full" height={640} />`. Below: 3 small diagrams (Sandbox isolation, Exchange Layer, Reliability stack) as static SVGs.

### 4.3 `src/pages/Pipeline.tsx`

Scoped to execution half (`<PipelineMap scope="execution" />`). Below: one MDX section per stage, with What/Who/Score/Example.

### 4.4 `src/pages/ExchangeLayer.tsx`

Five-pattern page. Diagrams as inline SVG (5 small ones, hand-authored).

### 4.5 `src/pages/Commands.tsx`

```tsx
import Fuse from "fuse.js";
import commands from "~/data/commands.json";

export default function Commands() {
  const [q, setQ] = useState("");
  const fuse = useMemo(() => new Fuse(commands, { keys: ["name", "description", "group"] }), []);
  const list = q ? fuse.search(q).map((r) => r.item) : commands;

  return (
    <div className="container-prose py-12">
      <h1>Commands</h1>
      <SearchBar onChange={setQ} placeholder="Search 30+ commands..." />
      {GROUPS.map((g) => (
        <section key={g}>
          <h2>{g}</h2>
          {list.filter((c) => c.group === g).map((c) => <CommandCard key={c.name} {...c} />)}
        </section>
      ))}
    </div>
  );
}
```

### 4.6 `src/pages/CommandPage.tsx`

`/commands/:name` — one command, deep linked from the list.

### 4.7 `src/pages/Roles.tsx` and `RolePage.tsx`

Role grid + per-role page. Pulls from `roles.json`.

### 4.8 `src/pages/GettingStarted.tsx`

Step-by-step. Each step is a `CodeBlock` with title and expected output.

### 4.9 `src/pages/Examples.tsx` and `ExamplePage.tsx`

List of examples, then per-example MDX page.

### 4.10 `src/pages/Learn.tsx` and `About.tsx`

Mostly text. Five-minute tour, thirty-minute deep dive, etc. About: vision, roadmap (copied from `SPEC.md` Phase 4), contributing.

### 4.11 `src/pages/NotFound.tsx`

Simple 404 with a search bar and a link home.

---

## 5. Data

### 5.1 `src/types.ts`

```ts
export type PipelineNode = {
  id: string;
  label: string;
  subtitle?: string;
  group: "plan" | "execute" | "support";
  role?: string;
  models?: string[];
  status?: "idle" | "running" | "passed" | "warn" | "failed";
  score?: number;
  body?: string;            // markdown for the side panel
  example?: { cmd: string; output: string };
  source?: string;          // path inside src/hero/
};

export type PipelineEdge = { id: string; source: string; target: string; label?: string };

export type Command = {
  name: string;             // e.g. "hero go"
  group: string;            // "spawn-deploy" etc.
  description: string;
  synopsis: string;
  example: { cmd: string; output: string };
  source: string;           // path to .py
};

export type Role = {
  name: string;             // e.g. "soldier"
  description: string;
  models: { model: string; provider: string; context_window: number }[];
  context_window: number;
  max_tokens_injected: number;
  triggers?: string[];
  never_runs_for?: string[];
};
```

### 5.2 `src/data/pipeline.json` (hand-authored)

A JSON object with `nodes: PipelineNode[]` and `edges: PipelineEdge[]`. Author all 12+ nodes (Council, Research, Prompt Engineer, Architect, Lead, Soldiers, PRE-COMMIT, BUILD, HARDEN, LEGAL, CI/PR, VERIFY, ARCHIVE) with realistic `body` markdown and `example` blocks. Cross-check against `army.yaml` and `SPEC.md` §"Pipeline" so names, models, and scores match exactly.

### 5.3 `scripts/extract-commands.mjs`

Walks `/home/max/Development/HERO/src/hero/commands/*.py`, finds the `@click.command(...)` decorator, reads the docstring and the click options, and emits `src/data/commands.json`.

Pseudo-algorithm:

1. Glob `commands/*.py`.
2. For each file, read the source as a string.
3. Find the `@click.command(...)` decorator block.
4. Find the `@click.option(...)` blocks after it.
5. Find the function signature and the first paragraph of the docstring (used as the description).
6. Find any `"""Example:"""` block in the docstring for an example.
7. Map to `{ name: "hero " + module_name, group: <derived>, description, synopsis, example, source }`.
8. Write to `src/data/commands.json` with 2-space indent.

Implementation hint: use a regex-based parser (cheaper than depending on Python's AST via a child process). For most HERO commands the shape is consistent. If parsing fails for a particular file, log a warning and continue — don't break the build.

The group mapping is heuristic:

| Module | Group |
|---|---|
| `scan`, `map`, `graph` | discovery |
| `spawn`, `deploy`, `tell`, `orchestrate`, `assemble`, `go` | spawn-deploy |
| `pre_commit`, `build`, `harden`, `legal`, `cipr`, `verify`, `archive`, `score`, `pipeline`, `ready`, `sweep` | pipeline |
| `status`, `budget`, `katana`, `heartbeat`, `dispatch`, `exchange` | state |
| `dlq` | reliability |
| `check`, `viewport`, `watch`, `brainstorm`, `eval` | diagnostics |
| `kill`, `kill_sandbox`, `clean`, `prune` | maintenance |

### 5.4 `scripts/extract-roles.mjs`

Reads `/home/max/.hero/army.yaml`, parses it (with `yaml` or `js-yaml`), and emits `src/data/roles.json` shaped as `Role[]`.

### 5.5 `src/data/examples/*.mdx`

One MDX file per example, e.g.:

```
src/data/examples/
  flutter-theme-fix.mdx
  cross-sandbox-refactor.mdx
  adversarial-review.mdx
  ci-gate-failure.mdx
  council-deliberation.mdx
```

Each one is a full MDX page that the Examples page renders.

---

## 6. Routing & app shell

### 6.1 `src/main.tsx`

```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import { HelmetProvider } from "react-helmet-async";
import { App } from "./App";
import "./styles/globals.css";

ReactDOM.createRoot(document.getElementById("root")!).render(
  <React.StrictMode>
    <HelmetProvider>
      <BrowserRouter>
        <App />
      </BrowserRouter>
    </HelmetProvider>
  </React.StrictMode>
);
```

### 6.2 `src/App.tsx`

```tsx
import { Routes, Route } from "react-router-dom";
import { Nav } from "~/components/Nav";
import { Footer } from "~/components/Footer";
import { ThemeToggle } from "~/components/ThemeToggle";
import Home from "~/pages/Home";
import Architecture from "~/pages/Architecture";
// ... etc

export function App() {
  return (
    <div className="flex min-h-screen flex-col">
      <header className="sticky top-0 z-30 border-b border-border-subtle bg-base/80 backdrop-blur">
        <div className="container-prose flex h-14 items-center justify-between">
          <Nav />
          <ThemeToggle />
        </div>
      </header>
      <main className="flex-1">
        <Routes>
          <Route path="/" element={<Home />} />
          <Route path="/architecture" element={<Architecture />} />
          <Route path="/pipeline" element={<Pipeline />} />
          <Route path="/exchange" element={<ExchangeLayer />} />
          <Route path="/commands" element={<Commands />} />
          <Route path="/commands/:name" element={<CommandPage />} />
          <Route path="/roles" element={<Roles />} />
          <Route path="/roles/:name" element={<RolePage />} />
          <Route path="/getting-started" element={<GettingStarted />} />
          <Route path="/examples" element={<Examples />} />
          <Route path="/examples/:slug" element={<ExamplePage />} />
          <Route path="/learn" element={<Learn />} />
          <Route path="/about" element={<About />} />
          <Route path="*" element={<NotFound />} />
        </Routes>
      </main>
      <Footer />
    </div>
  );
}
```

### 6.3 `index.html`

```html
<!doctype html>
<html lang="en" class="dark">
  <head>
    <meta charset="UTF-8" />
    <link rel="icon" type="image/svg+xml" href="/favicon.svg" />
    <meta name="viewport" content="width=device-width, initial-scale=1.0" />
    <meta name="color-scheme" content="dark light" />
    <meta name="description" content="HERO — a CLI that runs an army of AI agents across your projects." />
    <title>HERO</title>
  </head>
  <body>
    <div id="root"></div>
    <script type="module" src="/src/main.tsx"></script>
  </body>
</html>
```

---

## 7. Local development

```bash
cd ~/Development/hero-teach

# First time only: extract the latest data from HERO source
pnpm extract

# Start dev server with HMR
pnpm dev
# → http://localhost:5173

# Run TypeScript check + production build
pnpm build
# → dist/

# Preview the production build locally
pnpm preview
# → http://localhost:4173
```

### Development tips

- React Flow is heavy — keep its imports tight. Don't import from `reactflow` outside of `PipelineMap`, `NodePill`, `NodePanel`.
- Use `dangerouslySetInnerHTML` only for Shiki output. The codebase never trusts user content; Shiki output is HTML, not source.
- If MDX files are slow to recompile, add a `?` after the MDX import to disable HMR for those modules.
- `prefers-reduced-motion` is already honoured via `globals.css`; verify in DevTools → Rendering → Emulate.

---

## 8. Build & verification

Before deploying, run the full build and verify:

```bash
pnpm build           # must succeed with no TS errors
pnpm preview         # open http://localhost:4173 and click every page
```

Verification checklist:

- [ ] All 14 pages render.
- [ ] Dark theme is the default; toggle persists across reloads.
- [ ] Pipeline map shows on `/`, `/architecture`, `/pipeline`.
- [ ] Clicking a node opens the side panel; the example code block renders.
- [ ] Commands search returns relevant results for "spawn", "budget", "dlq".
- [ ] Mobile (DevTools, iPhone SE): nav collapses to a hamburger; pipeline map scrolls vertically.
- [ ] Lighthouse (DevTools): Performance ≥ 95, Accessibility ≥ 95, Best Practices ≥ 95, SEO ≥ 95.
- [ ] Bundle size: check `dist/assets/*.js` total gzipped < 200 KB (excluding React Flow chunk on routes that don't import it).
- [ ] `prefers-reduced-motion` disables animations.

---

## 9. Deploy to Cloudflare Pages

### 9.1 First-time setup

```bash
# Login to Cloudflare
wrangler login

# Create the Pages project (one-time)
wrangler pages project create hero-teach \
  --production-branch main \
  --compatibility-date 2024-09-23
```

### 9.2 Connect the GitHub repo (recommended)

In the Cloudflare dashboard:

1. Workers & Pages → `hero-teach` → Settings → Builds.
2. Connect to Git → pick the `hero-teach` repo.
3. Build settings:
   - **Build command:** `pnpm extract && pnpm build`
   - **Build output directory:** `dist`
   - **Root directory:** `/` (or whatever the repo uses)
   - **Environment variables:** none needed
4. Save. Cloudflare will trigger a first build.

Every push to a non-`main` branch → preview URL. Every push to `main` → production URL.

### 9.3 Manual deploy (alternative)

```bash
pnpm build
pnpm deploy
```

Output includes a `*.hero-teach.pages.dev` URL.

### 9.4 Custom domain

In Cloudflare dashboard → Pages → `hero-teach` → Custom domains → Set up a custom domain → follow the DNS instructions (CNAME or full setup).

---

## 10. Maintenance & updates

### 10.1 Updating commands

Whenever `src/hero/commands/*.py` changes:

```bash
pnpm extract
pnpm build
git add src/data/commands.json
git commit -m "docs(teach): refresh commands.json"
```

Consider adding this as a CI check:

```yaml
# .github/workflows/teach-freshness.yml
name: teach-freshness
on: [pull_request]
jobs:
  check:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
        with:
          repository: max/HERO
          path: HERO
      - uses: actions/checkout@v4
      - uses: pnpm/action-setup@v4
      - run: pnpm install
      - run: pnpm extract
      - run: git diff --exit-code src/data
```

(Adjust paths to your repo layout.)

### 10.2 Updating examples

The `src/data/examples/*.mdx` files contain real terminal output. Regenerate by:

1. Run the actual `hero` command on a clean sandbox.
2. Copy the output.
3. Replace the code block in the MDX file.
4. Commit.

### 10.3 Adding a new role

When `~/.hero/army.yaml` changes:

```bash
pnpm extract     # regenerates roles.json
```

If a new role appears, also add a new card to `src/pages/Roles.tsx` and a per-role page at `src/pages/RolePage.tsx`.

### 10.4 Adding a new pipeline stage

1. Add the new node to `src/data/pipeline.json` (with edges, body, example).
2. Update the `Pipeline.tsx` page sections.
3. Update the score reference table.

---

## 11. Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `pnpm build` fails with "Module not found" after adding a new dep | Stale lockfile or `node_modules` | `rm -rf node_modules pnpm-lock.yaml && pnpm install` |
| Pipeline map is blank | `pipeline.json` not loaded or wrong shape | Validate with `node -e "console.log(typeof require('./src/data/pipeline.json').nodes)"` |
| Code blocks are unstyled | Shiki highlighter failed to load | Check browser console; ensure `lang` is in the `LANGS` list in `src/lib/shiki.ts` |
| React Flow throws "Can't perform a React state update on an unmounted component" | Strict mode double-render; harmless in dev | If it persists, guard `useEffect` with a `cancelled` flag (already done in `CodeBlock`) |
| Theme toggle flashes light on first load | Initial class set after hydration | Move the class application to a `<script>` in `index.html` that runs before React mounts |
| `wrangler deploy` 401s | Not logged in | `wrangler login` |
| Search returns nothing | `commands.json` is empty | Run `pnpm extract` |

---

## 12. Definition of done

The Teach Skill is "done" when:

- [ ] All sections of `TEACH_SKILL_DESIGN.md` are reflected in the built site.
- [ ] All launch criteria in `TEACH_SKILL_DESIGN.md` §8.1 are green.
- [ ] The site is deployed to a stable URL (Cloudflare Pages or GitHub Pages).
- [ ] A link to the site is added to `README.md` of HERO.
- [ ] The site is mentioned in the next HERO changelog / announcement.

---

**Last updated:** 2026-06-07
