// Component/interaction tests for app/page.tsx — beyond the starter-artifact
// smoke check in rendered-html.test.mjs, which only exercises the static SSR
// output. These actually mount the component in a jsdom environment and
// simulate clicks, so real state transitions (menu toggle, tab switching)
// get verified, not just initial markup. See .solo/tasks.md T9.
//
// No component-testing library is added as a dependency: `jsdom` (already a
// devDependency) provides the DOM, and `esbuild` (already installed
// transitively via Vite) transpiles the .tsx source on the fly, matching
// this repo's evident preference for a lean dependency footprint.

import { test, after } from "node:test";
import assert from "node:assert/strict";
import { readFileSync, writeFileSync, rmSync } from "node:fs";
import { fileURLToPath, pathToFileURL } from "node:url";
import path from "node:path";
import { JSDOM } from "jsdom";
import * as esbuild from "esbuild";

const __dirname = path.dirname(fileURLToPath(import.meta.url));
const PAGE_PATH = path.join(__dirname, "..", "app", "page.tsx");

// esbuild's transform() output still has bare `import "react"` /
// `import "react/jsx-runtime"` specifiers, which Node's loader can only
// resolve against node_modules from a real file location — a `data:` URL
// has no such base, so `import(dataUrl)` fails with
// ERR_UNSUPPORTED_RESOLVE_REQUEST. Writing to a real (gitignored) temp file
// under tests/ gives Node a normal path to walk up from.
const COMPILED_PATH = path.join(__dirname, ".page-compiled.mjs");
let cachedHome;

after(() => {
  rmSync(COMPILED_PATH, { force: true });
});

/** Transpile app/page.tsx to plain ESM JS once, cache the component. */
async function loadHomeComponent() {
  if (cachedHome) return cachedHome;
  const source = readFileSync(PAGE_PATH, "utf8");
  const { code } = await esbuild.transform(source, {
    loader: "tsx",
    format: "esm",
    jsx: "automatic",
    jsxImportSource: "react",
    target: "es2020",
  });
  writeFileSync(COMPILED_PATH, code, "utf8");
  const mod = await import(pathToFileURL(COMPILED_PATH).href);
  cachedHome = mod.default;
  return cachedHome;
}

// Node 21+ predefines a getter-only `globalThis.navigator` (and similar),
// which a plain `globalThis.navigator = ...` assignment can't overwrite.
// Define each global with `configurable: true` instead, so it can also be
// cleanly removed again in uninstallDom().
function setGlobal(key, value) {
  Object.defineProperty(globalThis, key, { value, configurable: true, writable: true });
}

/** Install a fresh jsdom document as the global DOM for one test. */
function installDom() {
  const dom = new JSDOM("<!doctype html><html><body></body></html>", {
    url: "http://localhost/",
    pretendToBeVisual: true,
  });
  const { window } = dom;
  setGlobal("window", window);
  setGlobal("document", window.document);
  setGlobal("navigator", window.navigator);
  setGlobal("HTMLElement", window.HTMLElement);
  setGlobal("MouseEvent", window.MouseEvent);
  setGlobal("Element", window.Element);
  setGlobal("customElements", window.customElements);
  setGlobal("requestAnimationFrame", (cb) => window.setTimeout(() => cb(Date.now()), 0));
  setGlobal("cancelAnimationFrame", (id) => window.clearTimeout(id));
  // Tells React it may batch/flush synchronously inside act() rather than
  // warning that updates happened outside a recognized test environment.
  setGlobal("IS_REACT_ACT_ENVIRONMENT", true);
  return dom;
}

function uninstallDom() {
  for (const key of [
    "window",
    "document",
    "navigator",
    "HTMLElement",
    "MouseEvent",
    "Element",
    "customElements",
    "requestAnimationFrame",
    "cancelAnimationFrame",
    "IS_REACT_ACT_ENVIRONMENT",
  ]) {
    delete globalThis[key];
  }
}

/** Unmount inside act() so React flushes effect cleanup synchronously,
 * before uninstallDom() deletes `window`/`document` out from under any
 * deferred scheduler work. */
async function unmount(root) {
  await act_(() => root.unmount());
}

async function renderHome() {
  const { createRoot } = await import("react-dom/client");
  const { act } = await import("react");
  const React = await import("react");
  const Home = await loadHomeComponent();

  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);

  await act(async () => {
    root.render(React.createElement(Home));
  });

  return { container, root };
}

function click(el) {
  return act_(() =>
    el.dispatchEvent(new window.MouseEvent("click", { bubbles: true, cancelable: true })),
  );
}

// Small local helper so callers don't need to re-import `act` everywhere.
let actRef;
async function act_(fn) {
  if (!actRef) actRef = (await import("react")).act;
  return actRef(async () => {
    fn();
  });
}

test("mobile menu toggle opens and closes the nav, and updates aria-expanded", async () => {
  installDom();
  try {
    const { container, root } = await renderHome();

    const toggle = container.querySelector(".menu-toggle");
    assert.ok(toggle, "menu toggle button should render");
    assert.equal(toggle.getAttribute("aria-expanded"), "false", "starts closed");

    const navLinks = container.querySelector(".nav-links");
    assert.ok(navLinks, "nav links container should render");
    assert.ok(!navLinks.className.includes("is-open"), "starts without is-open");

    await click(toggle);
    assert.equal(toggle.getAttribute("aria-expanded"), "true", "opens on click");
    assert.ok(navLinks.className.includes("is-open"), "gains is-open on click");

    await click(toggle);
    assert.equal(toggle.getAttribute("aria-expanded"), "false", "closes on second click");
    assert.ok(!navLinks.className.includes("is-open"), "loses is-open on second click");

    await unmount(root);
  } finally {
    uninstallDom();
  }
});

test("clicking a nav link closes an open mobile menu (scrollTo also closes it)", async () => {
  installDom();
  try {
    const { container, root } = await renderHome();

    const toggle = container.querySelector(".menu-toggle");
    await click(toggle);
    const navLinks = container.querySelector(".nav-links");
    assert.ok(navLinks.className.includes("is-open"), "menu is open before nav click");

    // scrollIntoView isn't implemented in jsdom; stub it so scrollTo() doesn't throw.
    window.HTMLElement.prototype.scrollIntoView = () => {};

    const systemLink = Array.from(navLinks.querySelectorAll("button")).find(
      (b) => b.textContent === "System",
    );
    assert.ok(systemLink, "System nav link should render");

    await click(systemLink);
    assert.ok(!navLinks.className.includes("is-open"), "menu closes after a nav link click");

    await unmount(root);
  } finally {
    uninstallDom();
  }
});

test("module tabs switch the active module and its tab-panel content on click", async () => {
  installDom();
  try {
    const { container, root } = await renderHome();

    const tabs = container.querySelectorAll('[role="tab"]');
    assert.equal(tabs.length, 5, "five module tabs should render");
    assert.equal(tabs[0].getAttribute("aria-selected"), "true", "first tab starts selected");
    assert.equal(tabs[1].getAttribute("aria-selected"), "false");

    const heading = () => container.querySelector(".module-copy h3")?.textContent;
    const firstHeading = heading();
    assert.ok(firstHeading, "module heading should render");

    await click(tabs[1]);

    assert.equal(tabs[0].getAttribute("aria-selected"), "false", "first tab deselects");
    assert.equal(tabs[1].getAttribute("aria-selected"), "true", "second tab selects");
    assert.notEqual(heading(), firstHeading, "module heading content changes with the active tab");

    await unmount(root);
  } finally {
    uninstallDom();
  }
});

test("the primary CTA button updates its own label after being clicked (runStarted state)", async () => {
  installDom();
  try {
    const { container, root } = await renderHome();

    const primaryButtons = Array.from(container.querySelectorAll(".button-primary"));
    const heroCta = primaryButtons.find((b) => b.textContent.includes("Start a full-team run"));
    assert.ok(heroCta, "hero primary CTA should render with its initial label");

    await click(heroCta);

    assert.ok(
      heroCta.textContent.includes("Run queued"),
      "hero CTA label updates after click to reflect runStarted state",
    );

    await unmount(root);
  } finally {
    uninstallDom();
  }
});
