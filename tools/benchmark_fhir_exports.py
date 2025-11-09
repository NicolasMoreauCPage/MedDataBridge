"""
Benchmark FHIR export performance with/without cache.

Measures:
- Response times for structure/patient/venue exports
- Cache hit rates during exports
- Memory usage
- Throughput (exports per second)

Usage:
    python tools/benchmark_fhir_exports.py --iterations 10 --with-cache --without-cache
"""
import sys
import time
import json
import argparse
import statistics
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Any, Optional
import requests
from dataclasses import dataclass, asdict

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.cache_service import get_cache_service


@dataclass
class BenchmarkResult:
    """Results of a single benchmark run."""
    export_type: str
    cache_enabled: bool
    response_time_ms: float
    status_code: int
    payload_size_bytes: int
    cache_hit: Optional[bool] = None
    error: Optional[str] = None


@dataclass
class BenchmarkSummary:
    """Summary statistics for benchmark runs."""
    export_type: str
    cache_enabled: bool
    iterations: int
    min_time_ms: float
    max_time_ms: float
    mean_time_ms: float
    median_time_ms: float
    stddev_ms: float
    total_time_s: float
    throughput_per_sec: float
    cache_hit_rate: Optional[float] = None
    avg_payload_size_kb: float = 0.0
    
    def improvement_vs(self, baseline: 'BenchmarkSummary') -> float:
        """Calculate performance improvement percentage vs baseline."""
        if baseline.mean_time_ms == 0:
            return 0.0
        return ((baseline.mean_time_ms - self.mean_time_ms) / baseline.mean_time_ms) * 100


class FHIRExportBenchmark:
    """Benchmark FHIR export endpoints."""
    
    def __init__(self, base_url: str = "http://localhost:8000", auth_token: Optional[str] = None):
        self.base_url = base_url.rstrip('/')
        self.auth_token = auth_token
        self.cache = get_cache_service()
        self.results: List[BenchmarkResult] = []
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with optional authentication."""
        headers = {"Accept": "application/json"}
        if self.auth_token:
            headers["Authorization"] = f"Bearer {self.auth_token}"
        return headers
    
    def _get_cache_stats_before(self) -> Dict[str, int]:
        """Get cache stats before benchmark."""
        if not self.cache.enabled:
            return {"hits": 0, "misses": 0}
        
        stats = self.cache.get_stats()
        return {
            "hits": stats.get("keyspace_hits", 0),
            "misses": stats.get("keyspace_misses", 0)
        }
    
    def _calculate_cache_hit_rate(self, before: Dict[str, int], after: Dict[str, int]) -> float:
        """Calculate cache hit rate between two stats snapshots."""
        delta_hits = after["hits"] - before["hits"]
        delta_misses = after["misses"] - before["misses"]
        total = delta_hits + delta_misses
        
        if total == 0:
            return 0.0
        
        return (delta_hits / total) * 100
    
    def benchmark_export(
        self, 
        export_type: str, 
        ej_id: int, 
        iterations: int = 10,
        cache_enabled: bool = True
    ) -> List[BenchmarkResult]:
        """
        Benchmark a specific export type.
        
        Args:
            export_type: One of 'structure', 'patients', 'venues'
            ej_id: Entité juridique ID
            iterations: Number of iterations to run
            cache_enabled: Whether cache should be enabled
        
        Returns:
            List of benchmark results
        """
        endpoint_map = {
            "structure": f"/api/fhir/export/structure/ej/{ej_id}",
            "patients": f"/api/fhir/export/patients/ej/{ej_id}",
            "venues": f"/api/fhir/export/venues/ej/{ej_id}"
        }
        
        if export_type not in endpoint_map:
            raise ValueError(f"Invalid export_type: {export_type}")
        
        endpoint = endpoint_map[export_type]
        url = f"{self.base_url}{endpoint}"
        
        # Clear cache if testing non-cached performance
        if not cache_enabled and self.cache.enabled:
            self.cache.flush_all()
            print(f"  ℹ️  Cache cleared for non-cached benchmark")
        
        # Warmup request (not counted)
        print(f"  🔥 Warmup request...")
        try:
            requests.get(url, headers=self._get_headers(), timeout=30)
        except Exception as e:
            print(f"  ⚠️  Warmup failed: {e}")
        
        results = []
        cache_stats_before = self._get_cache_stats_before()
        
        print(f"  📊 Running {iterations} iterations...")
        for i in range(iterations):
            # Clear cache between iterations if cache_enabled=False
            if not cache_enabled and self.cache.enabled:
                self.cache.delete_pattern(f"fhir:export:{export_type}:*")
            
            start_time = time.perf_counter()
            
            try:
                response = requests.get(url, headers=self._get_headers(), timeout=60)
                end_time = time.perf_counter()
                
                response_time_ms = (end_time - start_time) * 1000
                payload_size = len(response.content)
                
                result = BenchmarkResult(
                    export_type=export_type,
                    cache_enabled=cache_enabled,
                    response_time_ms=response_time_ms,
                    status_code=response.status_code,
                    payload_size_bytes=payload_size
                )
                
                results.append(result)
                
                # Progress indicator
                if (i + 1) % 5 == 0:
                    print(f"    ✓ Completed {i + 1}/{iterations} iterations")
                
            except Exception as e:
                end_time = time.perf_counter()
                response_time_ms = (end_time - start_time) * 1000
                
                result = BenchmarkResult(
                    export_type=export_type,
                    cache_enabled=cache_enabled,
                    response_time_ms=response_time_ms,
                    status_code=0,
                    payload_size_bytes=0,
                    error=str(e)
                )
                results.append(result)
                print(f"    ❌ Iteration {i + 1} failed: {e}")
        
        # Calculate cache hit rate for this benchmark
        if cache_enabled and self.cache.enabled:
            cache_stats_after = self._get_cache_stats_before()
            hit_rate = self._calculate_cache_hit_rate(cache_stats_before, cache_stats_after)
            
            for result in results:
                result.cache_hit = hit_rate > 0
        
        self.results.extend(results)
        return results
    
    def summarize_results(self, results: List[BenchmarkResult]) -> BenchmarkSummary:
        """Generate summary statistics from benchmark results."""
        if not results:
            raise ValueError("No results to summarize")
        
        # Filter out errors
        valid_results = [r for r in results if r.error is None and r.status_code == 200]
        
        if not valid_results:
            raise ValueError("No valid results (all requests failed)")
        
        times = [r.response_time_ms for r in valid_results]
        sizes = [r.payload_size_bytes for r in valid_results]
        
        total_time_s = sum(times) / 1000
        throughput = len(valid_results) / total_time_s if total_time_s > 0 else 0
        
        # Cache hit rate
        cache_hits = [r for r in valid_results if r.cache_hit]
        cache_hit_rate = (len(cache_hits) / len(valid_results)) * 100 if valid_results else 0.0
        
        summary = BenchmarkSummary(
            export_type=results[0].export_type,
            cache_enabled=results[0].cache_enabled,
            iterations=len(valid_results),
            min_time_ms=min(times),
            max_time_ms=max(times),
            mean_time_ms=statistics.mean(times),
            median_time_ms=statistics.median(times),
            stddev_ms=statistics.stdev(times) if len(times) > 1 else 0.0,
            total_time_s=total_time_s,
            throughput_per_sec=throughput,
            cache_hit_rate=cache_hit_rate if results[0].cache_enabled else None,
            avg_payload_size_kb=statistics.mean(sizes) / 1024
        )
        
        return summary
    
    def generate_report(self, summaries: List[BenchmarkSummary]) -> str:
        """Generate a comprehensive benchmark report."""
        report_lines = [
            "=" * 80,
            "FHIR Export Performance Benchmark Report",
            "=" * 80,
            f"Date: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
            f"Base URL: {self.base_url}",
            f"Cache Available: {'Yes' if self.cache.enabled else 'No'}",
            "",
            "-" * 80,
            "SUMMARY BY EXPORT TYPE",
            "-" * 80,
            ""
        ]
        
        # Group by export type
        by_type: Dict[str, List[BenchmarkSummary]] = {}
        for summary in summaries:
            if summary.export_type not in by_type:
                by_type[summary.export_type] = []
            by_type[summary.export_type].append(summary)
        
        # Report for each export type
        for export_type, type_summaries in sorted(by_type.items()):
            report_lines.extend([
                f"📦 Export Type: {export_type.upper()}",
                "-" * 40,
                ""
            ])
            
            cached_summary = next((s for s in type_summaries if s.cache_enabled), None)
            non_cached_summary = next((s for s in type_summaries if not s.cache_enabled), None)
            
            if cached_summary:
                report_lines.extend([
                    "✅ WITH CACHE:",
                    f"  Iterations: {cached_summary.iterations}",
                    f"  Mean Response Time: {cached_summary.mean_time_ms:.2f} ms",
                    f"  Median Response Time: {cached_summary.median_time_ms:.2f} ms",
                    f"  Min/Max: {cached_summary.min_time_ms:.2f} / {cached_summary.max_time_ms:.2f} ms",
                    f"  Std Dev: {cached_summary.stddev_ms:.2f} ms",
                    f"  Throughput: {cached_summary.throughput_per_sec:.2f} req/sec",
                    f"  Cache Hit Rate: {cached_summary.cache_hit_rate:.1f}%" if cached_summary.cache_hit_rate is not None else "  Cache Hit Rate: N/A",
                    f"  Avg Payload Size: {cached_summary.avg_payload_size_kb:.2f} KB",
                    ""
                ])
            
            if non_cached_summary:
                report_lines.extend([
                    "❌ WITHOUT CACHE:",
                    f"  Iterations: {non_cached_summary.iterations}",
                    f"  Mean Response Time: {non_cached_summary.mean_time_ms:.2f} ms",
                    f"  Median Response Time: {non_cached_summary.median_time_ms:.2f} ms",
                    f"  Min/Max: {non_cached_summary.min_time_ms:.2f} / {non_cached_summary.max_time_ms:.2f} ms",
                    f"  Std Dev: {non_cached_summary.stddev_ms:.2f} ms",
                    f"  Throughput: {non_cached_summary.throughput_per_sec:.2f} req/sec",
                    f"  Avg Payload Size: {non_cached_summary.avg_payload_size_kb:.2f} KB",
                    ""
                ])
            
            # Performance improvement calculation
            if cached_summary and non_cached_summary:
                improvement = cached_summary.improvement_vs(non_cached_summary)
                if improvement > 0:
                    report_lines.extend([
                        f"🚀 PERFORMANCE GAIN WITH CACHE: {improvement:.1f}% faster",
                        f"   (Saved {non_cached_summary.mean_time_ms - cached_summary.mean_time_ms:.2f} ms per request)",
                        ""
                    ])
                elif improvement < 0:
                    report_lines.extend([
                        f"⚠️  Cache overhead: {abs(improvement):.1f}% slower (cache warmup phase?)",
                        ""
                    ])
                else:
                    report_lines.append("   No significant difference")
            
            report_lines.append("")
        
        report_lines.extend([
            "-" * 80,
            "RECOMMENDATIONS",
            "-" * 80,
            ""
        ])
        
        # Analyze and provide recommendations
        all_improvements = []
        for export_type, type_summaries in by_type.items():
            cached = next((s for s in type_summaries if s.cache_enabled), None)
            non_cached = next((s for s in type_summaries if not s.cache_enabled), None)
            
            if cached and non_cached:
                improvement = cached.improvement_vs(non_cached)
                all_improvements.append((export_type, improvement))
        
        if all_improvements:
            avg_improvement = statistics.mean([imp for _, imp in all_improvements])
            
            if avg_improvement > 30:
                report_lines.append("✅ Cache provides SIGNIFICANT performance benefits (>30% improvement)")
                report_lines.append("   → Cache is HIGHLY RECOMMENDED for production use")
            elif avg_improvement > 10:
                report_lines.append("✅ Cache provides MODERATE performance benefits (10-30% improvement)")
                report_lines.append("   → Cache is RECOMMENDED for production use")
            elif avg_improvement > 0:
                report_lines.append("⚠️  Cache provides MINOR performance benefits (<10% improvement)")
                report_lines.append("   → Consider cache based on workload patterns")
            else:
                report_lines.append("❌ Cache does not provide performance benefits")
                report_lines.append("   → Review cache configuration or disable caching")
        
        report_lines.extend([
            "",
            "=" * 80,
            "END OF REPORT",
            "=" * 80
        ])
        
        return "\n".join(report_lines)
    
    def save_report(self, report: str, output_path: str):
        """Save report to file."""
        with open(output_path, 'w') as f:
            f.write(report)
        print(f"\n✅ Report saved to: {output_path}")
    
    def save_json_results(self, summaries: List[BenchmarkSummary], output_path: str):
        """Save detailed results as JSON."""
        data = {
            "benchmark_date": datetime.now().isoformat(),
            "base_url": self.base_url,
            "cache_available": self.cache.enabled,
            "summaries": [asdict(s) for s in summaries]
        }
        
        with open(output_path, 'w') as f:
            json.dump(data, f, indent=2)
        
        print(f"✅ JSON results saved to: {output_path}")


def main():
    """Main benchmark execution."""
    parser = argparse.ArgumentParser(description="Benchmark FHIR export performance")
    parser.add_argument("--base-url", default="http://localhost:8000", help="Base URL of the API")
    parser.add_argument("--ej-id", type=int, default=1, help="Entité Juridique ID to test")
    parser.add_argument("--iterations", type=int, default=10, help="Number of iterations per benchmark")
    parser.add_argument("--with-cache", action="store_true", help="Benchmark with cache enabled")
    parser.add_argument("--without-cache", action="store_true", help="Benchmark without cache")
    parser.add_argument("--export-types", nargs="+", default=["structure", "patients", "venues"],
                       choices=["structure", "patients", "venues"], help="Export types to benchmark")
    parser.add_argument("--output-dir", default="benchmark_results", help="Output directory for reports")
    parser.add_argument("--auth-token", help="Authentication token (if required)")
    
    args = parser.parse_args()
    
    # Default to both if neither specified
    if not args.with_cache and not args.without_cache:
        args.with_cache = True
        args.without_cache = True
    
    # Create output directory
    output_dir = Path(args.output_dir)
    output_dir.mkdir(exist_ok=True)
    
    print("🚀 FHIR Export Performance Benchmark")
    print("=" * 80)
    print(f"Base URL: {args.base_url}")
    print(f"EJ ID: {args.ej_id}")
    print(f"Iterations: {args.iterations}")
    print(f"Export Types: {', '.join(args.export_types)}")
    print(f"Benchmarks: {'WITH CACHE' if args.with_cache else ''} {'WITHOUT CACHE' if args.without_cache else ''}")
    print("=" * 80)
    print()
    
    benchmark = FHIRExportBenchmark(base_url=args.base_url, auth_token=args.auth_token)
    all_summaries = []
    
    # Run benchmarks
    for export_type in args.export_types:
        print(f"\n📦 Benchmarking: {export_type.upper()}")
        print("-" * 40)
        
        if args.with_cache:
            print(f"\n✅ WITH CACHE (iterations: {args.iterations})")
            results = benchmark.benchmark_export(
                export_type=export_type,
                ej_id=args.ej_id,
                iterations=args.iterations,
                cache_enabled=True
            )
            summary = benchmark.summarize_results(results)
            all_summaries.append(summary)
            print(f"  ✓ Mean: {summary.mean_time_ms:.2f} ms, Throughput: {summary.throughput_per_sec:.2f} req/sec")
        
        if args.without_cache:
            print(f"\n❌ WITHOUT CACHE (iterations: {args.iterations})")
            results = benchmark.benchmark_export(
                export_type=export_type,
                ej_id=args.ej_id,
                iterations=args.iterations,
                cache_enabled=False
            )
            summary = benchmark.summarize_results(results)
            all_summaries.append(summary)
            print(f"  ✓ Mean: {summary.mean_time_ms:.2f} ms, Throughput: {summary.throughput_per_sec:.2f} req/sec")
    
    # Generate and save report
    print("\n\n📊 Generating report...")
    report = benchmark.generate_report(all_summaries)
    
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    report_path = output_dir / f"benchmark_report_{timestamp}.txt"
    json_path = output_dir / f"benchmark_results_{timestamp}.json"
    
    benchmark.save_report(report, str(report_path))
    benchmark.save_json_results(all_summaries, str(json_path))
    
    # Print report to console
    print("\n" + report)


if __name__ == "__main__":
    main()
