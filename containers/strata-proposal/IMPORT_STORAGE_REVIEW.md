# Separate capped import: design review

The owner selected a **separate store with an enforced disk cap**. That selects
the architecture; it approves no creation, formatting, mount, engine start or
import. Preparation and the archive transport rehearsal are implemented.
**The live import is not yet ready for approval or execution.** Control primitives
and the native bridge/runtime/bootstrap are now connected and tested offline.
The exact empty-engine native rehearsal is ready for its own approval; native
proof remains. See [the rehearsal review](NATIVE_REHEARSAL_REVIEW.md).

## Proposed operation

One offline attempt using the already verified Linux amd64 CUDA base:
`nvidia/cuda@sha256:435220c0fef35cbf712e11999f8670a83835ef3cdd18564e5e8122f83078c88c`.
No image container, compiler, Strata engine, OpenCode task or model may start.

| Control | Proposed value / behavior |
| --- | --- |
| Input | Configuration + 11 retained compressed layers; 3,951,095,908 bytes |
| Stream | Fifteen OCI archive members, exactly 3,951,112,192 bytes; no full archive file |
| Prior verification | 7,454,964,736 expanded bytes; not a disk-allocation bound |
| New store | New 32-GiB fixed-capacity VHDX, ext4; never resize |
| Owned path | `.runtime/isolated-import-1/store.vhdx` within this repository |
| Host allocation allowance | 32 GiB + 256 MiB container overhead; implementation must prove this bound |
| Host admission | At least 52 GiB + 260 MiB free before creation; retain 20 GiB reserve |
| Store reserve | Stop at or below 4 GiB free; fixed device capacity is the hard ceiling |
| Engine | Separate daemon/containerd; data, content, snapshots, temp and logs inside new store |
| Runtime state | Separate 64-MiB tmpfs, bounded independently |
| Engine cgroup | One CPU, 4 GiB RAM, no swap, 128 processes; verify before streaming |
| Global WSL envelope | Preserve approved one CPU / 6 GiB / swap=0; recheck actual limits |
| CPU admission | Propose <=92 C for ten seconds; stop at >=97 C |
| Operation deadline | 1,800 seconds including provisioning, readiness, streaming and identity checks; cleanup follows |
| Fault | Stop input and the whole owned engine, latch FAULT, retain evidence; no retry |
| Shutdown | Five seconds graceful, then five seconds to confirm forced owned-cgroup stop |
| Owner death | Independent guest lease expires after three seconds and stops owned engine |
| Networking | Private Unix socket through fixed WSL adapter; isolated network namespace, no egress |
| Cleanup | Confirm empty owned cgroup and reader exit, then unmount/detach new device; retain store |

The physical VHDX allowance is an **unproven acceptance requirement**, not an
established guarantee. Logical disk capacity alone does not establish exact host
allocation. Verify a newly created file's ownership, identity and attached device
mapping before formatting. Never format an existing device, expand automatically,
fall back to shared storage, change the default Docker context or stop global
Docker/WSL. Do not enable shared cgroup controllers without review.

The proposed thermal/source decision needs import-scope approval. Preserve raw
freshness/calibration limitations and null hardware-throttle status. Prior
download/verification or build decisions do not authorize import. No additional
manual Armoury comparison is requested.

The intended sequence is fresh admission, create/mount only the new owned device,
prove write containment and owned cgroup/watchdog, start the private offline
daemon, stream once, inspect identity, stop the whole engine and reader, then
unmount/detach. Stream a deterministic OCI-layout tar directly from retained
compressed blobs with size/hash verification. Write no full archive and provide
no download/repair fallback. If corrupt input is discovered after sending a
prefix, invalidate the attempt and retain partial state inside the capped store.

Inspect configuration ID
`sha256:949aeb228afe6b802c1dbddad76439bc158a86f5900223ab13b3f60536b005a0`,
Linux amd64 and all eleven ordered rootfs diff-IDs. Preserve original manifest
bytes; do not assume loading creates a repository digest. Client exit is not
daemon stopping proof. If stopping is unconfirmed, retain the mount/device and
latch FAULT; do not detach a device with possible writers or report success.

## Done

- `import_plan.py` revalidates all four attempts, approved helper archives and
  decisions, raw reader trees, and cache metadata. It checks the successful
  result against its archived approved packet. No real blob bodies are reread,
  copied or decompressed by preparation.
- `oci_archive.py` produces fifteen deterministic members with bounded chunks
  and exact byte count, unsafe/duplicate path rejection, size/hash checks,
  partial-write handling and guard checks. An external supervisor is required
  to interrupt blocked I/O; a callback alone cannot do this.
- Tiny in-memory transport cases cover success, simulated disk full, permission
  loss, corrupt/truncated/oversized input and a broken pipe. These do not prove
  a native quota, sensor watchdog, cgroup limit or daemon shutdown.
- CLI commands: `prepare-import`, `review-import`, `rehearse-import`.
  `run-import` refuses with `IMPORT_EXECUTION_NOT_IMPLEMENTED`, exit 3, before
  live state/sensor/cache-body/process/WSL access. There is no approval reader
  or bypass flag. Existing approvals cannot unlock it.
- **262 proposal tests passed.** No new disk, mount, daemon, import, compiler or
  model started. All three previous faults and the consumed success are intact.

## Left before import approval

1. Run the separately approved native empty-engine rehearsal. The installed
   runtime closure is staged and hashed without execution; owned device bridging
   and guest startup are connected. Native compatibility, allocation, identity,
   mount isolation and cleanup still need that actual observation.
2. Review the resulting native evidence before adapting to the 32-GiB store.
3. Qualify the proposed restricted outer capsule's resource envelope and prove
   whole-engine shutdown on cancel, disk full, monitor stall and owner death.
   Its controls are implemented; no shared cgroup policy change is proposed.
4. Prove OCI-load compatibility/identity with a tiny generated image without
   running it; connect the real reader and fresh admission and freeze the runner.
5. Obtain exact import-scope source/policy/workload approval after that review.

Native storage/empty-engine rehearsals need a concrete reviewed permission:
they create/format/mount storage and start a daemon. The current design packet
does not authorize them. The next preparation milestone is that bounded native
fixture operation, followed by retained-image import readiness.

The later first-build adapter must use this **same isolated engine/store**.
The old proposal targets Desktop and remains disabled/stale. Import here does
not make the base available to that target. Copying it into Desktop discards the
chosen storage boundary. Build and model/runtime approval remain later gates.

## Evidence and sources

Latest preservation receipt SHA256:
`23a48f19ab38b5b198ef9cc663f5457f57e7979a9ad87a4721ec0dcae2c7467f`.
Exact 42/43/46/48-helper archives remain preserved. No attempt, cache entry,
approval or fault was reset or replaced. The hash-bound design and preservation
binding are under `.runtime/import-review/`; the candidate is metadata only.
Previous checkpoint's preserved design SHA256:
`abb85f0d1895602ea8c4bf3c45490871ee57fa2a797c0e6570bc492556fbff03`.
Its `preparation-audit.json` confirms all four attempts and retained cache
metadata still match, and the existing `.wslconfig` and Desktop settings hashes
are unchanged. Seven transport cases passed at
`.runtime/import-rehearsals/d075f5575ec04ca6b2e48098a1a7660a/result.json`.

Current metadata-only successor after isolation-control implementation:
`179776b5fad8baf5dbfd3d302ce27e5a2ffa4e0cfa47b389bc5d123921d1c97b`.
It still does not authorize any live operation.

Docker's separate containerd paths mean moving only data-root does not contain
all writes: [containerd storage](https://docs.docker.com/engine/storage/containerd/).
Separate daemons need independent data/execution/configuration paths:
[daemon options](https://docs.docker.com/reference/cli/dockerd/).
WSL's VHD attachment requires administrator access:
[WSL mount commands](https://learn.microsoft.com/en-us/windows/wsl/basic-commands#mount-a-disk-or-device).
These support the architecture, not proof of this unimplemented runner.

Current inactive design successor after native wiring: `f5ce3f5f4dcc315d7f6767999f90bbf7d6f65650c6b09bdd9c4528d826daea62`.
The native empty-engine rehearsal is prepared but unapproved; import remains disabled.
