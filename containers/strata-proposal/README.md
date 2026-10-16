# Pinned Linux Strata build proposal

This directory is a review artifact. Nothing here has been built, started, or
approved. `build-proposal.json` has both build and model launch disabled. The
Dockerfile is named `.proposed`; its default entrypoint refuses execution even
if a future owner-approved build succeeds. No launch command or live thermal
policy is supplied while required CPU telemetry is missing.

The owner selected Strata itself in Docker. The prepared compile route now uses
an ordinary capped Docker container, specified in
`.runtime/strata-build/1537f5ec/build-manifest.json`; the Dockerfile below is the
earlier reference recipe, not the selected execution path. `prepare.py`
downloaded the two pinned source archives (62,426,870 bytes total), validated
their paths, staged the source without executing it, and cross-checked four key
Strata files against the previously reviewed snapshot. The llama.cpp source is
already staged where setup expects it, avoiding that source download at compile
time. SHA-256 records establish the downloaded archive identities; source origin
is the pinned GitHub URL over TLS, not an independent signature verification.

The manifest proposes one CPU, 4 GiB RAM, zero swap, 128 processes, runtime
`runc`, no GPU requests, no restart, and a 30-minute inner timeout. Only its own
source/helper input is mounted read-only; no original installation, weights,
host credentials, or Docker socket. The writable container layer is needed for
apt/pip and build output. Bridge networking is proposed solely for build
dependencies; its download volume is not yet bounded or approved. The base CUDA
image still has not been pulled. The separate monitor/guard must be adapted and
the actual Docker settings inspected before this compiler is admitted. The
manifest does not execute anything and remains `buildEnabled: false`.

The [compiler guard connection](BUILD_GUARD.md) supplies a manifest-bound target
matcher, bounded ASUS reader, and independent stop-path rehearsals. Nine mocked
checks and four real non-compiling Docker cases passed. The real three-sample
CPU reader completed; missing throttle status still prevents admission. No live
build policy has been approved or activated.

After a successful approved compilation, image creation is a separate reviewed
step, with a disabled default entrypoint and a recorded resulting image identity.
Do not automatically run the engine as a build check. The source/archive path
test rejects traversal, wrong archive roots, case aliases, reserved Windows
names and symlinks before writing output files.

Source: Strata v0.1.44.1 at commit
`296b59d2f73c8f04a805df29c2fa97655adace78`; its llama.cpp dependency is pinned to
`3cf03257f219afbe7334045ff7c6a06ac68c627d`. The official CUDA 13.0 Ubuntu 24.04
Linux amd64 base is pinned by manifest digest. Only registry metadata was read;
no CUDA image layers were pulled. Do not use the live `main` branch or copy the
existing `D:\AI` installation into the source context.

The suggested build targets only CUDA architecture 86, omits the vision build,
and compiles with exactly one job without an automatic retry. Inspection found
that upstream `setup.cmake_build` explicitly passes `-j max(2, cpu_count/2)`;
setting `CMAKE_BUILD_PARALLEL_LEVEL=1` alone would not override that. The proposed
helper uses explicit CMake commands instead. It is syntax-checked only, not a
validated Linux build recipe. It imports upstream setup only inside a future
approved builder; host tests never import or execute upstream code.

The proposed one-CPU / 4 GiB / no-swap builder envelope must be enforced and
inspected outside this Dockerfile, with a harmless quota check before compilation.
It is not assumed that ordinary Docker BuildKit build flags provide these caps.
Compiling CUDA code uses CPU/RAM and can heat the laptop even without GPU devices;
the CPU sensor/watchdog and explicit build-workload approval gates still apply.
There is no automatic builder start or approval bypass in this milestone.

The source and base identities are pinned; the build is not yet fully hermetic.
Upstream Python requirements pin versions but not all distribution hashes;
Ubuntu package repository state, compiler dependencies, and downloaded artifacts
need a captured lock/checksum record or an explicit reproducibility exception.
Full source staging, disk/download budgets, build output identity, and compiler
compatibility remain unverified. The current NVIDIA driver is 617.14, above the
CUDA 13 documented driver-generation floor of 580; no CUDA runtime test has run.
See [NVIDIA's CUDA 13.0 release notes](https://docs.nvidia.com/cuda/archive/13.0.0/cuda-toolkit-release-notes/index.html).

Runtime candidates deliberately differ from the preserved Windows setup:
8,192 engine context instead of 65,536; mmap expert reads instead of resident
experts; speculative decoding disabled initially; an explicit VRAM reserve;
separate capped RAM/CPU budgets; no automatic setup, downloads, or restart.
These are proposals requiring review, not established safe limits. mmap can
still cause substantial I/O and page-cache use or an OOM; a file fitting on disk
does not establish an acceptable runtime working set. The actual Linux engine
arguments, CPU-prefill behavior, profile update paths, and MTP-disabled path must
be checked before generating an owner-approvable launch manifest.

Model data would remain read-only, with a copied expert profile and generated
Linux configuration in an isolated session area. No existing launcher or JSON
configuration was modified. No automatic setup against the original data
volume is permitted by this proposal.
