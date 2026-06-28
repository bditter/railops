# Changelog

## 1.6.3

- Corrects sound-state tracking so F5 from shutdown starts at idle and F6 from idle moves to shutdown.
- Adds a Sound State select with Shutdown, Idle, and Speed 1 through Speed 7 style labels.
- Keeps sound shutdown separate from locomotive release/acquire state.

## 1.6.2

- Moves controller connection state to a connectivity binary sensor so Home Assistant renders connected/disconnected correctly.
- Removes the old controller text sensor during startup.

## 1.6.1

- Reloads RailOps automatically after changing the controller host or port.
- Adds a Reload integration action to the RailOps Configure menu.

## 1.6.0

- Marks configured locomotives acquired when track power is turned on and released when track power is turned off.
- Adds train Acquired binary sensors.
- Adds a train RPM number for sound-decoder notches, defaulting to F5 increase, F6 decrease, idle 0, max 7, and released -1.
- Lets locomotive setup edit RPM behavior and controller host/port.
- Lets F0-F28 function entities be disabled from Configure.
- Gives custom function mappings priority over built-in labels and replaces old custom labels for the same F-key.
- Polls only acquired locomotives so release is not undone by the heartbeat query.

## 1.5.1

- Sends DCC-EX's native `<- cab>` locomotive release command from release buttons.
- Stops querying a locomotive during release so DCC-EX does not immediately re-add it to active reminders.

## 1.5.0

- Adds per-function control type configuration for toggle switches or momentary buttons.
- Adds function button entities that pulse the DCC function on/off.
- Adds locomotive acquire and release buttons.
- Defaults toggle-style switch states to off when no DCC-EX feedback has arrived yet, so Home Assistant renders toggles instead of lightning-bolt actions after reload.
- Cleans up stale switch/button entities when a function control type changes.

## 1.4.1

- Changes Configure number fields for DCC addresses, subaddresses, and function mappings to whole-number box inputs.

## 1.4.0

- Adds heartbeat polling with `<s>` and configured locomotive `<t cab>` queries.
- Immediately reports current connection state to controller entities.
- Adds accessory configuration for DCC accessory decoder outputs.
- Adds function-decoder accessory mode for boards such as Digitrax TF4-style outputs.
- Adds accessory switch entities.

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
