/* Interactions localisées de l'atelier de validation. */
(function () {
  "use strict";

  function setupTabs() {
    const workspace = document.querySelector("[data-validation-workspace]");
    if (!workspace) return;

    const tabs = Array.from(workspace.querySelectorAll("[data-validation-tab]"));
    const panels = {
      single: workspace.querySelector("#form-single"),
      scenario: workspace.querySelector("#form-scenario"),
    };

    const activate = (mode, focus = false) => {
      if (!panels[mode]) return;
      tabs.forEach((tab) => {
        const selected = tab.dataset.validationTab === mode;
        tab.setAttribute("aria-selected", String(selected));
        tab.classList.toggle("border-blue-500", selected);
        tab.classList.toggle("text-blue-600", selected);
        tab.classList.toggle("dark:text-blue-400", selected);
        tab.classList.toggle("border-transparent", !selected);
        tab.classList.toggle("text-gray-500", !selected);
        tab.classList.toggle("dark:text-slate-400", !selected);
        if (selected && focus) tab.focus();
      });
      Object.entries(panels).forEach(([name, panel]) => {
        if (panel) panel.classList.toggle("hidden", name !== mode);
      });
    };

    tabs.forEach((tab, index) => {
      tab.addEventListener("click", () => activate(tab.dataset.validationTab));
      tab.addEventListener("keydown", (event) => {
        if (!["ArrowLeft", "ArrowRight", "Home", "End"].includes(event.key)) return;
        event.preventDefault();
        let nextIndex = index;
        if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
        if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
        if (event.key === "Home") nextIndex = 0;
        if (event.key === "End") nextIndex = tabs.length - 1;
        activate(tabs[nextIndex].dataset.validationTab, true);
      });
    });

    activate(workspace.dataset.initialMode || "single");
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupTabs();
    const results = document.querySelector("[data-validation-results]");
    if (results) results.scrollIntoView({ behavior: "smooth", block: "start" });
  });
})();
