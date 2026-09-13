/* Navigation et raccourcis communs au shell applicatif. */
(function () {
  "use strict";

  function setupCommandPalette() {
    const dialog = document.getElementById("command-palette");
    const input = document.getElementById("command-palette-search");
    const emptyState = document.getElementById("command-palette-empty");
    const items = Array.from(document.querySelectorAll("[data-command-item]"));
    if (!dialog || !input) return;

    const filter = () => {
      const query = input.value.trim().toLocaleLowerCase("fr");
      let count = 0;
      items.forEach((item) => {
        const matches = !query || (item.dataset.commandItem || "").includes(query);
        item.hidden = !matches;
        if (matches) count += 1;
      });
      if (emptyState) emptyState.hidden = count !== 0;
    };

    const open = () => {
      if (!dialog.open) dialog.showModal();
      input.value = "";
      filter();
      window.setTimeout(() => input.focus(), 0);
    };

    document.querySelectorAll("[data-command-palette-open]").forEach((trigger) => {
      trigger.addEventListener("click", open);
    });
    input.addEventListener("input", filter);
    dialog.addEventListener("keydown", (event) => {
      if (event.key === "Escape") {
        event.preventDefault();
        dialog.close();
      }
    });
    document.addEventListener("keydown", (event) => {
      if ((event.ctrlKey || event.metaKey) && event.key.toLowerCase() === "k") {
        event.preventDefault();
        open();
      }
    });
  }

  function setupAlertCount() {
    const config = document.getElementById("app-shell-config");
    const activeEgId = config?.dataset.activeEgId;
    const badge = document.getElementById("alert-badge");
    if (!activeEgId || !badge) return;

    const refresh = async () => {
      try {
        const response = await fetch("/api/analytics/alerts?eg_id=" + encodeURIComponent(activeEgId) + "&severity=high");
        if (!response.ok) return;
        const alerts = await response.json();
        const count = alerts.filter((alert) => alert.severity === "high").length;
        badge.textContent = count ? String(count) : "";
        badge.classList.toggle("hidden", count === 0);
      } catch (error) {
        console.debug("Le compteur d'alertes n'a pas pu être chargé.", error);
      }
    };

    void refresh();
    window.setInterval(refresh, 120000);
  }

  document.addEventListener("DOMContentLoaded", () => {
    setupCommandPalette();
    setupAlertCount();
  });
})();
