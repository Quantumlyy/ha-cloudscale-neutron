"""Constants for the CloudScale Neutron integration."""

DOMAIN = "cloudscale_neutron"

CONF_MODULE_ID = "module_id"
CONF_PIN = "pin"
CONF_HOST = "host"
CONF_PORT = "port"
CONF_PATH = "path"
CONF_TLS = "tls"
CONF_SCAN_INTERVAL = "scan_interval"
CONF_SMOOTHING = "smoothing"
CONF_SMOOTHING_WINDOW = "smoothing_window"
CONF_STABLE_ONLY = "stable_only"

DEFAULT_PORT = 443
DEFAULT_PATH = "/sm"
DEFAULT_TLS = True
DEFAULT_SCAN_INTERVAL = 5.0
MIN_SCAN_INTERVAL = 0.2
MAX_SCAN_INTERVAL = 3600.0

DEFAULT_SMOOTHING = "none"
DEFAULT_SMOOTHING_WINDOW = 30.0
MIN_SMOOTHING_WINDOW = 1.0
MAX_SMOOTHING_WINDOW = 86400.0
DEFAULT_STABLE_ONLY = True

# Values that get a smoothed sensor when smoothing is switched on.
SMOOTHED_KEYS = ("net", "gross", "adc", "millivolts")

# Command the Scale Monitor web app itself polls with. The module answers with
# one comma-separated line on the TX topic.
POLL_COMMAND = "QASI1C"

# Read-only command the Scale Monitor web app sends when it opens a scale. The
# module answers with its scale settings (unit, capacity, division, ...).
SETTINGS_COMMAND = "RSD"

# Scale commands from the CloudScale Communication Protocol (CSCP) manual. These
# are only sent when the user presses the matching button.
COMMAND_TARE = "T"
COMMAND_ZERO = "Z"
COMMAND_CLEAR_TARE = "TAC"
