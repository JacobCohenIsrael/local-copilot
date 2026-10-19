# Dedicated, low-overhead monitor proposal

The owner prefers a small dedicated monitor over adding a full monitoring suite.
Armoury Crate is already installed and running. This is a design proposal, not
an activated monitoring or live operating policy. No new sensor app/driver is
installed, no ASUS service is stopped, and no fan, firmware, clock, voltage,
performance mode, or power limit is changed.

## Data paths

| Required data | Proposed source | Current validation |
| --- | --- | --- |
| RAM use and AC status | Direct Windows `GlobalMemoryStatusEx` / `GetSystemPowerStatus` | One bounded read worked |
| GPU temperature, power, VRAM, thermal flags | NVIDIA NVML, through the installed NVIDIA driver | Read-only `nvidia-smi` audit worked; direct NVML adapter is not implemented/tested yet |
| CPU temperature | Existing ASUS read-status interface | Administrator probe succeeded: 90 °C candidate; owner screenshot later showed 81 °C. Access is resolved; sensor meaning/freshness validation remains |
| CPU thermal-throttling status | A verified read-only source for this Intel CPU | Missing; do not infer it from clock speed, GPU flags, or absence of events |

Windows is the operating environment, not a universal CPU sensor API. Existing
tools ultimately use hardware/driver interfaces, but not necessarily the same
ones. A custom user-mode program cannot bypass access restrictions or replace
the need for a suitable hardware driver. The preferred route reuses an existing
verified driver; writing a new kernel driver is outside this project milestone.

ASUS's WMI class exposes both status and control methods. Only DSTS (device
status) for the fixed CPU-temperature endpoint `0x00120094` was attempted;
DEVS/control, INIT, performance, fan, and firmware watchdog methods were not
called. The endpoint and read/write distinction were checked against
[G-Helper's implementation](https://github.com/seerge/g-helper/blob/main/app/AsusACPI.cs).
The initial non-administrator read was denied. After the owner authorized the
administrator check, a hash-checked copy completed with `isAdministrator: true`,
a successful DSTS return, and raw status 65626 (presence bit plus a 90 °C
candidate). No execution policy, device setting, service, or driver was changed.
The probe itself does not self-elevate or run automatically. The owner later
supplied an Armoury Crate screenshot showing CPU 81 °C and GPU 57 °C. These
observations were not simultaneous, so they establish neither an exact match nor
a mismatch. Sensor meaning and update/freshness behavior still require validation
before this becomes an admitted safety feed.

The availability audit did not find the LibreHardwareMonitor/OpenHardwareMonitor
WMI namespaces; ACPI thermal-zone access was denied and would not be substituted
for CPU package/core temperature even if readable. Armoury Crate's dashboard can
help manual cross-checking, but its UI alone does not provide a validated fresh
machine-readable CPU safety feed. No claim that every ASUS internal interface
has been ruled out is made.

## Small monitor process

Use one headless Windows process, no dashboard, overlay, web server, browser,
model framework, service installer, or continuous device scan. Enumerate and
validate providers once per session, pin the expected CPU/GPU identity, retain
the necessary read-only handles, and query only approved channels. Direct NVML
avoids launching a command for each GPU sample; use a maintained binding or a
carefully bounded native adapter. NVIDIA documents that the `nvidia-smi` text
format is not a stable interface; the one-shot XML audit is not the production
monitor. See [NVML](https://docs.nvidia.com/deploy/nvml-api/latest/index.html) and
[nvidia-smi documentation](https://docs.nvidia.com/deploy/nvidia-smi/index.html).

Start monitoring before admission/loading and keep it active through shutdown
and cooldown. Exit after verified cleanup; do not keep polling a sleeping GPU
while the local worker is off. A proposed initial cadence is one sample per
second, subject to owner review and measured detection/overhead requirements.
No particular CPU, RAM, or power overhead is promised until it is measured.

Each sample needs a session identity, strictly increasing sequence, monotonic
receipt time, UTC recording time, per-source query start/end and age, explicit
units, validity, and missing/unsupported reasons. Equal temperature values are
not proof of stale data; advancing wrapper timestamps are not proof that an
underlying sensor refreshed. Validate each provider's update semantics and
timeouts. Unsupported values remain null; parsing/range failures are faults.

Keep blocking driver/vendor calls outside both the supervisor and watchdog
safety loops. Put privileged readers behind a narrow, fixed read-only interface,
with deadlines and a watchdog-visible lease. A hung sensor process must be
discardable; do not let a blocked driver call stop cancellation. The independent
watchdog must observe sensor freshness independently, rather than accepting a
supervisor heartbeat as proof that monitoring is healthy.

## Authority and remaining gates

The dedicated monitor reports observations; it cannot self-tune or approve
thermal/power/resource limits. Use an immutable owner-reviewed policy. Missing
CPU temperature, missing CPU throttle status, stale/missing samples, lost AC,
or failed monitors block admission or latch a fault. Thresholds from dummy tests
are not approved laptop settings.

The watchdog prototype in this directory only guards specially labelled
non-GPU dummies. It is separate from the monitor and supervisor, can stop a
non-cooperating dummy without its host producer, and persists the first fault
before stopping. A production version still needs canonical protected state,
global admission, parent/watchdog liveness cross-checks, boot/resume handling,
two-container ordering, authenticated local IPC, and tested Docker outage
behavior. If the host/driver/daemon cannot act, process isolation is not a
guaranteed hardware power cutoff.

The next CPU step is a bounded privileged reader using this verified access
path, plus finding/validating the separate CPU throttle channel. A separate
read-only `CallNtPowerInformation(ProcessorInformation)` diagnostic works, but
is retained only as OS-limit evidence, not as a hardware-throttle flag. It
reported different limits across logical processors on this hybrid CPU. Counter
metadata exposes `PercentPerformanceLimit` and `PerformanceLimitFlags`, but no
validated reason-bit interpretation was established. Do not treat frequency
limits or zero flags as proof that hardware throttling is absent.
See [Microsoft's structure reference](https://learn.microsoft.com/en-us/windows/win32/power/processor-power-information-str).
New software, driver
installation, elevation, or changes to live policy require a concrete reviewed
action; this design does not silently perform any of them.
