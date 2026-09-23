/* Interactions de la liste historique des cotations. */
(function () {
  "use strict";

  const root = document.querySelector("[data-cotations-list]");
  if (!root) return;

  const selection = new Map();
  const byId = (id) => root.querySelector(`#${id}`);
  const rows = () => Array.from(root.querySelectorAll(".acte-row"));
  const checkboxes = () => Array.from(root.querySelectorAll(".acte-checkbox"));

  function showToast(message, kind = "info") {
    const tones = {
      info: "bg-slate-800",
      success: "bg-emerald-600",
      warn: "bg-amber-500",
      error: "bg-red-600",
    };
    const stack = byId("toastStack");
    if (!stack) return;
    const item = document.createElement("div");
    item.className = `toast-enter ${tones[kind] || tones.info} text-white text-sm font-semibold px-4 py-3 rounded-xl shadow-xl`;
    item.textContent = message;
    stack.appendChild(item);
    window.setTimeout(() => item.remove(), 2600);
  }

  function selectionItem(checkbox) {
    const type = checkbox.dataset.acteType;
    const id = Number.parseInt(checkbox.dataset.acteId || "", 10);
    if (!type || Number.isNaN(id)) return null;
    return { key: `${type}:${id}`, type, id };
  }

  function updateBulkActions() {
    const count = selection.size;
    byId("selected-count").textContent = String(count);
    byId("bulk-actions").classList.toggle("hidden", count === 0);
  }

  function syncSelectAll() {
    const visible = checkboxes().filter((checkbox) => !checkbox.closest(".acte-row").hidden);
    const selectAll = byId("select-all");
    selectAll.checked = visible.length > 0 && visible.every((checkbox) => checkbox.checked);
    selectAll.indeterminate = visible.some((checkbox) => checkbox.checked) && !selectAll.checked;
  }

  function deselectAll() {
    selection.clear();
    checkboxes().forEach((checkbox) => { checkbox.checked = false; });
    syncSelectAll();
    updateBulkActions();
  }

  function applyFilters() {
    const type = byId("filter-type").value;
    const status = byId("filter-statut").value;
    const startDate = byId("filter-date-debut").value;
    const endDate = byId("filter-date-fin").value;

    rows().forEach((row) => {
      let visible = true;
      if (type && row.dataset.type !== type) visible = false;
      if (status === "valide" && row.dataset.valide !== "True") visible = false;
      if (status === "provisoire" && row.dataset.valide === "True") visible = false;
      if (status === "facture" && row.dataset.facture !== "True") visible = false;

      const date = row.dataset.date || "";
      if (startDate && date < startDate) visible = false;
      if (endDate && date > `${endDate}T23:59:59`) visible = false;
      row.hidden = !visible;
    });
    syncSelectAll();
  }

  function resetFilters() {
    ["filter-type", "filter-statut", "filter-date-debut", "filter-date-fin"].forEach((id) => {
      byId(id).value = "";
    });
    applyFilters();
  }

  function setButtonBusy(button, busy, busyText) {
    if (!button) return;
    if (!button.dataset.initialText) button.dataset.initialText = button.textContent.trim();
    button.disabled = busy;
    button.classList.toggle("btn-busy", busy);
    button.textContent = busy ? busyText : button.dataset.initialText;
  }

  async function confirmAction({ title, message, acceptLabel, variant }) {
    if (!window.PameliaUi?.confirm) {
      showToast("Le dialogue de confirmation n’est pas disponible.", "error");
      return false;
    }
    return window.PameliaUi.confirm({ title, message, acceptLabel, variant });
  }

  async function runBulkAction(action, items, button) {
    if (!items.length) {
      showToast("Sélectionnez au moins un acte.", "warn");
      return;
    }
    const labels = {
      validate: { verb: "valider", progress: "Validation...", accept: "Valider", variant: "primary" },
      invoice: { verb: "facturer", progress: "Facturation...", accept: "Facturer", variant: "primary" },
      delete: { verb: "supprimer définitivement", progress: "Suppression...", accept: "Supprimer", variant: "danger" },
    };
    const label = labels[action];
    if (!label) return;
    const confirmed = await confirmAction({
      title: `Confirmer : ${label.accept.toLowerCase()} les actes`,
      message: `Voulez-vous ${label.verb} ${items.length} acte(s) sélectionné(s) ?`,
      acceptLabel: label.accept,
      variant: label.variant,
    });
    if (!confirmed) return;

    setButtonBusy(button, true, label.progress);
    try {
      const { data } = await window.medbridgeHttp.post("/cotations/api/bulk", { action, actes: items });
      showToast(data.message || "Action enregistrée.", "success");
      window.setTimeout(() => window.location.reload(), 550);
    } catch (error) {
      console.error("Cotation bulk action failed", error);
      showToast(error.message || "Impossible d’enregistrer cette action.", "error");
      setButtonBusy(button, false);
    }
  }

  function exportCotations(button) {
    const visibleRows = rows().filter((row) => !row.hidden);
    if (!visibleRows.length) {
      showToast("Aucune cotation visible à exporter.", "warn");
      return;
    }
    setButtonBusy(button, true, "Export...");
    const columns = ["Type", "Code", "Libellé", "Date", "Quantité", "Montant", "Statut"];
    const values = visibleRows.map((row) => Array.from(row.querySelectorAll("td"))
      .slice(1, 8)
      .map((cell) => cell.textContent.replace(/\s+/g, " ").trim()));
    const toCsv = (value) => `"${String(value).replaceAll('"', '""')}"`;
    const csv = [columns, ...values].map((line) => line.map(toCsv).join(";")).join("\r\n");
    const url = URL.createObjectURL(new Blob([`\ufeff${csv}`], { type: "text/csv;charset=utf-8" }));
    const link = document.createElement("a");
    link.href = url;
    link.download = `cotations-dossier-${root.dataset.dossierId}.csv`;
    document.body.appendChild(link);
    link.click();
    link.remove();
    URL.revokeObjectURL(url);
    setButtonBusy(button, false);
    showToast(`${visibleRows.length} cotation(s) exportée(s).`, "success");
  }

  root.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.matches("[data-cotations-filter]")) {
      applyFilters();
      return;
    }
    if (target.matches("[data-cotations-select-all]")) {
      checkboxes().forEach((checkbox) => {
        if (checkbox.closest(".acte-row").hidden) return;
        checkbox.checked = target.checked;
        const item = selectionItem(checkbox);
        if (!item) return;
        if (target.checked) selection.set(item.key, { type: item.type, id: item.id });
        else selection.delete(item.key);
      });
      updateBulkActions();
      return;
    }
    if (target.matches(".acte-checkbox")) {
      const item = selectionItem(target);
      if (!item) return;
      if (target.checked) selection.set(item.key, { type: item.type, id: item.id });
      else selection.delete(item.key);
      syncSelectAll();
      updateBulkActions();
    }
  });

  root.addEventListener("click", (event) => {
    const button = event.target.closest("[data-cotations-action]");
    if (!(button instanceof HTMLElement)) return;
    const action = button.dataset.cotationsAction;
    if (action === "toggle-filters") {
      const panel = byId("filters-panel");
      const willShow = panel.classList.contains("hidden");
      panel.classList.toggle("hidden", !willShow);
      button.setAttribute("aria-expanded", String(willShow));
    } else if (action === "reset-filters") resetFilters();
    else if (action === "export") exportCotations(button);
    else if (action === "deselect-all") deselectAll();
    else if (action === "validate-selected") runBulkAction("validate", Array.from(selection.values()), button);
    else if (action === "invoice-selected") runBulkAction("invoice", Array.from(selection.values()), button);
    else if (action === "delete-selected") runBulkAction("delete", Array.from(selection.values()), button);
    else if (action === "delete-one") {
      const id = Number.parseInt(button.dataset.acteId || "", 10);
      const type = button.dataset.acteType;
      if (type && !Number.isNaN(id)) runBulkAction("delete", [{ type, id }], button);
    }
  });
})();
