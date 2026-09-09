"use strict";
/* Read-only catalog UI. No prediction, tracking, external scripts or HTML injection. */
(() => {
  const api = window.SourceBrowser;
  const byId = id => document.getElementById(id);
  const search = byId("source-search"), language = byId("source-language"), sort = byId("source-sort");
  const status = byId("source-status"), results = byId("source-results"), more = byId("source-more");
  const reset = byId("source-reset"), download = byId("source-download"), permalink = byId("source-permalink");
  const chips = byId("source-collections"), summary = byId("source-summary");
  const controls = [search, language, sort, reset, download];
  const pageSize = 12;
  let files = [], state, shown = pageSize, loaded = false;
  const element = (tag, text, className) => {
    const node = document.createElement(tag);
    if (text !== undefined) node.textContent = text;
    if (className) node.className = className;
    return node;
  };
  function syncURL(mode) {
    const query = api.toSearch(state);
    const url = `${window.location.pathname}${query}${window.location.hash}`;
    try { window.history[mode === "push" ? "pushState" : "replaceState"](null, "", url); } catch (_) { /* Filters still work when history is unavailable. */ }
    permalink.href = `${window.location.pathname}${query}#source`;
  }
  function change(values, mode = "push") {
    if (!loaded) return;
    state = api.normalize({ ...state, ...values }, files);
    shown = pageSize;
    syncURL(mode);
    render();
  }
  function render() {
    search.value = state.q;
    language.value = state.language;
    sort.value = state.sort;
    const { matches, collectionCounts, languageCounts } = api.select(files, state);
    for (const button of chips.children) {
      const value = button.dataset.collection;
      button.setAttribute("aria-pressed", String(state.collection === value));
      button.lastElementChild.textContent = collectionCounts[value];
    }
    for (const option of language.options) option.textContent = `${option.value || "All languages"} (${languageCounts[option.value] || 0})`;
    results.replaceChildren();
    for (const file of matches.slice(0, shown)) {
      const row = element("li", undefined, "source-row");
      const title = element("a", file.name, "source-file");
      title.href = api.sourceURL(file.path);
      const info = element("div", undefined, "source-file-info");
      info.append(title, element("span", file.path, "source-path"));
      const tags = element("div", undefined, "source-tags");
      tags.append(element("span", file.language), element("span", api.collections[file.collection]), element("span", api.formatBytes(file.bytes)));
      const raw = element("a", "Raw file", "source-raw");
      raw.href = api.sourceURL(file.path, true);
      raw.setAttribute("aria-label", `Raw file: ${file.path}`);
      const detail = element("details", undefined, "source-integrity");
      detail.append(element("summary", "SHA-256"), element("code", file.sha256));
      row.append(info, tags, raw, detail);
      results.append(row);
    }
    const count = Math.min(shown, matches.length);
    status.textContent = matches.length ? `Showing ${count} of ${matches.length} matching files · ${files.length} total source files` : "No matching files. Clear a filter or try fewer search words.";
    summary.textContent = [state.collection ? api.collections[state.collection] : "All collections", state.language || "All languages", state.q.trim() ? `Search: ${state.q.trim()}` : "No search restriction"].join(" · ");
    byId("source-empty").hidden = matches.length > 0;
    more.hidden = shown >= matches.length;
    more.textContent = `Show ${Math.min(pageSize, Math.max(0, matches.length - shown))} more files`;
    download.disabled = matches.length === 0;
    reset.disabled = Object.keys(api.defaults).every(key => state[key] === api.defaults[key]);
  }
  controls.forEach(control => { control.disabled = true; });
  fetch("code/source-catalog.json", { cache: "no-cache" })
    .then(response => { if (!response.ok) throw new Error("Source catalog unavailable"); return response.json(); })
    .then(catalog => {
      files = api.prepare(catalog);
      state = api.fromSearch(window.location.search, files);
      for (const label of [...new Set(files.map(file => file.language))].sort()) {
        const option = element("option", label); option.value = label; language.append(option);
      }
      const present = new Set(files.map(file => file.collection));
      for (const [value, label] of [["", "All source"], ...Object.entries(api.collections).filter(([value]) => present.has(value))]) {
        const button = element("button"); button.type = "button"; button.dataset.collection = value;
        button.append(element("span", label), element("span", "", "filter-count"));
        button.addEventListener("click", () => change({ collection: value })); chips.append(button);
      }
      controls.forEach(control => { control.disabled = false; });
      loaded = true;
      byId("catalog-total").textContent = files.length.toLocaleString("en-US");
      byId("catalog-languages").textContent = new Set(files.map(file => file.language)).size;
      syncURL("replace"); render();
    })
    .catch(() => {
      status.textContent = "The source catalog could not be loaded. Use the direct GitHub folders below or reload this page. No prediction service is involved.";
      byId("source-fallback").hidden = false;
    });
  search.addEventListener("input", () => change({ q: search.value }, "replace"));
  language.addEventListener("change", () => change({ language: language.value }));
  sort.addEventListener("change", () => change({ sort: sort.value }));
  reset.addEventListener("click", () => { change(api.defaults); search.focus(); });
  byId("source-empty-reset").addEventListener("click", () => { change(api.defaults); search.focus(); });
  more.addEventListener("click", () => {
    const prior = shown; shown += pageSize; render();
    const next = results.children[prior]; if (next) next.querySelector("a").focus();
  });
  download.addEventListener("click", () => {
    if (!loaded) return;
    const blob = new Blob([JSON.stringify(api.exportMatches(files, state), null, 2) + "\n"], { type: "application/json" });
    const url = URL.createObjectURL(blob), link = element("a");
    link.href = url; link.download = "neuralfoil-source-selection.json";
    document.body.append(link); link.click(); link.remove();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  });
  window.addEventListener("popstate", () => {
    if (!loaded) return;
    state = api.fromSearch(window.location.search, files); shown = pageSize;
    permalink.href = `${window.location.pathname}${api.toSearch(state)}#source`; render();
  });
})();
