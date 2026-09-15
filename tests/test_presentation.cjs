/* Presentation contracts only: not an aerodynamic validation or browser audit. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const crypto = require("node:crypto");
const root = path.resolve(__dirname, "..");
const read = name => fs.readFileSync(path.join(root, name), "utf8");
const studio = read("index.html");
const research = read("research.html");
const hash = value => crypto.createHash("sha256").update(value).digest("hex");

test("workbench inline engine and embedded data are unchanged from the frozen presentation baseline", () => {
  // Baseline: 04d645ea2aa9bc873d5ad70b84125d78dd71fa47, 9 September 2026.
  // Intentional future engine changes require their own numerical validation.
  const scripts = [...studio.matchAll(/<script\b[^>]*>([\s\S]*?)<\/script>/gi)].map(m => hash(m[1]));
  assert.deepEqual(scripts, [
    "d3066c30a11ab980a1d0a85ebe27936ef25a4e7021a505d003986cc9f00b5d64",
    "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855"
  ]);
});
test("workbench keeps core controls and an accessible skip destination", () => {
  for (const id of ["tabs", "toolbar", "afSearch", "ai", "themeBtn", "prov", "p-polars", "p-geom", "p-checks"]) {
    assert.equal([...studio.matchAll(new RegExp(`id="${id}"`, "g"))].length, 1, id);
  }
  assert.match(studio, /href="#tabs">Skip to the workbench/);
  assert.match(studio, /active tool's Reynolds-number and angle controls/);
});
test("research has a unique heading and three explicit entry paths", () => {
  assert.equal([...research.matchAll(/<h1\b/g)].length, 1);
  const nav = research.match(/<nav class="reader-paths"[\s\S]*?<\/nav>/)[0];
  for (const dest of ["index.html", "#evidence", "#source"]) assert.ok(nav.includes(`href="${dest}"`));
});
test("research keeps its white-and-green identity independent of OS dark preference", () => {
  const css = read("research.css");
  assert.match(research, /<meta name="color-scheme" content="light">/);
  assert.match(research, /<meta name="theme-color" content="#ffffff">/);
  const tokens = css.match(/\.research-page\s*\{([^}]*--page:[^}]*)\}/)[1];
  for (const declaration of ["--page:#fff;", "--surface:#fff;", "--ink:#123c32;", "--aero:#146657;", "color-scheme:only light;"]) {
    assert.ok(tokens.includes(declaration), declaration);
  }
  assert.doesNotMatch(css, /prefers-color-scheme/);
  assert.equal([...css.matchAll(/--page:/g)].length, 1, "one page-theme token block");
  assert.doesNotMatch(studio, /<meta name="color-scheme" content="light">/);
});
test("local presentation assets and page links exist", () => {
  for (const html of [studio, research]) {
    for (const match of html.matchAll(/(?:href|src)="([^"#]+)"/g)) {
      const target = match[1].split(/[?#]/)[0];
      if (!target || /^(?:[a-z]+:|\/\/)/i.test(target) || target.includes("${")) continue;
      // Embedded templates contain URL fragments; only actual local presentation paths.
      if (/^(?:research|studio-presentation|source-browser|index|nfb)\.(?:html|js|css)$/.test(target)) {
        assert.ok(fs.existsSync(path.join(root, target)), target);
      }
    }
  }
  assert.ok(fs.existsSync(path.join(root, "assets/neuralfoil-overview.svg")));
});
test("presentation keeps limitations attached to the research gains", () => {
  for (const text of ["20.47", "19.69", "8,371", "93 conservative identities", "not two independent datasets", "Some rows, identities and external cases worsen", "Not installed in the browser", "drag correction is disabled"]) {
    assert.ok(research.includes(text), text);
  }
});
test("overview is an explicitly illustrative local SVG with no script or external asset", () => {
  const svg = read("assets/neuralfoil-overview.svg");
  assert.match(svg, /viewBox="0 0 1200 460"/);
  assert.match(svg, /illustration/i);
  assert.doesNotMatch(svg, /<script|<foreignObject|(?:href|src)="(?:https?:|data:)/i);
});
test("current reader-facing wording describes applicability directly", () => {
  const retiredTerm = /\b(?:gate|gates|gated|gating)\b/i;
  for (const file of ["README.md", "research.html", "index.html", "nfb.js", "docs/METHODS.md", "docs/DATA.md", "docs/STATUS.md"]) {
    // The public API signature remains exact; this is an editorial check, not an API rename.
    const prose = read(file).replace(/```[\s\S]*?```|`[^`]*`/g, "");
    assert.doesNotMatch(prose, retiredTerm, file);
  }
  assert.ok(read("docs/METHODS.md").includes("predict(artifact, X62, BASE_CD, all_model_CD, gate, label)"));
  assert.ok(research.includes("Check the operating limits"));
  assert.ok(research.includes("Boolean eligibility flag"));
});
