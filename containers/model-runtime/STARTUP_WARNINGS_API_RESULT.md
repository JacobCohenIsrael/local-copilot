# First real Strata answer in Docker

19 October 2026, 08:26–08:28 Israel time. Strata returned **READY** from the existing GPU model in Docker. One real request: 19 prompt tokens, two completion tokens, 21 total. Prompt processing took 35.4065 seconds and generation 3.4973 seconds. Container exit code 0, no OOM; owned stop confirmed in 0.1814 seconds. Parent, watchdog, CPU reader and administrator wrapper all confirmed exited.

Startup warning recorded: CPU reached 95 C against the advisory 94 C target. Ten seconds of valid monitoring completed without resetting for target exceedances, and startup proceeded. CPU never exceeded 95 C during this run. The CPU 97 C emergency stop and all other emergency conditions stayed enforced. No threshold, power or firmware increase was made. The startup/status handoff also completed live successfully.

The container is retained stopped: `e2a8ec167003cd9fa4e3da49e2b35dd132e474c30868d80145ae521dacf92447`. All eight earlier attempts/build/configuration evidence was verified unchanged. Raw readings and logs remain preserved. Docker event evidence is an explicitly marked 128-KiB excerpt; real answer, API result and native logs are retained separately.

Review: `9213527ebc1861f5ee83004a9a1393c1b9903d3184fba118453c023efd48cad9`.
Result: `.runtime/model-api-startup-warnings-review/9213527ebc1861f5ee83004a9a1393c1b9903d3184fba118453c023efd48cad9/execution-result.json`.
Preservation SHA256: `129e6a88fe24f9ffab058b7cedea6963989f2959457e43db3e9acbc91783b83a`.

The API attempt is consumed and cannot be rerun. Next is the owner-authorized one-file Codex/OpenCode integration task. This answer proves real text generation, not yet a coding patch or a full interactive OpenCode provider.
