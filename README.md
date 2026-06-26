# JMRI Trains for Home Assistant

Custom Home Assistant integration for controlling model trains through the JMRI JSON WebSocket API.

![JMRI Trains banner](artwork/jmri-trains-banner-v1.png)

## Version

`1.0.0`

## What it creates

- One controller sensor for the configured JMRI Web Server.
- One train sensor per configured train.
- Services to add, edit, remove, stop, emergency stop, release, and control trains.

JMRI must have the Web Server running. By default this is usually `http://<jmri-host>:12080`, with JSON available at `/json`.

## Install

Copy `custom_components/jmri_trains` into your Home Assistant `custom_components` directory and restart Home Assistant.

Then add the integration from **Settings > Devices & services > Add integration > JMRI Trains**.

## Add a train

Call `jmri_trains.add_train`:

```yaml
train_id: loco_3
name: Switcher 3
address: 3
is_long_address: false
```

Or by JMRI roster entry:

```yaml
train_id: big_boy
name: Big Boy
roster_entry: UP 4014
```

If multiple JMRI controllers are configured, include `entry_id`.

## Control a train

Set speed:

```yaml
service: jmri_trains.set_speed
target:
  entity_id: sensor.switcher_3
data:
  speed: 0.35
```

Set direction:

```yaml
service: jmri_trains.set_direction
target:
  entity_id: sensor.switcher_3
data:
  forward: true
```

Set a function, such as `F0`:

```yaml
service: jmri_trains.set_function
target:
  entity_id: sensor.switcher_3
data:
  function: F0
  enabled: true
```

Stop:

```yaml
service: jmri_trains.stop
target:
  entity_id: sensor.switcher_3
```

Emergency stop:

```yaml
service: jmri_trains.emergency_stop
target:
  entity_id: sensor.switcher_3
```

## Notes

JMRI throttle speed is normalized from `0.0` to `1.0`. The integration uses JMRI JSON throttle messages with `speed`, `forward`, `F0` through supported function names, `idle`, `eStop`, and `release`.
