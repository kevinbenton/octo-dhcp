from multiprocessing import Process, Queue
import sys
import time

from oslo_config import cfg
from oslo_log import log as logging
from oslo_serialization import jsonutils

import configurator
import packetgen

LOG = logging.getLogger(__name__)


def setup_logging():
    name = 'octo-dhcp'
    logging.register_options(cfg.CONF)
    cfg.CONF.set_override('debug', True)
    logging.setup(cfg.CONF, name)
    LOG.info("Logging intialized!")


def main():
    setup_logging()
    config_states = Queue()
    fpath = sys.argv[1]
    cproc = Process(target=configurator.config_watcher,
                    args=(fpath, config_states))
    pproc = Process(target=packetgen.run_from_queue,
                    args=(config_states,))
    cproc.start()
    pproc.start()

if __name__ == '__main__':
    main()
