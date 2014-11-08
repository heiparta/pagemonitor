from datetime import datetime
import gevent
import simplejson as json
import logging
from logging.handlers import RotatingFileHandler, SMTPHandler
import os
import requests
import signal

PAGEMONITOR_CONFIG_PATH = 'pagemonitor.json'
CONFIG_KEYS = ["email_username",
               "email_password",
               "email_host",
               "email_from",
               "email_to",
               "email_subject",
               "pages",
               "check_interval",
               "fail_threshold",
               ]

log = logging.getLogger("pagemonitor")
log.setLevel(logging.INFO)


class PageGreenlet(gevent.Greenlet):
    def __init__(self, url, config):
        super(PageGreenlet, self).__init__(self)
        if not url.startswith('http'):
            url = 'http://' + url
        self.url = url
        self.fail_start = None
        self.fail_count = 0

        self.config = config
        self.poll_interval = config['check_interval']
        self.fail_threshold = config['fail_threshold']

    def run(self):
        log.info("Starting to monitor page '%s'", self.url)
        while True:
            response = requests.get(self.url)
            if response.ok:
                if self.fail_start is not None:
                    # url is back online, log error to get email notification
                    log.error("Page %s is back online after %s downtime",
                        self.url, datetime.utcnow() - self.fail_start)
                    self.fail_start = None
                    self.fail_count = 0
            else:
                self.fail_count += 1
                if self.fail_start is None:
                    # url has gone down
                    self.fail_start = datetime.utcnow()
                    log.info("Page %s started failing at %s", self.url, self.fail_start)
                if self.fail_count == self.fail_threshold:
                    log.error("Page %s has been failing since %s", self.url, self.fail_start)
            gevent.sleep(self.config['check_interval'])

def load_config(config_path):
    config = dict()
    with open(config_path, "r") as fp:
        raw_config = json.load(fp)

    for key in CONFIG_KEYS:
        if key not in raw_config:
            raise Exception("Required parameter {0} not found in config file {1}".format(key, config_path))
        value = raw_config[key]
        if key == "pages":
            if isinstance(value, basestring):
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

def main():
    config = load_config(os.environ.get('PAGEMONITOR_CONFIG_PATH', PAGEMONITOR_CONFIG_PATH))
    setup_logging(config)
    greenlets = [PageGreenlet(url, config) for url in config['pages']]
    [g.start() for g in greenlets]
    gevent.joinall(greenlets)

if __name__ == '__main__':
    gevent.signal(signal.SIGQUIT, gevent.kill)
    main()
