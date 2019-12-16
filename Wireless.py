from abc import ABCMeta, abstractmethod
import subprocess
from time import sleep
from packaging import version
import re

"""
Module copied from https://github.com/joshvillbrandt/wireless, with disconnect() function and dynamic ip allocation in connect() added for only wpa-supplicant driver.
"""

# send a command to the shell and return the result
def cmd(cmd):
    return subprocess.Popen(
        cmd, shell=True,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT
    ).stdout.read().decode()


# abstracts away wireless connection
class Wireless:
    _driver_name = None
    _driver = None

    # init
    def __init__(self, interface=None):
        # detect and init appropriate driver
        self._driver_name = self._detectDriver()
        if self._driver_name == 'nmcli':
            self._driver = NmcliWireless(interface=interface)
        elif self._driver_name == 'nmcli0990':
            self._driver = Nmcli0990Wireless(interface=interface)
        elif self._driver_name == 'wpa_supplicant':
            self._driver = WpasupplicantWireless(interface=interface)
        elif self._driver_name == 'networksetup':
            self._driver = NetworksetupWireless(interface=interface)

        # attempt to auto detect the interface if none was provided
        if self.interface() is None:
            interfaces = self.interfaces()
            if len(interfaces) > 0:
                self.interface(interfaces[0])

        # raise an error if there is still no interface defined
        if self.interface() is None:
            raise Exception('Unable to auto-detect the network interface.')

    def _detectDriver(self):
        # try nmcli (Ubuntu 14.04)
        response = cmd('which nmcli')
        if len(response) > 0 and 'not found' not in response:
            response = cmd('nmcli --version')
            parts = response.split()
            ver = parts[-1]
            if version.parse(ver) > version.parse('0.9.9.0'):
                return 'nmcli0990'
            else:
                return 'nmcli'

        # try nmcli (Ubuntu w/o network-manager)
        response = cmd('which wpa_supplicant')
        if len(response) > 0 and 'not found' not in response:
            return 'wpa_supplicant'

        # try networksetup (Mac OS 10.10)
        response = cmd('which networksetup')
        if len(response) > 0 and 'not found' not in response:
            return 'networksetup'

        raise Exception('Unable to find compatible wireless driver.')

    # connect to a network
    def connect(self, ssid, password):
        return self._driver.connect(ssid, password)

    # disconnect from wifis
    def disconnect(self):
        return self._driver.disconnect()

    # return the ssid of the current network
    def current(self):
        return self._driver.current()

    # return a list of wireless adapters
    def interfaces(self):
        return self._driver.interfaces()

    # return the current wireless adapter
    def interface(self, interface=None):
        return self._driver.interface(interface)

    # return the current wireless adapter
    def power(self, power=None):
        return self._driver.power(power)

    # return the driver name
    def driver(self):
        return self._driver_name


# abstract class for all wireless drivers
class WirelessDriver:
    __metaclass__ = ABCMeta

    @abstractmethod
    def connect(self, ssid, password):
        pass

    @abstractmethod
    def disconnect(self):
        pass

    @abstractmethod
    def current(self):
        pass

    @abstractmethod
    def interfaces(self):
        pass

    @abstractmethod
    def interface(self, interface=None):
        pass

    @abstractmethod
    def power(self, power=None):
        pass




# Linux wpa_supplicant Driver
class WpasupplicantWireless(WirelessDriver):
    _file = '/tmp/wpa_supplicant.conf'
    _interface = None

    # init
    def __init__(self, interface=None):
        self.interface(interface)

    # Simply disconnect from all wifis
    def disconnect(self):
        cmd('sudo killall wpa_supplicant')
        return True

    # connect to a network
    def connect(self, ssid, password):
        # attempt to stop any active wpa_supplicant instances
        # ideally we do this just for the interface we care about
        cmd('sudo killall wpa_supplicant')

        # Just changed to dynamic
        cmd('sudo ifconfig {} dynamic up'.format(self._interface))

        # create configuration file
        f = open(self._file, 'w')
        f.write('network={{\n    ssid="{}"\n    psk="{}"\n}}\n'.format(
            ssid, password))
        f.close()

        # attempt to connect
        cmd('sudo wpa_supplicant -i{} -c{} -B'.format(
            self._interface, self._file))

        # check that the connection was successful
        # i've never seen it take more than 3 seconds for the link to establish
        sleep(5)
        if self.current() != ssid:
            return False

        # attempt to grab an IP
        # better hope we are connected because the timeout here is really long
        # cmd('sudo dhclient {}'.format(self._interface))

        # parse response
        return True

    # returned the ssid of the current network
    def current(self):
        # get interface status
        response = cmd('iwconfig {}'.format(
            self.interface()))

        # the current network is on the first line.
        # ex: wlan0     IEEE 802.11AC  ESSID:"SSID"  Nickname:"<WIFI@REALTEK>"
        line = response.splitlines()[0]
        match = re.search('ESSID:\"(.+?)\"', line)
        if match is not None:
            network = match.group(1)
            if network != 'off/any':
                return network

        # return none if there was not an active connection
        return None

    # return a list of wireless adapters
    def interfaces(self):
        # grab list of interfaces
        response = cmd('iwconfig')

        # parse response
        interfaces = []
        for line in response.splitlines():
            if len(line) > 0 and not line.startswith(' '):
                # this line contains an interface name!
                if 'no wireless extensions' not in line:
                    # this is a wireless interface
                    interfaces.append(line.split()[0])

        # return list
        return interfaces

    # return the current wireless adapter
    def interface(self, interface=None):
        if interface is not None:
            self._interface = interface
        else:
            return self._interface

    # enable/disable wireless networking
    def power(self, power=None):
        # not supported yet
        return None
