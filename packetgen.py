import eventlet
import fcntl
import time
import struct

from oslo_log import log as logging
import scapy

LOG = logging.getLogger(__name__)



def run_from_config(config):
    known_taps = set()
    listenerpool = eventlet.GreenPool()
    while True:
        for intf in config.interface_configs_by_interface:
            if intf in known_taps:
                continue
            listenerpool.spawn_n(start_listener, intf,
                config.interface_configs_by_interface[intf])
            known_taps.add(intf)
        time.sleep(0.25)


def start_listener(tap, tap_config):
    try:
        LOG.debug("Starting listener for tap %s", tap)
        tun = prep_tap(tap)
    except Exception:
        LOG.exception("Error prepping tap device")
    LOG.debug("Tap device %s ready", tap)
    while True:
        binary = eventlet.green.os.read(tun, 2048)
        import pdb; pdb.set_trace()
        packet = scapy.Ether(binary)



def prep_tap(tap):
    TUNSETIFF = 0x400454ca
    IFF_TUN = 0x0001
    IFF_TAP = 0x0002
    IFF_NO_PI = 0x1000
    TUNMODE = IFF_TAP
    TUNSETOWNER = TUNSETIFF + 2
    tun = eventlet.green.os.open("/dev/net/tun", eventlet.green.os.O_RDWR)
    ifs = fcntl.ioctl(tun, TUNSETIFF,
                      struct.pack("16sH", str(tap), TUNMODE | IFF_NO_PI))
    ifname = ifs[:16].strip("\x00")  # will be tap0
    return tun
