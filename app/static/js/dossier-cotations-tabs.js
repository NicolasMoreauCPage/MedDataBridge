(() => {
  "use strict";

  const tabColors = {
    ccam: ["border-emerald-500", "text-emerald-600"],
    ngap: ["border-blue-500", "text-blue-600"],
    ucd: ["border-amber-500", "text-amber-600"],
    lpp: ["border-purple-500", "text-purple-600"],
  };
  const colorClasses = Object.values(tabColors).flat();

  function activateTab(tabName, shouldFocus = false) {
    const selectedTab = document.querySelector(`[data-cotation-tab="${tabName}"]`);
    const selectedPanel = document.getElementById(`content-${tabName}`);
    if (!selectedTab || !selectedPanel) return;

    document.querySelectorAll("[data-cotation-tab]").forEach((tab) => {
      tab.classList.remove(...colorClasses);
      tab.classList.add("border-transparent", "text-slate-500");
      tab.setAttribute("aria-selected", "false");
      tab.tabIndex = -1;
    });
    document.querySelectorAll(".tab-content").forEach((panel) => {
      panel.classList.add("hidden");
    });

    selectedPanel.classList.remove("hidden");
    selectedTab.classList.remove("border-transparent", "text-slate-500");
    selectedTab.classList.add(...tabColors[tabName]);
    selectedTab.setAttribute("aria-selected", "true");
    selectedTab.tabIndex = 0;
    if (shouldFocus) selectedTab.focus();
  }

  const tabs = Array.from(document.querySelectorAll("[data-cotation-tab]"));
  tabs.forEach((tab, index) => {
    tab.addEventListener("click", () => activateTab(tab.dataset.cotationTab));
    tab.addEventListener("keydown", (event) => {
      let nextIndex;
      if (event.key === "ArrowRight") nextIndex = (index + 1) % tabs.length;
      else if (event.key === "ArrowLeft") nextIndex = (index - 1 + tabs.length) % tabs.length;
      else if (event.key === "Home") nextIndex = 0;
      else if (event.key === "End") nextIndex = tabs.length - 1;
      else return;

      event.preventDefault();
      activateTab(tabs[nextIndex].dataset.cotationTab, true);
    });
  });
})();
