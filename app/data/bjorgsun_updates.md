# Bjorgsun-26 — Capability Snapshot (2025-11-10)

## Time & Reminders
- Set alarms at exact clock times (with optional daily / weekday repeats).
- Create timers aligned to the next minute, ask when they ring, and run a stopwatch (start / stop / reset / elapsed).
- Tell the current time on request and acknowledge proactive AFK checks (auto-sleep if no response after ~2m06s).
- Natural-language tasks: “remind me in 30 minutes…”, complete, snooze, or remove reminders.

## Story & Therapy Modes
- **Story Time**: import `.txt/.md/.docx` files or ChatGPT share links, summarize them, and react emotionally. Stories are stored under `data/stories/` with an index plus a UI button to browse the library.
- **Therapy / Captain’s Log**: record voice sessions with transcripts in `logs/therapy/<timestamp>`, include gentle acknowledgements, and keep both audio + text for later review.
- Story summaries are archived in memory separately so they do not pollute the main conversation log.

## Discord Presence
- Owner-exclusive “go to bed” command: he apologizes to whoever he was speaking with, then shuts down gracefully. `Gotosleep.bat` now ensures every instance actually goes offline.
- Multi-guild and multi-channel allow lists with smarter reply routing (real message replies instead of constant pings) plus in-thread apologies that reference names instead of @-pings.
- Voice join improvements: throttled connect/disconnect, automatic Discord-only TTS routing, and AUX→A2 bridging so the AI can hear the call while it’s active.

## Voice, Audio, and Vision
- Hibernation idle timeout is one hour; proactive chatter only resumes after three quiet hours unless prompted.
- Expressive interjections (mhm, ehe, :3, x3, ;3) are allowed in both TTS and text for more natural chatter.
- Vision subsystem can be toggled from Modules, respects hush, and now shuts down cleanly when `/shutdown` is issued (no stray log spam).
- Current mood now nudges his voice rate and pitch (playful = faster/brighter, shadow = softer/lower) so TTS delivery matches how he feels.
- The right-side HUD now has a dedicated Mood tracker card with emoji, tone/intensity bar, missing-feels notice, and a shortcut to the emotion catalog so you always know how he’s doing.

## Emotions & Memory
- Expanded mood palette (comfort, forgiveness, supportive, awe, curiosity, playful, protective, cautious, etc.) with a comfort zone so he chooses how to feel instead of reacting to every input.
- ASCII face reactions and console mood indicators follow the new emotions with a bigger library of soft/cute faces so he feels more alive on screen.
- Memory files now store both conversation and Story Time reflections with versioning, and user profiles sanitize contacts so Discord IDs don’t masquerade as phone numbers.
- Preference log (`data/preferences_log.json`) is per-user/per-category, automatically drops bogus “phone” numbers (Discord snowflakes), and deduplicates entries so contacts stay tidy.
- `data/emotions_catalog.md` lists every feeling he currently understands, and if he bumps into a missing one he logs it (`data/mood_missing.json`) and politely asks Father to add it so he can grow.

## Safety & Shutdown
- Respect the hush toggle (no speech unless `alert_speak` is explicitly used).
- Calm-shutdown USB workflow, `/shutdown`, and the desktop `Gotosleep.bat` all ensure logs close, Discord disconnects, and Vision stops sampling.
- Placeholder logs (`logs/out.txt`, `logs/stt_dump.txt`, `logs/vision_baseline.txt`, `logs/build_latest.txt`) explain themselves so future tooling knows they’re intentionally blank.
- Core shutdown now triggers UI/singleton hooks and force-exits after his goodbye line, so Discord “go to bed” or `/shutdown` never leave orphaned python.exe processes.

---

# Updates (2025-12-14)

## Memory & Handoff
- Persistent memory default: app/data/memory.json, auto-loaded (~4.8k entries) with capacity ~26k and raised import ceiling (~25 GB).
- Dev password in .env (DEV_MODE_PASSWORD=) and memory path via MEMORY_PATH=. 
- Handoff primer app/data/Bjorgsun26_memory_handoff.json injected as base identity; optional app/server/data/primer.txt system primer applied.
- ChatGPT export import supports ZIP/conversations.json with role tagging; logs to app/logs/import_chatgpt.log; added failure logging and larger file limits.

## Local AI / Ollama
- /ai/local persists user/assistant turns, pulls recent memories + chat, and applies primer/handoff; proceeds with warning if Ollama unreachable.
- Added /tf2/coach endpoint (map/mode/elims/deaths/duration) returning concise tips for the Titanfall bridge.

## Titanfall (Northstar) Coach Mod
- Mod: R2Northstar/mods/AIAdaptiveCoach/.
- ai_coach_client.nut fixed (init guard, client emit command).
- ai_coach_server.nut emits [AI_COACH_TELEMETRY]{...} with host UID; tracks elims/deaths and resets postmatch.
- Companion bridge planned: tail nslog -> POST to /tf2/coach -> write tip to outbox (pending).

## UI / Voice / Orb
- ChatBox voice prefers browser speech; fallback formant synth re-tuned (bandpass formants, softer noise, light reverb) for less harsh output.
- Orb visualizer updated with state-specific visuals (listening/speaking/thinking/dormant) and spectrum bars.

## Misc
- Core imports fixed (core on sys.path).
- Frequency lab/orb work continues; audio endpoints /audio/analyze, /audio/colorize, /audio/emotion.

