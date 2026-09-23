/* Supervision périodique des endpoints, messages et cache du tableau de bord GHT. */
(function () {
  "use strict";

  const byId = (id) => document.getElementById(id);

  async function loadSystemHealth() {
    try {
      const { data: endpoints } = await window.medbridgeHttp.get("/api/endpoints");
      byId("endpoints-active").textContent = String(endpoints.filter((endpoint) => endpoint.is_active).length);
      byId("endpoints-total").textContent = String(endpoints.length);
      byId("endpoints-running").textContent = String(endpoints.filter((endpoint) => endpoint.status === "RUNNING").length);
      byId("endpoints-stopped").textContent = String(endpoints.filter((endpoint) => endpoint.status === "STOPPED").length);

      const dateFrom = new Date(Date.now() - 24 * 60 * 60 * 1000).toISOString().split("T")[0];
      const { data: errorMessages } = await window.medbridgeHttp.get(`/api/messages?status=error&date_from=${dateFrom}`);
      const { data: totalMessages } = await window.medbridgeHttp.get(`/api/messages?date_from=${dateFrom}`);
      const errorCount = errorMessages.total || 0;
      const totalCount = totalMessages.total || 0;
      byId("messages-errors").textContent = String(errorCount);
      byId("error-rate").textContent = `${totalCount ? ((errorCount / totalCount) * 100).toFixed(1) : "0.0"}%`;

      const { data: cache } = await window.medbridgeHttp.get("/api/cache/stats");
      byId("cache-hit-rate").textContent = cache.hit_rate ? (cache.hit_rate * 100).toFixed(1) : "0.0";
      const badge = byId("cache-status-badge");
      const label = byId("cache-status-text");
      const indicator = badge?.querySelector(".w-1\\.5");
      if (cache.connected) {
        badge.className = "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-emerald-100 text-emerald-700";
        indicator.className = "w-1.5 h-1.5 rounded-full mr-1 bg-emerald-500";
        label.textContent = "Connecté";
      } else {
        badge.className = "inline-flex items-center px-2 py-0.5 rounded-full text-xs font-medium bg-red-100 text-red-700";
        indicator.className = "w-1.5 h-1.5 rounded-full mr-1 bg-red-500";
        label.textContent = "Déconnecté";
      }
    } catch (error) {
      console.error("Erreur lors du chargement de la santé du système :", error);
      ["endpoints-active", "messages-errors", "cache-hit-rate"].forEach((id) => { byId(id).textContent = "ERR"; });
    }
  }

  if (!byId("endpoints-active")) return;
  void loadSystemHealth();
  window.setInterval(() => { void loadSystemHealth(); }, 30000);
})();
