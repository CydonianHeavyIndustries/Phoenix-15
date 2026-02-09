TitanCommander – Quick Notes

Purpose
- Override Titan AI and consume commands from %LOCALAPPDATA%/Northstar/bjorgsun_telemetry/commands.json
- Works with existing Bjorgsun.Autopilot / Bjorgsun.Telemetry bridge

Command schema (JSON in commands.json)
{
  "mode": "MOVE_TO",           // MOVE_TO | HOLD | FOLLOW | ATTACK | OVERRIDE_INPUT | STOP
  "pos": [x,y,z],              // required for MOVE_TO
  "target_id": 123,            // entity id for ATTACK
  "input": {                   // for OVERRIDE_INPUT puppet mode
    "forward": 1,
    "strafe": 0,
    "yaw": 45,
    "pitch": 0,
    "fire": true,
    "ability": "ronin_block",  // ronin_block | ronin_phase | ronin_dash | any ability name
    "core": true
  }
}

Ronin ability tokens
- block: ronin_block | block | swordblock
- phase: ronin_phase | phase | phase_dash
- dash: ronin_dash | dash
- core: set input.core = true

Loop timing
- TitanCommander polls commands.json every ~0.20s (server script)
- Bjorgsun.Autopilot also polls and now understands the expanded modes

Mod files
- scripts/vscripts/titan_ai_override.nut     (override state + think loop)
- scripts/vscripts/titan_controller.nut      (movement/combat/puppet + ability map)
- scripts/vscripts/command_bridge.nut        (IssueCommand* helpers)
- scripts/vscripts/command_file_bridge.nut   (commands.json reader)
- scripts/server/titan_override_server.nut   (includes + starts polling)
- scripts/client/input_handler.nut           (example hotkeys F1/F2/F3)

Placement
- Drop TitanCommander folder into Titanfall2\R2Northstar\mods\TitanCommander and enable.
