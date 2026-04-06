# Autodarts for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

A [Home Assistant](https://www.home-assistant.io/) custom integration for [Autodarts](https://autodarts.io/) — the automatic dart scoring system.

This integration connects to the **Autodarts cloud API** (via OAuth2) to retrieve real-time match data and board status. Optionally, it also connects to your **local board** for faster throw detection.

## Features

### Board Sensors
- **Board Status** — connected / disconnected
- **Board Event** — last detection event (Throw, Takeout, Starting)

### Match Sensors
- **Game Mode** — X01, Cricket, Count Up, etc.
- **Match State** — Active / Finished / No match
- **Round** — current round number
- **Visit Score** — points scored in the current turn
- **Total Turns** — total turns played in the match

### Detection Sensors (requires local board IP)
- **Last Throw** — segment hit (e.g. T20, D16, S5, Bull)
- **Throws in Turn** — number of darts thrown in the current turn (0–3)

## Requirements

- An **Autodarts account** (email + password) at [autodarts.io](https://autodarts.io/)
- At least one board registered to your account
- *(Optional)* Local network access to the board for throw detection (default port: **3180**)

## Installation

### HACS (recommended)

1. Open HACS in your Home Assistant instance
2. Go to **Integrations** → click the **three dots** menu → **Custom repositories**
3. Add `https://github.com/Trkal/HACSAutodarts` as an **Integration**
4. Search for **Autodarts** and install it
5. Restart Home Assistant

### Manual

1. Copy the `custom_components/autodarts` folder into your Home Assistant `config/custom_components/` directory
2. Restart Home Assistant

## Configuration

1. Go to **Settings** → **Devices & Services** → **Add Integration**
2. Search for **Autodarts**
3. *(Optional)* Enter the **local board IP** for throw detection, then click **Submit**
4. Click the link to **log in to your Autodarts account** in the browser
5. After logging in, your browser will redirect — **copy the full URL** from the address bar
6. Paste the URL into the config flow and click **Submit**
7. If you have multiple boards, select which one to use

The integration authenticates via OAuth2 (Authorization Code + PKCE) to the Autodarts cloud, then creates all sensor entities automatically. Tokens are refreshed automatically and persisted across restarts.

## Sensors

| Sensor | Source | Description | Unit |
|--------|--------|-------------|------|
| Board Status | Cloud | Board connection state | — |
| Board Event | Local/Cloud | Last detection event | — |
| Game Mode | Cloud | Active game type (X01, Cricket, etc.) | — |
| Match State | Cloud | Match status (Active/Finished/No match) | — |
| Round | Cloud | Current round number | — |
| Last Throw | Local | Last dart segment (e.g. T20, D16) | — |
| Throws in Turn | Local | Darts thrown this turn (0–3) | darts |
| Visit Score | Cloud | Points scored in current turn | points |
| Total Turns | Cloud | Total turns in the match | turns |

## Automations

Use these sensors to trigger Home Assistant automations, for example:

- Flash lights when a player checks out (match state changes to "Finished")
- Play a sound when a 180 is scored (visit score = 180)
- Send a notification with match results
- Display live scores on a dashboard

## License

MIT
