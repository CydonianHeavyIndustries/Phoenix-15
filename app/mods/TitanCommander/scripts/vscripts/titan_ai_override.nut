//------------------------------------------------------------
// TitanCommander : Titan AI override bootstrap
//------------------------------------------------------------

// Shared state helpers
function OverrideTitanAI(titan)
{
    titan.ai_override <- true;
    titan.current_command <- "IDLE";
    titan.target_pos <- null;
    titan.custom_target <- null;
    titan.override_input <- null;
}

//------------------------------------------------------------
// Core Think loop for overridden Titans
//------------------------------------------------------------
function TitanCommanderThink(titan)
{
    if (!("ai_override" in titan) || !titan.ai_override)
        return;

    switch (titan.current_command)
    {
        case "MOVE_TO":
            TitanMoveTo(titan, titan.target_pos);
            break;

        case "HOLD":
            titan.Stop();
            break;

        case "ATTACK":
            TitanAttack(titan, titan.custom_target);
            break;

        case "FOLLOW_PLAYER":
            TitanMoveTo(titan, GetPlayer().GetOrigin());
            break;

        case "OVERRIDE_INPUT":
            TitanApplyPuppetInput(titan, titan.override_input);
            break;

        default:
            // idle
            titan.Stop();
            break;
    }
}

// Register on spawn
AddCallback_OnTitanSpawned(function(titan) {
    OverrideTitanAI(titan);
    titan.SetThinkFunction("TitanCommanderThink");
});
