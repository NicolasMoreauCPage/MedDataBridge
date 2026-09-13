/* Comportements partagés des catalogues rendus par list.html. */
(function () {
  "use strict";

  const notify = (message, kind = "info") => window.toastSystem?.show(message, kind);

  function setupFilters(config) {
    const trigger = document.getElementById("toggle-filters-btn");
    const panel = document.getElementById("list-filters-panel");
    if (trigger && panel) {
      trigger.addEventListener("click", () => {
        const open = panel.hasAttribute("hidden");
        panel.toggleAttribute("hidden", !open);
        trigger.setAttribute("aria-expanded", String(open));
        if (open) panel.querySelector("input, select, textarea")?.focus();
      });
    }

    document.querySelectorAll("[data-submit-on-change]").forEach((field) => {
      field.addEventListener("change", () => field.form?.requestSubmit());
    });

    document.addEventListener("keydown", (event) => {
      const tagName = event.target?.tagName;
      const isEditing = ["INPUT", "TEXTAREA", "SELECT"].includes(tagName) || event.target?.isContentEditable;
      if (config.newUrl && (event.ctrlKey || event.metaKey) && event.key?.toLowerCase() === "n") {
        event.preventDefault();
        window.location.assign(config.newUrl);
      } else if (event.key === "/" && !event.ctrlKey && !event.metaKey && !event.altKey && !isEditing && panel) {
        event.preventDefault();
        panel.removeAttribute("hidden");
        trigger?.setAttribute("aria-expanded", "true");
        panel.querySelector("input, select, textarea")?.focus();
      } else if ((event.key === "Escape" || event.key === "Esc") && panel && !panel.hasAttribute("hidden")) {
        panel.setAttribute("hidden", "hidden");
        trigger?.setAttribute("aria-expanded", "false");
        trigger?.focus();
      }
    });
  }

  function setupRows() {
    document.querySelectorAll('tr[role="link"][tabindex="0"]').forEach((row) => {
      const open = () => {
        if (row.dataset.detailUrl) window.location.assign(row.dataset.detailUrl);
      };
      row.addEventListener("click", open);
      row.addEventListener("keydown", (event) => {
        if (event.key === "Enter" || event.key === " ") {
          event.preventDefault();
          open();
        }
      });
    });
    document.querySelectorAll('tr[role="link"] a, tr[role="link"] button, tr[role="link"] form, tr[role="link"] input').forEach((element) => {
      element.addEventListener("click", (event) => event.stopPropagation());
    });
    document.querySelectorAll("[data-page-size]").forEach((select) => {
      select.addEventListener("change", () => {
        const url = new URL(window.location.href);
        url.searchParams.set(select.dataset.pageSizeParam || "page_size", select.value);
        url.searchParams.set("page", "1");
        window.location.assign(url.toString());
      });
    });
  }

  function setupBulkExecution() {
    const button = document.getElementById("bulkSubmitBtn");
    const endpointSelect = document.getElementById("bulkEndpoint");
    if (!button || !endpointSelect) return;
    const selectedIds = () => Array.from(document.querySelectorAll("input.row-select:checked"), (element) => element.value);
    const refresh = () => {
      const selected = selectedIds();
      const counter = document.getElementById("bulkSelectedCount");
      if (counter) counter.textContent = selected.length;
      button.disabled = !(selected.length && endpointSelect.value);
    };
    document.querySelectorAll("input.row-select").forEach((input) => input.addEventListener("change", refresh));
    endpointSelect.addEventListener("change", refresh);
    button.addEventListener("click", () => {
      const scenarioIds = selectedIds();
      if (!scenarioIds.length || !endpointSelect.value) {
        notify("Sélectionnez au moins un scénario et un endpoint.", "warning");
        return;
      }
      const form = document.createElement("form");
      form.method = "post";
      form.action = "/scenarios/bulk-execute";
      [["endpoint_id", endpointSelect.value], ...scenarioIds.map((id) => ["scenario_ids", id])].forEach(([name, value]) => {
        const input = document.createElement("input");
        input.type = "hidden";
        input.name = name;
        input.value = value;
        form.appendChild(input);
      });
      document.body.appendChild(form);
      form.submit();
    });
    refresh();
  }

  function setupDelete() {
    document.querySelectorAll(".delete-btn").forEach((button) => {
      button.addEventListener("click", async (event) => {
        event.preventDefault();
        event.stopPropagation();
        const form = button.closest("form");
        if (!form) return;
        const itemName = form.dataset.itemName || "cet élément";
        const confirmed = await window.PameliaUi.confirm({
          title: "Confirmer la suppression",
          message: "Supprimer « " + itemName + " » ? Cette action est irréversible.",
          acceptLabel: "Supprimer",
          variant: "danger",
        });
        if (!confirmed) return;

        const initialLabel = button.textContent;
        button.disabled = true;
        button.textContent = "Suppression…";
        try {
          const response = await fetch(form.action, {
            method: "POST",
            body: new FormData(form),
            headers: { "X-Requested-With": "XMLHttpRequest" },
          });
          if (response.redirected) {
            window.location.assign(response.url);
          } else if (response.ok) {
            window.location.reload();
          } else {
            throw new Error("La suppression a été refusée.");
          }
        } catch (error) {
          notify(error.message || "Erreur réseau. Veuillez réessayer.", "error");
          button.disabled = false;
          button.textContent = initialLabel;
        }
      });
    });
  }

  document.addEventListener("DOMContentLoaded", () => {
    const config = document.getElementById("list-workspace-config");
    setupFilters({ newUrl: config?.dataset.newUrl || "" });
    setupRows();
    setupBulkExecution();
    setupDelete();
  });
})();
