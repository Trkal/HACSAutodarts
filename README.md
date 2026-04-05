# Autodarts for Home Assistant

[![HACS Custom](https://img.shields.io/badge/HACS-Custom-orange.svg)](https://hacs.xyz)

A [Home Assistant](https://www.home-assistant.io/) custom integration for [Autodarts](https://autodarts.io/) — the automatic dart scoring system.

This integration polls your local Autodarts board to expose real-time match data, player statistics, and board status as Home Assistant sensor entities.

## Features

- **Board status** — connection state of your Autodarts board
- **Match state** — active, waiting, or finished
- **Game mode** — X01, Cricket, and all supported modes
- **Current player** — who's throwing right now
- **Per-player score** — remaining score for each player
- **Per-player PPD** — points per dart average
- **Per-player legs won** — legs/sets won count
- **Last throw** — segment hit (e.g. T20, D16, Bull)
- **Last visit score** — total points from the last 3 darts
- **Darts thrown** — total darts thrown in the match

Player sensors are created dynamically — new players are detected automatically when they join a match.

## Requirements

- An Autodarts board running on your local network
- The board's local API must be accessible (default port: **3180**)

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
3. Enter the **IP address** (or hostname) of your Autodarts board
4. Enter the **port** (default: `3180`)
5. Click **Submit**

The integration will test the connection and create all sensor entities automatically.

## Sensors

| Sensor | Description | Unit |
|--------|-------------|------|
| Board Status | Board connection state | — |
| Game Mode | Active game type (X01, Cricket, etc.) | — |
| Match State | Match status (active/waiting/finished) | — |
| Current Player | Name of the player whose turn it is | — |
| *Player* Score | Remaining score for each player | points |
| *Player* PPD | Points per dart average | PPD |
| *Player* Legs Won | Number of legs/sets won | — |
| Last Throw | Last dart thrown (e.g. T20, D16) | — |
| Last Visit Score | Total points from the last visit | points |
| Darts Thrown | Total darts thrown in the match | darts |

## Automations

Use these sensors to trigger Home Assistant automations, for example:

- Flash lights when a player checks out (match state changes to "finished")
- Play a sound when a 180 is scored (last visit score = 180)
- Send a notification with match results
- Display live scores on a dashboard

## License

MIT
