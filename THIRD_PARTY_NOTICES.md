# Third-Party Notices

The agent platform uses original adapters, audited references, and the safety-adapted instruction files listed below. Source names and URLs are retained for attribution and provenance; no upstream hooks or installers are vendored or activated.

| Source | Pinned commit | License | Integration |
| --- | --- | --- | --- |
| [addyosmani/agent-skills](https://github.com/addyosmani/agent-skills) | `7829ffd90d973b6325f5f12f1b1226dcace74443` | `MIT` | `ADAPTED` 24 project skills and 8 commands/workflows; hooks excluded |
| [greensock/GSAP](https://github.com/greensock/GSAP) | `13e2b790546426a1a2e0e9b409f3f8dc6d6611f2` | `LicenseRef-GSAP-Standard-No-Charge` | exact project dependency `gsap@3.15.0` |
| [Aider-AI/aider](https://github.com/Aider-AI/aider) | `5dc9490bb35f9729ef2c95d00a19ccd30c26339c` | `Apache-2.0` | `REJECTED` reference/original adapter |
| [tirth8205/code-review-graph](https://github.com/tirth8205/code-review-graph) | `90d760aa23fac0353637d2e8f2a431aa08f14366` | `MIT` | `REJECTED` reference/original adapter |
| [upstash/context7](https://github.com/upstash/context7) | `b250c2515694eee4b6df4db82fa056df9ed3e306` | `MIT` | `REJECTED` reference/original adapter |
| [Graphify-Labs/graphify](https://github.com/Graphify-Labs/graphify) | `00efd6e7969837ae4a9f11d8d504dcd3b20b09df` | `Apache-2.0 OR MIT` | `EXTERNAL_TOOL_ONLY` exact CLI v0.9.32 |
| [greensock/gsap-skills](https://github.com/greensock/gsap-skills) | `aed9cfd3277740755f6bfc1155c7aa645403b760` | `MIT` | `ADAPTED` reference/original adapter |
| [Anasss/qa-orchestra](https://github.com/Anasss/qa-orchestra) | `5df9ad4012f78b9ff6ba551c36a3a0f583d26bf3` | `MIT` | `ADAPTED` reference/original adapter |
| [yamadashy/repomix](https://github.com/yamadashy/repomix) | `b921db74351fd9185897a641a8f39c0b82de7fcb` | `MIT` | `EXTERNAL_TOOL_ONLY` reference/original adapter |
| [oraios/serena](https://github.com/oraios/serena) | `9a9d07e83d8c1cba3458992707f440c624446c6d` | `MIT` | `REJECTED` reference/original adapter |
| [MartinForReal/storymap-skill](https://github.com/MartinForReal/storymap-skill) | `35cf8a10fc240f809eb7c248c8f3a254e856c65f` | `MIT` | `ADAPTED` reference/original adapter |
| [wshobson/agents](https://github.com/wshobson/agents) | `c4b82b0ad771190355eb8e204b1329732a18449a` | `MIT` | `ADAPTED` reference/original adapter |
| [Semgrep](https://pypi.org/project/semgrep/1.171.0/) | `1.171.0` | `LGPL-2.1-or-later` | project-local security scanner |
| [pip-audit](https://pypi.org/project/pip-audit/2.10.1/) | `2.10.1` | `Apache-2.0` | project-local security scanner |
| [Gitleaks](https://github.com/gitleaks/gitleaks/releases/tag/v8.30.1) | `8.30.1` | `MIT` | project-local security scanner |
| [Trivy](https://github.com/aquasecurity/trivy/releases/tag/v0.72.0) | `0.72.0` | `Apache-2.0` | project-local security scanner |

License files and package declarations were inspected at the pinned commits. The Addy Osmani MIT text is retained under `agent-platform/licenses/`; GSAP remains governed by the license URL declared in its package metadata. Future copied implementation must retain all applicable notices and obligations.
