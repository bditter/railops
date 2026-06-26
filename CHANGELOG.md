# Changelog

## 1.1.0

- Renames the integration to RailOps.
- Replaces JMRI WebSocket control with direct DCC-EX TCP command control.
- Changes the Home Assistant domain to `railops`.
- Adds DCC-EX services for speed, direction, functions, track power, stop, and emergency stop.
- Adds editable function mappings for friendly names like horn, bell, and headlight.
- Adds a momentary function pulse service for horn/whistle style controls.
- Moves artwork into the integration branding folder.

## 1.0.1

- Adds HACS metadata and issue tracker URL.
- Publishes a GitHub release so HACS uses a semantic version instead of a commit hash.
- Hides the default branch option in HACS to steer installs to releases.

## 1.0.0

- Initial private release.
- Adds a Home Assistant config flow for a JMRI Web Server controller.
- Adds one controller sensor and one train sensor per configured train.
- Adds services to add, update, remove, stop, emergency stop, release, and control trains.
- Adds Train Control artwork for the integration.
