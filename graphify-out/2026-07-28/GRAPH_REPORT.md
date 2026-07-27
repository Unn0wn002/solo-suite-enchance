# Graph Report - .  (2026-07-27)

## Corpus Check
- cluster-only mode — file stats not available

## Summary
- 139 nodes · 137 edges · 17 communities (11 shown, 6 thin omitted)
- Extraction: 100% EXTRACTED · 0% INFERRED · 0% AMBIGUOUS
- Token cost: 0 input · 0 output

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

## God Nodes (most connected - your core abstractions)
1. `compilerOptions` - 16 edges
2. `scripts` - 7 edges
3. `include` - 7 edges
4. `safeRelativeReturnPath()` - 4 edges
5. `getDb()` - 4 edges
6. `lib` - 4 edges
7. `getChatGPTUser()` - 3 edges
8. `requireChatGPTUser()` - 3 edges
9. `chatGPTSignInPath()` - 3 edges
10. `toRouteErrorMessage()` - 3 edges

## Surprising Connections (you probably didn't know these)
- `GET()` --calls--> `getDb()`  [EXTRACTED]
  examples/d1/app/api/notes/route.ts → db/index.ts
- `POST()` --calls--> `getDb()`  [EXTRACTED]
  examples/d1/app/api/notes/route.ts → db/index.ts

## Import Cycles
- None detected.

## Communities (17 total, 6 thin omitted)

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

## Knowledge Gaps
- **73 isolated node(s):** `sidebarWidths`, `articleWidths`, `ChatGPTUser`, `geistSans`, `geistMono` (+68 more)
  These have ≤1 connection - possible missing edges or undocumented components.
- **6 thin communities (<3 nodes) omitted from report** — run `graphify query` to explore isolated nodes.

## Suggested Questions
_Questions this graph is uniquely positioned to answer:_

- **Why does `devDependencies` connect `devDependencies` to `package.json`?**
  _High betweenness centrality (0.135) - this node is a cross-community bridge._
- **Why does `dependencies` connect `dependencies` to `package.json`?**
  _High betweenness centrality (0.054) - this node is a cross-community bridge._
- **Why does `compilerOptions` connect `compilerOptions` to `include`?**
  _High betweenness centrality (0.035) - this node is a cross-community bridge._
- **What connects `sidebarWidths`, `articleWidths`, `ChatGPTUser` to the rest of the system?**
  _73 weakly-connected nodes found - possible documentation gaps or missing edges._
- **Should `devDependencies` be split into smaller, more focused modules?**
  _Cohesion score 0.06060606060606061 - nodes in this community are weakly interconnected._
- **Should `compilerOptions` be split into smaller, more focused modules?**
  _Cohesion score 0.10526315789473684 - nodes in this community are weakly interconnected._
- **Should `package.json` be split into smaller, more focused modules?**
  _Cohesion score 0.14285714285714285 - nodes in this community are weakly interconnected._