#!/usr/bin/env python3
# scripts/monitor_flaky_tests.py
"""
Monitor and detect flaky tests by running them multiple times
Identifies tests that fail intermittently for investigation
"""

import subprocess
import json
import sys
from pathlib import Path
from collections import defaultdict
import argparse


def run_test_multiple_times(test_path, runs=5):
    """Run a specific test multiple times and collect results"""
    results = []

    for i in range(runs):
        print(f"Run {i+1}/{runs} for {test_path}...")
        try:
            result = subprocess.run([
                'python', '-m', 'pytest', test_path, '-q', '--tb=no', '--disable-warnings'
            ], capture_output=True, text=True, timeout=300)

            success = result.returncode == 0
            results.append({
                'run': i + 1,
                'success': success,
                'returncode': result.returncode,
                'stdout': result.stdout,
                'stderr': result.stderr
            })

        except subprocess.TimeoutExpired:
            results.append({
                'run': i + 1,
                'success': False,
                'returncode': -1,
                'stdout': '',
                'stderr': 'Timeout after 300 seconds'
            })

    return results


def analyze_flakiness(results):
    """Analyze test results to determine flakiness"""
    total_runs = len(results)
    successful_runs = sum(1 for r in results if r['success'])
    failure_rate = (total_runs - successful_runs) / total_runs

    failures = [r for r in results if not r['success']]

    return {
        'total_runs': total_runs,
        'successful_runs': successful_runs,
        'failure_rate': failure_rate,
        'is_flaky': failure_rate > 0 and failure_rate < 1.0,
        'failures': failures
    }


def find_potential_flaky_tests():
    """Find tests that might be flaky based on markers and recent failures"""
    try:
        # Get all tests with flaky marker
        result = subprocess.run([
            'python', '-m', 'pytest', '--collect-only', '-q', '-m', 'flaky'
        ], capture_output=True, text=True)

        flaky_tests = []
        for line in result.stdout.split('\n'):
            if '::' in line and 'test_' in line:
                flaky_tests.append(line.strip())

        return flaky_tests

    except Exception as e:
        print(f"Error finding flaky tests: {e}")
        return []


def main():
    parser = argparse.ArgumentParser(description='Monitor flaky tests')
    parser.add_argument('--runs', type=int, default=5, help='Number of runs per test')
    parser.add_argument('--test', help='Specific test to monitor')
    parser.add_argument('--output', help='Output JSON file for results')

    args = parser.parse_args()

    if args.test:
        tests_to_monitor = [args.test]
    else:
        tests_to_monitor = find_potential_flaky_tests()
        if not tests_to_monitor:
            print("No flaky tests found. Use --test to specify a test to monitor.")
            return

    print(f"Monitoring {len(tests_to_monitor)} test(s) with {args.runs} runs each...")

    all_results = {}

    for test_path in tests_to_monitor:
        print(f"\n{'='*60}")
        print(f"Monitoring: {test_path}")
        print(f"{'='*60}")

        results = run_test_multiple_times(test_path, args.runs)
        analysis = analyze_flakiness(results)

        all_results[test_path] = {
            'results': results,
            'analysis': analysis
        }

        print(f"Results: {analysis['successful_runs']}/{analysis['total_runs']} passed")
        print(".2f")

        if analysis['is_flaky']:
            print("⚠️  FLAKY TEST DETECTED!")
            print("Failure details:")
            for failure in analysis['failures']:
                print(f"  Run {failure['run']}: {failure['stderr'] or 'Failed'}")
        elif analysis['failure_rate'] == 0:
            print("✅ CONSISTENTLY PASSING")
        else:
            print("❌ CONSISTENTLY FAILING")

    # Save results to JSON if requested
    if args.output:
        with open(args.output, 'w') as f:
            json.dump(all_results, f, indent=2)
        print(f"\nResults saved to: {args.output}")

    # Summary
    flaky_count = sum(1 for r in all_results.values() if r['analysis']['is_flaky'])
    print(f"\n{'='*60}")
    print("SUMMARY")
    print(f"{'='*60}")
    print(f"Total tests monitored: {len(all_results)}")
    print(f"Flaky tests detected: {flaky_count}")
    print(f"Consistently passing: {sum(1 for r in all_results.values() if r['analysis']['failure_rate'] == 0)}")
    print(f"Consistently failing: {sum(1 for r in all_results.values() if r['analysis']['failure_rate'] == 1.0)}")

    if flaky_count > 0:
        print("\nFlaky tests requiring investigation:")
        for test, data in all_results.items():
            if data['analysis']['is_flaky']:
                rate = data['analysis']['failure_rate']
                print(".2f")


if __name__ == "__main__":
    main()