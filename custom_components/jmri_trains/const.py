"""Constants for the JMRI Trains integration."""

from __future__ import annotations

from typing import Final

DOMAIN: Final = "jmri_trains"

CONF_HOST: Final = "host"
CONF_PORT: Final = "port"
CONF_SSL: Final = "ssl"
CONF_VERIFY_SSL: Final = "verify_ssl"

DEFAULT_PORT: Final = 12080
DEFAULT_SSL: Final = False
DEFAULT_VERIFY_SSL: Final = True

PLATFORMS: Final = ["sensor"]

DATA_CLIENT: Final = "client"
DATA_UNSUB_LISTENERS: Final = "unsub_listeners"

OPT_TRAINS: Final = "trains"

ATTR_ENTRY_ID: Final = "entry_id"
ATTR_TRAIN_ID: Final = "train_id"
ATTR_NAME: Final = "name"
ATTR_ADDRESS: Final = "address"
ATTR_ROSTER_ENTRY: Final = "roster_entry"
ATTR_IS_LONG_ADDRESS: Final = "is_long_address"
ATTR_PREFIX: Final = "prefix"
ATTR_SPEED: Final = "speed"
ATTR_FORWARD: Final = "forward"
ATTR_FUNCTION: Final = "function"
ATTR_ENABLED: Final = "enabled"

SERVICE_ADD_TRAIN: Final = "add_train"
SERVICE_UPDATE_TRAIN: Final = "update_train"
SERVICE_REMOVE_TRAIN: Final = "remove_train"
SERVICE_SET_SPEED: Final = "set_speed"
SERVICE_SET_DIRECTION: Final = "set_direction"
SERVICE_SET_FUNCTION: Final = "set_function"
SERVICE_STOP: Final = "stop"
SERVICE_ESTOP: Final = "emergency_stop"
SERVICE_RELEASE: Final = "release_train"
