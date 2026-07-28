---
name: infrastructure-audit
description: Audit the infrastructure a website or app runs on — servers, containers (Docker/Kubernetes), cloud configuration (AWS/GCP/Azure), TLS certificates, DNS, reverse proxy/load balancer setup, firewall and network exposure, secrets management, and resource limits. Use whenever the user wants an infrastructure review, hosting/server audit, cloud config check, "is my server set up right", container hardening, TLS/DNS review, or is preparing infrastructure for production traffic. Complements security-review (app layer) and observability (monitoring).
---

# Infrastructure Audit

The infrastructure layer is where a well-built app still gets breached or knocked over — an open port, an expired cert, a container running as root, a wide-open security group. Review what's exposed, what's hardened, and what's a single point of failure. Read config (IaC files, Dockerfiles, compose/manifests, proxy config) for causes; confirm with safe external probes.

## Setup

Identify the stack: bare server / VM / containers / serverless, which cloud (or on-prem), and how it's provisioned (Terraform, CloudFormation, Pulumi, Ansible, or by hand). Get the IaC/config files if they exist — auditing declared infrastructure is far more reliable than probing a running system. Only probe systems the user owns.

## 1. Network exposure & firewall (check first — this is where breaches start)

- **What's reachable from the internet?** Only the ports that must be (443, maybe 80-for-redirect). Databases, caches, admin panels, and internal services must NOT be publicly reachable. `nmap`/`ss -tlnp` or the cloud console's security groups.
- **Security groups / firewall rules**: no `0.0.0.0/0` on database ports, SSH, RDP, or admin interfaces. SSH restricted to known IPs or behind a bastion/VPN. Default-deny inbound.
- **Cloud metadata endpoint** protected (IMDSv2 on AWS) — an SSRF that reaches `169.254.169.254` on IMDSv1 hands out credentials.
- **No management ports exposed**: Docker daemon (2375/2376), Kubernetes API, etcd, Redis (6379), Elasticsearch (9200) open to the world is a classic full-compromise vector.

## 2. TLS / certificates

- Valid certificate, not expired, not self-signed in production, matching the hostname (and SANs for all served domains). `echo | openssl s_client -connect host:443 -servername host 2>/dev/null | openssl x509 -noout -dates -subject`.
- **Auto-renewal** configured (Let's Encrypt/ACME or managed cert) — expired certs are a top cause of self-inflicted outages. Alert on expiry (hand to observability).
- Modern config: TLS 1.2+ only (1.0/1.1 disabled), strong cipher suites, HSTS at the edge, OCSP stapling. Test with an SSL checker.
- Certs cover apex + www + any subdomains actually served.

## 3. DNS

- Records correct and pointing where intended; no dangling records (a CNAME to a decommissioned service invites subdomain takeover).
- **TTLs** sensible (low enough to fail over, high enough to not hammer resolvers); appropriate records present (A/AAAA, MX if email, CAA to restrict who can issue certs).
- Redundant nameservers; registrar lock enabled; domain expiry monitored (another silent-outage cause).
- Email auth records if the domain sends mail — SPF/DKIM/DMARC (hand off to email-deliverability).

## 4. Containers (Docker / Kubernetes)

**Dockerfiles / images:**
- Not running as root — a `USER` directive dropping to non-root; matters a lot if the container is ever compromised.
- Minimal/pinned base images (specific tags or digests, not `:latest`); multi-stage builds so build tools aren't in the runtime image.
- No secrets baked into layers (`docker history` leaks them — grep build files, and the secret scanner from security-review helps).
- Image scanned for CVEs (Trivy/Grype/Scout); `.dockerignore` excludes `.env`, `.git`.

**Kubernetes / compose:**
- Resource requests/limits set (an unbounded container can starve the node); liveness/readiness probes defined.
- Least-privilege: no `privileged: true` without cause, dropped capabilities, read-only root filesystem where possible, secrets via secret objects (not env-in-manifest or committed).
- Network policies restricting pod-to-pod traffic; no `hostNetwork`/`hostPath` unless justified.

## 5. Secrets management

- Secrets in a manager (Vault, AWS Secrets Manager, SSM, Doppler, cloud KMS) or at least injected as runtime env — **not** committed, not baked into images, not in plaintext config. Rotation possible (versioned keys / envelope encryption).
- Different secrets per environment; production secrets not shared with staging/dev; least-privilege IAM for the app's own credentials (not an admin/root key).

## 6. Compute & resilience

- **Single points of failure**: one server / one AZ / one database with no standby? Note the blast radius of each. Redundancy appropriate to the stakes.
- Autoscaling or headroom for traffic spikes; resource utilization not pinned at the ceiling (ties to observability's saturation signal).
- Backups exist and are restore-tested (hand off to backup-recovery); IaC in version control so infra is reproducible, not a hand-built pet.
- Patch/update strategy for the OS and runtime; no years-out-of-date kernel or base image.

## Report format

Shared audit structure (Summary → Scorecard → Findings → Fix order), grouped **Network / TLS / DNS / Containers / Secrets / Resilience**. Each finding names the exact rule, file, or resource and the concrete change (the security-group edit, the Dockerfile line, the cert-renewal setup). Rank by exposure and blast radius — a publicly open database port or an about-to-expire cert outranks a missing resource limit. Cross-reference security-review for app-layer issues and observability for the alerting that catches cert/domain expiry.

## Project memory integration (solo-team)

**AgentRoom proposal mode:** when a trusted seat lists any memory target below under `proposes`, write the intended target, patch/entries, evidence, and merge notes to `.solo/proposals/<seat>-<run_id>.md` instead of editing that target. Only the memory steward merges it; missing seat or run identity stops the write. Direct memory updates remain normal outside a stewarded room.

If a `.solo/` directory exists at the project root — the solo-team suite's shared memory — read `handoff.md` and `tasks.md` for context before starting, so the work is grounded in the project's actual state. Afterward, persist the results: capture the prioritized fix list as tasks in `.solo/tasks.md` (stable T-IDs, Doing/Todo/Blocked/Done sections, per project-memory-manager's conventions), append significant findings, decisions, or accepted risks to `.solo/decisions.md`, and note what was run in `handoff.md`. This keeps results in persistent project memory instead of dying with the session, and lets `/solo:next-step` and `/release:preflight` see them. If `.solo/` doesn't exist, proceed normally (and optionally mention the solo plugin can add cross-session memory).

## Session lifecycle

This skill works inside a session that the solo plugin bookends: `/solo:start-session` restores project context at the start (reading `.solo/`), and `/solo:end-session` saves progress, blockers, decisions, and the next task at the end. `/solo:run-cycle` may invoke this skill as one step of a complete task cycle (select → design → implement → review → test → audit → document → save). The read-before / update-after memory behavior described above is exactly what makes those session boundaries work — keep `.solo/` current as you go so start-session and end-session stay accurate.

## Stack awareness

Before auditing or building, read `.solo/stack.md` if it exists — it records the project's actual tools (hosting, DNS/CDN/WAF, database, auth, storage, analytics/tags, email, payments, repo/CI), captured by `/stack:intake`. Tailor the work to the real stack instead of giving generic advice (e.g. don't suggest an S3 lifecycle rule to a Cloudinary project, or a generic WAF to a site already on Cloudflare). If `stack.md` is missing and the stack matters here, suggest running `/stack:intake` first. For vendor-specific depth, the stack plugin adds `/stack:audit-cloudflare`, `-vercel`, `-supabase`, `-tags`, and `-payments`.
