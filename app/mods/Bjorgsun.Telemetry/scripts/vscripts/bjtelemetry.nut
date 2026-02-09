//---------------------------------------------------------
//  Bjorgsun Telemetry Exporter
//---------------------------------------------------------

function WriteJSON(path, tbl)
{
    local json = JsonDump(tbl);
    FileSystem.WriteToFile(path, json);
}

function CollectPilotData()
{
    local p = GetLocalClientPlayer();
    if (!p) return null;

    return {
        health = p.GetHealth(),
        max_health = p.GetMaxHealth(),
        armor = p.GetArmorValue(),
        pos = p.GetOrigin(),
        vel = p.GetVelocity(),
        weapon = p.GetActiveWeapon().GetWeaponClassName(),
        is_ads = p.IsWeaponInADS(),
        tactical_cd = p.GetTacticalCooldown(),
        grenade_count = p.GetGrenadeAmmoCount()
    };
}

function CollectTitanData()
{
    local t = GetPlayerTitan(GetLocalClientPlayer());
    if (!t) return null;

    return {
        health = t.GetHealth(),
        max_health = t.GetMaxHealth(),
        shield = t.GetTitanShieldHealth(),
        pos = t.GetOrigin(),
        core = t.GetCoreChargeFraction(),
        chassis = t.GetTitanSubClass(),
        ability = t.GetActiveTitanAbilityName()
    };
}

function CollectGameData()
{
    return {
        map = GetMapName(),
        mode = GetGameMode(),
        time = Time(),
        match_state = GetGameState()
    };
}

function TelemetryTick()
{
    local base = GetLocalAppDataDir() + "/Northstar/bjorgsun_telemetry/";

    WriteJSON(base + "pilot.json", CollectPilotData());
    WriteJSON(base + "titan.json", CollectTitanData());
    WriteJSON(base + "game.json", CollectGameData());

    thread TelemetryTick_Delayed();
}

function TelemetryTick_Delayed() { wait 0.10; TelemetryTick(); }

function OnLevelInit()
{
    thread TelemetryTick();
}

RegisterScriptCallback("OnLevelInit", OnLevelInit);
