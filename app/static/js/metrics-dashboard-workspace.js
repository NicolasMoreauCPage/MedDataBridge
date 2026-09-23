(() => {
  "use strict";

  let refreshInterval;

  const setText = (id, value) => {
    document.getElementById(id).textContent = value;
  };

  async function fetchMetrics() {
    try {
      const { data } = await window.medbridgeHttp.get("/api/metrics/dashboard");
      updateUI(data);
    } catch (error) {
      console.error("Erreur lors du chargement des métriques:", error);
      setText("health-status", "Erreur");
      setText("health-message", "Impossible de charger les métriques");
      setText("health-icon", "❌");
    }
  }

  function updateUI(data) {
    const health = data.health;
    const healthCard = document.getElementById("health-card");
    const healthStatus = document.getElementById("health-status");
    setText("health-status", health.status.charAt(0).toUpperCase() + health.status.slice(1));
    setText("health-message", health.message);

    healthCard.classList.remove(
      "border-green-200",
      "border-yellow-200",
      "border-red-200",
      "bg-green-50",
      "bg-yellow-50",
      "bg-red-50",
    );
    healthStatus.classList.remove("text-green-700", "text-yellow-700", "text-red-700");
    if (health.status === "healthy") {
      healthCard.classList.add("border-green-200", "bg-green-50");
      healthStatus.classList.add("text-green-700");
      setText("health-icon", "✅");
    } else if (health.status === "degraded") {
      healthCard.classList.add("border-yellow-200", "bg-yellow-50");
      healthStatus.classList.add("text-yellow-700");
      setText("health-icon", "⚠️");
    } else {
      healthCard.classList.add("border-red-200", "bg-red-50");
      healthStatus.classList.add("text-red-700");
      setText("health-icon", "❌");
    }

    const summary = data.summary;
    setText("total-ops", summary.total_operations.toLocaleString());
    setText("success-rate", `${summary.success_rate.toFixed(1)}%`);
    setText("error-rate", `${summary.error_rate.toFixed(1)}%`);

    const operations = data.operations || {};
    updateProtocolMetrics(operations);
    updateOperationsTable(operations);
  }

  function updateProtocolMetrics(operations) {
    const hprimInbound = operations.hprim_validation_inbound || {};
    const hprimOutbound = operations.hprim_validation_outbound || {};
    const hprimInboundCount = hprimInbound.count || 0;
    const hprimOutboundCount = hprimOutbound.count || 0;
    const hprimAvgDuration = ((hprimInbound.avg_duration || 0) + (hprimOutbound.avg_duration || 0)) / 2;
    setText("hprim-inbound-count", hprimInboundCount);
    setText("hprim-outbound-count", hprimOutboundCount);
    setText("hprim-avg-duration", `${(hprimAvgDuration * 1000).toFixed(0)}ms`);
    setText("hprim-xsd-errors", (hprimInbound.error_count || 0) + (hprimOutbound.error_count || 0));

    const pamInbound = operations.pam_message_inbound || {};
    const pamOutbound = operations.pam_message_outbound || {};
    const pamInboundCount = pamInbound.count || 0;
    const pamOutboundCount = pamOutbound.count || 0;
    const pamAvgDuration = ((pamInbound.avg_duration || 0) + (pamOutbound.avg_duration || 0)) / 2;
    const pamTotalCount = pamInboundCount + pamOutboundCount;
    const pamSuccessRate = pamTotalCount
      ? (((pamInbound.success_count || 0) + (pamOutbound.success_count || 0)) / pamTotalCount) * 100
      : 0;
    setText("pam-inbound-count", pamInboundCount);
    setText("pam-outbound-count", pamOutboundCount);
    setText("pam-avg-duration", `${(pamAvgDuration * 1000).toFixed(0)}ms`);
    setText("pam-success-rate", `${pamSuccessRate.toFixed(1)}%`);

    const fhirImport = operations.fhir_import || {};
    const fhirExport = operations.fhir_export || {};
    const fhirImportCount = fhirImport.count || 0;
    const fhirExportCount = fhirExport.count || 0;
    const fhirAvgDuration = ((fhirImport.avg_duration || 0) + (fhirExport.avg_duration || 0)) / 2;
    const fhirTotalCount = fhirImportCount + fhirExportCount;
    const fhirSuccessRate = fhirTotalCount
      ? (((fhirImport.success_count || 0) + (fhirExport.success_count || 0)) / fhirTotalCount) * 100
      : 0;
    setText("fhir-import-count", fhirImportCount);
    setText("fhir-export-count", fhirExportCount);
    setText("fhir-avg-duration", `${(fhirAvgDuration * 1000).toFixed(0)}ms`);
    setText("fhir-success-rate", `${fhirSuccessRate.toFixed(1)}%`);
  }

  function updateOperationsTable(operations) {
    const tableContainer = document.getElementById("operations-table");
    if (Object.keys(operations).length === 0) {
      tableContainer.innerHTML = '<p class="text-center text-slate-600 py-8">Aucune métrique disponible</p>';
      return;
    }

    const rows = Object.entries(operations)
      .map(([name, metrics]) => {
        const successRate = metrics.success_rate ? (metrics.success_rate * 100).toFixed(1) : "0.0";
        const avgDuration = metrics.avg_duration ? (metrics.avg_duration * 1000).toFixed(0) : "0";
        const successClass =
          metrics.success_rate >= 0.95
            ? "text-green-600"
            : metrics.success_rate >= 0.8
              ? "text-yellow-600"
              : "text-red-600";
        return `<tr class="hover:bg-slate-50"><td class="px-4 py-3 text-sm font-medium text-slate-900">${name}</td><td class="px-4 py-3 text-sm text-slate-600 text-right">${metrics.count}</td><td class="px-4 py-3 text-sm text-green-600 text-right">${metrics.success_count}</td><td class="px-4 py-3 text-sm text-red-600 text-right">${metrics.error_count}</td><td class="px-4 py-3 text-sm text-slate-600 text-right">${avgDuration}ms</td><td class="px-4 py-3 text-sm ${successClass} text-right font-semibold">${successRate}%</td></tr>`;
      })
      .join("");
    tableContainer.innerHTML = `<table class="min-w-full divide-y divide-slate-200"><thead class="bg-slate-50"><tr><th class="px-4 py-3 text-left text-xs font-medium text-slate-600 uppercase tracking-wider">Opération</th><th class="px-4 py-3 text-right text-xs font-medium text-slate-600 uppercase tracking-wider">Total</th><th class="px-4 py-3 text-right text-xs font-medium text-slate-600 uppercase tracking-wider">Succès</th><th class="px-4 py-3 text-right text-xs font-medium text-slate-600 uppercase tracking-wider">Erreurs</th><th class="px-4 py-3 text-right text-xs font-medium text-slate-600 uppercase tracking-wider">Durée Moy.</th><th class="px-4 py-3 text-right text-xs font-medium text-slate-600 uppercase tracking-wider">Taux Succès</th></tr></thead><tbody class="bg-white divide-y divide-slate-200">${rows}</tbody></table>`;
  }

  document.getElementById("refreshMetricsBtn")?.addEventListener("click", fetchMetrics);
  fetchMetrics();
  refreshInterval = window.setInterval(fetchMetrics, 5000);
  window.addEventListener("beforeunload", () => clearInterval(refreshInterval));
})();
