# Docker lifecycle harness — sleeping workers only

Implemented 16 October 2026. This is a real Docker control test with **synthetic
telemetry**, not a working Strata/OpenCode integration or an approved model
operating policy. It has no AI-engine startup path, GPU/device requests, model
mounts, project mounts, network, API calls, or hardware probes. It never reads
`D:\AI` or model data. The earlier TypeScript supervisor remains a separate,
unchanged pure simulator.

The default successful worker sleeps briefly, emits a completion marker, and
exits. It spawns another sleeping Python process so shutdown tests include a
descendant. No coding result, patch, token accounting, or real safety measurement
is produced. Every result identifies `mode: docker-dummy-only` and
`codingPerformed: false`.

## CLI for orchestration development

Run from the Local Copilot project with the installed Python interpreter. The
Docker engine must already be running and the preflight image must be cached.
The harness never silently starts Docker, pulls images, or builds dependencies.

```powershell
python -B containers/lifecycle/supervisor.py plan
python -B containers/lifecycle/supervisor.py policy
python -B containers/lifecycle/supervisor.py run
python -B containers/lifecycle/supervisor.py status
```

`plan` and `policy` write nothing and contact no Docker service. `run` executes
one fixed dummy scenario; there is no arbitrary command, task input, executable,
model, mount, policy override, or live-mode option. Supported scenarios:
`success`, `wait`, `gpu-hot`, `sensor-lost`, `hang`, `ignore-stop`.
`gpu-hot` injects a numeric sample; it does not heat or query the GPU.
`wait` and `hang` both sleep until cancellation or deadline; `ignore-stop`
additionally ignores SIGTERM to test forced stopping.

While a `wait` scenario is active, another process can inspect the status and
request cancellation of that exact run:

```powershell
python -B containers/lifecycle/supervisor.py run --scenario wait
# In another terminal, obtain runId from status, then:
python -B containers/lifecycle/supervisor.py cancel --run-id <runId>
```

Cancellation acknowledges the request, not completed cleanup. Check the run
result/status afterward. Ctrl+C also requests cancellation during the polling
loop. A Windows process termination is not assumed to deliver that handler;
the worker's lease expiry covers loss of the host process in these tests.

Faults persist across invocations and block new work. Review the evidence before
resetting this **dummy-only** domain:

```powershell
python -B containers/lifecycle/supervisor.py reset-fault --acknowledge-dummy --reason "Reviewed expected dummy fault and verified cleanup"
```

A reset requires verified container removal, matching policy, an explicit
acknowledgement, and an audit reason. It cannot approve a policy change or live
work. Do not reset a real incident automatically. The integration tests reset
only their isolated test domains to verify the reset mechanism.

Commands emit JSON. Exit 0 means command/success; 2 means rejection, ordinary
error, or cancellation; 3 means a fault result/status; 4 means a busy run/reset.
`status` during an active run returns `busy: true` without taking over. Treat
the completed response, saved receipt, and current state together; partial
artifacts after a failure are not a completion receipt.

## Isolation and failure behavior

The fixed image is the same pinned official Python Linux amd64 image used by
preflight. Each running container receives 0.5 CPU, 256 MiB RAM, no swap, at most
32 processes, a read-only root, a non-root user, no capabilities, and no new
privileges. Its only mounts are the staged dummy script and its session control
directory, both read-only. There is no published port, Docker socket, GPU,
network, or automatic restart. The exact entrypoint, arguments, image, labels,
mounts, resource caps, and logging options are inspected before startup.

The CLI uses one canonical state domain at
`.runtime/docker-dummy-supervisor`, with an OS byte-range lock on Windows.
The OS releases the lock when its process exits; the saved active marker remains.
The lock file is not deleted or guessed stale. Tests use separate domains under
`.runtime/docker-dummy-tests` through the Python test API, never a live domain.
This is a development guard for a single checkout, not yet a protected
machine-wide guard across copies of the project or Windows accounts.

State transitions are `OFF → STARTING → RUNNING → STOPPING → OFF`.
Safety/infrastructure failures latch `FAULT` before cleanup. The first fault is
preserved. `status` or the next `run` after host-process death latches
`UNCLEAN_EXIT`, attempts cleanup of the saved owned identity, and refuses a new
run. Neither recovery nor fault reset restarts a worker. Reset is a separately
audited action.

The host refreshes a bounded append-only heartbeat. Both dummy processes check
its size using file metadata, exit after 2.5 seconds without a change, and also
exit after 12 seconds of their own runtime regardless of heartbeats. This avoids
Windows/Linux bind-mount sharing conflicts when replacing an open lease file.
The host task deadline is 4 seconds; sampling sleeps 0.2 seconds between Docker
operations. Docker operations have 5-second timeouts. Detection and cleanup
latency include those calls and scheduling; these are not hard real-time bounds.

Normal cleanup sends SIGTERM with a one-second grace period. Docker then uses
SIGKILL if needed; exit 137 latches `STOP_TIMEOUT`. A failed stop command triggers
a separately bounded kill after verifying ownership again. These settings are
for sleeping dummies only, not Strata's model-loading or normal shutdown policy.
See [Docker stop behavior](https://docs.docker.com/reference/cli/docker/container/stop/).

Cleanup verifies the exact container name and session labels before acting and
targets the returned ID. It never stops by process name or broad container
filter, prunes Docker, or touches existing workloads. Log/journal failures cannot
prevent the attempt to stop/remove the owned dummy. If Docker or storage becomes
unavailable, cleanup is not guaranteed; the fault/active marker blocks further
admission. The dummy's own expiry ends its processes while the Linux VM remains
scheduled. This cooperative expiry is not an independent watchdog capable of
controlling a hung native Strata engine or CUDA work.

## Evidence and tests

Each session saves its launch plan and script hash, bounded JSONL events with
synthetic metrics, a bounded worker log, and a structured result. Docker log
rotation explicitly uses `json-file`, 64 KiB, one file. Events are capped at
128 KiB; the heartbeat at 128 bytes; captured worker output at 16 KiB. Historical
session directories are retained, so total retained disk use still grows.
State/result writes flush before replacement. This is not a guarantee against
power loss or file tampering; corrupt/mismatched state blocks admission.

Mocked host tests need no Docker access:

```powershell
python -B -m unittest discover -s containers/lifecycle -p 'test_supervisor.py' -v
```

Real Docker verification is explicitly invoked:

```powershell
python -B containers/lifecycle/verify_docker.py --execute
```

It runs seven cases sequentially: completion, cancellation/concurrent rejection,
synthetic heat, synthetic sensor loss, task deadline, ignored graceful stop,
and abrupt termination of the exact host test process. The last case waits for
lease expiry before testing recovery. A stopped foreign-labelled test fixture
must survive all sessions and is then removed by the test that created it.
No actual pre-existing container is deliberately interrupted. Receipts are under
`.runtime/docker-dummy-tests/<testId>/verification.json`.

The completed tests do not establish model fit, CUDA/driver compatibility, real
sensor availability, safe thermal thresholds, context/file/token gates for
OpenCode, authenticated network access, two-container stop ordering, a native
engine watchdog, or behavior through Windows suspend/resume or daemon failure.

## Next gate

Prepare a pinned Linux Strata build and configuration proposal, then design and
validate read-only host telemetry and an independent host watchdog. A real
model configuration, resource/thermal policy, build workload, and first model
launch must be concrete and separately reviewed. Existing Windows settings stay
untouched. No successful dummy test authorizes Strata startup or policy changes.
