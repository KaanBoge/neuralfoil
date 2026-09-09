"use strict";
/* Read-only source catalog UI. No model execution, tracking or third-party JS. */
(() => {
  const search = document.getElementById("source-search");
  const language = document.getElementById("source-language");
  const status = document.getElementById("source-status");
  const results = document.getElementById("source-results");
  const more = document.getElementById("source-more");
  const pageSize = 12;
  let files = [];
  let shown = pageSize;

  function validFile(file) {
    return file && typeof file.path === "string" && file.path.length > 0 &&
      !file.path.startsWith("/") && !file.path.includes("\\") &&
      file.path.split("/").every(part => part && part !== "." && part !== "..") &&
      typeof file.language === "string" && typeof file.role === "string" &&
      Number.isSafeInteger(file.bytes) && file.bytes >= 0 &&
      typeof file.sha256 === "string" && /^[a-f0-9]{64}$/.test(file.sha256);
  }

  function render() {
    const query = search.value.toLocaleLowerCase().trim();
    const filtered = files.filter(file =>
      (!language.value || file.language === language.value) &&
      (!query || `${file.path} ${file.role}`.toLocaleLowerCase().includes(query)));
    results.replaceChildren();
    for (const file of filtered.slice(0, shown)) {
      const row = document.createElement("li");
      const link = document.createElement("a");
      link.textContent = file.path;
      link.href = "https://github.com/KaanBoge/neuralfoil/blob/main/" +
        file.path.split("/").map(encodeURIComponent).join("/");
      const meta = document.createElement("small");
      const bytes = file.bytes < 1000 ? `${file.bytes} B` : `${(file.bytes / 1000).toFixed(1)} kB`;
      meta.textContent = `${file.language} · ${bytes} · ${file.role.replaceAll("_", " ")}`;
      row.append(link, meta);
      results.append(row);
    }
    status.textContent = filtered.length
      ? `Showing ${Math.min(shown, filtered.length)} of ${filtered.length} matching files · ${files.length} cataloged source files in this release.`
      : `No matching source files. Try a different filename or language. ${files.length} files are cataloged.`;
    more.hidden = shown >= filtered.length;
  }

  search.disabled = true;
  language.disabled = true;
  fetch("code/source-catalog.json", { cache: "no-cache" })
    .then(response => {
      if (!response.ok) throw new Error("Source catalog unavailable");
      return response.json();
    })
    .then(catalog => {
      if (catalog.schema !== "source-catalog-v1" || !Array.isArray(catalog.files) ||
          !catalog.files.every(validFile) || new Set(catalog.files.map(file => file.path)).size !== catalog.files.length) {
        throw new Error("Invalid source catalog");
      }
      files = [...catalog.files].sort((a, b) => a.path.localeCompare(b.path));
      for (const label of [...new Set(files.map(file => file.language))].sort()) {
        const option = document.createElement("option");
        option.value = label;
        option.textContent = label;
        language.append(option);
      }
      search.disabled = false;
      language.disabled = false;
      render();
    })
    .catch(() => {
      status.textContent = "The source catalog could not be loaded. Use the GitHub source guide or repository download below; no prediction service is involved.";
    });
  search.addEventListener("input", () => { shown = pageSize; render(); });
  language.addEventListener("change", () => { shown = pageSize; render(); });
  more.addEventListener("click", () => { shown += pageSize; render(); });
})();
