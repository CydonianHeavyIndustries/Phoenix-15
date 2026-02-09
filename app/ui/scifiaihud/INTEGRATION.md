# Sci-Fi HUD UI (scifiaihuduidesign-main) Integration Notes

Imported into `app/ui/scifiaihud/` without modifying upstream files. Use these pointers to hook it up to Bjorgsun-26 and the TF2 AI Coach bridge:

- API base: `http://localhost:1326`.
- Coach/advice endpoint (from tf2_ai_coach module): `GET /tf2/coach/advice` → `{ telemetry, coach: { advice, bot_tuning } }`.
- Telemetry push (optional): `POST /tf2/coach/telemetry` with the same JSON shape the Northstar mod emits.
- To display advice: read `coach.advice` (array of tips) and `coach.bot_tuning` (aggression/evasiveness/range_preference).
- To show live match stats: read `telemetry` (map, mode, elims, deaths, duration).

Build/run (inside this folder):
```
pnpm install    # or npm install / yarn
pnpm dev        # or npm run dev
pnpm build      # or npm run build
```

Suggested wiring in the UI:
- Add a data fetcher hook targeting `/tf2/coach/advice`.
- Map advice tips into your existing card/toast components.
- If you want bot tuning sliders, bind them to `coach.bot_tuning` and POST back to `/tf2/coach/telemetry` or write to the command file the companion watches.

No upstream files were edited; this folder is a drop-in of the provided ZIP with this integration note added.
