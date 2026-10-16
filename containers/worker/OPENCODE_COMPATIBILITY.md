# Linux OpenCode compatibility: passed against a fake backend

**OpenCode 2.0.26 actually ran in Docker and printed `synthetic OK` through our
request gate.** The reply came from a scripted Python server, not an AI model.
Strata remains off. No files were edited by OpenCode.

## What this diff adds

- `stage_opencode.py` fetches one exact npm package, verifies the pinned published
  SHA-512, and copies only package metadata and an x64 ELF binary. It never
  installs or executes anything. Unsafe members/links, duplicates, wrong
  identities and size overruns are rejected.
- `opencode-lock.json` pins the selected archive/binary SHA-256. Our cached
  Python image is Alpine 3.24.2; the selected package is therefore
  `@opencode/cli-linux-x64-baseline-musl`, version 2.0.26. The initial glibc
  download lacks a compatible loader in this image and is retained as evidence.
- `stage_opencode_runtime.py` stages two pinned Alpine libraries as files.
  It never runs APK install scripts. Libraries are mounted read-only and
  selected only inside the container; nothing is installed on Windows.
- `verify_opencode.py` checks the exact container envelope before an explicitly
  selected version or fake-backend probe. It accepts no arbitrary command or
  upstream URL and removes only its matching owned container afterward.

The actual pinned CLI rejects the earlier draft's `--dir`. The corrected
proposal uses verified `--standalone` and the container working directory,
keeping its private server inside this disposable container.

The gate now strictly supports observed `store: false`, usage-only
`stream_options` and the `max_completion_tokens` alias. Both output-cap names
obey the same ceiling; providing both is rejected. Storage requests and other
stream options remain rejected. The staged Strata source recognizes the alias,
but has not been executed. These are offline protocol fixes, not live approval.

## Results

| Check | Result |
| --- | --- |
| Native version command | Exit 0, `opencode v2.0.26` |
| Native OpenCode through proxy/gate | Exit 0, `synthetic OK`, 2 fake requests, no gate fault |
| Worker regression suite | 48 tests passed, including 6 new staging/envelope tests |
| Cleanup | Container removed, fake servers closed, no handler errors or OOM |

Successful integration receipt:
`.runtime/opencode-linux/checks/4c0271d5a7514d5f8c4b62f89519500e/result.json`.
Native version output:
`.runtime/opencode-linux/checks/15fa1dd00430413ca1068c33282678c8/result.json`.
That historical receipt's `versionMatched: false` was an assessment bug: the
old checker expected a bare version number. Its process exit/output are valid;
the checker now matches the observed prefix.

Both probes use the cached pinned image with **network none, no GPU, half a
CPU, 512 MiB RAM/no extra swap, 64 processes, read-only root/input, non-root
user, dropped capabilities, 64 MiB tmpfs and a 10-second inner deadline**.
The OpenCode child has six seconds. Only staged binary/libraries and fixed
helpers are mounted; no original repository, host credentials, Docker socket,
`D:\AI` or model data. No image build/pull or host settings change occurred.
Fake servers communicate only over container loopback.

Token counts remain synthetic. This proves a text-response path; named-file
editing, denied shell/external access, real tokenization, persistent FAULT
recovery, independent live watchdog and engine shutdown remain unvalidated.
The smoke consumed **both allowed requests**. Identify/control auxiliary calls
before a coding test; do not silently increase that budget.

## Reproduce

```powershell
python -B containers/worker/stage_opencode.py --download
python -B containers/worker/stage_opencode_runtime.py --download
python -B containers/worker/verify_opencode.py --artifact <returned-artifact-directory> --execute-fake-only
```

Sources: [official release](https://github.com/anomalyco/opencode/releases/tag/v2.0.26),
[pinned npm metadata](https://registry.npmjs.org/@opencode%2fcli-linux-x64-baseline-musl/2.0.26),
[Alpine runtime](https://pkgs.alpinelinux.org/package/v3.24/main/x86_64/libstdc%2B%2B).
The published npm hash was verified; signatures were not independently checked.
Alpine packages came from official HTTPS and their full SHA-256 values were
pinned after inspection. Large artifacts stay in `.runtime`, outside commits
and user-facing reports.
