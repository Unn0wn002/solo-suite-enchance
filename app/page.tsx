"use client";

import { useState } from "react";

const workflow = [
  { id: "01", label: "Intake", meta: "stack + context", tone: "gold" },
  { id: "02", label: "Shape", meta: "brief + architecture", tone: "mint" },
  { id: "03", label: "Build", meta: "implementation room", tone: "blue" },
  { id: "04", label: "Prove", meta: "QA + security + gates", tone: "violet" },
  { id: "05", label: "Ship", meta: "release + handoff", tone: "coral" },
];

const modules = [
  {
    kicker: "01 / ORIENT",
    title: "Make the brief executable.",
    copy: "Move from a rough idea to a decision-ready PRD, architecture map, contracts, and a clean task queue.",
    tags: ["Product", "Architecture", "Spec"],
    accent: "gold",
  },
  {
    kicker: "02 / CREATE",
    title: "Give every task a room.",
    copy: "AgentRooms staff the work with focused roles, shared context, explicit handoffs, and one writer per artifact.",
    tags: ["Design", "Dev", "AI"],
    accent: "mint",
  },
  {
    kicker: "03 / VERIFY",
    title: "Turn quality into evidence.",
    copy: "Browser QA, security reviews, audits, and production gates create a paper trail you can trust.",
    tags: ["Test", "Security", "Gate"],
    accent: "blue",
  },
  {
    kicker: "04 / OPERATE",
    title: "Stay fast after launch.",
    copy: "Keep stack context, release notes, monitoring, growth, and documentation connected to the same project memory.",
    tags: ["Release", "Stack", "Docs"],
    accent: "violet",
  },
];

const runtimes = [
  { name: "Claude", symbol: "C", detail: "command-native marketplace" },
  { name: "Codex", symbol: "⌘", detail: "skill-native execution" },
  { name: "Antigravity", symbol: "A", detail: "portable suite surface" },
];

export default function Home() {
  const [menuOpen, setMenuOpen] = useState(false);
  const [activeModule, setActiveModule] = useState(0);
  const [runStarted, setRunStarted] = useState(false);

  const scrollTo = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth" });
    setMenuOpen(false);
  };

  return (
    <main className="site-shell">
      <nav className="topbar">
        <button className="brand" onClick={() => scrollTo("top")} aria-label="Solo Suite home">
          <span className="brand-mark">S</span>
          <span>SOLO SUITE</span>
        </button>
        <div className={`nav-links ${menuOpen ? "is-open" : ""}`}>
          <button onClick={() => scrollTo("system")}>System</button>
          <button onClick={() => scrollTo("workflow")}>Workflow</button>
          <button onClick={() => scrollTo("rooms")}>Rooms</button>
          <button onClick={() => scrollTo("proof")}>Proof</button>
        </div>
        <button className="nav-cta" onClick={() => scrollTo("start")}>
          Enter the suite <span aria-hidden="true">↗</span>
        </button>
        <button
          className="menu-toggle"
          onClick={() => setMenuOpen((value) => !value)}
          aria-expanded={menuOpen}
          aria-label="Toggle navigation"
        >
          <span />
          <span />
        </button>
      </nav>

      <section className="hero section-pad" id="top">
        <div className="hero-copy">
          <p className="eyebrow"><span className="eyebrow-dot" /> THE SOLO DEVELOPER OPERATING SYSTEM</p>
          <h1>Ship like a company.<br /><em>Think like a solo.</em></h1>
          <p className="hero-lede">
            Solo Suite connects the full product team — from first brief to safe release — inside one
            shared memory layer built for Claude, Codex, and Antigravity.
          </p>
          <div className="hero-actions">
            <button className="button button-primary" onClick={() => setRunStarted(true)}>
              {runStarted ? "Run queued ✓" : "Start a full-team run"} <span aria-hidden="true">↗</span>
            </button>
            <button className="button button-quiet" onClick={() => scrollTo("workflow")}>
              See the operating loop <span aria-hidden="true">↓</span>
            </button>
          </div>
          <div className="hero-note">
            <span className="pulse" /> Built for ambitious one-person teams shipping real products.
          </div>
        </div>

        <div className="flight-deck" aria-label="Solo Suite live run preview">
          <div className="deck-topline">
            <span>FULL-TEAM / WEBSITE</span>
            <span className="deck-live"><span className="live-dot" /> LIVE RUN</span>
          </div>
          <div className="deck-heading">
            <div>
              <p className="micro-label">RUN 0048 · PUBLIC MARKETING SITE</p>
              <h2>Northstar launch</h2>
            </div>
            <span className="deck-kebab">•••</span>
          </div>
          <div className="run-meter">
            <div className="meter-row"><span>Production readiness</span><strong>72%</strong></div>
            <div className="meter-track"><span /></div>
            <div className="meter-foot"><span>11 of 15 stages complete</span><span>ETA 18 min</span></div>
          </div>
          <div className="stage-list">
            {[
              ["✓", "Stack intake", "context bound", "done"],
              ["✓", "Architecture", "approved", "done"],
              ["→", "Interface system", "in progress", "current"],
              ["○", "Browser QA", "queued", "queued"],
            ].map(([icon, name, detail, state]) => (
              <div className={`stage-row ${state}`} key={name}>
                <span className="stage-icon">{icon}</span>
                <span className="stage-name">{name}</span>
                <span className="stage-detail">{detail}</span>
              </div>
            ))}
          </div>
          <div className="deck-footer">
            <span><span className="avatar avatar-a">P</span><span className="avatar avatar-b">D</span><span className="avatar avatar-c">Q</span> 24 room seats</span>
            <span className="memory-lock">⌁ memory synced</span>
          </div>
        </div>
      </section>

      <section className="signal-strip">
        <p className="signal-label">ONE SUITE / MANY SPECIALISTS</p>
        <div className="signal-stats">
          <div><strong>19</strong><span>plugins</span></div>
          <div><strong>184</strong><span>skills</span></div>
          <div><strong>16</strong><span>workflow stages</span></div>
          <div><strong>01</strong><span>project memory</span></div>
        </div>
      </section>

      <section className="system section-pad" id="system">
        <div className="section-intro">
          <p className="eyebrow">01 / THE SYSTEM</p>
          <h2>Your whole product team,<br /><em>in one operating rhythm.</em></h2>
          <p>Solo Suite keeps the work moving in the right order — and keeps the decisions attached to the work that follows.</p>
        </div>
        <div className="system-grid">
          <div className="system-card system-card-large">
            <div className="card-label">SHARED PROJECT MEMORY</div>
            <div className="memory-visual">
              <div className="memory-core"><span>PROJECT<br />TRUTH</span></div>
              <span className="orbit orbit-one" />
              <span className="orbit orbit-two" />
              <span className="orbit orbit-three" />
              <span className="orbit-node node-a">PRD</span>
              <span className="orbit-node node-b">STACK</span>
              <span className="orbit-node node-c">TASKS</span>
              <span className="orbit-node node-d">GATES</span>
            </div>
            <p>Every room reads the same context. Every handoff leaves a trace.</p>
          </div>
          <div className="system-card system-card-stack">
            <div className="card-label">THE STACK</div>
            <h3>Context before checklists.</h3>
            <p>Tell the suite what you run on once. Vendor-aware audits follow the evidence.</p>
            <div className="stack-lines">
              <span><b>HOST</b> Vercel / Cloudflare</span>
              <span><b>DATA</b> Supabase / Postgres</span>
              <span><b>SHIP</b> GitHub / CI</span>
            </div>
          </div>
          <div className="system-card system-card-gate">
            <div className="card-label">THE GATE</div>
            <div className="gate-score"><span>94</span><small>/100</small></div>
            <h3>Evidence-backed<br />go / no-go.</h3>
            <p>One failed hard check blocks the launch. No average can hide it.</p>
            <span className="gate-status">SAFE WITH WARNINGS</span>
          </div>
        </div>
      </section>

      <section className="workflow section-pad" id="workflow">
        <div className="workflow-header">
          <div>
            <p className="eyebrow">02 / THE OPERATING LOOP</p>
            <h2>From blank page<br /><em>to shipped product.</em></h2>
          </div>
          <p className="workflow-caption">A 16-stage cycle with hard stops, resumable runs, and memory-aware handoffs.</p>
        </div>
        <div className="workflow-track">
          <div className="track-line" />
          {workflow.map((step, index) => (
            <div className={`workflow-step ${index === 2 ? "active" : ""}`} key={step.id}>
              <span className={`step-node ${step.tone}`}>{step.id}</span>
              <span className="step-label">{step.label}</span>
              <span className="step-meta">{step.meta}</span>
            </div>
          ))}
        </div>
        <div className="workflow-bottom">
          <div className="workflow-quote">
            <span className="quote-mark">“</span>
            <p>Less context switching.<br /><em>More shipping.</em></p>
          </div>
          <div className="workflow-detail">
            <span className="detail-index">STAGE 03 / 16</span>
            <h3>Build with the right people in the room.</h3>
            <p>Design, engineering, QA, security, and release each get a focused seat — then hand off a verified artifact.</p>
            <button className="text-link" onClick={() => scrollTo("rooms")}>Explore AgentRooms <span>↗</span></button>
          </div>
        </div>
      </section>

      <section className="modules section-pad" id="rooms">
        <div className="modules-header">
          <div>
            <p className="eyebrow">03 / THE ROOMS</p>
            <h2>Specialists that<br /><em>move as one.</em></h2>
          </div>
          <div className="module-tabs" role="tablist" aria-label="Solo Suite modules">
            {modules.map((module, index) => (
              <button
                key={module.kicker}
                className={activeModule === index ? "active" : ""}
                onClick={() => setActiveModule(index)}
                role="tab"
                aria-selected={activeModule === index}
              >
                {String(index + 1).padStart(2, "0")}
              </button>
            ))}
          </div>
        </div>
        <div className="module-feature">
          <div className={`module-index ${modules[activeModule].accent}`}>{modules[activeModule].kicker}</div>
          <div className="module-copy">
            <h3>{modules[activeModule].title}</h3>
            <p>{modules[activeModule].copy}</p>
            <div className="module-tags">
              {modules[activeModule].tags.map((tag) => <span key={tag}>{tag}</span>)}
            </div>
          </div>
          <div className="module-visual">
            <div className="room-window">
              <div className="window-top"><span /><span /><span /><b>agent-room / {modules[activeModule].tags[0].toLowerCase()}</b></div>
              <div className="window-body">
                <div className="window-line line-long" /><div className="window-line line-mid" />
                <div className="window-line line-short" /><div className="window-line line-long highlight" />
                <div className="window-line line-mid" /><div className="window-line line-short" />
              </div>
              <div className="window-stamp">HANDOFF READY</div>
            </div>
          </div>
        </div>
      </section>

      <section className="proof section-pad" id="proof">
        <div className="proof-heading">
          <p className="eyebrow">04 / THE PROMISE</p>
          <h2>One source of truth.<br /><em>Three ways to work.</em></h2>
        </div>
        <div className="runtime-grid">
          {runtimes.map((runtime) => (
            <div className="runtime-card" key={runtime.name}>
              <span className="runtime-symbol">{runtime.symbol}</span>
              <div><h3>{runtime.name}</h3><p>{runtime.detail}</p></div>
              <span className="runtime-arrow">↗</span>
            </div>
          ))}
        </div>
        <div className="proof-bottom">
          <p>Built from the rigor of a full product org, tuned for the speed of one exceptional builder.</p>
          <div className="proof-pills"><span>Auditable</span><span>Resumable</span><span>Portable</span></div>
        </div>
      </section>

      <section className="start section-pad" id="start">
        <div className="start-inner">
          <p className="eyebrow">READY WHEN YOU ARE</p>
          <h2>Make your next<br /><em>big thing inevitable.</em></h2>
          <p>Bring the ambition. Solo Suite brings the operating system.</p>
          <button className="button button-primary button-large" onClick={() => setRunStarted(true)}>
            {runStarted ? "Your first run is queued ✓" : "Start building with Solo Suite"} <span aria-hidden="true">↗</span>
          </button>
          <div className="start-orbit" aria-hidden="true"><span /><span /><span /></div>
        </div>
      </section>

      <footer className="footer">
        <div className="footer-brand"><span className="brand-mark">S</span><span>SOLO SUITE</span></div>
        <p>Full-team development for focused builders.</p>
        <span className="footer-meta">v1.0.27 / EST. 2026</span>
      </footer>
    </main>
  );
}
