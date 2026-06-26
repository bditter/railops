# RailOps for Home Assistant

Custom Home Assistant integration for controlling model trains directly through a DCC-EX command station.

![RailOps banner](brand/logo.png)

## Version

`1.5.1`

## What it creates

- One controller sensor for the configured DCC-EX command station.
- Controller controls for track power and global emergency stop.
- One train device per configured locomotive.
- Train controls for speed, direction, stop, emergency stop, and mapped DCC functions.
- Standard F0-F28 function switches for each locomotive, labeled with friendly mappings when available.
- Function controls can be configured as toggles or momentary buttons.
- Locomotive acquire and release buttons for marking active RailOps control.
- Accessory setup for DCC accessory decoder outputs and function-decoder outputs.
- Controller and locomotive polling using DCC-EX status and throttle queries.
- Services to add, edit, remove, stop, emergency stop, power, and control trains.

DCC-EX must be reachable over TCP. ESP8266 WiFi setups commonly expose the DCC-EX command station on port `2560`.

## Install

Copy `custom_components/railops` into your Home Assistant `custom_components` directory and restart Home Assistant.

Then add the integration from **Settings > Devices & services > Add integration > RailOps**.

To add or edit locomotives and accessories, open the RailOps integration entry and choose **Configure**.

## HACS

Add this repository as a custom HACS integration repository:

```text
https://github.com/bditter/railops
```

Use the latest GitHub release, then restart Home Assistant after HACS downloads it.

## Add a train

Call `railops.add_train`:

```yaml
train_id: loco_3
name: Switcher 3
address: 3
functions:
  headlight: 0
  bell: 1
  horn: 2
```

If multiple DCC-EX command stations are configured, include `entry_id`.

## Control a train

Set speed:

```yaml
service: railops.set_speed
target:
  entity_id: sensor.switcher_3
data:
  speed: 35
```

Set direction:

```yaml
service: railops.set_direction
target:
  entity_id: sensor.switcher_3
data:
  forward: true
```

Set a function, such as `F0`:

```yaml
service: railops.set_function
target:
  entity_id: sensor.switcher_3
data:
  function: headlight
  enabled: true
```

Pulse a momentary function, such as a horn:

```yaml
service: railops.pulse_function
target:
  entity_id: sensor.switcher_3
data:
  function: horn
  duration: 0.5
```

Edit a train's function mapping:

```yaml
service: railops.set_function_mapping
target:
  entity_id: sensor.switcher_3
data:
  function_name: horn
  function_number: 2
```

Remove a custom function mapping:

```yaml
service: railops.remove_function_mapping
target:
  entity_id: sensor.switcher_3
data:
  function_name: horn
```

Stop:

```yaml
service: railops.stop
target:
  entity_id: sensor.switcher_3
```

Emergency stop:

```yaml
service: railops.emergency_stop
target:
  entity_id: sensor.switcher_3
```

Turn on main track power:

```yaml
service: railops.set_power
data:
  enabled: true
  track: MAIN
```

## Notes

DCC-EX throttle speed uses integer speed steps from `0` to `126`. RailOps sends native DCC-EX commands such as `<t cab speed direction>`, `<F cab function state>`, `<!>`, and `<1 MAIN>` / `<0 MAIN>`.

Function mappings accept `F0` through `F28`. RailOps creates standard F0-F28 controls for each locomotive and uses friendly mappings to label them. Each function can be configured as a toggle switch or momentary button. Default aliases include `headlight`, `bell`, `horn`, `whistle`, `short_horn`, `dynamic_brake`, `ditch_lights`, `mars_light`, `dim_headlight`, and `mute`.

Accessory setup supports two command styles:

- DCC accessory decoder: `<a address subaddress state>`
- Function decoder output: `<F address function state>`
