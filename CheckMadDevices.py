#!/usr/bin/env python3
__author__ = "GhostTalker"
__copyright__ = "Copyright 2019, The GhostTalker project"
__version__ = "0.1.0"
__status__ = "Dev"

# generic/built-in and other libs
import configparser
import os
import requests
import sys
import time
import subprocess
import logging
import logging.handlers
import argparse


class MonitoringItem(object):
    mitm_receiver_ip = None
    mitm_receiver_port = None
    mitm_receiver_status_endpoint = None
    device_list = None
    devices = {}
    device_values = None
    injection_status = None
    latest_data = None
    response = None

    def __init__(self):
        self._set_data()

    def _set_data(self):
        config = self._read_config()
        for section in config.sections():
            for option in config.options(section):
                if section == 'Devices':
                    self.devices[option] = config.get(section, option)
                else:
                    self.__setattr__(option, config.get(section, option))
        self.create_device_origin_list()

    def create_device_origin_list(self):
        device_list = []
        for device_name, device_value in self.devices.items():
            active_device = device_value.split(';', 1)
            dev_origin = active_device[0]
            device_list.append((dev_origin))
        return device_list

    def _check_config(self):
        conf_file = os.path.join(os.path.dirname(__file__), "configs", "config.ini")
        if not os.path.isfile(conf_file):
            raise FileExistsError('"{}" does not exist'.format(conf_file))
        self.conf_file = conf_file

    def _read_config(self):
        try:
            self._check_config()
        except FileExistsError as e:
            raise e
        config = configparser.ConfigParser()
        config.read(self.conf_file)
        return config

    def check_mitm_status_page(self, check_url):
        """  Check Response Code and Output from MITM status page """
        response = requests.get(check_url)
        if response.status_code == 200:
            return response
        else:
            time.sleep(10)
            self.check_mitm_status_page(check_url)

    def read_device_status_values(self, device_origin):
        """ Read Values for a device from MITM status page """
        check_url = "http://{}:{}/{}/".format(self.mitm_receiver_ip, self.mitm_receiver_port,
                                              self.mitm_receiver_status_endpoint)
        self.check_mitm_status_page(check_url)
        # Read Values
        global injection_status
        global latest_data
        json_respond = self.check_mitm_status_page(check_url).json()
        devices = (json_respond["origin_status"])
        device_values = (devices[device_origin])
        injection_status = (device_values["injection_status"])
        latest_data = (device_values["latest_data"])
        return injection_status, latest_data

    def check_time_since_last_data(self, device_origin):
        """ calculate time between now and latest_data """
        actual_time = time.time()
        if self.read_device_status_values(device_origin)[1] == None:
            return 99999
        sec_since_last_data = actual_time - self.read_device_status_values(device_origin)[1]
        min_since_last_data = sec_since_last_data / 60
        min_since_last_data = int(min_since_last_data)
        latest_data_hr = time.strftime('%Y-%m-%d %H:%M:%S',
                                       time.localtime(self.read_device_status_values(device_origin)[0]))
        return min_since_last_data


# Make a class we can use to capture stdout and sterr in the log
class MyLogger(object):
    def __init__(self, logger, level):
        """Needs a logger and a logger level."""
        self.logger = logger
        self.level = level

    def write(self, message):
        # Only log if there is a message (not just a new line)
        if message.rstrip() != "":
            self.logger.log(self.level, message.rstrip())

    def flush(self):
        pass


if __name__ == '__main__':
    mon_item = MonitoringItem()

    # Logging params
    LOG_LEVEL = logging.getLevelName(mon_item.log_level)
    logger = logging.getLogger(__name__)
    logger.setLevel(LOG_LEVEL)
    handler = logging.handlers.TimedRotatingFileHandler(mon_item.log_filename, when="midnight", backupCount=3)
    formatter = logging.Formatter('%(asctime)s %(levelname)-8s %(message)s')
    handler.setFormatter(formatter)
    logger.addHandler(handler)

    sys.stdout = MyLogger(logger, logging.INFO)
    sys.stderr = MyLogger(logger, logging.ERROR)

    print("MAD - Check and Reboot - Daemon started")
    # check and reboot device if nessessary
    while 1:
        device_origin_list = mon_item.create_device_origin_list()
        for device_origin in device_origin_list:
            print("Device = {}	Minutes_since_last_Connect = {}	Inject = {}".format(device_origin,
                                                                                         mon_item.check_time_since_last_data(
                                                                                             device_origin),
                                                                                         mon_item.read_device_status_values(
                                                                                             device_origin)[0]))
            if mon_item.read_device_status_values(device_origin)[0] == False and mon_item.check_time_since_last_data(
                    device_origin) > 10:
                subprocess.Popen(["/root/adb_scripts/RebootMadDevice.py", device_origin])
                time.sleep(180)
        time.sleep(600)
