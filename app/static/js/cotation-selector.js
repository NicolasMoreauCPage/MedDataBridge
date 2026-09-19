/* Recherche et sélection d'un séjour pour la saisie des cotations. */
(function () {
  "use strict";

  const escapeHtml = (value) =>
    String(value ?? "")
      .replaceAll("&", "&amp;")
      .replaceAll("<", "&lt;")
      .replaceAll(">", "&gt;")
      .replaceAll('"', "&quot;")
      .replaceAll("'", "&#039;");

  const highlightMatch = (text, query) => {
    const escapedText = escapeHtml(text);
    if (!query) return escapedText;
    const escapedQuery = escapeHtml(query).replace(/[.*+?^${}()|[\]\\]/g, "\\$&");
    return escapedText.replace(
      new RegExp(escapedQuery, "ig"),
      (match) => `<mark class="bg-yellow-100 text-yellow-800 rounded-sm px-0.5">${match}</mark>`,
    );
  };

  function setupCotationSelector() {
    const input = document.getElementById("searchInput");
    const button = document.getElementById("searchBtn");
    const results = document.getElementById("results");
    const pagination = document.getElementById("pagination");
    if (!input || !button || !results || !pagination || !window.medbridgeHttp) return;

    let currentResults = [];
    let highlightedIndex = -1;
    let currentQuery = "";
    let requestController = null;
    let debounceTimer = null;

    const resetExpanded = () => input.setAttribute("aria-expanded", "false");

    function renderResults(payload) {
      currentResults = payload.results || [];
      const meta = payload.meta || { total: 0, page: 1, per_page: 20 };
      if (!currentResults.length) {
        results.innerHTML = '<div class="text-slate-500">Aucun dossier trouvé.</div>';
        pagination.innerHTML = "";
        resetExpanded();
        return;
      }

      results.innerHTML = currentResults
        .map(
          (dossier, index) => `
            <div role="option" data-result-index="${index}" tabindex="-1" class="result-item p-3 bg-white rounded-lg border border-slate-200 flex items-center justify-between ${index === highlightedIndex ? "ring-2 ring-primary/30" : ""}">
              <div>
                <div class="font-semibold">Dossier #${escapeHtml(dossier.dossier_seq || dossier.dossier_id)} — ${highlightMatch(dossier.patient_family, currentQuery)} ${highlightMatch(dossier.patient_given, currentQuery)}</div>
                <div class="text-sm text-slate-500">ID: ${escapeHtml(dossier.dossier_id)} • Patient ID: ${escapeHtml(dossier.patient_id)}</div>
              </div>
              <a href="/cotation-modern/dossiers/${encodeURIComponent(dossier.dossier_id)}/cotation" class="btn-primary">Ouvrir</a>
            </div>`,
        )
        .join("");
      input.setAttribute("aria-expanded", "true");

      const total = meta.total || 0;
      const page = meta.page || 1;
      const perPage = meta.per_page || currentResults.length;
      const totalPages = Math.max(1, Math.ceil(total / perPage));
      pagination.innerHTML = [
        page > 1 ? '<button type="button" data-page="previous" class="px-3 py-1 rounded border">Précédent</button>' : "",
        `<span>Page ${page} / ${totalPages} — ${total} résultats</span>`,
        page < totalPages ? '<button type="button" data-page="next" class="px-3 py-1 rounded border">Suivant</button>' : "",
      ].join(" ");
      pagination.querySelector("[data-page='previous']")?.addEventListener("click", () => performSearch(currentQuery, page - 1));
      pagination.querySelector("[data-page='next']")?.addEventListener("click", () => performSearch(currentQuery, page + 1));
    }

    async function performSearch(query, page = 1) {
      const normalizedQuery = query.trim();
      if (!normalizedQuery) {
        currentResults = [];
        results.innerHTML = "";
        pagination.innerHTML = "";
        resetExpanded();
        return;
      }
      requestController?.abort();
      requestController = new AbortController();
      currentQuery = normalizedQuery;
      highlightedIndex = -1;
      results.innerHTML = '<div class="text-slate-500" aria-live="polite">Recherche en cours...</div>';
      button.disabled = true;
      try {
        const { data } = await window.medbridgeHttp.get(
          `/cotation-modern/search?q=${encodeURIComponent(normalizedQuery)}&page=${page}`,
          { signal: requestController.signal },
        );
        renderResults(data);
      } catch (error) {
        if (requestController.signal.aborted) return;
        results.innerHTML = `<div class="text-red-600" role="alert">Erreur : ${escapeHtml(error.message || "recherche indisponible")}</div>`;
        pagination.innerHTML = "";
        resetExpanded();
      } finally {
        button.disabled = false;
      }
    }

    button.addEventListener("click", (event) => {
      event.preventDefault();
      void performSearch(input.value);
    });
    input.addEventListener("input", () => {
      globalThis.clearTimeout(debounceTimer);
      debounceTimer = globalThis.setTimeout(() => void performSearch(input.value), 300);
    });
    input.addEventListener("keydown", (event) => {
      const items = Array.from(results.querySelectorAll(".result-item"));
      if (event.key === "ArrowDown" && items.length) {
        event.preventDefault();
        highlightedIndex = Math.min(items.length - 1, highlightedIndex + 1);
        items[highlightedIndex].focus();
      } else if (event.key === "ArrowUp" && items.length) {
        event.preventDefault();
        highlightedIndex = Math.max(0, highlightedIndex - 1);
        items[highlightedIndex].focus();
      } else if (event.key === "Enter") {
        event.preventDefault();
        void performSearch(input.value);
      }
    });
    results.addEventListener("click", (event) => {
      const item = event.target.closest("[data-result-index]");
      if (!item || event.target.closest("a")) return;
      const dossier = currentResults[Number(item.dataset.resultIndex)];
      if (dossier) window.location.assign(`/cotation-modern/dossiers/${dossier.dossier_id}/cotation`);
    });
    results.addEventListener("keydown", (event) => {
      if (event.key === "Enter" && document.activeElement?.matches("[data-result-index]")) {
        document.activeElement.click();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", setupCotationSelector);
})();
