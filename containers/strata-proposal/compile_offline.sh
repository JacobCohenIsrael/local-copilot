#!/bin/bash
# Unexecuted proposal. Only an approved controller may start this compiler.
set -euo pipefail
export PATH=/tools/cmake/bin:/tools/ninja/bin:/usr/local/cuda/bin:/usr/bin:/bin
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CMAKE_BUILD_PARALLEL_LEVEL=1
export HOME=/work/home TMPDIR=/work/tmp XDG_CACHE_HOME=/work/cache
export CUDA_CACHE_DISABLE=1
test -f /source/CMakeLists.txt
test -f /source/third_party/llama.cpp/ggml/CMakeLists.txt
test -x /usr/bin/g++
test -x /usr/local/cuda/bin/nvcc
test -x /tools/cmake/bin/cmake
test -x /tools/ninja/bin/ninja
mkdir -p /work/home /work/tmp /work/cache /work/build /work/engine
# No apt, pip, setup.py, source copy, automatic retry or network fallback.
test "$(/tools/cmake/bin/cmake --version | head -n 1)" = 'cmake version 4.4.3'
test "$(/tools/ninja/bin/ninja --version)" = '1.13.2'
/tools/cmake/bin/cmake -G Ninja -DCMAKE_MAKE_PROGRAM=/tools/ninja/bin/ninja \
    -S /source -B /work/build -DCMAKE_BUILD_TYPE=Release \
    -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
    -DSTRATA_BUILD_CONVERSATION_TESTS=OFF -DCMAKE_CUDA_ARCHITECTURES=86 \
    -DCMAKE_CXX_COMPILER=/usr/bin/g++ -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
    -DSTRATA_GGML_DIR=/source/third_party/llama.cpp -DFETCHCONTENT_FULLY_DISCONNECTED=ON
/tools/cmake/bin/cmake --build /work/build --target strata --parallel 1
test -f /work/build/strata
cp /work/build/strata /work/engine/strata
if [ -f /work/build/libstrata_kq.so ]; then
    cp /work/build/libstrata_kq.so /work/engine/libstrata_kq.so
fi
cp /input/BUILD.json /work/engine/BUILD.json
printf '{"state":"BUILD_COMPLETE_AWAITING_EXPORT","modelStarted":false}\n' > /work/ready.json
# tmpfs vanishes at stop. A future bounded exporter must collect engine artifacts
# before acknowledging completion. The outer 1800-second timeout still applies.
while [ ! -f /work/export.complete ]; do sleep 1; done
