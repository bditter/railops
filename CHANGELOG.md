# Changelog

## 1.3.1

- Replaces the unlabeled Configure menu row with an explicit action dropdown.

## 1.3.0

- Removes the locomotive telemetry sensor from the default entity model.
- Cleans up older locomotive telemetry sensor entities on startup.
- Creates stable F0-F28 function switches for each locomotive.
- Uses friendly function mappings to label standard function switches.
- Uses Home Assistant platform enums for setup forwarding.

## 1.2.0

- Adds visible Home Assistant controls for RailOps instead of service-only control.
- Adds controller track power switch and global emergency-stop button.
- Adds train speed number, direction select, stop button, emergency-stop button, and function switches.
- Adds a Configure options flow for adding, editing, and removing locomotives.
- Adds Configure options for editing friendly function mappings.
- Publishes branding in both HACS repo-level and integration-level brand folders.

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
- Adds project artwork for the integration.
