#!/bin/bash
# Quick benchmark runner for FHIR exports

set -e

# Colors
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

echo -e "${GREEN}🚀 FHIR Export Benchmark Runner${NC}"
echo ""

# Check if server is running
echo "Checking if API server is running..."
if ! curl -s http://localhost:8000/health > /dev/null 2>&1; then
    echo -e "${YELLOW}⚠️  API server not detected at http://localhost:8000${NC}"
    echo "Please start the server first: uvicorn app.app:app --reload"
    exit 1
fi

echo -e "${GREEN}✓ Server is running${NC}"
echo ""

# Default parameters
EJ_ID=${1:-1}
ITERATIONS=${2:-10}

echo "Parameters:"
echo "  EJ ID: $EJ_ID"
echo "  Iterations: $ITERATIONS"
echo ""

# Run benchmark
python3 tools/benchmark_fhir_exports.py \
    --ej-id "$EJ_ID" \
    --iterations "$ITERATIONS" \
    --with-cache \
    --without-cache \
    --export-types structure patients venues

echo ""
echo -e "${GREEN}✅ Benchmark complete!${NC}"
echo "Results saved in: benchmark_results/"
