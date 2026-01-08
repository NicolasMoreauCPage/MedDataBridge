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

  function fmt(ms){return (ms*1000).toFixed(1);} // seconds->ms string
  function pct(v){return (v*100).toFixed(1)+'%';}

  async function fetchJSON(url){
    const r = await fetch(url);
    if(!r.ok) throw new Error('HTTP '+r.status+' '+url);
    return r.json();
  }

  async function loadHealth(){
    try {
      const h = await fetchJSON('/api/metrics/health');
      els.healthStatus.textContent = h.status;
      els.healthOps.textContent = h.total_operations;
      els.healthErrors.textContent = h.total_errors;
      els.opsTracked.textContent = h.operations_tracked;
      if(h.status === 'healthy') els.healthStatus.classList.add('text-success');
      else if(h.status === 'degraded') els.healthStatus.classList.add('text-warning');
      else els.healthStatus.classList.add('text-danger');
    } catch(e){console.warn('Health fail', e);}
  }

  async function loadCache(){
    try {
      const c = await fetchJSON('/api/cache/stats');
      els.cacheEnabled.textContent = c.enabled? 'Enabled' : 'Disabled';
      els.cacheHitRate.textContent = (c.hit_rate ?? 0)+'%';
      els.cacheMemory.textContent = c.used_memory || '--';
      drawCacheChart(c.keyspace_hits || 0, c.keyspace_misses || 0);
    } catch(e){
      els.cacheEnabled.textContent = 'Unavailable';
    }
  }

  async function loadOperations(){
    const data = await fetchJSON('/api/metrics/operations');
    // Build table
    els.opsTableBody.innerHTML='';
    const options=['(All)'];
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
    // Populate select once
    if(!els.opSelect.dataset.filled){
      options.forEach(o=>{const opt=document.createElement('option');opt.value=o;opt.textContent=o;els.opSelect.appendChild(opt);});
      els.opSelect.dataset.filled='1';
    }
    drawOpChart(data);
    els.lastUpdated.textContent = 'Last update: '+ new Date().toLocaleTimeString();
  }

  function drawOpChart(data){
    const selected = els.opSelect.value;
    let durations=[]; let labels=[];
    Object.entries(data).forEach(([name,m])=>{
      if(selected && selected!=='(All)' && name!==selected) return;
      labels.push(name);
      durations.push(m.avg_duration? (m.avg_duration*1000):0);
    });
    if(opChart){opChart.destroy();}
    const ctx=document.getElementById('chart-operation');
    opChart=new Chart(ctx,{type:'bar',data:{labels,datasets:[{label:'Avg Duration (ms)',data:durations,backgroundColor:'#0d6efd'}]},options:{responsive:true,scales:{y:{beginAtZero:true}}}});
  }

  function drawCacheChart(hits, misses){
    if(cacheChart){cacheChart.destroy();}
    const ctx=document.getElementById('chart-cache');
    cacheChart=new Chart(ctx,{type:'doughnut',data:{labels:['Hits','Misses'],datasets:[{data:[hits,misses],backgroundColor:['#198754','#dc3545']}]},options:{cutout:'60%'}});
  }

  async function refreshAll(){
    await Promise.all([loadHealth(), loadCache(), loadOperations()]);
  }

  els.btnRefresh.addEventListener('click', ()=> refreshAll());
  els.btnReset.addEventListener('click', async ()=>{
    if(!confirm('Reset all metrics?')) return;
    await fetch('/api/metrics/operations', {method:'DELETE'});
    await refreshAll();
  });
  els.opSelect.addEventListener('change', ()=>{loadOperations();});

  // Auto refresh every 10s
  setInterval(refreshAll, 10000);
  refreshAll();
})();
