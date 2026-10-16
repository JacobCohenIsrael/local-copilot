# OpenCode file action and denial checks

**Tested with the real pinned Linux OpenCode CLI and a scripted fake model.**
Strata stayed off. Only synthetic files inside a disposable container were used.

## Results

| Scenario | Model requests | Verified result |
| --- | ---: | --- |
| `reply` | 1 | Scripted reply, no file changes; auxiliary title request removed |
| `edit` | 2 | Only `example.py` changed from `VALUE = 1` to `VALUE = 2` |
| `deny-shell` | 2 | Actual `shell` tool unavailable under this configuration; marker not created |
| `deny-external` | 2 | `Permission denied: external_directory`; synthetic private content not disclosed |
| `deny-file-write` | 2 | `Permission denied: edit`; unlisted `other.py` not created |

All five native cases completed without OOM and removed their test containers.
The worker regression suite passed **51 tests**, including three new tests for
specific denial evidence, prompt-free metadata and rejecting unknown scenarios.
Invalid tool arguments or the obsolete `bash` tool name do not count as a
successful command-denial test. The valid pinned command capability is `shell`.

The fixture retains network=none, no GPU, 0.5 CPU, 512 MiB RAM/no extra swap,
64 processes, read-only root/input, 64 MiB scratch, a six-second child timeout
and ten-second inner deadline. Request/token limits were not raised. No original
project, host credentials, Docker socket or model files are mounted. Native
tool execution here is scripted; no AI inference or live policy is enabled.

## Corrections established by the pinned implementation

OpenCode's [title selection](https://github.com/anomalyco/opencode/blob/v2.0.26/packages/core/src/session/context.ts#L95)
requires a title agent. Setting `agent.title.disable: true` removes the extra
model request; the reply-only check confirms the reduction from two calls to
one. The two-call ceiling is now available for a tool action and its reply.

Internal file permissions use [location-relative resources](https://github.com/anomalyco/opencode/blob/v2.0.26/packages/core/src/file-access.ts#L93).
The allowlist now names `example.py`, with all other resources denied. The
earlier absolute pattern incorrectly denied the permitted edit. Tool arguments
use `path`, not the older `filePath`. Both the fixture and disabled worker
proposal reflect these observed semantics.

The shell check demonstrates that the capability is unavailable to this agent;
the external-read and unlisted-write checks demonstrate explicit permission
rejections. These checks do not establish protection against every possible
tool exploit, concurrent host changes, symlinks or a compromised executable.
No real engine cancellation, tokenizer accounting or persistent fault recovery
is established by this milestone.

## Evidence and reproduction

Receipts under `.runtime/opencode-linux/checks/<id>/result.json`:

| Scenario | Receipt ID |
| --- | --- |
| reply | `89ff357cd30a44e2ba9162f05eafcd97` |
| edit | `416c1e10454a47209c64ef6580e80abb` |
| deny-shell | `5c36133f82dd4004b02b45e9b1face9c` |
| deny-external | `201dfcb1d96b4400aebf9f04744325a9` |
| deny-file-write | `51579650c3524ddab160da141557886a` |

```powershell
python -B containers/worker/verify_opencode.py --artifact <staged-musl-artifact> --execute-fake-only --scenario edit
```

Other scenario names are the table's exact values. Each invocation creates
only its fixed synthetic files, uses the owned fake backend, and removes its
container. Output includes a small patch and explicit denial evidence.

Next connect this verified fake edit to `task_bundle.py` input/patch collection
in one bounded command. Live Strata build/admission gates remain unchanged.
