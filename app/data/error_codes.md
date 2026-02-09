# Phoenix-15 Error Codes

Format: `PHX-<MODULE>-<CODE>`

## Modules
- `SYS` system / self-check
- `API` HTTP layer responses
- `SRV` server runtime
- `NET` backend connectivity
- `MEM` memory store
- `AUD` audio lab + EQ
- `TTS` text-to-speech
- `OLL` Ollama / local model
- `SPT` Spotify integration
- `FRQ` frequency analysis
- `EMO` emotion prompt / tagging
- `VIS` vision module
- `UI` user interface
- `UNK` unknown

## Core Codes
- `PHX-SYS-000` self-check system OK
- `PHX-SYS-001` system metrics failed
- `PHX-SYS-900` self-check found failures
- `PHX-SYS-999` self-check call failed

- `PHX-API-4xx` HTTP client error (status-specific)
- `PHX-API-5xx` HTTP server error (status-specific)
- `PHX-SRV-500` unhandled server exception

- `PHX-NET-000` backend online / ping OK
- `PHX-NET-101` backend offline / ping failed

## Memory
- `PHX-MEM-000` memory OK
- `PHX-MEM-001` memory empty
- `PHX-MEM-002` memory list failed
- `PHX-MEM-101` memory check failed
- `PHX-MEM-102` memory reinject failed

## Audio
- `PHX-AUD-000` audio OK
- `PHX-AUD-001` audio module not mounted
- `PHX-AUD-002` audio health not OK
- `PHX-AUD-003` audio health request failed
- `PHX-AUD-004` pycaw missing
- `PHX-AUD-101` audio devices unavailable
- `PHX-AUD-102` audio device update failed
- `PHX-AUD-110` EQ data unavailable
- `PHX-AUD-111` EQ engine unavailable
- `PHX-AUD-112` audio profiles unavailable

## TTS
- `PHX-TTS-000` TTS OK
- `PHX-TTS-001` edge_tts missing

## Ollama
- `PHX-OLL-000` Ollama OK
- `PHX-OLL-001` Ollama non-200 response
- `PHX-OLL-002` Ollama endpoint not configured
- `PHX-OLL-003` Ollama request failed

## Spotify
- `PHX-SPT-000` Spotify OK
- `PHX-SPT-001` Spotify not authorized
- `PHX-SPT-010` Spotify not authorized (ignored by self-check)
- `PHX-SPT-101` Spotify status unavailable
- `PHX-SPT-201` Spotify play failed
- `PHX-SPT-202` Spotify pause failed
- `PHX-SPT-203` Spotify next failed
- `PHX-SPT-204` Spotify previous failed
- `PHX-SPT-205` Spotify transfer failed

## Frequency
- `PHX-FRQ-000` frequency analysis requested
- `PHX-FRQ-010` frequency analysis complete
- `PHX-FRQ-101` no file selected
- `PHX-FRQ-102` audio decode unavailable
- `PHX-FRQ-103` audio decode failed
- `PHX-FRQ-110` direct analyze failed; fallback decode
- `PHX-FRQ-120` no analysis returned
- `PHX-FRQ-201` network fetch failed
- `PHX-FRQ-404` analyze endpoint not found

## Emotion
- `PHX-EMO-201` emotion tag save failed

## Vision
- `PHX-VIS-000` vision OK
- `PHX-VIS-001` vision model missing

## UI
- `PHX-UI-101` wake failed
- `PHX-UI-102` sleep failed
- `PHX-UI-201` open logs failed
- `PHX-UI-202` file browser failed
- `PHX-UI-500` UI error

## Unknown
- `PHX-UNK-000` unknown issue
