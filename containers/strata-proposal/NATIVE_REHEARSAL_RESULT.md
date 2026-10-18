# First native rehearsal: FAULT before guest startup

The owner-approved attempt ran once on 18 October 2026. It exited with code 3
and retained its original FAULT. There was no retry or reset. The earlier
canceled administrator launch and the subsequent successful launch are both
preserved. Import, compilation and model execution remain disabled.

## What ran

- Exact approved review:
  `2b5bda1e8c35a5520562c7967d2e1a518faf285e9b4406f4d9b57c2ff20aa743`.
- The real CPU admission baseline passed. Seventy-one raw frames match the
  metrics, spanning 05:34:21.518 to 05:35:31.495 UTC. Observed temperatures were
  79-95 C, below the 97 C stop threshold. The original sensor-validation flag
  remains false and hardware-throttle status remains null; acceptance was
  limited to this exact approved scope.
- Windows created the new fixed 128-MiB VHDX. Its reported physical size at
  creation was 138,412,032 bytes (132 MiB), within the reviewed allowance.
  This is an observation of this file, not proof of every future allocation.
- The owned-handle marker write/readback and Windows detach completed. The WSL
  bridge found the same marker on `/dev/sdc`, major/minor `8:32`, disk sequence
  `27`. A later read-only scan confirms that retained mapping remains unmounted
  in the inspected WSL namespace, without partitions or holders.
- Docker created the restricted outer container, but admission rejected its
  configuration before calling start. The guest, runtime binaries, formatter,
  private containerd and dockerd never ran. The lease-fault test was not reached.

## Cause reproduced offline

Docker records the approved capability names as `CAP_CHOWN`, `CAP_SYS_ADMIN`,
and so on. Our checker compares them with the unprefixed names `CHOWN`,
`SYS_ADMIN`, etc. It therefore rejected the same approved capability set with
`ISOLATED_CAPSULE_CONFIGURATION_CHANGED`.

Replaying the captured inspection offline and normalizing only that prefix
makes the complete existing configuration check pass. No live configuration or
helper was changed, and no native startup was retried.

There is also a cleanup/reporting issue: the stop predicate requires status
`exited`, so it does not recognize a container that was created but never started.
The final cleanup error masked the earlier admission error. The original state
therefore reports `NATIVE_ENGINE_STOP_UNCONFIRMED`; it has not been rewritten.

## Retained state and evidence

The Windows helper and CPU reader stopped. The captured Docker inspection
positively shows the owned container in `created` state, PID zero, not running
or restarting, with its start timestamp still zero. No private engine ran.

The unstarted container and unformatted disk are retained. The disk remains
attached bare because the reviewed guest unmount/exclusive-device proof is
absent. No forced detach, global Docker/WSL stop, deletion or cleanup fallback
was attempted. The consumed claim and original fault deny another attempt.

Structured result and preservation receipts are beside the approved packet:

- `native-execution-result.json`
- `native-execution-preservation.json`
- `native-approved-decision.json`
- Both administrator launch request/response pairs and the earlier canceled
  launch's `execution-outcome.json`

Live attempt evidence is under `.runtime/native-isolation-1/`, including the
original state, metrics, device proof, captured container inspection and offline
root-cause replay. Raw CPU frames remain under
`.runtime/compiler-guard/7ab8b9599c8e4236aaada55edc8fcb30/`.
The retained VHDX is
`.runtime/isolated-stores/f1705ab385be4fedb419fb33921aec56/store.vhdx`.

All four previous image attempts, their code/decisions, twelve verified blobs,
and Docker/WSL settings still match their preserved bindings. The 61 exact
approved helpers and the WSL script remain snapshotted beside the packet.

## Left

Correct capability-name normalization and the never-started cleanup/error
handling offline, using the captured native response as a regression fixture.
Prepare an explicit retained-device recovery plan and a new bounded attempt for
review. Do not reuse or reset this attempt, silently broaden permissions,
detach without proof, import images, compile or load a model.
