// Client/UI side stub for future hooks. Currently no UI is injected; telemetry lives in server script.

if (typeof ai_coach_client_init_done == "null")
{
    ai_coach_client_init_done <- true

    // Simple console command to force an emit for debugging if needed.
    AddClientCommandCallback("ai_coach_emit", function(player, args)
    {
        // Telemetry emit lives in server script; this is just a placeholder.
        printl("[AI_COACH] client emit requested (no-op on client).")
        return true
    })
}
