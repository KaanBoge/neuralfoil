/* Deterministic catalog navigation; no model or scientific-status classification. */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.SourceBrowser = api;
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const collections = Object.freeze({
    research: "Research archive", supplement: "Source supplement", study: "Legacy study",
    browser: "Browser application", checks: "Public checks & examples", other: "Other source"
  });
  const sorts = Object.freeze({ path: "Folder / path", name: "Filename", largest: "Largest first", smallest: "Smallest first" });
  const defaults = Object.freeze({ q: "", collection: "", language: "", sort: "path" });
  const compare = (a, b) => a < b ? -1 : a > b ? 1 : 0;
  const searchable = value => value.toLowerCase().replace(/[_/.-]+/g, " ");
  function validFile(file) {
    return !!file && typeof file.path === "string" && file.path.length > 0 &&
      !file.path.startsWith("/") && !/[\\\u0000-\u001f\u007f]/.test(file.path) &&
      file.path.split("/").every(part => part && part !== "." && part !== ".." && part !== ".git") &&
      typeof file.language === "string" && !!file.language && typeof file.role === "string" &&
      Number.isSafeInteger(file.bytes) && file.bytes >= 0 &&
      typeof file.sha256 === "string" && /^[a-f0-9]{64}$/.test(file.sha256);
  }
  function collectionFor(path) {
    if (path.startsWith("code/research/")) return "research";
    if (path.startsWith("code/supplement/")) return "supplement";
    if (path.startsWith("study/")) return "study";
    if (/^(tools|tests|examples|\.github)\//.test(path)) return "checks";
    if (!path.includes("/") && /\.(html|css|js)$/.test(path)) return "browser";
    return "other";
  }
  function prepare(catalog) {
    if (!catalog || catalog.schema !== "source-catalog-v1" || !Array.isArray(catalog.files) ||
        !catalog.files.every(validFile) || new Set(catalog.files.map(file => file.path)).size !== catalog.files.length) {
      throw new Error("Invalid source catalog");
    }
    return catalog.files.map(file => {
      const collection = collectionFor(file.path);
      const name = file.path.split("/").pop();
      return { ...file, collection, name, search: searchable(`${file.path} ${file.role} ${file.language} ${collections[collection]}`) };
    });
  }
  function normalize(state, files) {
    const languages = new Set(files.map(file => file.language));
    return {
      q: typeof state.q === "string" ? state.q.slice(0, 300) : "",
      collection: Object.hasOwn(collections, state.collection) ? state.collection : "",
      language: languages.has(state.language) ? state.language : "",
      sort: Object.hasOwn(sorts, state.sort) ? state.sort : "path"
    };
  }
  function fromSearch(search, files) {
    const params = new URLSearchParams(search);
    return normalize(Object.fromEntries(Object.keys(defaults).map(key => [key, params.get(key)])), files);
  }
  function toSearch(state) {
    const params = new URLSearchParams();
    for (const key of Object.keys(defaults)) if (state[key] && state[key] !== defaults[key]) params.set(key, state[key]);
    return params.size ? `?${params}` : "";
  }
  function select(files, state) {
    const tokens = searchable(state.q).split(/\s+/).filter(Boolean);
    const queried = files.filter(file => tokens.every(token => file.search.includes(token)));
    const collectionCounts = Object.fromEntries(["", ...Object.keys(collections)].map(key => [key, 0]));
    const languageCounts = Object.create(null);
    languageCounts[""] = 0;
    for (const file of queried) {
      if (!state.language || file.language === state.language) {
        collectionCounts[""]++; collectionCounts[file.collection]++;
      }
      if (!state.collection || file.collection === state.collection) {
        languageCounts[""]++; languageCounts[file.language] = (languageCounts[file.language] || 0) + 1;
      }
    }
    const matches = queried.filter(file => (!state.collection || file.collection === state.collection) &&
      (!state.language || file.language === state.language));
    matches.sort((a, b) => {
      if (state.sort === "name") return compare(a.name, b.name) || compare(a.path, b.path);
      if (state.sort === "largest") return b.bytes - a.bytes || compare(a.path, b.path);
      if (state.sort === "smallest") return a.bytes - b.bytes || compare(a.path, b.path);
      return compare(a.path, b.path);
    });
    return { matches, collectionCounts, languageCounts };
  }
  function sourceURL(path, raw = false) {
    const prefix = raw ? "https://raw.githubusercontent.com/KaanBoge/neuralfoil/main/" : "https://github.com/KaanBoge/neuralfoil/blob/main/";
    return prefix + path.split("/").map(encodeURIComponent).join("/");
  }
  function formatBytes(bytes) {
    return bytes < 1000 ? `${bytes} B` : bytes < 1000000 ? `${(bytes / 1000).toFixed(1)} kB` : `${(bytes / 1000000).toFixed(2)} MB`;
  }
  function exportMatches(files, state) {
    return { schema: "source-catalog-selection-v1", scope: "Published source metadata only; not model outputs or experimental data",
      filters: { ...state }, files: select(files, state).matches.map(({ path, bytes, sha256, language, role }) => ({ path, bytes, sha256, language, role })) };
  }
  return Object.freeze({ collections, sorts, defaults, validFile, collectionFor, prepare, normalize, fromSearch, toSearch, select, sourceURL, formatBytes, exportMatches });
});
