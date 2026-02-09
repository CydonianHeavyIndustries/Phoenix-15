//------------------------------------------------------------
// TitanCommander : client-side hotkeys (example)
//------------------------------------------------------------

// Simple hotkey bindings for testing; adjust key codes as needed.
function ClientCommandThink()
{
    // Example: F1 move to crosshair hit
    if (IsKeyPressed(KEY_F1))
    {
        local hit = GetCrosshairHitPos();
        IssueCommandMoveTo(GetPlayer().GetTitan(), hit);
    }
    else if (IsKeyPressed(KEY_F2))
    {
        IssueCommandHold(GetPlayer().GetTitan());
    }
    else if (IsKeyPressed(KEY_F3))
    {
        IssueCommandFollow(GetPlayer().GetTitan());
    }
}

AddCallback_OnPlayerSpawned(function(player){
    player.SetThinkFunction("ClientCommandThink");
});
