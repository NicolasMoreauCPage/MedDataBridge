# FHIR Export Performance Benchmarking & Extended Demo Initialization

## Overview

This document has two purposes:

1. Describe the FHIR export benchmarking tools and methodology used to measure and optimize cache performance.
2. Document the initialization of the extended multi-EJ demo dataset (realistic GHT: CHU, hôpital local, EHPAD, psychiatrie) used as a foundation for performance and interoperability tests.

If you only need benchmarking usage, you can skip directly to the section "Benchmark Tools". For reproducing a realistic dataset before benchmarking, start with "Extended Demo Initialization".

---

## Extended Demo Initialization (Multi-EJ GHT)

### Goal

Provide a realistic territory-wide GHT containing 4 juridical entities:

- CHU Universitaire Lyon (multi-sites: MCO, Maternité, Urgences, SSR)
- Centre Hospitalier Local (médecine, chirurgie légère / soins courants)
- EHPAD (hébergement personnes âgées dépendantes)
- Établissement Psychiatrique (PSY)

Each EJ includes its own sites (EG), poles, services, UF, UH, chambres, lits, and associated identifier namespaces. Endpoints (HL7 MLLP inbound/outbound + FHIR export/import) are provisioned per EJ. A synthetic patient population with venues/mouvements is generated idempotently.

### Main Seeding Functions

Located in `app/services/structure_seed.py`:

- `ensure_extended_demo_ght(session, ght_context_id)`
  - Iterates over `EXTENDED_GHT_DATA['juridical_entities']` and upserts full hierarchy.
- `ensure_endpoints_for_context(session, ght_context_id)`
  - Creates or updates a standard set of endpoints (MLLP sender/receiver, FHIR export/import) for every EJ present in the context.
- `seed_demo_population(session, ght_context_id, target_patient_count=120)`
  - Populates patients, dossiers, venues, mouvements. Idempotent: if patient count ≥ target, it skips creation.

### Orchestration Script

Run `tools/init_extended_demo.py` to perform all steps (DB init + structure + endpoints + population):

```bash
export PYTHONPATH=.
.venv/bin/python tools/init_extended_demo.py
```

The script prints summary counters for created/updated entities and patient/movement counts.

### Idempotence & Re-run Behavior

- Structural entities (EJ/EG/Pole/Service/UF/UH/Chambre/Lit) use stable `identifier` or business keys (FINESS) → upsert without duplication.
- Endpoints matched by `(entite_juridique_id, name)` → updated if already present.
- Patient population: counts existing patients for the context; if already at or above target, no new patients are added.

### Expected Counts (First Run Approximation)

| Category | Approx Count | Notes |
|----------|--------------|-------|
| Entités Juridiques (EJ) | 4 | CHU + Local + EHPAD + PSY |
| Sites (EG) | ~8 | Varies per EJ (CHU multi-sites) |
| Pôles | 8–12 | Depends on dataset version |
| Services | 12–20 | Urgences, MCO, SSR, etc. |
| UF | 20–30 | Includes hospitalisation, urgences, bloc, consultations |
| UH | 20–25 | Some UF sans UH (ex: consultations only) |
| Chambres/Boxes | 60–90 | Includes lits EHPAD chambres simples/doubles |
| Lits | 100–140 | Operational status varied (available/occupied/maintenance) |
| Patients | 120 | Target default |
| Mouvements | 200–250 | Admission/transfers/discharges synthetic chain |

Second run: structural counts unchanged; endpoints updated only; patient + mouvements stable (no increment if target met).

### Verifying Initialization

1. Start the API server (Linux task or manual):
   ```bash
   .venv/bin/python -m uvicorn app.app:app --reload
   ```
2. Visit `/admin/ght/1/ej/1` (CHU) and `/admin/ght/1/ej/2` etc. to inspect counts.
3. Check endpoints via `/endpoints` UI or API.
4. Confirm patient volume via `/patients` or direct DB query.

### Troubleshooting

| Symptom | Cause | Resolution |
|---------|-------|------------|
| 404 on `/admin/ght/1/ej/1` | Router partial load | Ensure fallback removed only after full `ght` load; restart server |
| Duplicate endpoints | Script re-run with name changes | Keep names stable; they are used as upsert keys |
| Excess patients | Manual data injection before seed | Adjust `target_patient_count` or purge DB |
| Slow seed time | Large movement generation | Lower target count (`seed_demo_population(..., target_patient_count=60)`) |

### Future Improvements

- Modularize `app/routers/ght.py` (currently large) into sub-routers.
- Configurable endpoint templates per EJ type (e.g., EHPAD minimal set vs CHU full set).
- Parameterize movement generation (patterns, ADT mix ratios).

---

## Benchmark Tools

## Tools

### 1. Benchmark Script (`tools/benchmark_fhir_exports.py`)

Comprehensive Python script for benchmarking FHIR export endpoints.

**Features:**
- Measures response times (min/max/mean/median/stddev)
- Calculates throughput (requests per second)
- Tracks cache hit rates
- Monitors payload sizes
- Compares cached vs non-cached performance
- Generates detailed reports

**Usage:**

```bash
# Basic usage (defaults to 10 iterations)
python tools/benchmark_fhir_exports.py --ej-id 1

# Custom iterations
python tools/benchmark_fhir_exports.py --ej-id 1 --iterations 20

# Specific export types only
python tools/benchmark_fhir_exports.py --ej-id 1 --export-types structure patients

# With authentication
python tools/benchmark_fhir_exports.py --ej-id 1 --auth-token "your-jwt-token"

# Only test cached performance
python tools/benchmark_fhir_exports.py --ej-id 1 --with-cache

# Only test non-cached performance
python tools/benchmark_fhir_exports.py --ej-id 1 --without-cache
```

### 2. Quick Benchmark Runner (`tools/run_benchmark.sh`)

Bash script for quick benchmarking with default settings.

**Usage:**

```bash
# Run with defaults (EJ=1, 10 iterations)
./tools/run_benchmark.sh

# Specify EJ ID
./tools/run_benchmark.sh 2

# Specify EJ ID and iterations
./tools/run_benchmark.sh 2 20
```

## Benchmark Methodology

### Warm-up Phase
- One initial request to warm up the server (not counted)
- Ensures JIT compilation and initialization are complete

### Measurement Phase
- Multiple iterations (default: 10) per scenario
- Measures:
  - **Response Time**: Time from request to complete response
  - **Throughput**: Requests per second
  - **Cache Hit Rate**: Percentage of cache hits during benchmark
  - **Payload Size**: Average response size in KB

### Scenarios Tested

1. **WITH CACHE** - Cache enabled, normal operation:
   - First request: Cache miss (DB query)
   - Subsequent requests: Cache hits (Redis retrieval)
   - Measures optimal cached performance

2. **WITHOUT CACHE** - Cache cleared between requests:
   - Every request: Cache miss (forces DB query)
   - Measures worst-case performance without caching

### Export Types Benchmarked

- **structure**: Organizational structure export (GHT/EJ/EG/Pole/Service/UF)
- **patients**: Patient demographics export
- **venues**: Encounters/visits export

## Output

### Text Report

Generated at: `benchmark_results/benchmark_report_YYYYMMDD_HHMMSS.txt`

**Contents:**
- Summary statistics per export type
- Performance comparison (cached vs non-cached)
- Performance gain percentage
- Throughput metrics
- Cache hit rates
- Recommendations based on results

**Example Output:**

```
================================================================================
FHIR Export Performance Benchmark Report
================================================================================
Date: 2025-11-09 14:30:00
Base URL: http://localhost:8000
Cache Available: Yes

--------------------------------------------------------------------------------
SUMMARY BY EXPORT TYPE
--------------------------------------------------------------------------------

📦 Export Type: STRUCTURE
----------------------------------------

✅ WITH CACHE:
  Iterations: 10
  Mean Response Time: 45.23 ms
  Median Response Time: 42.10 ms
  Min/Max: 38.50 / 62.30 ms
  Std Dev: 6.45 ms
  Throughput: 22.11 req/sec
  Cache Hit Rate: 90.0%
  Avg Payload Size: 156.32 KB

❌ WITHOUT CACHE:
  Iterations: 10
  Mean Response Time: 234.56 ms
  Median Response Time: 228.40 ms
  Min/Max: 215.20 / 268.90 ms
  Std Dev: 15.23 ms
  Throughput: 4.26 req/sec
  Avg Payload Size: 156.45 KB

🚀 PERFORMANCE GAIN WITH CACHE: 80.7% faster
   (Saved 189.33 ms per request)

...

--------------------------------------------------------------------------------
RECOMMENDATIONS
--------------------------------------------------------------------------------

✅ Cache provides SIGNIFICANT performance benefits (>30% improvement)
   → Cache is HIGHLY RECOMMENDED for production use

================================================================================
END OF REPORT
================================================================================
```

### JSON Results

Generated at: `benchmark_results/benchmark_results_YYYYMMDD_HHMMSS.json`

**Structure:**

```json
{
  "benchmark_date": "2025-11-09T14:30:00.123456",
  "base_url": "http://localhost:8000",
  "cache_available": true,
  "summaries": [
    {
      "export_type": "structure",
      "cache_enabled": true,
      "iterations": 10,
      "min_time_ms": 38.50,
      "max_time_ms": 62.30,
      "mean_time_ms": 45.23,
      "median_time_ms": 42.10,
      "stddev_ms": 6.45,
      "total_time_s": 0.452,
      "throughput_per_sec": 22.11,
      "cache_hit_rate": 90.0,
      "avg_payload_size_kb": 156.32
    },
    ...
  ]
}
```

## Interpreting Results

### Response Time
- **< 50ms**: Excellent (typical with cache)
- **50-200ms**: Good (acceptable for API)
- **200-500ms**: Moderate (needs optimization)
- **> 500ms**: Poor (critical optimization needed)

### Cache Performance Gain
- **> 80%**: Excellent cache effectiveness
- **50-80%**: Good cache effectiveness
- **20-50%**: Moderate cache effectiveness
- **< 20%**: Limited cache benefit (investigate)

### Cache Hit Rate
- **> 90%**: Excellent (cache working optimally)
- **70-90%**: Good (some cache misses expected)
- **50-70%**: Moderate (review TTL settings)
- **< 50%**: Poor (cache not effective)

### Throughput
- **> 100 req/sec**: Excellent
- **50-100 req/sec**: Good
- **10-50 req/sec**: Moderate
- **< 10 req/sec**: Poor (optimization needed)

## Optimization Recommendations

### Based on Results

#### High Cache Gain (>50%)
✅ **Action**: Enable caching in production
- Cache is providing significant value
- Configure appropriate TTL (default: 3600s)
- Monitor cache hit rates in production

#### Moderate Cache Gain (20-50%)
⚠️ **Action**: Tune cache configuration
- Review TTL settings (may be too short)
- Check cache invalidation patterns
- Consider increasing Redis memory allocation

#### Low Cache Gain (<20%)
❌ **Action**: Investigate cache configuration
- Verify Redis is running and accessible
- Check for excessive cache invalidations
- Review export data volatility
- Consider disabling cache if overhead exceeds benefit

### Cache Configuration

**Recommended Settings** (in `app/services/cache_service.py`):

```python
# For high-traffic, stable data
default_ttl = 7200  # 2 hours

# For moderate traffic, semi-stable data
default_ttl = 3600  # 1 hour (current default)

# For low traffic or volatile data
default_ttl = 1800  # 30 minutes
```

## Continuous Monitoring

### Production Metrics

Monitor these metrics in production:

1. **Cache Hit Rate** (`/api/metrics/cache`):
   - Target: > 80%
   - Alert: < 50%

2. **Response Times** (application logs):
   - Target: < 100ms (P95)
   - Alert: > 500ms (P95)

3. **Memory Usage** (`/api/metrics/cache`):
   - Monitor Redis memory
   - Alert on > 80% usage

### Alerting Thresholds

```yaml
cache_hit_rate_low:
  threshold: 50%
  severity: warning
  
response_time_high:
  threshold: 500ms  # P95
  severity: critical
  
redis_memory_high:
  threshold: 80%
  severity: warning
```

## Troubleshooting

### Benchmark Not Running

**Issue**: `Connection refused to http://localhost:8000`

**Solution**: Start the API server:
```bash
.venv/bin/python -m uvicorn app.app:app --reload
```

### Redis Not Available

**Issue**: Cache benchmarks show 0% hit rate

**Solution**: Start Redis:
```bash
# Linux/MacOS
redis-server

# Docker
docker run -d -p 6379:6379 redis:alpine
```

### High Variance in Results

**Issue**: Large standard deviation (> 50% of mean)

**Solutions**:
- Increase iterations (--iterations 50)
- Run on a quieter system (close background apps)
- Exclude outliers (first request after restart)
- Check for competing database queries

### Unexpected Slow Performance

**Issue**: Even cached requests are slow (> 200ms)

**Solutions**:
- Check Redis latency: `redis-cli --latency`
- Verify network not saturated
- Check application CPU usage
- Review payload serialization overhead

## Future Enhancements

Planned improvements for benchmarking:

1. **Memory Profiling**: Track memory consumption during exports
2. **Concurrent Load**: Test with multiple simultaneous requests
3. **Database Query Analysis**: Profile SQL queries during non-cached runs
4. **Network Latency Simulation**: Test with artificial network delays
5. **Historical Trending**: Track benchmark results over time
6. **Automated Regression Detection**: Alert when performance degrades

## References

- Cache Service Implementation: `app/services/cache_service.py`
- FHIR Export Service: `app/services/fhir_export_service.py`
- Cache Metrics Dashboard: `/cache-dashboard`
- Cache Metrics API: `/api/metrics/cache`
