# Manual Strata chat

Separate terminal client for the installed Docker Strata model. Prepared offline
on 20 October 2026. **No live session is authorized or proven by this feature.**
See [LAUNCH_REVIEW.md](LAUNCH_REVIEW.md) for the exact proposed scope.

After approval for the frozen manual-chat review, open an administrator PowerShell
terminal in this checkout and run:

```powershell
& .\containers\manual-chat\launch.ps1 run
```

The administrator terminal is required by the existing ASUS CPU reader. The
launcher does not elevate, change execution policy, install anything or approve
the operation. Opening the launcher without an action only reviews the packet.
If your existing PowerShell policy blocks local scripts, the same approved
operation can be entered directly as `python -B containers/manual-chat/chat.py run`
in that administrator terminal; no execution-policy change is required.

If the terminal says **"Manual chat has not been approved yet"**, launch stopped
before any Docker/model operation. Approve the reviewed session in this chat so
its matching approval can be recorded, then enter the same launch command again.
This refusal does not consume a model attempt.

Wait for `READY`, then type a short prompt and press Enter. Each line is one
message. Replies appear as text arrives; prompt reading shows actual processed /
total counts when the native engine supplies them. Five-second status messages
show startup/busy state and remaining model lifetime. A waiting heartbeat is not
reported as native progress. Commands:

| Command | Effect |
| --- | --- |
| `/help` | Show commands |
| `/new` | Clear conversation history before the next prompt |
| `/tokens N` | Set the next response cap to 1–4,096 tokens |
| `/stop`, `/quit`, `/exit` | Stop the owned session |
| Ctrl+C or terminal EOF | End the controller and invoke owned shutdown |

Up to three explicit requests share one 300-second model lifetime. Startup and
typing consume that lifetime. Each request has an absolute 150-second deadline
and is also bounded by the remaining lifetime. The first proposal keeps those
existing limits. 4,096 is an output ceiling, not a promise to generate that much
in 150 seconds. Short replies may stop naturally. A `length` finish is displayed
and saved as truncated. A timeout or broken stream ends the session; no resend,
continuation, retry or automatic fault reset occurs.

The actual rendered prompt, including template and conversation history, must
fit **512 input tokens**. Strata's own tokenizer checks this before inference.
There is no padding or automatic input growth. If the API rejects the prompt,
the session ends and the decision remains consumed. Start with a short message.
Use `/new` between completed turns when history is no longer useful. A later
increase in input or time requires a separate reviewed scope and fresh approval.
The configured context is 16,384; small prompts cannot prove full-window capacity.

Prompts typed while busy are refused, not queued. `/stop` remains available while
starting or generating. To stop from a second terminal:

```powershell
python -B containers/manual-chat/chat.py stop
```

That command signals the session and directly stops only its recorded immutable
Docker ID. It does not require another launch approval. A stop request alone is
not shutdown confirmation: inspect the returned `stopConfirmed` result and the
session result. Failed stopping remains explicitly unresolved.

Offline commands, which do not query Docker, sensors or the model:

```powershell
python -B containers/manual-chat/chat.py prepare
python -B containers/manual-chat/chat.py review
python -B containers/manual-chat/chat.py status
python -B -m unittest discover -s containers/manual-chat -p test_manual_chat.py -v
```

`prepare` verifies recorded files and freezes a new packet; it reads cached
build/runtime artifacts and model identities but starts nothing. `status` reads
recorded state only and cannot certify that Docker is currently stopped.

Completed requests, returned replies, last observed partial reply, telemetry,
watchdog records, exact container inspection, bounded native logs and final
shutdown result are retained under `.runtime/strata-manual-chat-session/`.
User text is local plaintext evidence. Stream snapshots are observed about once
per second; a fault may lose tokens produced since the last host observation.
Guest raw SSE/tmpfs is ephemeral and is not claimed as preserved after stopping.
Stopped containers remain retained. The terminal launcher separately records
that the controller command returned; the terminal itself stays open for you.

No original experiment module, shared CLI, context plan, AGENTS.md, NEXT_STEPS.md,
simulator, retired component, model installation or prior approval is edited.
