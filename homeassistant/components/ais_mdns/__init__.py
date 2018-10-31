"""
This module exposes AIS dom via Zeroconf.

For more details about this component, please refer to the documentation at
https://sviete.github.io/AIS-docs
"""
import logging
import socket
import subprocess
import voluptuous as vol

from homeassistant import util
from homeassistant.const import (EVENT_HOMEASSISTANT_STOP, __version__)

REQUIREMENTS = ['zeroconf==0.21.3']

_LOGGER = logging.getLogger(__name__)

DEPENDENCIES = ['api']
DOMAIN = 'ais_mdns'
ZEROCONF_NAME = 'ais-dom'

CONFIG_SCHEMA = vol.Schema({
    DOMAIN: vol.Schema({}),
}, extra=vol.ALLOW_EXTRA)


def setup(hass, config):
    """Set up Zeroconf and make AIS dom discoverable."""
    from zeroconf import Zeroconf, ServiceInfo

    zero_config = Zeroconf()
    host_ip = util.get_local_ip()

    try:
        return_value = subprocess.check_output('getprop net.hostname', shell=True, timeout=15)
        host_name = return_value.strip().decode('utf-8')
    except subprocess.CalledProcessError:
        host_name = socket.gethostname()
    if host_name.endswith('.local'):
        host_name = host_name[:-len('.local')]

    try:
        ip = socket.inet_pton(socket.AF_INET, host_ip)
    except socket.error:
        ip = socket.inet_pton(socket.AF_INET6, host_ip)

    # hass.http.server_port - 8180
    # hass.config.api.base_url
    params = {
        'version': __version__,
        'company_url': "https://ai-speaker.com",
    }

    # https://ais-dom.local:8123
    # http://ais-dom.local:8180

    # HTTP
    http_info = ServiceInfo("_http._tcp.local.",
                            ZEROCONF_NAME + "._http._tcp.local.",
                            ip, 8180, 0, 0,
                            params, host_name + ".local.")

    zero_config.register_service(http_info)

    # MQTT
    mqtt_info = ServiceInfo("_mqtt._tcp.local.",
                            ZEROCONF_NAME + "._mqtt._tcp.local.",
                            ip, 1883, 0, 0,
                            params, host_name + ".local.")

    zero_config.register_service(mqtt_info)

    # FTP
    ftp_info = ServiceInfo("_ftp._tcp.local.",
                           ZEROCONF_NAME + "._ftp._tcp.local.",
                           ip, 1024, 0, 0,
                           params, host_name + ".local.")

    zero_config.register_service(ftp_info)

    # SSH
    ssh_info = ServiceInfo("_ssh._tcp.local.",
                           ZEROCONF_NAME + "._ssh._tcp.local.",
                           ip, 8022, 0, 0,
                           params, host_name + ".local.")

    zero_config.register_service(ssh_info)

    def stop_zeroconf(event):
        """Stop Zeroconf."""
        zero_config.unregister_service(http_info)
        zero_config.unregister_service(mqtt_info)
        zero_config.unregister_service(ftp_info)
        zero_config.unregister_service(ssh_info)
        zero_config.close()

    hass.bus.listen_once(EVENT_HOMEASSISTANT_STOP, stop_zeroconf)

    return True
