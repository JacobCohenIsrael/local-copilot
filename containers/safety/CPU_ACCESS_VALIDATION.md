# CPU read access — 16 October 2026

Administrator access resolved the ASUS CPU temperature read denial. The fixed
read-only probe ran successfully after the owner's authorization and returned:

| Field | Evidence |
| --- | --- |
| Model | ASUS ROG Strix G733CX / Intel Core i9-12950HX |
| Query | Existing `AsusAtkWmi_WMNB.DSTS`, CPU temperature endpoint `0x00120094` |
| Privilege | `isAdministrator: true` |
| Return | Success; presence bit set; raw device status 65626 |
| Decoded temperature | 90 °C candidate |
| Probe time | 16 October 2026, 17:10:22 Asia/Jerusalem (14:10:22 UTC) |
| Owner's subsequent screenshot | Armoury Crate: CPU 81 °C, GPU 57 °C, CPU use 7%, GPU use 14% |
| Safety admission | Still disabled; the candidate is not automatically certified as a safety sensor |

The probe and screenshot were taken at different times. Temperature variation,
sampling delay, and sensor meaning have not been disentangled, so neither an
exact match nor an offset/mismatch is established. No controlled workload was
used to compare them. Further validation should use a short bounded reader and
contemporaneous observation, without a stress test or performance-mode change.

The administrator launch used a dedicated workspace copy whose SHA-256 was
checked before execution:
`8F5E8B119E9EF5A0EBD46C26C01E82AD1D330D95D6B7CCCB07AD74C010BD1ADF`.
Only the fixed DSTS status endpoint was queried. The script scopes the computer
model, records privilege and the stage reached, and leaves `verifiedSafetySensor`
false. No new driver/app/service, scheduled task, persistent elevated process,
execution-policy change, ASUS control method, or power/firmware change occurred.
The elevated helper completed and exited; no model or container was started.

## Remaining CPU throttling gap

A separate query-only Windows `CallNtPowerInformation(ProcessorInformation)`
diagnostic returned records for all 24 logical processors. Some limit values
differed across processors. Microsoft's documentation describes the OS-reported
frequency limit, but these observations do not prove an Intel hardware thermal
status bit or its absence. On this hybrid CPU, do not diagnose throttling solely
from a comparison of those frequency numbers. The diagnostic always leaves
`cpuThermalThrottling: null` and `validatedHardwareThrottleSource: false`.
[Microsoft API structure reference](https://learn.microsoft.com/en-us/windows/win32/power/processor-power-information-str).

Read-only metadata also found `PercentPerformanceLimit` and
`PerformanceLimitFlags` counter fields. No validated reason mapping was obtained,
so they are not promoted to the required CPU thermal-throttle channel. Three
mocked tests check that OS-limit readings cannot silently become a hardware
"not throttling" assertion. All 13 mocked checks in `containers/safety` pass.

The next implementation step is a small, bounded privileged CPU reader using
the existing ASUS status source, with timestamps, deadlines, explicit unknowns,
and an isolated read-only interface. No arbitrary vendor method/endpoint should
be exposed to the cloud orchestrator. The separate hardware throttle source,
sensor freshness validation, integrated watchdog, and owner-reviewed live policy
remain admission requirements. No Strata build or inference was authorized by
this CPU access check.
