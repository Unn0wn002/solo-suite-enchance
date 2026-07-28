# Graph Report - EC Solo Suite  (2026-07-28)

## Corpus Check
- 20 files · ~79,442 words
- Verdict: corpus is large enough that graph structure adds value.

## Summary
- 148 nodes · 145 edges · 18 communities (12 shown, 6 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

## Graph Freshness
- Built from commit: `01bf61a7`
- Run `git rev-parse HEAD` and compare to check if the graph is stale.
- Run `graphify update .` after code changes (no API cost).

## Community Hubs (Navigation)
- devDependencies
- compilerOptions
- package.json
- dependencies
- include
- chatgpt-auth.ts
- route.ts
- worker/index.ts
- layout.tsx
- page.tsx
- SkeletonPreview.tsx
- rendered-html.test.mjs
- eslint.config.mjs
- next.config.ts
- postcss.config.mjs
- vite.config.ts
- vinext-starter

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 16 edges
2. `vinext-starter` - 8 edges
3. `scripts` - 7 edges
4. `include` - 7 edges
5. `safeRelativeReturnPath()` - 4 edges
6. `getDb()` - 4 edges
7. `lib` - 4 edges
8. `getChatGPTUser()` - 3 edges
9. `requireChatGPTUser()` - 3 edges
10. `chatGPTSignInPath()` - 3 edges

## Surprising Connections (you probably didn't know these)
- `GET()` --calls--> `getDb()`  [EXTRACTED]
  examples/d1/app/api/notes/route.ts → db/index.ts
- `POST()` --calls--> `getDb()`  [EXTRACTED]
  examples/d1/app/api/notes/route.ts → db/index.ts

## Import Cycles
- None detected.

## Communities (18 total, 6 thin omitted)

### Community 0 - "devDependencies"
Cohesion: 0.06
Nodes (33): @cloudflare/vite-plugin, drizzle-kit, eslint, eslint-config-next, devDependencies, @cloudflare/vite-plugin, drizzle-kit, eslint (+25 more)

### Community 1 - "compilerOptions"
Cohesion: 0.11
Nodes (19): dom, dom.iterable, esnext, compilerOptions, allowJs, esModuleInterop, incremental, isolatedModules (+11 more)

### Community 2 - "package.json"
Cohesion: 0.14
Nodes (13): engines, node, name, private, scripts, build, db:generate, dev (+5 more)

### Community 3 - "dependencies"
Cohesion: 0.18
Nodes (11): drizzle-orm, next, dependencies, drizzle-orm, next, react, react-dom, react-loading-skeleton (+3 more)

### Community 4 - "include"
Cohesion: 0.20
Nodes (9): **/*.mts, .next/dev/types/**/*.ts, next-env.d.ts, .next/types/**/*.ts, node_modules, **/*.ts, **/*.tsx, exclude (+1 more)

### Community 5 - "chatgpt-auth.ts"
Cohesion: 0.39
Nodes (8): chatGPTSignInPath(), chatGPTSignOutPath(), ChatGPTUser, getChatGPTUser(), isReservedAuthPath(), requireChatGPTUser(), safeDecodeURIComponent(), safeRelativeReturnPath()

### Community 6 - "route.ts"
Cohesion: 0.39
Nodes (5): getDb(), GET(), POST(), toRouteErrorMessage(), notes

### Community 7 - "worker/index.ts"
Cohesion: 0.29
Nodes (3): Env, ExecutionContext, worker

### Community 8 - "layout.tsx"
Cohesion: 0.40
Nodes (3): geistMono, geistSans, metadata

### Community 9 - "page.tsx"
Cohesion: 0.40
Nodes (3): modules, runtimes, workflow

### Community 17 - "vinext-starter"
Cohesion: 0.22
Nodes (8): Included Shape, Learn More, Optional Dispatch-Owned ChatGPT Sign-In, Prerequisites, Quick Start, Useful Commands, vinext-starter, Workspace Auth Headers

## Knowledge Gaps
- **80 isolated node(s):** `sidebarWidths`, `articleWidths`, `ChatGPTUser`, `geistSans`, `geistMono` (+75 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `devDependencies` connect `devDependencies` to `package.json`?**
  _High betweenness centrality (0.119) - this node is a cross-community bridge._
- **Why does `dependencies` connect `dependencies` to `package.json`?**
  _High betweenness centrality (0.048) - this node is a cross-community bridge._
- **Why does `compilerOptions` connect `compilerOptions` to `include`?**
  _High betweenness centrality (0.030) - this node is a cross-community bridge._
- **What connects `sidebarWidths`, `articleWidths`, `ChatGPTUser` to the rest of the system?**
  _80 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `devDependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.06060606060606061 - nodes in this community are weakly interconnected._
- **Should `compilerOptions` be split into smaller, more focused modules?**
  _Cohesion score 0.10526315789473684 - nodes in this community are weakly interconnected._
- **Should `package.json` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._