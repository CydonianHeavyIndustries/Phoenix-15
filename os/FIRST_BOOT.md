# Phoenix-15 First Boot Wizard (Design)

Goal: present a Windows-style setup flow on first boot while keeping the Phoenix UI as the primary interface.

## Trigger
- If `/phoenix-data/phoenix/firstboot_complete` does not exist, the UI should open a setup panel on launch.
- After completion, write `firstboot_complete` to the same folder.

## Data Paths (Windows-accessible)
- `/phoenix-data/phoenix/storage_policy.json`
- `/phoenix-data/phoenix/network.json`
- `/phoenix-data/phoenix/firstboot_complete`

## Suggested Steps
1) Welcome + explain USB-only mode.
2) Install target (USB only / install to other disk).
3) Disk access policy (block internal disks unless user opts in).
4) Wi-Fi setup (list SSIDs, connect, optional skip).
5) Updates & behavior (offline-only / allow network fetch).
6) Finish.

## Storage Policy Format
```
{
  "allow_internal_mounts": false
}
```

## Networking Format (example)
```
{
  "wifi_enabled": true,
  "ssid": "MyNetwork",
  "autoconnect": true
}
```

## Implementation Notes
- The OS service `phoenix-storage-policy.service` reads the policy file on boot.
- The Phoenix UI should be the only place users need to interact; no CLI.
