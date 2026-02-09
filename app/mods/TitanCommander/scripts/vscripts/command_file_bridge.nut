//------------------------------------------------------------
// TitanCommander : LocalAppData JSON command bridge
// Polls %LOCALAPPDATA%/Northstar/bjorgsun_telemetry/commands.json
// Compatible with Bjorgsun.Autopilot command file schema.
//------------------------------------------------------------

const TC_CMD_PATH = GetLocalAppDataDir() + "/Northstar/bjorgsun_telemetry/commands.json";

function TC_ReadCommands()
{
    try {
        if (!FileSystem.FileExists(TC_CMD_PATH))
            return null;
        local data = FileSystem.ReadFile(TC_CMD_PATH);
        if (!data || data.len() == 0) return null;
        return JsonParse(data);
    } catch (e) {
        printl("[TitanCommander] read error: " + e);
        return null;
    }
}

function TC_GetTitan()
{
    local p = GetLocalClientPlayer();
    if (!p) return null;
    return GetPlayerTitan(p);
}

function TC_ApplyCommand(cmd)
{
    local t = TC_GetTitan();
    if (!t) return;
    if (cmd == null || !("mode" in cmd)) return;

    local mode = cmd.mode;
    if (mode == "MOVE_TO" && "pos" in cmd) {
        IssueCommandMoveTo(t, Vector(cmd.pos[0], cmd.pos[1], cmd.pos[2]));
    } else if (mode == "HOLD") {
        IssueCommandHold(t);
    } else if (mode == "FOLLOW") {
        IssueCommandFollow(t);
    } else if (mode == "ATTACK" && "target_id" in cmd) {
        local ent = GetEntity(cmd.target_id);
        IssueCommandAttack(t, ent);
    } else if (mode == "OVERRIDE_INPUT" && "input" in cmd) {
        StartManualOverride(t, cmd.input);
    } else if (mode == "IDLE" || mode == "STOP") {
        StopManualOverride(t);
    }
}

function TC_CommandFileTick()
{
    TC_ApplyCommand(TC_ReadCommands());
    thread TC_CommandFileTick_Delayed();
}

function TC_CommandFileTick_Delayed() { wait 0.20; TC_CommandFileTick(); }
