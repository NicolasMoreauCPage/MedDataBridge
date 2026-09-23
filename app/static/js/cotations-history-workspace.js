/* Filtres, actions groupées et édition de l'historique de cotations. */
(function () {
  "use strict";

  const root = document.querySelector("[data-cotations-history-workspace]");
  if (!root) return;

  const selection = new Set();
  let editingActe = null;
  const byId = (id) => document.getElementById(id);
  const rows = () => Array.from(root.querySelectorAll(".acte-row"));
  const checkboxes = () => Array.from(root.querySelectorAll(".acte-checkbox"));
  const notify = (message, kind) => window.showNotification?.(message, kind)
    || window.toastSystem?.show?.(message, kind)
    || console.info(message);

  function updateBulkActions() {
    const count = selection.size;
    byId("selected-count").textContent = String(count);
    byId("bulk-actions").classList.toggle("hidden", count === 0);
  }

  function syncSelectAll() {
    const visible = checkboxes().filter((checkbox) => !checkbox.closest(".acte-row").hidden);
    const checkbox = byId("select-all");
    checkbox.checked = visible.length > 0 && visible.every((item) => item.checked);
    checkbox.indeterminate = visible.some((item) => item.checked) && !checkbox.checked;
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
    ["filter-type", "filter-statut", "filter-date-debut", "filter-date-fin"].forEach((id) => { byId(id).value = ""; });
    applyFilters();
  }

  function deselectAll() {
    selection.clear();
    checkboxes().forEach((checkbox) => { checkbox.checked = false; });
    syncSelectAll();
    updateBulkActions();
  }

  function selectedActePayload() {
    return Array.from(selection).map((value) => {
      const [type, id] = value.split(":", 2);
      return { type, id: Number(id) };
    }).filter((item) => item.type && Number.isInteger(item.id) && item.id > 0);
  }

  async function runBulkAction(action, label, actes = selectedActePayload()) {
    if (!actes.length) return;
    if (!window.PameliaUi?.confirm) {
      notify("Le dialogue de confirmation n’est pas disponible.", "error");
      return;
    }
    const confirmed = await window.PameliaUi.confirm({
      title: action === "delete" ? "Supprimer des actes" : "Confirmer l’action",
      message: `${label} ${actes.length} acte(s) ?`,
      acceptLabel: label,
      variant: action === "delete" ? "danger" : "primary",
    });
    if (!confirmed) return;
    try {
      const { data } = await window.medbridgeHttp.post("/cotations/api/bulk", { action, actes });
      notify(data.message || `${actes.length} acte(s) mis à jour`, "success");
      window.setTimeout(() => window.location.reload(), 350);
    } catch (error) {
      notify(`Erreur : ${error.message}`, "error");
    }
  }

  async function editActe(type, id) {
    try {
      const { data: acte } = await window.medbridgeHttp.get(`/cotations/api/${encodeURIComponent(type)}/${id}`);
      editingActe = acte;
      byId("edit-cotation-title").textContent = `Acte ${acte.type.toUpperCase()} #${acte.id}`;
      byId("edit-cotation-date").value = acte.execute_date ? acte.execute_date.slice(0, 16) : "";
      byId("edit-cotation-quantity").value = acte.quantity ?? 1;
      byId("edit-cotation-amount").value = acte.amount ?? "";
      byId("edit-cotation-comment").value = acte.commentaire ?? "";
      byId("edit-cotation-quantity-label").textContent = acte.type === "ngap" ? "Dénombrement" : "Quantité";
      byId("edit-cotation-amount-label").textContent = ["ucd", "lpp"].includes(acte.type) ? "Montant unitaire TTC" : "Montant total";
      byId("edit-cotation-dialog").showModal();
    } catch (error) {
      notify(`Erreur : ${error.message}`, "error");
    }
  }

  function closeEditActe() {
    editingActe = null;
    byId("edit-cotation-dialog").close();
  }

  root.addEventListener("change", (event) => {
    const target = event.target;
    if (!(target instanceof HTMLElement)) return;
    if (target.matches("[data-cotations-history-filter]")) {
      applyFilters();
    } else if (target.matches("[data-cotations-history-select-all]")) {
      checkboxes().forEach((checkbox) => {
        if (checkbox.closest(".acte-row").hidden) return;
        checkbox.checked = target.checked;
        if (target.checked) selection.add(checkbox.value);
        else selection.delete(checkbox.value);
      });
      updateBulkActions();
    } else if (target.matches(".acte-checkbox")) {
      if (target.checked) selection.add(target.value);
      else selection.delete(target.value);
      syncSelectAll();
      updateBulkActions();
    }
  });

  document.addEventListener("click", (event) => {
    const button = event.target.closest("[data-cotations-history-action]");
    if (!(button instanceof HTMLElement)) return;
    const action = button.dataset.cotationsHistoryAction;
    if (action === "toggle-filters") {
      const panel = byId("filters-panel");
      const willShow = panel.classList.contains("hidden");
      panel.classList.toggle("hidden", !willShow);
      button.setAttribute("aria-expanded", String(willShow));
    } else if (action === "reset-filters") resetFilters();
    else if (action === "deselect-all") deselectAll();
    else if (action === "validate-selected") void runBulkAction("validate", "Valider");
    else if (action === "invoice-selected") void runBulkAction("invoice", "Marquer comme facturé");
    else if (action === "delete-selected") void runBulkAction("delete", "Supprimer définitivement");
    else if (action === "delete-one") void runBulkAction("delete", "Supprimer définitivement", [{ type: button.dataset.acteType, id: Number(button.dataset.acteId) }]);
    else if (action === "edit") void editActe(button.dataset.acteType, Number(button.dataset.acteId));
    else if (action === "close-edit") closeEditActe();
  });

  byId("edit-cotation-form")?.addEventListener("submit", async (event) => {
    event.preventDefault();
    if (!editingActe) return;
    const payload = {
      execute_date: byId("edit-cotation-date").value,
      quantity: Number(byId("edit-cotation-quantity").value),
      amount: byId("edit-cotation-amount").value || null,
      commentaire: byId("edit-cotation-comment").value || null,
    };
    try {
      const { data } = await window.medbridgeHttp.request(`/cotations/api/${editingActe.type}/${editingActe.id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      if (!data.success) throw new Error(data.detail || "Modification impossible");
      closeEditActe();
      notify("Acte modifié avec succès.", "success");
      window.setTimeout(() => window.location.reload(), 350);
    } catch (error) {
      notify(`Erreur : ${error.message}`, "error");
    }
  });
})();
