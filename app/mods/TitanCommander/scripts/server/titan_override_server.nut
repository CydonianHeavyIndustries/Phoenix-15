//------------------------------------------------------------
// TitanCommander : server-side entry
// Hooks Titan spawn and provides RPC entry points if needed.
//------------------------------------------------------------

IncludeScript("scripts/vscripts/titan_ai_override.nut");
IncludeScript("scripts/vscripts/titan_controller.nut");
IncludeScript("scripts/vscripts/command_bridge.nut");
IncludeScript("scripts/vscripts/command_file_bridge.nut");

// Start command polling on level init
function OnLevelInit()
{
    printl("[TitanCommander] Command file bridge armed.");
    thread TC_CommandFileTick();
}

RegisterScriptCallback("OnLevelInit", OnLevelInit);
