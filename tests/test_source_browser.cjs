/* Synthetic navigation and DOM-contract tests. Not browser rendering or model tests. */
"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const api = require("../source-browser.js");
const root = path.resolve(__dirname, "..");
const item = (path, language = "Python", bytes = 100) => ({ path, language, bytes, sha256: "a".repeat(64), role: "historical source" });
const catalog = { schema: "source-catalog-v1", files: [
  item("code/research/risk_policy/portable/predictor.py"), item("code/research/risk_policy/test_policy.py", "Python", 200),
  item("code/supplement/render.py", "Python", 500), item("research.js", "JavaScript", 300),
  item("tests/test_public.py"), item("study/legacy.py", "Python", 50), item("vendor/example.c", "C", 80)
] };
const files = api.prepare(catalog);
const state = changes => api.normalize({ ...api.defaults, ...changes }, files);

test("each path belongs to exactly one location-based collection", () => {
  assert.deepEqual(files.map(file => file.collection), ["research", "research", "supplement", "browser", "checks", "study", "other"]);
  assert.equal(api.collectionFor("examples/synthetic_policy.py"), "checks");
  assert.equal(api.collectionFor("code/research/tests/historical_test.py"), "research");
  assert.equal(api.collectionFor(".github/workflows/check.yml"), "checks");
});
test("search combines words and normalizes path separators", () => {
  assert.equal(api.select(files, state({ q: "RISK policy" })).matches.length, 2);
  assert.equal(api.select(files, state({ q: "portable predictor" })).matches[0].name, "predictor.py");
  assert.equal(api.select(files, state({ q: "risk nonexistent" })).matches.length, 0);
  assert.equal(api.select(files, state({ q: "   " })).matches.length, files.length);
});
test("combined filters and contextual facet counts remain consistent", () => {
  const selected = api.select(files, state({ collection: "research", language: "Python" }));
  assert.equal(selected.matches.length, 2);
  assert.equal(selected.collectionCounts[""], 5);
  assert.equal(selected.collectionCounts.browser, 0);
  assert.equal(selected.languageCounts[""], 2);
  assert.equal(selected.languageCounts.Python, 2);
  assert.equal(api.select(files, state({ collection: "research", language: "JavaScript" })).matches.length, 0);
});
test("four sorts have deterministic ties and do not mutate input", () => {
  const snapshot = JSON.stringify(files);
  assert.equal(api.select(files, state({ sort: "largest" })).matches[0].bytes, 500);
  assert.equal(api.select(files, state({ sort: "smallest" })).matches[0].bytes, 50);
  assert.equal(api.select(files, state({ sort: "name" })).matches[0].name, "example.c");
  assert.deepEqual(api.select(files, state({ sort: "path" })).matches.map(f => f.path), files.map(f => f.path).sort());
  assert.equal(JSON.stringify(files), snapshot);
});
test("URL state round-trips special characters and rejects unknown values", () => {
  const chosen = state({ q: "risk & α / <script>", collection: "research", language: "Python", sort: "name" });
  assert.deepEqual(api.fromSearch(api.toSearch(chosen), files), chosen);
  assert.deepEqual(api.fromSearch("?collection=__proto__&language=Fake&sort=constructor&extra=ignored", files), api.defaults);
  assert.equal(api.toSearch(api.defaults), "");
  assert.equal(api.fromSearch("?q=" + "x".repeat(500), files).q.length, 300);
});
test("invalid catalogs, duplicate paths and unsafe paths fail closed", () => {
  for (const unsafe of ["/root.py", "../a.py", "a/../b.py", "a//b.py", "a\\b.py", "a/./b.py", ".git/config", "a\n.py"]) {
    assert.equal(api.validFile(item(unsafe)), false, unsafe);
  }
  for (const broken of [null, {}, { ...catalog, schema: "wrong" }, { ...catalog, files: [catalog.files[0], catalog.files[0]] },
    { ...catalog, files: [{ ...catalog.files[0], bytes: -1 }] }, { ...catalog, files: [{ ...catalog.files[0], sha256: "bad" }] }]) {
    assert.throws(() => api.prepare(broken));
  }
});
test("source URLs stay on fixed hosts and encode unusual names", () => {
  const name = "code/a #?<b>.py";
  assert.equal(api.sourceURL(name), "https://github.com/KaanBoge/neuralfoil/blob/main/code/a%20%23%3F%3Cb%3E.py");
  assert.equal(new URL(api.sourceURL(name, true)).host, "raw.githubusercontent.com");
});
test("metadata export matches filter and excludes UI-only fields", () => {
  const exported = api.exportMatches(files, state({ collection: "research" }));
  assert.equal(exported.files.length, 2);
  assert.deepEqual(Object.keys(exported.files[0]).sort(), ["bytes", "language", "path", "role", "sha256"]);
  assert.match(exported.scope, /metadata only/);
  assert.equal(api.formatBytes(10), "10 B");
  assert.equal(api.formatBytes(1500), "1.5 kB");
  assert.equal(api.formatBytes(1500000), "1.50 MB");
});
test("empty catalog is valid, exportable and produces no matches", () => {
  const empty = api.prepare({ schema: catalog.schema, files: [] });
  assert.equal(api.select(empty, api.defaults).matches.length, 0);
  assert.deepEqual(api.exportMatches(empty, api.defaults).files, []);
});

// Deliberately small DOM double: fails if rendering attempts to use innerHTML.
class Element {
  constructor(tag) { this.tag = tag; this.children = []; this.dataset = {}; this.attributes = {}; this.listeners = {}; this.value = ""; this.hidden = false; }
  set textContent(value) { this.text = String(value); this.children = []; }
  get textContent() { return (this.text || "") + this.children.map(c => c.textContent).join(""); }
  set innerHTML(_) { throw new Error("HTML injection forbidden"); }
  append(...nodes) { this.children.push(...nodes); }
  replaceChildren(...nodes) { this.children = nodes; }
  get lastElementChild() { return this.children.at(-1); }
  get options() { return this.children; }
  setAttribute(key, value) { this.attributes[key] = value; }
  addEventListener(event, fn) { this.listeners[event] = fn; }
  emit(event) { this.listeners[event]?.(); }
  click() { this.emit("click"); }
  focus() { this.focused = true; }
  remove() { this.removed = true; }
  querySelector(tag) { for (const child of this.children) { if (child.tag === tag) return child; const match = child.querySelector(tag); if (match) return match; } return null; }
}
async function harness({ search = "", data = catalog, ok = true, reject = false } = {}) {
  const html = fs.readFileSync(path.join(root, "research.html"), "utf8");
  const nodes = Object.fromEntries([...html.matchAll(/id="([^"]+)"/g)].map(match => [match[1], new Element("div")]));
  for (const id of ["source-empty", "source-more", "source-fallback"]) nodes[id].hidden = true;
  nodes["source-language"].append(new Element("option"));
  const events = {}, history = [], blobs = [], revoked = [];
  const window = { SourceBrowser: api, location: new URL("https://example.test/neuralfoil/research.html" + search), addEventListener: (name, fn) => { events[name] = fn; } };
  window.history = Object.fromEntries(["pushState", "replaceState"].map(method => [method, (_, __, url) => { history.push([method, url]); window.location = new URL(url, window.location); }]));
  class MockURL extends URL { static createObjectURL(blob) { blobs.push(blob); return "blob:test"; } static revokeObjectURL(url) { revoked.push(url); } }
  const document = { getElementById: id => { assert.ok(nodes[id], `Missing HTML id ${id}`); return nodes[id]; }, createElement: tag => new Element(tag), body: new Element("body") };
  vm.runInNewContext(fs.readFileSync(path.join(root, "research.js"), "utf8"), {
    window, document, URL: MockURL, Blob, setTimeout: fn => fn(),
    fetch: () => reject ? Promise.reject(new Error("offline")) : Promise.resolve({ ok, json: () => Promise.resolve(data) })
  });
  assert.equal(nodes["source-search"].disabled, true, "Loading controls disabled");
  await new Promise(setImmediate);
  return { nodes, window, events, history, blobs, revoked, document };
}
test("UI loads linkable state, filters, sorts, resets and restores browser history", async () => {
  const h = await harness({ search: "?collection=research&language=Python#source" });
  const n = h.nodes;
  assert.equal(n["source-results"].children.length, 2);
  assert.equal(n["source-search"].disabled, false);
  assert.equal(n["source-collections"].children.find(b => b.dataset.collection === "research").attributes["aria-pressed"], "true");
  n["source-search"].value = "portable"; n["source-search"].emit("input");
  assert.equal(n["source-results"].children.length, 1);
  assert.match(n["source-permalink"].href, /q=portable/);
  n["source-sort"].value = "largest"; n["source-sort"].emit("change");
  assert.equal(h.history.at(-1)[0], "pushState");
  n["source-reset"].click();
  assert.equal(n["source-results"].children.length, files.length);
  assert.equal(n["source-search"].focused, true);
  assert.equal(n["source-reset"].disabled, true);
  h.window.location = new URL("https://example.test/neuralfoil/research.html?collection=browser#source"); h.events.popstate();
  assert.equal(n["source-results"].children.length, 1);
  assert.match(n["source-results"].children[0].textContent, /research.js/);
});
test("UI reports empty results, exports selection and uses text-safe rendering", async () => {
  const h = await harness({ data: { ...catalog, files: [...catalog.files, item("tests/<script>.py")] } });
  const n = h.nodes;
  n["source-search"].value = "<script>"; n["source-search"].emit("input");
  assert.equal(n["source-results"].children.length, 1);
  assert.match(n["source-results"].children[0].querySelector("a").href, /%3Cscript%3E/);
  n["source-download"].click();
  assert.equal(JSON.parse(await h.blobs[0].text()).files[0].path, "tests/<script>.py");
  assert.deepEqual(h.revoked, ["blob:test"]);
  n["source-search"].value = "not-found"; n["source-search"].emit("input");
  assert.equal(n["source-empty"].hidden, false);
  assert.equal(n["source-download"].disabled, true);
  assert.equal(n["source-more"].hidden, true);
  n["source-empty-reset"].click();
  assert.equal(n["source-empty"].hidden, true);
});
test("pagination focuses first newly revealed link and hides at end", async () => {
  const h = await harness({ data: { ...catalog, files: Array.from({ length: 27 }, (_, i) => item(`tests/test_${String(i).padStart(2, "0")}.py`)) } });
  const n = h.nodes;
  assert.equal(n["source-results"].children.length, 12);
  n["source-more"].click();
  assert.equal(n["source-results"].children.length, 24);
  assert.equal(n["source-results"].children[12].querySelector("a").focused, true);
  n["source-more"].click();
  assert.equal(n["source-results"].children.length, 27);
  assert.equal(n["source-more"].hidden, true);
});
test("network and invalid-catalog errors show direct fallback without enabling controls", async () => {
  for (const options of [{ reject: true }, { ok: false }, { data: { schema: "wrong" } }]) {
    const { nodes } = await harness(options);
    assert.equal(nodes["source-fallback"].hidden, false);
    assert.equal(nodes["source-search"].disabled, true);
    assert.match(nodes["source-status"].textContent, /could not be loaded/);
  }
});
test("HTML contract has unique IDs, labels, static fallback and ordered deferred scripts", () => {
  const html = fs.readFileSync(path.join(root, "research.html"), "utf8");
  const ids = [...html.matchAll(/id="([^"]+)"/g)].map(match => match[1]);
  assert.equal(new Set(ids).size, ids.length);
  for (const id of ["source-search", "source-language", "source-sort"]) assert.ok(html.includes(`for="${id}"`));
  assert.match(html, /<noscript>/);
  assert.ok(html.indexOf("source-browser.js") < html.indexOf("research.js"));
  assert.ok(html.indexOf('id="source"') < html.indexOf('id="implementations"'));
});
test("published catalog partitions exhaustively and README explorer links return results", () => {
  const published = api.prepare(JSON.parse(fs.readFileSync(path.join(root, "code/source-catalog.json"), "utf8")));
  assert.equal(api.select(published, api.defaults).matches.length, published.length);
  for (const file of published) assert.ok(Object.hasOwn(api.collections, file.collection));
  const readme = fs.readFileSync(path.join(root, "README.md"), "utf8");
  for (const [href] of readme.matchAll(/https:\/\/kaanboge\.github\.io\/neuralfoil\/research\.html\?[^)]+/g)) {
    const state = api.fromSearch(new URL(href).search, published);
    assert.ok(api.select(published, state).matches.length > 0, href);
  }
});
