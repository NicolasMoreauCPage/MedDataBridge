"""
Tests for FHIR export benchmarking tools.
"""
import pytest
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
import sys

# Add tools to path
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from benchmark_fhir_exports import (
    BenchmarkResult,
    BenchmarkSummary,
    FHIRExportBenchmark
)


class TestBenchmarkResult:
    """Test BenchmarkResult dataclass."""
    
    def test_create_result_success(self):
        """Test creating a successful benchmark result."""
        result = BenchmarkResult(
            export_type="structure",
            cache_enabled=True,
            response_time_ms=45.5,
            status_code=200,
            payload_size_bytes=15000
        )
        
        assert result.export_type == "structure"
        assert result.cache_enabled is True
        assert result.response_time_ms == 45.5
        assert result.status_code == 200
        assert result.payload_size_bytes == 15000
        assert result.cache_hit is None
        assert result.error is None
    
    def test_create_result_with_error(self):
        """Test creating a failed benchmark result."""
        result = BenchmarkResult(
            export_type="patients",
            cache_enabled=False,
            response_time_ms=1000.0,
            status_code=500,
            payload_size_bytes=0,
            error="Connection timeout"
        )
        
        assert result.error == "Connection timeout"
        assert result.status_code == 500


class TestBenchmarkSummary:
    """Test BenchmarkSummary dataclass."""
    
    def test_create_summary(self):
        """Test creating a benchmark summary."""
        summary = BenchmarkSummary(
            export_type="structure",
            cache_enabled=True,
            iterations=10,
            min_time_ms=40.0,
            max_time_ms=60.0,
            mean_time_ms=50.0,
            median_time_ms=49.0,
            stddev_ms=5.0,
            total_time_s=0.5,
            throughput_per_sec=20.0,
            cache_hit_rate=90.0,
            avg_payload_size_kb=150.0
        )
        
        assert summary.export_type == "structure"
        assert summary.mean_time_ms == 50.0
        assert summary.throughput_per_sec == 20.0
        assert summary.cache_hit_rate == 90.0
    
    def test_improvement_vs_baseline(self):
        """Test improvement calculation vs baseline."""
        cached = BenchmarkSummary(
            export_type="structure",
            cache_enabled=True,
            iterations=10,
            min_time_ms=40.0,
            max_time_ms=60.0,
            mean_time_ms=50.0,
            median_time_ms=49.0,
            stddev_ms=5.0,
            total_time_s=0.5,
            throughput_per_sec=20.0
        )
        
        non_cached = BenchmarkSummary(
            export_type="structure",
            cache_enabled=False,
            iterations=10,
            min_time_ms=200.0,
            max_time_ms=300.0,
            mean_time_ms=250.0,
            median_time_ms=245.0,
            stddev_ms=25.0,
            total_time_s=2.5,
            throughput_per_sec=4.0
        )
        
        # Cached should be 80% faster than non-cached
        # (250 - 50) / 250 * 100 = 80%
        improvement = cached.improvement_vs(non_cached)
        assert improvement == 80.0
    
    def test_improvement_vs_slower_baseline(self):
        """Test negative improvement (regression)."""
        slower = BenchmarkSummary(
            export_type="structure",
            cache_enabled=True,
            iterations=10,
            min_time_ms=100.0,
            max_time_ms=120.0,
            mean_time_ms=110.0,
            median_time_ms=109.0,
            stddev_ms=5.0,
            total_time_s=1.1,
            throughput_per_sec=9.0
        )
        
        faster = BenchmarkSummary(
            export_type="structure",
            cache_enabled=False,
            iterations=10,
            min_time_ms=40.0,
            max_time_ms=60.0,
            mean_time_ms=50.0,
            median_time_ms=49.0,
            stddev_ms=5.0,
            total_time_s=0.5,
            throughput_per_sec=20.0
        )
        
        # Slower is actually slower (negative improvement)
        improvement = slower.improvement_vs(faster)
        assert improvement < 0


class TestFHIRExportBenchmark:
    """Test FHIRExportBenchmark class."""
    
    def test_init(self):
        """Test benchmark initialization."""
        benchmark = FHIRExportBenchmark(
            base_url="http://localhost:8000",
            auth_token="test-token"
        )
        
        assert benchmark.base_url == "http://localhost:8000"
        assert benchmark.auth_token == "test-token"
        assert benchmark.results == []
    
    def test_get_headers_with_auth(self):
        """Test header generation with authentication."""
        benchmark = FHIRExportBenchmark(auth_token="test-token")
        headers = benchmark._get_headers()
        
        assert headers["Accept"] == "application/json"
        assert headers["Authorization"] == "Bearer test-token"
    
    def test_get_headers_without_auth(self):
        """Test header generation without authentication."""
        benchmark = FHIRExportBenchmark()
        headers = benchmark._get_headers()
        
        assert headers["Accept"] == "application/json"
        assert "Authorization" not in headers
    
    def test_calculate_cache_hit_rate(self):
        """Test cache hit rate calculation."""
        benchmark = FHIRExportBenchmark()
        
        before = {"hits": 100, "misses": 50}
        after = {"hits": 190, "misses": 60}
        
        # Delta: +90 hits, +10 misses = 90/100 = 90%
        hit_rate = benchmark._calculate_cache_hit_rate(before, after)
        assert hit_rate == 90.0
    
    def test_calculate_cache_hit_rate_zero_total(self):
        """Test cache hit rate with no change."""
        benchmark = FHIRExportBenchmark()
        
        stats = {"hits": 100, "misses": 50}
        
        hit_rate = benchmark._calculate_cache_hit_rate(stats, stats)
        assert hit_rate == 0.0
    
    @patch('requests.get')
    def test_benchmark_export_success(self, mock_get):
        """Test successful benchmark execution."""
        # Mock successful responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"resourceType": "Bundle"}'
        mock_get.return_value = mock_response
        
        benchmark = FHIRExportBenchmark()
        
        results = benchmark.benchmark_export(
            export_type="structure",
            ej_id=1,
            iterations=3,
            cache_enabled=True
        )
        
        # Should have 3 results
        assert len(results) == 3
        
        # All should be successful
        for result in results:
            assert result.status_code == 200
            assert result.error is None
            assert result.response_time_ms > 0
    
    @patch('requests.get')
    def test_benchmark_export_failure(self, mock_get):
        """Test benchmark with request failures."""
        # Mock failing responses
        mock_get.side_effect = Exception("Connection error")
        
        benchmark = FHIRExportBenchmark()
        
        results = benchmark.benchmark_export(
            export_type="structure",
            ej_id=1,
            iterations=2,
            cache_enabled=False
        )
        
        # Should have 2 results with errors
        assert len(results) == 2
        
        for result in results:
            assert result.error is not None
            assert "Connection error" in result.error
    
    def test_summarize_results(self):
        """Test result summarization."""
        results = [
            BenchmarkResult("structure", True, 40.0, 200, 10000),
            BenchmarkResult("structure", True, 50.0, 200, 10000),
            BenchmarkResult("structure", True, 60.0, 200, 10000),
        ]
        
        benchmark = FHIRExportBenchmark()
        summary = benchmark.summarize_results(results)
        
        assert summary.export_type == "structure"
        assert summary.cache_enabled is True
        assert summary.iterations == 3
        assert summary.min_time_ms == 40.0
        assert summary.max_time_ms == 60.0
        assert summary.mean_time_ms == 50.0
        assert summary.median_time_ms == 50.0
    
    def test_summarize_results_with_errors(self):
        """Test summarization excludes errors."""
        results = [
            BenchmarkResult("structure", True, 50.0, 200, 10000),
            BenchmarkResult("structure", True, 1000.0, 500, 0, error="Timeout"),
            BenchmarkResult("structure", True, 60.0, 200, 10000),
        ]
        
        benchmark = FHIRExportBenchmark()
        summary = benchmark.summarize_results(results)
        
        # Should only count successful results
        assert summary.iterations == 2
        assert summary.mean_time_ms == 55.0  # (50 + 60) / 2
    
    def test_summarize_empty_results(self):
        """Test summarization with no results."""
        benchmark = FHIRExportBenchmark()
        
        with pytest.raises(ValueError, match="No results"):
            benchmark.summarize_results([])
    
    def test_summarize_all_errors(self):
        """Test summarization with all failures."""
        results = [
            BenchmarkResult("structure", True, 1000.0, 500, 0, error="Error 1"),
            BenchmarkResult("structure", True, 1000.0, 500, 0, error="Error 2"),
        ]
        
        benchmark = FHIRExportBenchmark()
        
        with pytest.raises(ValueError, match="No valid results"):
            benchmark.summarize_results(results)
    
    def test_generate_report(self):
        """Test report generation."""
        summaries = [
            BenchmarkSummary(
                export_type="structure",
                cache_enabled=True,
                iterations=10,
                min_time_ms=40.0,
                max_time_ms=60.0,
                mean_time_ms=50.0,
                median_time_ms=49.0,
                stddev_ms=5.0,
                total_time_s=0.5,
                throughput_per_sec=20.0,
                cache_hit_rate=90.0,
                avg_payload_size_kb=150.0
            ),
            BenchmarkSummary(
                export_type="structure",
                cache_enabled=False,
                iterations=10,
                min_time_ms=200.0,
                max_time_ms=300.0,
                mean_time_ms=250.0,
                median_time_ms=245.0,
                stddev_ms=25.0,
                total_time_s=2.5,
                throughput_per_sec=4.0,
                avg_payload_size_kb=150.0
            ),
        ]
        
        benchmark = FHIRExportBenchmark()
        report = benchmark.generate_report(summaries)
        
        # Check report contains key sections
        assert "FHIR Export Performance Benchmark Report" in report
        assert "STRUCTURE" in report
        assert "WITH CACHE" in report
        assert "WITHOUT CACHE" in report
        assert "PERFORMANCE GAIN" in report
        assert "RECOMMENDATIONS" in report
        
        # Check performance improvement is calculated
        assert "80.0% faster" in report
    
    def test_generate_report_high_improvement(self):
        """Test report recommendations for high improvement."""
        summaries = [
            BenchmarkSummary(
                export_type="structure",
                cache_enabled=True,
                iterations=10,
                min_time_ms=20.0,
                max_time_ms=30.0,
                mean_time_ms=25.0,
                median_time_ms=25.0,
                stddev_ms=2.0,
                total_time_s=0.25,
                throughput_per_sec=40.0,
                cache_hit_rate=95.0,
                avg_payload_size_kb=100.0
            ),
            BenchmarkSummary(
                export_type="structure",
                cache_enabled=False,
                iterations=10,
                min_time_ms=200.0,
                max_time_ms=300.0,
                mean_time_ms=250.0,
                median_time_ms=250.0,
                stddev_ms=25.0,
                total_time_s=2.5,
                throughput_per_sec=4.0,
                avg_payload_size_kb=100.0
            ),
        ]
        
        benchmark = FHIRExportBenchmark()
        report = benchmark.generate_report(summaries)
        
        # Should recommend cache for high improvement (90% = 250->25)
        assert "SIGNIFICANT" in report or "HIGHLY RECOMMENDED" in report


class TestIntegration:
    """Integration tests for benchmark workflow."""
    
    @patch('requests.get')
    def test_full_benchmark_workflow(self, mock_get):
        """Test complete benchmark workflow."""
        # Mock responses
        mock_response = Mock()
        mock_response.status_code = 200
        mock_response.content = b'{"resourceType": "Bundle", "entry": []}'
        mock_get.return_value = mock_response
        
        benchmark = FHIRExportBenchmark(base_url="http://localhost:8000")
        
        # Run benchmark
        results = benchmark.benchmark_export(
            export_type="structure",
            ej_id=1,
            iterations=5,
            cache_enabled=True
        )
        
        # Summarize
        summary = benchmark.summarize_results(results)
        
        # Generate report
        report = benchmark.generate_report([summary])
        
        # Verify complete workflow
        assert len(results) == 5
        assert summary.iterations == 5
        assert "STRUCTURE" in report
        assert benchmark.base_url in report


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
