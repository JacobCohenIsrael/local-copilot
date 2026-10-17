# CPU-only build admission decision

**Owner approved the build-only exception and controls on 16 October 2026.
No build is authorized or enabled.**

The current guard requires a validated CPU-temperature source and CPU hardware
thermal-throttle status. The bounded ASUS reader returns temperature candidates,
but validation is incomplete and throttle status remains unknown. The existing
guard therefore continues to block compilation. Another fake task rehearsal
cannot resolve this hardware-data gap.

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
Approved controls (still awaiting live implementation/validation):

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

## Remaining gates after a policy decision

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
