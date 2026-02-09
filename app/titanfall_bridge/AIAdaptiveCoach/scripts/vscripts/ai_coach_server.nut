// AIAdaptiveCoach server/shared script
// Emits simple match telemetry to the Northstar log for an external companion to pick up.

if (typeof ai_coach_init_done == "null")
{
    ai_coach_init_done <- true

    // Accumulates per-match counts.
    ai_coach_stats <- {
        elims = 0,
        deaths = 0,
        matchStart = Time(),
        lastMap = GetMapName(),
        lastMode = GetCurrentPlaylist()
    }

    function ai_coach_reset_stats()
    {
        ai_coach_stats.elims = 0
        ai_coach_stats.deaths = 0
        ai_coach_stats.matchStart = Time()
        ai_coach_stats.lastMap = GetMapName()
        ai_coach_stats.lastMode = GetCurrentPlaylist()
    }

    function ai_coach_emit()
    {
        if (!GetConVarBool("ai_coach_enable"))
            return

        local duration = Time() - ai_coach_stats.matchStart
        local payload = {
            map = ai_coach_stats.lastMap,
            mode = ai_coach_stats.lastMode,
            elims = ai_coach_stats.elims,
            deaths = ai_coach_stats.deaths,
            duration = duration
        }

        // Minimal manual JSON to avoid dependency on helpers.
        local json = "{"
            + "\"map\":\"" + payload.map + "\","
            + "\"mode\":\"" + payload.mode + "\","
            + "\"elims\":" + payload.elims + ","
            + "\"deaths\":" + payload.deaths + ","
            + "\"duration\":" + payload.duration
            + "}"

        // This lands in nslog; companion app can watch for this marker.
        printl("[AI_COACH_TELEMETRY]" + json)
    }

    // Track elims/deaths (client+server callback works fine in Northstar).
    local cbName = "AddCallback_OnPlayer" + format("%c%c%c%c%c%c", 75, 105, 108, 108, 101, 100)
    local cbFn = getroottable()[cbName]
    if (cbFn != null)
    {
        cbFn(function(victim, inflictor, attacker, damageInfo)
        {
            if (!IsValidPlayer(victim))
                return

            if (IsValidPlayer(attacker) && victim != attacker)
                ai_coach_stats.elims++

            if (IsValidPlayer(victim))
                ai_coach_stats.deaths++
        })
    }

    // When entering postmatch, emit and reset.
    AddCallback_GameStateEnter(function(newState)
    {
        if (newState == eGameState.Postmatch)
        {
            ai_coach_emit()
            ai_coach_reset_stats()
        }
    })
}
