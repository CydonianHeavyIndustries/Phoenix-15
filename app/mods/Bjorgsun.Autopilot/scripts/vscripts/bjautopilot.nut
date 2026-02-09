//---------------------------------------------------------
//  Bjorgsun Autopilot (experimental)
//  Reads commands from %LOCALAPPDATA%/Northstar/bjorgsun_telemetry/commands.json
//  and attempts to drive the player's Titan accordingly.
//
//  NOTE: This is experimental and intended for private/PVE use.
//  It does NOT alter real-world behavior; it only manipulates a fictional game entity.
//---------------------------------------------------------

function _read_commands()
{
    try {
        local base = GetLocalAppDataDir() + "/Northstar/bjorgsun_telemetry/";
        local path = base + "commands.json";
        if (!FileSystem.FileExists(path)) {
            return null;
        }
        local data = FileSystem.ReadFile(path);
        if (!data || data.len() == 0) return null;
        return JsonParse(data);
    } catch (e) {
        printl("[BjAutopilot] read error: " + e);
        return null;
    }
}

function _get_titan()
{
    local p = GetLocalClientPlayer();
    if (!p) return null;
    return GetPlayerTitan(p);
}

// Simple behaviors: follow pilot, hold position, or idle.
function _apply_command(cmd)
{
    local t = _get_titan();
    if (!t) return;

    // Only operate on the local client's titan
    if (cmd == null || !("mode" in cmd)) return;
    local mode = cmd.mode;

    // Legacy modes mapped to TitanCommander bridge
    if (mode == "follow") {
        local p = GetLocalClientPlayer();
        if (p) {
            local pos = p.GetOrigin();
            t.SetMoveTarget(pos + Vector(50, 0, 0));
            t.SetRunTo(pos + Vector(50, 0, 0));
            t.SetAIEnabled(true);
        }
    } else if (mode == "hold") {
        t.SetAIEnabled(true);
        t.ClearMoveTarget();
    } else if (mode == "idle") {
        t.SetAIEnabled(false);
    } else if (mode == "MOVE_TO" && "pos" in cmd) {
        IssueCommandMoveTo(t, Vector(cmd.pos[0], cmd.pos[1], cmd.pos[2]));
    } else if (mode == "FOLLOW") {
        IssueCommandFollow(t);
    } else if (mode == "HOLD") {
        IssueCommandHold(t);
    } else if (mode == "ATTACK" && "target_id" in cmd) {
        local ent = GetEntity(cmd.target_id);
        IssueCommandAttack(t, ent);
    } else if (mode == "OVERRIDE_INPUT" && "input" in cmd) {
        StartManualOverride(t, cmd.input);
    } else if (mode == "STOP") {
        StopManualOverride(t);
    }

    if ("fire" in cmd && cmd.fire == true) {
        t.PressAttackButton();
    }
}

function _tick()
{
    local cmd = _read_commands();
    _apply_command(cmd);
    thread _tick_delay();
}

function _tick_delay() { wait 0.25; _tick(); }

function OnLevelInit()
{
    printl("[BjAutopilot] Autopilot armed (experimental).");
    thread _tick();
}

RegisterScriptCallback("OnLevelInit", OnLevelInit);
