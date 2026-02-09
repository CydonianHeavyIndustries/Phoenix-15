//------------------------------------------------------------
// TitanCommander : command bridge (callable by client/server)
//------------------------------------------------------------

// Shared command appliers
function IssueCommandMoveTo(titan, pos)
{
    if (!pos) return;
    titan.current_command <- "MOVE_TO";
    titan.target_pos <- pos;
}

function IssueCommandHold(titan)
{
    titan.current_command <- "HOLD";
    titan.target_pos <- null;
}

function IssueCommandAttack(titan, target)
{
    titan.current_command <- "ATTACK";
    titan.custom_target <- target;
}

function IssueCommandFollow(titan)
{
    titan.current_command <- "FOLLOW_PLAYER";
    titan.target_pos <- null;
}

function StartManualOverride(titan, input)
{
    titan.current_command <- "OVERRIDE_INPUT";
    titan.override_input <- input;
}

function StopManualOverride(titan)
{
    titan.current_command <- "IDLE";
    titan.override_input <- null;
}
