# Third-Party Notices

The `seo` plugin's methodology, checklists, and command surface were adapted
from **claude-seo** by AgriciDaniel (https://github.com/AgriciDaniel/claude-seo),
licensed under the MIT License:

```
MIT License

Copyright (c) 2026 agricidaniel

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.
```

## Additional attribution

Two parts of the source repository carry attribution beyond the top-level
MIT grant above:

- **`seo-content-brief`** in the source repository credits a separate
  contributor, **puneetindersingh**, alongside AgriciDaniel. The Solo Suite
  `seo-content-brief` skill is adapted from that contribution.
- **`seo-flow`** implements the **FLOW framework** (Find → Leverage →
  Optimize → Win), which AgriciDaniel publishes separately at
  `github.com/AgriciDaniel/flow` under **CC BY 4.0** — a different license
  from claude-seo's MIT grant. The Solo Suite `seo-flow` skill's methodology
  section is adapted from that CC BY 4.0-licensed framework; attribution:
  FLOW framework by AgriciDaniel (github.com/AgriciDaniel/flow), CC BY 4.0.

## What was adapted vs. what was not

This plugin ports claude-seo's **analysis methodology and knowledge**
(category checklists, scoring weights, quality gates, schema/CWV/E-E-A-T
reference thresholds) rewritten into Solo Suite's own skill format, report
structure, and `.solo/` memory integration — prose and file structure are
original to Solo Suite, not verbatim copies.

**Not ported**: claude-seo's isolated Python/Chromium runtime and launcher
(`bin/claude-seo`), its Node.js schema-validation hook, its PDF report
generator, and its live API client implementations for Google Search
Console/PageSpeed/CrUX/GA4, Ahrefs, DataForSEO, Moz, Bing Webmaster, SE
Ranking, Firecrawl, and Profound. Those integration points are represented
here as **Connector mode** (used only when the corresponding MCP tool or
credential is already present in the environment) with an explicit **Manual
mode** fallback — the same pattern the `stack` plugin already uses for
Cloudflare/Vercel/Supabase/payments — rather than a bundled installer for a
separate runtime, to stay consistent with the suite's stdlib-only,
manual-first design.
