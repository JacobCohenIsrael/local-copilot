# Isolated store and engine controls implemented

**Superseded implementation status:** the bridge, offline runtime qualification
and admitted guest startup are now wired. See
[the native rehearsal review](NATIVE_REHEARSAL_REVIEW.md) for the exact ready
packet, 320 passing proposal tests and the proposed 128-MiB empty-engine test.
No native operation has run. The text below preserves the previous milestone;
its missing/unwired descriptions and blocked packet are historical.

This milestone implements the control primitives and connected synthetic
lifecycle. It **does not complete or enable the live native workflow**. No VHDX,
filesystem, container, private engine or image import was created or started.
The next integration work is the owned Windows-to-WSL device bridge, runtime
qualification and admitted guest bootstrap.

## Done

- `isolated_store.py`: exclusive per-session claim, new fixed VHDX creation using
  Windows' virtual-disk API, identifier/capacity/type/physical-size checks, host
  reserve and stable file identity. Accepts only proposed 128-MiB canary or
  32-GiB import sizes. No adoption, expansion, deletion or reset operation exists.
- Creation uses overlapped I/O with live permission/deadline checks, `CancelIoEx`
  and provider-progress confirmation. Cancellation requests alone never prove
  stopping. Uncertain operations retain native buffers/handles and block new
  creation in that process. Failed claims and partial files remain for review.
- Each store has an owner/session marker with a random 32-byte nonce and checksum.
  Guest qualification requires that exact marker and host file/disk identity.
  The host bridge that attaches the disk and writes this marker is still missing.
- `isolated_agent.py`: one passed block device only; nonce, capacity and Linux
  disk-sequence checks before formatting/mounting. Rejects already mounted
  devices, unqualified commands and missing/mismatched proof. Formatting disables
  discard and deferred inode/journal initialization. These native primitives
  have not been exercised on an actual device.
- `isolated_engine.py`: restricted outer-container configuration, effective
  cgroup/mount validation, separate Docker/containerd roots and Unix sockets,
  and emergency stop by full container ID plus captured ownership. Changed
  safety settings do not disable stopping an otherwise still-owned container.
  Lost identity, unresponsive Docker or uncertain exit cannot become success.
- `isolated_session.py`: one-attempt controller, independent watchdog, terminal
  fencing, deadline/lease failure, stopping before final journal I/O, retained
  faults and no detachment without positive stop and device-qualification results.
  Unexpected exceptions and interruption also trigger stopping.
- A separate guest lease-fuse primitive is implemented for an inspected private
  PID namespace. It is **unwired and unproven natively**. It must never be called
  from a host namespace. The guest entry point always refuses before device or
  process access; no native fork or namespace-wide signal was exercised.
- CLI now exposes `prepare-isolation`, `review-isolation`, `rehearse-isolation`.
  `run-isolation` refuses with exit 3 before reading proposals/approvals or making
  native calls. `run-import` remains blocked. No approval file was created.

## Proposed enforcement route

Use Docker Desktop to run one restricted outer container from the already-cached
pinned Python fixture, with `pull=never`. Its whole process tree, including the
private engine, gets **one CPU, 4 GiB RAM, no swap and 128 processes**. Keep the
approved global WSL envelope unchanged. This avoids modifying shared WSL cgroup
controllers. All imported-image content, snapshots, temporary payload and daemon
data go on the separate fixed-capacity ext4 device, never Desktop's image store.

The outer root and input/runtime binds are read-only, networking is `none`,
restart is disabled, logs use no Docker log file, and no host Docker socket,
host PID namespace, GPU or arbitrary device is passed. Only the newly qualified
store device is writable. Bounded tmpfs mounts provide runtime state and the
initial empty store mountpoint. Desktop still keeps outer-container metadata;
that small control-plane overhead is distinct from the capped image-data store.

This route proposes root inside that container, a small explicit capability set
including `SYS_ADMIN`, and `apparmor=unconfined` for filesystem mounts. It does
**not** use `--privileged`, a seccomp exception, host namespaces or wildcard
device access. These privilege choices require explicit review/approval before
activation. The renderer and inspector currently describe a proposal only.

The later build must use this same isolated store/engine. Nested build-container
creation and its cgroup/runtime requirements have not been qualified by these
import-only controls. Do not silently fall back to Desktop or assume this
canary establishes build/model readiness.

## Validation

**295 proposal tests passed.** The frozen isolation-control packet is
`6b498442c4e5876b927a56ce8deca9048e9c5cd7fd97c95009a1b1cc24afd585`;
its status is `IMPLEMENTED_CONTROLS_NATIVE_ADMISSION_BLOCKED`.
Connected evidence is
`.runtime/isolation-rehearsals/c6d741b4a72c4fcbaf7d3836b3eebb65/result.json`.

The connected rehearsal exercises fifteen cases: normal completion, wrong device,
capacity overflow, wrong limits, extra mounts, shared-containerd rejection,
injected heat/sensor/cancel faults, simulated disk full, blocked I/O, owner lease
loss, deadline, unconfirmed engine stop and unconfirmed detachment. The watchdog
really runs on a separate thread and releases blocked synthetic I/O. Rehearsal
deadlines are shortened. Heat/sensor events are injected fault signals, not
hardware readings or a new native thermal-policy validation.

Unit checks cover malicious configuration changes, owned-stop behavior despite
policy drift, provider cancellation that never completes, late/failed provider
completion, Windows structure layout, marker rejection and refusal before native
calls. The installed DLL exports were resolved read-only; the guard prevented
even event/disk creation. This does not establish provider or device behavior.

## Left

1. Implement the owned attach/marker/mapping/detach bridge. A new sdX name alone
   is insufficient. Prove that the passed device is the newly created VHDX and
   never act on an existing disk. Preserve active/uncertain mappings on failure.
2. Qualify the installed Linux runtime and dependency layout. Read-only ISO ELF
   header inspection found that bundled dockerd, containerd and runc use dynamic
   interpreters; copying them as assumed standalone binaries is insufficient.
   No engine binary was executed or copied by this inspection.
3. Wire that bridge and runtime to the guest bootstrap, independent lease, real
   CPU admission and host controller. Freeze a fully executable canary packet.
4. Obtain approval for one **128-MiB / 180-second empty-engine canary**, including
   its source limitation, thermal controls and proposed capsule privileges. The
   prepared canary outline is not approval-ready while the above gaps remain.
5. After native proof, review the separate 32-GiB retained-image import. Keep all
   image loads, compilation and model execution disabled until their exact scope
   is approved. No further manual Armoury comparison is needed absent new evidence.

See `IMPORT_STORAGE_REVIEW.md` for the retained-image design. Its earlier packets
remain preserved; the metadata-only successor is
`179776b5fad8baf5dbfd3d302ce27e5a2ffa4e0cfa47b389bc5d123921d1c97b`.
Both review families remain inactive; synthetic success grants no native authority.

Windows documents asynchronous virtual-disk creation and provider progress:
[CreateVirtualDisk](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-createvirtualdisk),
[operation progress](https://learn.microsoft.com/en-us/windows/win32/api/virtdisk/nf-virtdisk-getvirtualdiskoperationprogress).
Cancellation is a request whose completion must still be checked:
[CancelIoEx](https://learn.microsoft.com/en-us/windows/win32/api/ioapiset/nf-ioapiset-cancelioex).
The outer resource envelope uses documented
[container resource constraints](https://docs.docker.com/engine/containers/resource_constraints/).
