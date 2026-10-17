# CPU-only build admission decision

**Owner approved the build-only exception and controls on 16 October 2026.
No build is authorized or enabled.**

## Approved thermal revision — 17 October 2026

The owner asked to reconsider the temperature limits based on ordinary CPU
workload temperatures. `thermal-revision.proposed.json` proposes **start at or
below 92 C for ten seconds; latch FAULT and invoke stopping at or above 97 C**.
The owner explicitly approved this numeric revision. The original 75/80 C
controls remain as a historical snapshot; effective controls are now 92/97 C.
`thermal-revision-approval.json` binds the unchanged revision file's normalized
SHA256 and quotes the approval. The unknown-throttle exception remains
CPU-build-only. Neither decision authorizes a build, image pull or model load.

[Intel's exact i9-12950HX specification](https://www.intel.com/content/www/us/en/products/sku/228439/intel-core-i912950hx-processor-30m-cache-up-to-5-00-ghz/specifications.html)
lists a 100 C maximum junction temperature. [Intel's temperature guidance](https://www.intel.com/content/www/us/en/support/articles/000005597/processors.html)
explains that high temperature during sustained work need not indicate a fault.
[ASUS's laptop guidance](https://rog.asus.com/sg/articles/guides/why-is-my-laptop-overheating-its-probably-not/)
similarly says 95–100 C can occur under demanding workloads, while identifying
unexpected shutdowns and high light-load temperatures as reasons to investigate.
These sources support revisiting an arbitrary 80 C cutoff; they do not validate
this laptop's sensor, diagnose the previous shutdown, or certify a 97 C
application threshold. Sampling, source coverage and exit-confirmation delay
mean a three-degree numeric gap is not a guaranteed physical margin.

The proposed lower start threshold retains headroom before adding a compiler.
A 94–95 C baseline would still wait; after a qualifying 92 C baseline, 94–95 C
would not itself fault. No fan, firmware, power or performance-mode change is
involved. All other controls and remaining build/runtime gates are unchanged.

Run `python -B containers/strata-proposal/build_policy_review.py --thermal-revision`
for the synthetic comparison. Four new tests cover the changed boundaries,
running at 94/95/96 C, immediate fault on a 97 C sample, no start from a 95 C
baseline, preserved missing-data failures and explicit approval binding for the
new numbers. That command accepts no live feed and enables no workload.

## Compiler readiness and refreshed package

`load_effective_controls()` resolves both approvals without changing their
historical files. The compiler plan now reports 92/97 C controls and unknown
throttle status as optional for CPU compilation only. The legacy dummy validator
retains its own test policy; no model-runtime telemetry rule is changed.

`CpuBuildReadinessGate` accepts non-synthetic frame shapes and rejects synthetic,
unvalidated, stale, replayed or invalid data. It uses the same baseline/hot rules
as the rehearsal and preserves unknown throttle as null. A separate `tick`
detects missing sensor/controller updates and clock regression. This class has
no timers, process controls or start authority; an independent live controller
must still drive it. Unit tests use mocked frame data, not validated hardware.
The real reader continues to emit `validatedCpuSensor=false`.

`build_preflight.py` is a read-only report of the selected build candidate,
approval scope, exact compiler resource/command profile and helper hashes.
It neither calls Docker nor reads sensors. It refuses altered candidate hashes
or resources and always leaves build/model disabled.

The source-only package was refreshed from the two existing, verified archives:
`.runtime/strata-build/1c9c3253`, selected by `build-candidate.json`. Its manifest
SHA256 is `ea5b063e3ebbacb3fea1f82d9b83f78b7502abc9d2b5bc1656514c4cbbf48804`.
The current helper is staged, its hash matches, and a disabled guard contract
was generated for this identity. No new archive, dependency or image was
downloaded; no upstream source was executed. The original package `1537f5ec`
and its approved historical manifest remain unchanged. The existing dummy
watch CLI still targets its historical fixture; a live controller for the new
candidate is not implemented or enabled.

43 proposal tests passed. The preflight lists four blockers: CPU-source
validation, live controller connection, dependency/disk budgets and final
build-workload approval. There is no additional temperature approval to request.

The build-only gate requires validated CPU-temperature data; hardware throttle
status is optional under the approved exception. The bounded ASUS reader returns
temperature candidates, but validation is incomplete and throttle stays unknown.
The real compiler remains disabled. Another fake task rehearsal cannot resolve
this hardware-data gap.

The approved decision is to allow **unknown CPU throttle status for one capped
CPU-only compilation**, while retaining temperature monitoring and independent
stop controls. This is a real reduction in required observability, requiring
explicit owner approval under the original request to approve policy changes.
That approval is recorded in `build-policy-approval.json`, quoting the owner's
reply and binding the reviewed draft hash. It does not apply to model loading
or inference. Hardware throttle status remains unknown; it is never set false
to pass admission. No new provider or driver is installed.

## Concrete proposal

`build-policy.draft.json` is preserved as the original reviewed snapshot, including
its disabled flags. Its approval hash normalizes CRLF to LF so a Git line-ending
conversion cannot change the decision. A changed policy/manifest requires review.
The updated reader has a new implementation hash; the report shows both old and
current hashes and requires revalidation before the final executable manifest.
Original controls (historical snapshot; 75/80 C superseded by approved 92/97 C above):

| Control | Candidate rule |
| --- | --- |
| Workload | One compiler job; no engine execution, model files or GPU devices |
| Resource caps | One CPU, 4 GiB RAM, no extra swap, 128 processes |
| Admission | Validated CPU source at or below 75 °C continuously for 10 seconds |
| Temperature stop | At or above 80 °C, including before admission |
| Monitoring | One sample/second; maximum sample age and controller lease 2.5 seconds; maximum query duration 1 second |
| Missing CPU temperature, invalid source, stale feed or lost controller | Block admission or latch FAULT and stop |
| CPU throttle | Unknown remains null under this approved exception; known throttling still faults |
| Build deadline | 30 minutes, no retries or automatic restart |
| Stop proposal | TERM grace 1 second; confirm stopped within 5 seconds or retain unresolved FAULT |
| Recovery | First fault latched; no automatic reset or resume |

75/80 °C are deliberately restrictive proposal values, **not certified safe
limits** or an explanation for the earlier laptop shutdown. CPU quotas do not
guarantee power draw or temperature. The previous 81/83/90/94 °C observations
would all fail this draft's admission; historical readings cannot establish
the current temperature. Equal readings alone do not establish staleness, and
an advancing wrapper timestamp does not prove hardware refresh.

CPU temperature meaning and update behavior still need validation, including
an ordinary-use comparison with Armoury Crate without deliberately creating
load or changing performance settings. That comparison cannot establish a
safe operating envelope or replace a hardware throttle flag. The current
reader leaves `validatedCpuSensor=false` until validation is reviewed.

## What this step verifies

Run `python -B containers/strata-proposal/build_policy_review.py` for a read-only
report. It checks the approval/draft/manifest hashes, reports reader changes and runs synthetic
observations through the draft temperature rules. It cannot read sensors,
control Docker, accept a live feed, approve a policy or start a workload.

Unit tests cover the cool baseline and its reset, exact hot boundary,
historical hot samples, missing/unvalidated channels, replay/staleness, invalid
values, monitor/controller loss, cancellation, first-fault persistence and
the 30-minute deadline, approval scope and remaining reader coverage. The existing
guard still blocks every actual build. These tests do not prove real stopping
latency or sensor validity.

The reader now has fixed monotonic sample slots, a 1,920-sample/32-minute hard
ceiling (within the existing 2,048-frame limit), and declared remaining coverage.
Its three-sample default stays unchanged and cannot cover a full build. Admission
simulation rejects insufficient remaining time for the full build and confirmed
stop, subtracting the sample's age. The reader exits on query error or a query
exceeding the approved one-second duration; a hung query still requires the
independent watchdog's freshness stop. `-Describe` tests the PowerShell contract
without CIM, administrator access or sensor reads. Long hardware runs remain
unvalidated; the larger ceiling is not a guarantee of future liveness.

## Remaining gates before an approved build

- Validate the CPU-temperature source's meaning and update behavior.
- Validate the revised reader's actual coverage and scheduling, including source
  failure and process loss; connect the remaining-coverage check to the eventual
  live controller before compilation. The old timing gap is addressed in code
  and simulation, not by a 32-minute hardware run.
- Implement the approved controller/watchdog stop deadlines and test the real
  builder identity, reader loss and Docker failure behavior before compiling.
- Measure disk reserve and bound dependency downloads. The current apt/pip
  recipe is not fully pinned or download-bounded; this remains a separate gate.
- Review and approve the final executable build manifest/workload. This draft
  is not that approval, and no build/start command has been added.

GPU monitoring, runtime thermal-throttle requirements and model-start approval
remain separate. Software monitoring cannot guarantee shutdown if the host,
driver or Docker daemon cannot act. Original installation/configurations,
firmware, power and fan settings are untouched.
