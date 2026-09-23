/* Assistant de création : progression courte, validation locale et clé proposée. */
(function () {
  "use strict";

  const labels = { template: "Parcours type", duplicate: "Duplication d'un scénario", manual: "Scénario vide (mode expert)" };
  const selectedMode = (form) => form.querySelector("[data-creation-mode]:checked")?.value || "template";

  function updateModeContent(form) {
    const mode = selectedMode(form);
    form.querySelectorAll("[data-mode-content]").forEach((element) => {
      const visible = element.dataset.modeContent === mode;
      element.hidden = !visible;
      // Certaines sections utilisent une classe Tailwind comme `grid`, dont
      // la règle CSS peut primer sur l'attribut HTML `hidden`. Le style
      // explicite garantit qu'un mode non choisi ne laisse pas ses champs
      // désactivés visibles à l'écran.
      element.style.display = visible ? "" : "none";
      element.querySelectorAll("input, select, textarea").forEach((field) => { field.disabled = !visible; });
    });
    form.querySelectorAll("[data-creation-mode]").forEach((input) => {
      input.closest("label")?.classList.toggle("border-violet-500", input.checked);
      input.closest("label")?.classList.toggle("ring-2", input.checked);
    });
  }

  function renderSummary(form) {
    const target = form.querySelector("[data-builder-summary]");
    if (!target) return;
    const mode = selectedMode(form);
    const template = form.querySelector("[data-template-choice]:checked");
    const source = form.querySelector("[data-source-scenario]")?.selectedOptions[0]?.text || "À sélectionner";
    const origin = mode === "template"
      ? template?.closest("label")?.querySelector(".font-semibold")?.textContent.trim() || "Modèle à sélectionner"
      : mode === "duplicate" ? source : "Création manuelle";
    const fields = [
      ["Nom", form.querySelector("[data-builder-name]")?.value.trim() || "Nom à renseigner"],
      ["Méthode", labels[mode]], ["Parcours source", origin],
      ["Clé", form.querySelector("[data-builder-key]")?.value.trim() || "générée automatiquement"],
      ["Objectif", form.querySelector("[name='description']")?.value.trim() || "Aucun objectif précisé"],
    ];
    target.replaceChildren();
    fields.forEach(([label, value]) => {
      const row = document.createElement("div");
      row.className = "grid grid-cols-[9rem_1fr] gap-3 border-b border-slate-200 py-2 text-sm last:border-0 dark:border-slate-700";
      const term = document.createElement("strong"); term.textContent = label;
      const detail = document.createElement("span"); detail.textContent = value;
      row.append(term, detail); target.append(row);
    });
  }

  function validateStep(form, step) {
    const mode = selectedMode(form);
    if (step === 2) {
      const name = form.querySelector("[data-builder-name]");
      if (!name?.value.trim()) { name?.focus(); window.toastSystem?.show?.("Le nom du scénario est obligatoire.", "warning"); return false; }
    }
    if (step === 3 && mode === "template" && !form.querySelector("[data-template-choice]:checked")) { window.toastSystem?.show?.("Choisissez un parcours type.", "warning"); return false; }
    if (step === 3 && mode === "duplicate" && !form.querySelector("[data-source-scenario]")?.value) { form.querySelector("[data-source-scenario]")?.focus(); window.toastSystem?.show?.("Choisissez le scénario à dupliquer.", "warning"); return false; }
    return true;
  }

  function bindKeySuggestion(form) {
    const name = form.querySelector("[data-builder-name]");
    const key = form.querySelector("[data-builder-key]");
    const help = form.querySelector("[data-key-help]");
    let timer, controller;
    async function check() {
      if (!(key?.value.trim() || name?.value.trim()) || !window.medbridgeHttp) return;
      controller?.abort(); controller = new AbortController();
      try {
        const parameters = new URLSearchParams({ name: name?.value.trim() || "", key: key?.value.trim() || "" });
        const { data } = await window.medbridgeHttp.get(`/scenarios/new/key-availability?${parameters}`, { signal: controller.signal });
        if (!controller.signal.aborted && help) help.textContent = data.available ? `Clé « ${data.suggested_key} » disponible.` : `Clé proposée : « ${data.suggested_key} » (utilisée si ce champ est vide).`;
      } catch (_) { if (help) help.textContent = "La clé sera vérifiée lors de la création."; }
    }
    [name, key].forEach((field) => field?.addEventListener("input", () => { clearTimeout(timer); timer = setTimeout(check, 250); }));
  }

  function bindUnsavedChanges(form) {
    const status = form.querySelector("[data-builder-dirty-status]");
    const cancel = form.querySelector("[data-builder-cancel]");
    let dirty = false;
    const setDirty = (value) => {
      dirty = value;
      if (status) status.hidden = !value;
    };
    const markDirty = (event) => {
      if (event.target instanceof HTMLInputElement || event.target instanceof HTMLSelectElement || event.target instanceof HTMLTextAreaElement) setDirty(true);
    };
    form.addEventListener("input", markDirty);
    form.addEventListener("change", markDirty);
    cancel?.addEventListener("click", (event) => {
      if (!dirty || window.confirm("Quitter sans enregistrer les modifications ?")) return;
      event.preventDefault();
    });
    window.addEventListener("beforeunload", (event) => {
      if (!dirty) return;
      event.preventDefault();
      event.returnValue = "";
    });
    return { markClean: () => setDirty(false) };
  }

  document.addEventListener("DOMContentLoaded", () => {
    const root = document.querySelector("[data-scenario-builder]");
    const form = root?.querySelector("[data-builder-form]");
    if (!root || !form) return;
    let current = 1;
    const panels = [...form.querySelectorAll("[data-builder-panel]")];
    const previous = form.querySelector("[data-builder-previous]");
    const next = form.querySelector("[data-builder-next]");
    const submit = form.querySelector("[data-builder-submit]");
    const unsavedChanges = bindUnsavedChanges(form);
    const show = (step) => {
      current = Math.min(5, Math.max(1, step));
      panels.forEach((panel) => { panel.hidden = Number(panel.dataset.builderPanel) !== current; });
      root.querySelectorAll("[data-builder-go]").forEach((button) => {
        const active = Number(button.dataset.builderGo) === current;
        button.classList.toggle("bg-violet-600", active); button.classList.toggle("text-white", active); button.setAttribute("aria-current", active ? "step" : "false");
      });
      previous.classList.toggle("hidden", current === 1); next.classList.toggle("hidden", current === 5); submit.classList.toggle("hidden", current !== 5);
      if (current === 3 || current === 4) updateModeContent(form);
      if (current === 5) renderSummary(form);
    };
    form.querySelectorAll("[data-creation-mode]").forEach((input) => input.addEventListener("change", () => updateModeContent(form)));
    root.querySelectorAll("[data-builder-go]").forEach((button) => button.addEventListener("click", () => { const target = Number(button.dataset.builderGo); if (target <= current || validateStep(form, current)) show(target); }));
    previous.addEventListener("click", () => show(current - 1));
    next.addEventListener("click", () => { if (validateStep(form, current)) show(current + 1); });
    form.addEventListener("submit", (event) => { if (![2, 3].every((step) => validateStep(form, step))) { event.preventDefault(); return; } unsavedChanges.markClean(); submit.disabled = true; submit.textContent = "Création du brouillon…"; });
    bindKeySuggestion(form); updateModeContent(form); show(1);
  });
})();
