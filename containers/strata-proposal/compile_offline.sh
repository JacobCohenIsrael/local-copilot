#!/bin/bash
# Unexecuted proposal. Only an approved controller may start this compiler.
set -Eeuo pipefail
stage=startup
trap 'code=$?; printf "STRATA_BUILD_FAILURE stage=%s line=%s exit=%s\n" "$stage" "$LINENO" "$code" >&2; exit "$code"' ERR
export PATH=/tools/cmake/bin:/tools/ninja/bin:/usr/local/cuda/bin:/usr/bin:/bin
export OMP_NUM_THREADS=1 OPENBLAS_NUM_THREADS=1 CMAKE_BUILD_PARALLEL_LEVEL=1
export HOME=/work/home TMPDIR=/work/tmp XDG_CACHE_HOME=/work/cache
export CUDA_CACHE_DISABLE=1
require() {
    local check=$1; shift
    if ! test "$@"; then
        printf 'STRATA_STARTUP_FAILURE check=%s\n' "$check" >&2
        return 31
    fi
}
require source-readable -r /source/CMakeLists.txt
require ggml-readable -r /source/third_party/llama.cpp/ggml/CMakeLists.txt
require cxx-executable -x /usr/bin/g++
require cuda-executable -x /usr/local/cuda/bin/nvcc
require cmake-executable -x /tools/cmake/bin/cmake
require ninja-executable -x /tools/ninja/bin/ninja
mkdir -p /work/home /work/tmp /work/cache /work/build /work/engine
# No apt, pip, setup.py, source copy, automatic retry or network fallback.
stage=tool-versions
# Capture complete output: head under pipefail can turn a valid version into SIGPIPE.
cmake_version=$(/tools/cmake/bin/cmake --version)
ninja_version=$(/tools/ninja/bin/ninja --version)
printf 'STRATA_TOOL_VERSION cmake=%s ninja=%s\n' "${cmake_version%%$'\n'*}" "$ninja_version"
require cmake-version "${cmake_version%%$'\n'*}" = 'cmake version 4.4.3'
# This exact Kitware suffix is embedded in the hash-pinned PyPI Ninja wheel.
require ninja-version "$ninja_version" = '1.13.2.git.kitware.jobserver-pipe-1'
stage=configure
printf 'STRATA_BUILD_STAGE %s\n' "$stage"
/tools/cmake/bin/cmake -G Ninja -DCMAKE_MAKE_PROGRAM=/tools/ninja/bin/ninja \
    -S /source -B /work/build -DCMAKE_BUILD_TYPE=Release \
    -DSTRATA_ENABLE_CUDA=ON -DSTRATA_BUILD_TESTS=OFF \
    -DSTRATA_BUILD_CONVERSATION_TESTS=OFF -DCMAKE_CUDA_ARCHITECTURES=86 \
    -DCMAKE_CXX_COMPILER=/usr/bin/g++ -DCMAKE_CUDA_COMPILER=/usr/local/cuda/bin/nvcc \
    -DSTRATA_GGML_DIR=/source/third_party/llama.cpp -DFETCHCONTENT_FULLY_DISCONNECTED=ON
stage=compile
printf 'STRATA_BUILD_STAGE %s\n' "$stage"
/tools/cmake/bin/cmake --build /work/build --target strata --parallel 1
stage=export
test -f /work/build/strata
cp /work/build/strata /work/engine/strata
if [ -f /work/build/libstrata_kq.so ]; then
    cp /work/build/libstrata_kq.so /work/engine/libstrata_kq.so
fi
cp /input/BUILD.json /work/engine/BUILD.json
printf '{"state":"BUILD_COMPLETE_AWAITING_EXPORT","modelStarted":false}\n' > /work/ready.tmp
mv /work/ready.tmp /work/ready.json
# tmpfs vanishes at stop. A future bounded exporter must collect engine artifacts
# before acknowledging completion. The outer 1800-second timeout still applies.
while [ ! -f /work/export.complete ]; do sleep 1; done
