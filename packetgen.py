import fcntl
import os
import Queue as lq
import time
import struct
import socket

from oslo_log import log as logging
from ryu.lib import packet

LOG = logging.getLogger(__name__)


def _check_for_new_config(config_queue):
    try:
        return config_queue.get(False)
    except lq.Empty:
        pass


class InterfaceHandler(object):
    def __init__(self):
        self.interface_handles = {}
        # TODO(kevinbenton): retry mechanism
        self.failed_devices = set()

    def get_interface_handles_to_drain(self, config):
        new_ints = (set(config.interface_configs_by_interface) -
                    (set(self.interface_handles) | self.failed_devices))
        removed_ints = (set(self.interface_handles) -
                        set(config.interface_configs_by_interface))
        if removed_ints:
            LOG.debug("Cleaning up unnecessary handles %s", removed_ints)
            for intf in removed_ints:
                self.interface_handles[intf].close()
                self.interface_handles.pop(intf)
                self.failed_devices.pop(intf, None)
        if new_ints:
            LOG.debug("Creating newly required handles %s", new_ints)
            for intf in new_ints:
                if intf in self.failed_devices:
                    continue
                handle = self._open_handle(intf)
                if not handle:
                    self.failed_devices.add(intf)
                    continue
                self.interface_handles[intf] = handle
        return self.interface_handles.items()

    def _open_handle(self, intf):
        LOG.debug("Creating to handle to interface %s", intf)
        #create a raw socket
        try:
            return prep_tap(intf)
            s = socket.socket(socket.AF_PACKET, socket.SOCK_RAW)
            s.bind((intf, 0))
            s.setblocking(0)
            return s
        except Exception:
            LOG.exception("Could not open socket to %s", intf)


def run_from_queue(config_queue):
    config = None
    int_handler = InterfaceHandler()
    while config is None:
        config = _check_for_new_config(config_queue)
    while True:
        interface_handles = int_handler.get_interface_handles_to_drain(config)
        LOG.debug("Got some handles: %s", interface_handles)
        while True:
            new_config = _check_for_new_config(config_queue)
            if new_config:
                config = new_config
                break
            did_something = False
            for int_name, handle in interface_handles:
                int_config = config.interface_configs_by_interface[int_name]
                did_something |= handle_a_packet(int_config, handle)
            if not did_something:
                time.sleep(0.05)


def handle_a_packet(int_config, handle):
    try:
        #packet = handle.recv(4096)[0]
        payload = os.read(handle, 4096)
        pkt = packet.packet.Packet(data=payload)
        pkt_ethernet = pkt.get_protocol(packet.ethernet.ethernet)
        if not pkt_ethernet:
            return
        icmp_resp = _get_icmp_response(pkt, pkt_ethernet, int_config)
        if icmp_resp:
            os.write(handle, icmp_resp)
            return True
        return True
    except (socket.error, OSError):
        return False

def _get_icmp_response(pkt, pkt_eth, conf):
    src = conf.ip_add
    pkt_ipv4 = pkt.get_protocol(packet.ipv4.ipv4)
    pkt_icmp = pkt.get_protocol(packet.icmp.icmp)
    if not pkt_icmp or pkt_ipv4.dst != src:
        return
    pkt = packet.packet.Packet()
    pkt.add_protocol(packet.ethernet.ethernet(
        ethertype=pkt_eth.ethertype,
        dst=pkt_eth.src,
        src=randomMAC()))
    pkt.add_protocol(packet.ipv4.ipv4(
        dst=pkt_ipv4.src, src=src, proto=pkt_ipv4.proto))
    pkt.add_protocol(packet.icmp.icmp(
        type_=0, code=0, csum=0, data=pkt_icmp.data))
    pkt.serialize()
    return pkt.data

def start_listener(tap, tap_config):
    try:
        LOG.debug("Starting listener for tap %s", tap)
        tun = prep_tap(tap)
    except Exception:
        LOG.exception("Error prepping tap device")
    LOG.debug("Tap device %s ready", tap)


def randomMAC():
    import random
    mac = [0x00, 0x01, 0x02, random.randint(0x00, 0x7f),
           random.randint(0x00, 0xff), random.randint(0x00, 0xff) ]
    return ':'.join(("%02x" % x for x in mac))

def prep_tap(tap):
    TUNSETIFF = 0x400454ca
    IFF_TUN = 0x0001
    IFF_TAP = 0x0002
    NO_EXTRA_INFO = 0x1000
    TUNMODE = IFF_TAP
    TUNSETOWNER = TUNSETIFF + 2
    tun = os.open("/dev/net/tun", os.O_RDWR)
    ifs = fcntl.ioctl(tun, TUNSETIFF,
                      struct.pack("16sH", str(tap), TUNMODE | NO_EXTRA_INFO))
    flag = fcntl.fcntl(tun, fcntl.F_GETFL)
    fcntl.fcntl(tun, fcntl.F_SETFL, flag | os.O_NONBLOCK)
    ifname = ifs[:16].strip("\x00")  # will be tap0
    return tun
