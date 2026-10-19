# Native empty-engine rehearsal: ready for owner review

**Execution update:** this reviewed attempt has now run once and is consumed.
It reached FAULT before guest startup. See
[the preserved result](NATIVE_REHEARSAL_RESULT.md). Keep the original fault,
unstarted container and bare attached disk; no automatic retry or detach.
The preparation and canceled-launch descriptions below are historical.

The Windows-to-WSL bridge, installed runtime staging and admitted guest startup
are connected. **No native disk, mount or private engine has been started.**
The next operation is one small, monitored rehearsal. Import, compilation and
model execution remain disabled. The actual approval file is absent.

## Exact proposed operation

Review SHA256:
`2b5bda1e8c35a5520562c7967d2e1a518faf285e9b4406f4d9b57c2ff20aa743`.
The complete packet is at
`.runtime/isolation-review/2b5bda1e8c35a5520562c7967d2e1a518faf285e9b4406f4d9b57c2ff20aa743/review.json`.
Its helper, interpreter, source-evidence, runtime and configuration hashes must
still match immediately before execution. Existing approvals cannot unlock it.

| Control | This rehearsal only |
| --- | --- |
| Attempt | One; session `f1705ab385be4fedb419fb33921aec56`; no automatic retry/reset |
| Disk | New fixed 128-MiB VHDX; at most 384 MiB including file overhead; never resize |
| Disk path | `.runtime/isolated-stores/f1705ab385be4fedb419fb33921aec56/store.vhdx` |
| Evidence | New `.runtime/native-isolation-1/`; old attempts and cache remain intact |
| Host reserve | Retain at least 20 GiB free; reject wrong allocation/type/identity |
| Duration | At most 180 seconds of work, 90-second baseline wait, 300-second outer deadline |
| CPU admission | Fresh real readings at or below 92 C for ten seconds; stop at or above 97 C |
| Sensor | Existing read-only ASUS reader; source latency/calibration remain limited and throttle status unknown |
| Existing WSL limits | Unchanged: one CPU, 6 GiB maximum RAM, no swap |
| Private engine envelope | One CPU, 4 GiB RAM, no swap, 128 processes; checked before disk work |
| Windows helper | Owned job: one logical CPU, 256 MiB, four processes |
| Runtime | 33 staged files, 182,104,353 bytes, from the installed Docker ISO; no download |
| Temporary memory | Runtime 256 MiB; `/run` 64 MiB; `/tmp` 64 KiB; empty `/store` anchor 4 KiB; shared memory 64 KiB |
| Container input | Cached pinned Python image only, `pull=never`; read-only root and input/runtime binds |
| Network / GPU | Network `none`; no GPU device, host socket or shared PID namespace |
| Logs | Two outer Docker log files, each at most 128 KiB; bounded guest diagnostics |
| Retention | Keep the VHDX, stopped container and all evidence; no automatic deletion |

This proposes root inside the isolated container with CHOWN, DAC_OVERRIDE,
FOWNER, KILL, SETGID, SETUID, SETFCAP and **SYS_ADMIN**, plus
**AppArmor unconfined** for the owned filesystem mount. Docker's default seccomp
profile remains. These choices, the new workload scope and its source/throttle
exception need explicit approval. No firmware, power mode, global Docker
configuration or WSL configuration change is part of the operation.

## Sequence and acceptance

1. Recheck exact approval, preserved evidence, global limits and fresh CPU
   baseline. Claim the one attempt durably before starting the reader/work.
2. Create only the new owned VHDX. Query its fixed type, identifier, capacity,
   physical size and file identity. Temporarily attach its own handle on Windows
   without a drive letter. Derive the physical disk path from that handle;
   recheck disk number/capacity and zeroed first block before writing and reading
   back the session's random ownership marker. Detach that handle.
3. Attach that exact VHDX to WSL with `--bare`. A read-only bounded scan must find
   exactly one unmounted device matching capacity and the full marker. Bind its
   major/minor number and kernel disk sequence. A guessed device name is refused.
4. Create and inspect the restricted container. Start its PID-1 bootstrap with
   the exact approved packet. Arm an independent guest lease fuse; require new
   pulse growth before work. Copy and hash the runtime into bounded executable
   memory and check dynamic-library resolution before any format/daemon start.
5. Recheck the passed device's nonce, capacity and disk sequence. Format only
   that new device as ext4, disable deferred initialization/discard, mount it,
   then start separate containerd and dockerd processes. All their persistent
   data and temporary payload go on that device; control state uses bounded memory.
6. Require the private Unix endpoint to report its owned data/socket paths and
   **zero images and zero containers**. No image-load or container-run API is used.
7. After validated READY, deliberately withhold only the guest pulse. The real
   Windows CPU monitor continues. The three-second guest lease must expire and
   fence all descendant processes in its private PID namespace. This tests the
   emergency stop path, including a stalled/dead owner; it is not a graceful
   import-shutdown qualification.
8. Require confirmed process exit, no remaining namespace descendants, normal
   filesystem unmount and a successful exclusive block-device claim. Recheck
   device sequence/capacity/filesystem UUID in WSL. Only then detach the exact
   owned VHDX and retain it. Never use a global unmount, Docker/WSL shutdown or
   cleanup fallback.

Unexpected heat, stale/error sensor data, lost monitoring/worker lease, changed
identity/configuration, output/storage limit, deadline or uncertain stopping
invalidates the attempt and latches FAULT. Stop owned processes before final
journal writes. A retained unfinished claim also blocks reuse. If device or
writer state is uncertain, retain the mapping rather than detach it. Successful
observation of the deliberate lease fault completes this one rehearsal only;
it grants no retry or later workload authority.

## Completed preparation and remaining proof

- **320 proposal tests passed**, including 25 new offline bridge/runtime/guest/
  admission checks. Windows raw-disk APIs, WSL, engine operations and namespace
  signals are mocked in those checks. Tiny fixtures exercise identity failures,
  stale/replaced leases, wrong limits, corrupt runtime bytes, startup failure,
  missing stop proof and configuration drift.
- Fifteen connected synthetic lifecycle cases pass. Latest result:
  `.runtime/isolation-rehearsals/d4b5ddc53fca40c89ef42e6c000fa9bf/result.json`.
  Simulated heat is a fault signal and does not heat hardware.
- Runtime staging reads only selected ELF files and their dependency closure
  from the installed Docker ISO. The staged manifest SHA256 is
  `d8edefbc145d704ad3b170c9b0f6bec19297f0a84abf74107f71ed172dfa0c61`.
  Staging executed none of those files. Native compatibility is **unproven**.
- The installed WSL tools were located read-only. Whether this Docker/WSL
  installation exposes the newly attached device to the restricted capsule is
  an explicit rehearsal question. Missing visibility or mount permission fails
  closed; there is no switch to a shared store or broader privilege fallback.
- All four image attempts and helper archives remain bound. The twelve verified
  blobs remain at 3,951,095,908 bytes; their bodies are not read by this preparation.

After a successful rehearsal, connect a tiny synthetic OCI import/identity test
without running an image, then prepare the retained CUDA-image import for its own
approval. Adapt the disabled build to that same isolated engine/store after
import. Model loading and the first bounded coding task remain later scopes.

## Execution after approval

The disabled template is `native-isolation-approval.template.json`. It is not an
approval. The actual `native-isolation-approval.json` may be created only after
the owner approves this exact operation, source limitation, thermal controls and
capsule privileges. Then run the packet's exact `local_worker.py run-isolation`
operation in an administrator process. It does not self-elevate. A launch wrapper
must keep its window hidden and preserve exit/evidence records. No second attempt
is allowed if this attempt is consumed.

Windows' owned-handle mapping uses documented
[attachment](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-attachvirtualdisk)
and [physical-path lookup](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-getvirtualdiskphysicalpath).
WSL's [disk mounting interface](https://learn.microsoft.com/en-us/windows/wsl/wsl2-mount-disk)
supports bare VHD attachment and explicit disk detachment. Container limits use
Docker's [resource controls](https://docs.docker.com/engine/containers/resource_constraints/).

Preparation audit and the parsed, unexecuted administrator launch wrapper are
retained beside this exact packet as `preparation-audit.json` and
`run-native-reviewed.ps1`. All 61 reviewed Python/PowerShell helpers and the WSL
script are snapshotted there. The actual approval, live attempt and store remain absent.

Execution update, 18 October 2026: the owner approved this exact operation and its
exceptions. Approval and preflight evidence are preserved beside the packet.
Windows reported administrator launch canceled before startup. No native attempt
was consumed and no sensor, disk, container or private engine started. See
`execution-outcome.json`; do not automatically relaunch the administrator request.
