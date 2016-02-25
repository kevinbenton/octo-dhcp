import eventlet
eventlet.monkey_patch()
import Queue
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
    config_update_queue = Queue.Queue()
    fpath = sys.argv[1]
    pool = eventlet.GreenPool()
    pool.spawn_n(configurator.config_watcher, fpath, config_update_queue)
    config = configurator.ConfigStore()
    pool.spawn_n(config.dict_parser, config_update_queue)
    pool.spawn_n(packetgen.run_from_config, config)
    pool.waitall()


if __name__ == '__main__':
    main()
