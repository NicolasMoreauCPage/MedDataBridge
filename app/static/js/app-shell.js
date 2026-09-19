/* Navigation et raccourcis communs au shell applicatif. */
(function () {
  "use strict";

  function setupCommandPalette() {
    const dialog = document.getElementById("command-palette");
    const input = document.getElementById("command-palette-search");
    const emptyState = document.getElementById("command-palette-empty");
    const items = Array.from(document.querySelectorAll("[data-command-item]"));
    if (!dialog || !input) return;
    let activeIndex = -1;

    const visibleItems = () => items.filter((item) => !item.hidden);
    const setActiveItem = (index) => {
      const visible = visibleItems();
      activeIndex = visible.length ? (index + visible.length) % visible.length : -1;
      items.forEach((item) => {
        const selected = item === visible[activeIndex];
        item.setAttribute("aria-selected", String(selected));
        item.classList.toggle("bg-violet-50", selected);
        item.classList.toggle("dark:bg-slate-700", selected);
      });
      if (activeIndex >= 0) {
        const activeItem = visible[activeIndex];
        input.setAttribute("aria-activedescendant", activeItem.id);
        activeItem.scrollIntoView({ block: "nearest" });
      } else {
        input.removeAttribute("aria-activedescendant");
      }
    };

    const filter = () => {
      const query = input.value.trim().toLocaleLowerCase("fr");
      let count = 0;
      items.forEach((item) => {
        const matches = !query || (item.dataset.commandItem || "").includes(query);
        item.hidden = !matches;
        if (matches) count += 1;
      });
      if (emptyState) emptyState.hidden = count !== 0;
      setActiveItem(0);
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
    input.addEventListener("keydown", (event) => {
      const visible = visibleItems();
      if (event.key === "ArrowDown" && visible.length) {
        event.preventDefault();
        setActiveItem(activeIndex + 1);
      } else if (event.key === "ArrowUp" && visible.length) {
        event.preventDefault();
        setActiveItem(activeIndex - 1);
      } else if (event.key === "Home" && visible.length) {
        event.preventDefault();
        setActiveItem(0);
      } else if (event.key === "End" && visible.length) {
        event.preventDefault();
        setActiveItem(visible.length - 1);
      } else if (event.key === "Enter" && activeIndex >= 0) {
        event.preventDefault();
        visible[activeIndex].click();
      }
    });
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
        const { data: alerts } = await window.medbridgeHttp.get(
          "/api/analytics/alerts?eg_id=" + encodeURIComponent(activeEgId) + "&severity=high",
        );
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
