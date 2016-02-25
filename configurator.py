import time

from oslo_log import log as logging
from oslo_serialization import jsonutils


LOG = logging.getLogger(__name__)


def config_watcher(fpath, queue):
    config = ConfigStore()
    handle = open(fpath, 'r')
    while True:
        line = handle.readline()
        if not line:
            time.sleep(0.25)
            continue
        try:
            data = jsonutils.loads(line)
            LOG.debug("Got new DHCP entry: %s", data)
            config.add_entry(data)
            queue.put(config)
        except Exception as e:
            LOG.exception("Exception loading config line: %s", line)


class ConfigStore(object):
    def __init__(self):
        self.interface_configs_by_interface = {}

    def add_entry(self, entry):
       for req in ['port', 'dhcp_server_ip', 'client_info']:
           if req in entry:
               continue
           LOG.error("Invalid entry, missing '%(k)s': %(l)s",
                     {'k': req, 'l': entry})
       tap = entry['port']
       if tap not in self.interface_configs_by_interface:
           intconfig = InterfaceConfig(tap, entry['dhcp_server_ip'])
           self.interface_configs_by_interface[tap] = intconfig
       else:
           intconfig = self.interface_configs_by_interface[tap]
           intconfig.update_ip(entry['dhcp_server_ip'])
       intconfig = self.interface_configs_by_interface[tap]
       intconfig.setup_client_entry(entry['client_info'])


class InterfaceConfig(object):
    def __init__(self, interface, ip_addr):
        self.interface = interface
        self.ip_add = ip_addr
        self.host_configs_by_hwaddr = {}

    def get_host(self, hwaddr):
        return self.host_configs_by_hwaddr(hwaddr)

    def setup_client_entry(self, info):
        hwaddr = info['hwaddr']
        ip4 = info['ip4']
        self.host_configs_by_hwaddr[hwaddr] = HostConfig(hwaddr, ip4)

    def update_ip(self, ip):
        if ip == self.ip_add:
            return
        self.ip_add = ip
        LOG.debug("Interface %(intf)s IP updated to %(ip)s",
                  {'intf': self.interface, 'ip': ip})


class HostConfig(object):
    def __init__(self, hwaddr, ip4):
        self.hwaddr = hwaddr
        self.ip4_info = ip4
        LOG.debug("Host entry for %s: %s" % (hwaddr, ip4))
