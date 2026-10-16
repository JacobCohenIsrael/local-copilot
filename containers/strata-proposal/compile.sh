#!/bin/bash
# Run only inside the separately approved, inspected capped compiler container.
set -euo pipefail
export DEBIAN_FRONTEND=noninteractive OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1
export CMAKE_BUILD_PARALLEL_LEVEL=1 STRATA_NVCC=/usr/local/cuda/bin/nvcc
cd /opt/strata
cp -a /input/source/. .
apt-get update
apt-get install -y --no-install-recommends build-essential ca-certificates curl git libatomic1 libgomp1 python3 python3-pip python3-venv unzip
python3 -m venv .venv
.venv/bin/pip install --no-cache-dir -r requirements.txt
.venv/bin/python /input/bounded_build.py
# No engine execution, model setup, inference, benchmark, or automatic image commit.
