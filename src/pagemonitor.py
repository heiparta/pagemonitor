import asyncio
from datetime import datetime
import logging
from logging.handlers import RotatingFileHandler, SMTPHandler
import os
import aiohttp
import signal
import simplejson as json
import sys

PAGEMONITOR_CONFIG_PATH = '/etc/pagemonitor/pagemonitor.json'
CONFIG_KEYS = ["email_username",
               "email_password",
               "email_host",
               "email_from",
               "email_to",
               "email_subject",
               "pages",
               "check_interval",
               "fail_threshold",
               "logfile",
               ]

log = logging.getLogger("pagemonitor")
log.setLevel(logging.DEBUG)

def sigterm_handler(signal, stack_frame):
    # Just quit, don't worry about the state of the asyncio tasks
    sys.exit(0)
signal.signal(signal.SIGTERM, sigterm_handler)

class PageAsyncTask:
    def __init__(self, url, config):
        self.url = url
        self.fail_start = None
        self.fail_count = 0

        self.config = config
        self.poll_interval = config['check_interval']
        self.fail_threshold = config['fail_threshold']

    async def fetch_page(self):
        async with aiohttp.ClientSession() as session:
            async with session.get(self.url) as response:
                log.debug("%s - %s", self.url, response.status)
                return response

    async def monitor_page(self):
        while True:
            response = await self.fetch_page()
            if response.status == 200:
                if self.fail_start is not None:
                    # URL is back online, log error to get email notification
                    log.error("Page %s is back online after %s downtime",
                              self.url, datetime.utcnow() - self.fail_start)
                    self.fail_start = None
                    self.fail_count = 0
            else:
                self.fail_count += 1
                if self.fail_start is None:
                    # URL has gone down
                    self.fail_start = datetime.utcnow()
                    log.info("Page %s started failing at %s", self.url, self.fail_start)
                if self.fail_count == self.fail_threshold:
                    log.error("Page %s has been failing since %s", self.url, self.fail_start)
            await asyncio.sleep(self.config['check_interval'])

def load_config(config_path):
    config = dict()
    with open(config_path, "r") as fp:
        raw_config = json.load(fp)

    for key in CONFIG_KEYS:
        if key not in raw_config:
            raise Exception("Required parameter {0} not found in config file {1}".format(key, config_path))
        value = raw_config[key]
        if key == "pages":
            if isinstance(value, str):
                value = [value]
            if not isinstance(value, list):
                raise Exception("Invalid value for parameter {0} in config file {1}".format(key, config_path))
        config[key] = value
    return config

def setup_logging(config):
    logfile = config.get("logfile")
    if logfile:
        handler = RotatingFileHandler(filename=logfile, maxBytes=10 * 1024 ** 3)
        handler.setFormatter(logging.Formatter(
            '%(asctime)s %(levelname)s: %(message)s '
            '[in %(pathname)s:%(lineno)d]'))
        log.addHandler(handler)

    email_handler = SMTPHandler(mailhost=config["email_host"],
                                fromaddr=config["email_from"],
                                toaddrs=config["email_to"],
                                subject=config["email_subject"],
                                credentials=(config["email_username"], config["email_password"]),
                                secure=())
    email_handler.setFormatter(logging.Formatter(
        '%(asctime)s %(levelname)s: %(message)s '
        '[in %(pathname)s:%(lineno)d]'))
    email_handler.setLevel(logging.ERROR)
    log.addHandler(email_handler)

async def main():
    config = load_config(os.environ.get('PAGEMONITOR_CONFIG_PATH', PAGEMONITOR_CONFIG_PATH))
    setup_logging(config)
    tasks = [PageAsyncTask(url, config).monitor_page() for url in config['pages']]
    await asyncio.gather(*tasks)

if __name__ == '__main__':
    loop = asyncio.get_event_loop()
    loop.add_signal_handler(signal.SIGQUIT, loop.stop)
    loop.run_until_complete(main())