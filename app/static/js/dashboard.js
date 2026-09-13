(function(){
  const els = {
    healthStatus: document.getElementById('health-status'),
    healthOps: document.getElementById('health-ops'),
    healthErrors: document.getElementById('health-errors'),
    cacheEnabled: document.getElementById('cache-enabled'),
    cacheHitRate: document.getElementById('cache-hit-rate'),
    cacheMemory: document.getElementById('cache-memory'),
    opsTotal: document.getElementById('ops-total'),
    successRate: document.getElementById('success-rate'),
    opsTracked: document.getElementById('ops-tracked'),
    opsTableBody: document.querySelector('#ops-table tbody'),
    lastUpdated: document.getElementById('last-updated'),
    opSelect: document.getElementById('operation-select'),
    btnRefresh: document.getElementById('btn-refresh'),
    btnReset: document.getElementById('btn-reset-metrics')
  };

  let opChart, cacheChart;

  const statusLabels = {
    healthy: 'Disponible',
    degraded: 'Dégradé',
    unhealthy: 'Indisponible',
  };

  function fmt(ms){return (ms*1000).toFixed(1);} // seconds->ms string
  function pct(v){return (v*100).toFixed(1)+'%';}
  function destroyChart(chart){
    if(chart) chart.destroy();
    return null;
  }

  async function fetchJSON(url){
    const r = await fetch(url);
    if(!r.ok) throw new Error('HTTP '+r.status+' '+url);
    return r.json();
  }

  async function loadHealth(){
    try {
      const h = await fetchJSON('/api/metrics/health');
      els.healthStatus.textContent = statusLabels[h.status] || h.status || 'Inconnu';
      els.healthOps.textContent = h.total_operations;
      els.healthErrors.textContent = h.total_errors;
      els.opsTracked.textContent = h.operations_tracked;
      els.healthStatus.classList.remove('text-success', 'text-warning', 'text-danger');
      if(h.status === 'healthy') els.healthStatus.classList.add('text-success');
      else if(h.status === 'degraded') els.healthStatus.classList.add('text-warning');
      else els.healthStatus.classList.add('text-danger');
    } catch(e){
      els.healthStatus.textContent = 'Indisponible';
      els.healthOps.textContent = '--';
      els.healthErrors.textContent = '--';
      els.opsTracked.textContent = '--';
      els.healthStatus.classList.remove('text-success', 'text-warning');
      els.healthStatus.classList.add('text-danger');
      console.warn('État de santé indisponible', e);
    }
  }

  async function loadCache(){
    try {
      const c = await fetchJSON('/api/cache/stats');
      els.cacheEnabled.textContent = c.enabled ? 'Activé' : 'Désactivé';
      els.cacheHitRate.textContent = (c.hit_rate ?? 0)+'%';
      els.cacheMemory.textContent = c.used_memory || '--';
      drawCacheChart(c.keyspace_hits || 0, c.keyspace_misses || 0);
    } catch(e){
      els.cacheEnabled.textContent = 'Indisponible';
      els.cacheHitRate.textContent = '--';
      els.cacheMemory.textContent = '--';
      cacheChart = destroyChart(cacheChart);
    }
  }

  async function loadOperations(){
    try {
      const data = await fetchJSON('/api/metrics/operations');
      // Build table
      els.opsTableBody.innerHTML='';
      const options=['Toutes'];
      let total=0, totalSuccess=0;
      Object.entries(data).forEach(([name,m])=>{
        total += m.count||0; totalSuccess += m.success_count||0;
        const tr=document.createElement('tr');
        tr.innerHTML=`<td>${name}</td><td>${m.count||0}</td><td>${m.success_count||0}</td><td>${m.error_count||0}</td><td>${m.count? pct((m.success_count||0)/m.count):'0%'}</td><td>${m.avg_duration?fmt(m.avg_duration):'0.0'}</td><td>${m.min_duration!==undefined&&m.min_duration!==Infinity?fmt(m.min_duration):'0.0'}</td><td>${m.max_duration?fmt(m.max_duration):'0.0'}</td>`;
        els.opsTableBody.appendChild(tr);
        options.push(name);
      });
      els.opsTotal.textContent = total;
      els.successRate.textContent = total? pct(totalSuccess/total):'0%';
      const previousSelection = els.opSelect.value;
      els.opSelect.replaceChildren();
      options.forEach((optionLabel) => {
        const option = document.createElement('option');
        option.value = optionLabel;
        option.textContent = optionLabel;
        els.opSelect.appendChild(option);
      });
      els.opSelect.value = options.includes(previousSelection) ? previousSelection : 'Toutes';
      drawOpChart(data);
      els.lastUpdated.textContent = new Date().toLocaleTimeString('fr-FR');
    } catch(e) {
      els.opsTotal.textContent = '--';
      els.successRate.textContent = '--';
      els.opsTableBody.replaceChildren();
      const row = document.createElement('tr');
      const cell = document.createElement('td');
      cell.colSpan = 8;
      cell.className = 'px-6 py-8 text-center text-slate-500 dark:text-slate-400';
      cell.textContent = 'Les métriques d’opérations sont temporairement indisponibles.';
      row.append(cell);
      els.opsTableBody.append(row);
      opChart = destroyChart(opChart);
      els.lastUpdated.textContent = 'Actualisation impossible';
      console.warn('Métriques d’opérations indisponibles', e);
    }
  }

  function drawOpChart(data){
    const selected = els.opSelect.value;
    let durations=[]; let labels=[];
    Object.entries(data).forEach(([name,m])=>{
      if(selected && selected!=='Toutes' && name!==selected) return;
      labels.push(name);
      durations.push(m.avg_duration? (m.avg_duration*1000):0);
    });
    opChart = destroyChart(opChart);
    const ctx=document.getElementById('chart-operation');
    opChart=new Chart(ctx,{type:'bar',data:{labels,datasets:[{label:'Durée moyenne (ms)',data:durations,backgroundColor:'#0d6efd'}]},options:{responsive:true,scales:{y:{beginAtZero:true}}}});
  }

  function drawCacheChart(hits, misses){
    cacheChart = destroyChart(cacheChart);
    const ctx=document.getElementById('chart-cache');
    cacheChart=new Chart(ctx,{type:'doughnut',data:{labels:['Succès','Échecs'],datasets:[{data:[hits,misses],backgroundColor:['#198754','#dc3545']}]},options:{cutout:'60%'}});
  }

  async function refreshAll(){
    await Promise.all([loadHealth(), loadCache(), loadOperations()]);
  }

  els.btnRefresh.addEventListener('click', ()=> refreshAll());
  els.btnReset.addEventListener('click', async ()=>{
    if (!window.PameliaUi?.confirm) {
      window.toastSystem?.show?.('Le dialogue de confirmation n’est pas disponible.', 'error');
      return;
    }
    const confirmed = await window.PameliaUi.confirm({
      title: 'Réinitialiser les métriques',
      message: 'Réinitialiser toutes les métriques ?',
      acceptLabel: 'Réinitialiser',
      variant: 'danger',
    });
    if (!confirmed) return;
    try {
      const response = await fetch('/api/metrics/operations', {method:'DELETE'});
      if (!response.ok) throw new Error(`HTTP ${response.status}`);
      window.toastSystem?.show?.('Les métriques ont été réinitialisées.', 'success');
      await refreshAll();
    } catch (error) {
      window.toastSystem?.show?.(`Impossible de réinitialiser les métriques : ${error.message}`, 'error');
    }
  });
  els.opSelect.addEventListener('change', ()=>{loadOperations();});

  // Auto refresh every 10s
  setInterval(refreshAll, 10000);
  refreshAll();
})();
