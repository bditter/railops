"""Constants for the RailOps integration."""

from __future__ import annotations

from typing import Final

from homeassistant.const import Platform

DOMAIN: Final = "railops"

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
DEFAULT_PORT: Final = 2560

PLATFORMS: Final = [
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.SELECT,
    Platform.SENSOR,
    Platform.SWITCH,
]

DATA_CLIENT: Final = "client"
DATA_UNSUB_LISTENERS: Final = "unsub_listeners"

OPT_TRAINS: Final = "trains"
OPT_ACCESSORIES: Final = "accessories"

ATTR_ENTRY_ID: Final = "entry_id"
ATTR_TRAIN_ID: Final = "train_id"
ATTR_NAME: Final = "name"
ATTR_ADDRESS: Final = "address"
ATTR_SPEED: Final = "speed"
ATTR_FORWARD: Final = "forward"
ATTR_FUNCTION: Final = "function"
ATTR_FUNCTIONS: Final = "functions"
ATTR_FUNCTION_NAME: Final = "function_name"
ATTR_FUNCTION_NUMBER: Final = "function_number"
ATTR_ENABLED: Final = "enabled"
ATTR_TRACK: Final = "track"
ATTR_DURATION: Final = "duration"
ATTR_ACCESSORY_ID: Final = "accessory_id"
ATTR_MODE: Final = "mode"
ATTR_SUBADDRESS: Final = "subaddress"
ATTR_OUTPUT: Final = "output"
ATTR_INVERTED: Final = "inverted"

ACCESSORY_MODE_DCC: Final = "dcc_accessory"
ACCESSORY_MODE_FUNCTION: Final = "function_decoder"

SERVICE_ADD_TRAIN: Final = "add_train"
SERVICE_UPDATE_TRAIN: Final = "update_train"
SERVICE_REMOVE_TRAIN: Final = "remove_train"
SERVICE_SET_SPEED: Final = "set_speed"
SERVICE_SET_DIRECTION: Final = "set_direction"
SERVICE_SET_FUNCTION: Final = "set_function"
SERVICE_SET_FUNCTION_MOMENTARY: Final = "pulse_function"
SERVICE_SET_FUNCTION_MAPPING: Final = "set_function_mapping"
SERVICE_REMOVE_FUNCTION_MAPPING: Final = "remove_function_mapping"
SERVICE_SET_POWER: Final = "set_power"
SERVICE_STOP: Final = "stop"
SERVICE_ESTOP: Final = "emergency_stop"
