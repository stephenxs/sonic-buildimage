#!/usr/bin/env python

#############################################################################
# Mellanox
#
# Module contains an implementation of SONiC PSU Base API and
# provides the PSUs status which are available in the platform
#
#############################################################################

try:
    import os.path
    import syslog
    import subprocess
    from glob import glob
    from sonic_psu.psu_base import PsuBase
except ImportError as e:
    raise ImportError (str(e) + "- required module not found")

def log_err(msg):
    syslog.openlog("psuutil")
    syslog.syslog(syslog.LOG_ERR, msg)
    syslog.closelog()


class PsuUtil(PsuBase):
    """Platform-specific PSUutil class"""

    MAX_PSU_FAN = 1
    MAX_NUM_PSU = 2
    GET_HWSKU_CMD = "sonic-cfggen -d -v DEVICE_METADATA.localhost.hwsku"
    # for spectrum1 switches with plugable PSUs, the output voltage file is psuX_volt
    # for spectrum2 switches the output voltage file is psuX_volt_out2
    psu_sku_lookup = {'ACS-MSN2410' : 0, 'ACS-MSN2700' : 0, 'Mellanox-SN2700' : 0, 'Mellanox-SN2700-D48C8' : 0, 'LS-SN2700' : 0, 'ACS-MSN2740' : 1}
    psu_dir_pattern_list = [
        [
            # for 2410, 2700
            "/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-10/10-0059/hwmon/hwmon*",
            "/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-10/10-0058/hwmon/hwmon*"
        ],
        [
            # for 2740
            "/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-4/4-0059/hwmon/hwmon*",
            "/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-4/4-0058/hwmon/hwmon*"
        ]
    ]
    PSU_STATUS_DIR_PATTERN = "/sys/devices/platform/mlxplat/mlxreg-hotplug/hwmon/hwmon*/"

    def _init_one_psu(self, index):
        psu_dir_temp_list = glob(self.psu_dir_pattern[index])
        if not len(psu_dir_temp_list) == 1:
            log_err("Can't find hwmon path for psu power related values")
            self.psu_current.append("")
            self.psu_power.append("")
            self.psu_voltage.append("")
            self.fan_speed.append("")
        else:
            psu_dir_path = psu_dir_temp_list[0]
            self.psu_current.append(os.path.join(psu_dir_path, "curr2_input"))
            self.psu_power.append(os.path.join(psu_dir_path, "power2_input"))
            self.psu_voltage.append(os.path.join(psu_dir_path, "in2_input"))
            self.fan_speed.append(os.path.join(psu_dir_path, "fan1_input"))

    def __init__(self):
        PsuBase.__init__(self)

        self.sku_name = self._get_sku_name()

        self.psu_path = ""
        hwmon_path_list = glob(self.PSU_STATUS_DIR_PATTERN)
        if not len(hwmon_path_list) == 1:
            raise RuntimeError("Can't find hwmon path for psu presence status from {}".format(self.PSU_STATUS_DIR_PATTERN))
        psu_status_path = hwmon_path_list[0]
        self.psu_presence = os.path.join(psu_status_path, "psu{}")
        self.psu_oper_status = os.path.join(psu_status_path, "pwr{}")

        self.psu_dir = []
        self.psu_current = []
        self.psu_power = []
        self.psu_voltage = []
        self.fan_speed = []
        self.psu_dir_pattern = self.psu_dir_pattern_list[self.psu_sku_lookup[self.sku_name]]
        for i in range(self.MAX_NUM_PSU):
            self._init_one_psu(i)

    def _get_sku_name(self):
        p = subprocess.Popen(self.GET_HWSKU_CMD, shell=True, stdout=subprocess.PIPE)
        out, err = p.communicate()
        return out.rstrip('\n')

    def get_num_psus(self):
        """
        Retrieves the number of PSUs available on the device

        :return: An integer, the number of PSUs available on the device
        """
        return self.MAX_NUM_PSU

    def _read_file(self, file_pattern, index):
        """
        Reads the file of the PSU

        :param file_pattern: The filename convention
        :param index: An integer, 1-based index of the PSU of which to query status
        :return: int
        """
        return_value = 0
        try:
            with open(file_pattern.format(index), 'r') as file_to_read:
                return_value = int(file_to_read.read())
        except IOError:
            log_err("Read file {} failed".format(self.psu_path + file_pattern.format(index)))
            self._init_one_psu(index)
            return 0

        return return_value

    def get_psu_status(self, index):
        """
        Retrieves the oprational status of power supply unit (PSU) defined
                by 1-based index <index>

        :param index: An integer, 1-based index of the PSU of which to query status
        :return: Boolean, True if PSU is operating properly, False if PSU is faulty
        """
        if index is None:
            return False
        if index > self.MAX_NUM_PSU:
            raise RuntimeError("index ({}) shouldn't be greater than {}".format(index, self.MAX_NUM_PSU))

        status = self._read_file(self.psu_oper_status, index)

        return status == 1

    def get_psu_presence(self, index):
        """
        Retrieves the presence status of power supply unit (PSU) defined
                by 1-based index <index>

        :param index: An integer, 1-based index of the PSU of which to query status
        :return: Boolean, True if PSU is plugged, False if not
        """
        if index is None:
            raise RuntimeError("index shouldn't be None")
        if index > self.MAX_NUM_PSU:
            raise RuntimeError("index ({}) shouldn't be greater than {}".format(index, self.MAX_NUM_PSU))

        status = self._read_file(self.psu_presence, index)

        return status == 1

    def get_output_voltage(self, index):
        """
        Retrieves the ouput volatage in milli volts of a power supply unit (PSU) defined
                by 1-based index <index>
        :param index: An integer, 1-based index of the PSU of which to query o/p volatge
        :return: An integer, value of o/p voltage in mV if PSU is good, else zero
        """
        if index is None:
            raise RuntimeError("index shouldn't be None")

        if not self.get_psu_presence(index) or not self.get_psu_status(index):
            return 0

        voltage = self._read_file(self.psu_voltage[index - 1], index)

        return voltage

    def get_output_current(self, index):
        """
        Retrieves the output current in milli amperes of a power supply unit (PSU) defined
                by 1-based index <index>
        :param index: An integer, 1-based index of the PSU of which to query o/p current
        :return: An integer, value of o/p current in mA if PSU is good, else zero
        """
        if index is None:
            raise RuntimeError("index shouldn't be None")

        if not self.get_psu_presence(index) or not self.get_psu_status(index):
            return 0

        current = self._read_file(self.psu_current[index - 1], index)

        return current

    def get_output_power(self, index):
        """
        Retrieves the output power in micro watts of a power supply unit (PSU) defined
                by 1-based index <index>
        :param index: An integer, 1-based index of the PSU of which to query o/p power
        :return: An integer, value of o/p power in micro Watts if PSU is good, else zero
        """
        if index is None:
            raise RuntimeError("index shouldn't be None")

        if not self.get_psu_presence(index) or not self.get_psu_status(index):
            return 0

        power = self._read_file(self.psu_power[index - 1], index) / 1000.0

        return power

    def get_fan_speed(self, index, fan_index):
        """
        Retrieves the speed of fan, in rpm, denoted by 1-based <fan_index> of a power 
                supply unit (PSU) defined by 1-based index <index>
        :param index: An integer, 1-based index of the PSU of which to query fan speed
        :param fan_index: An integer, 1-based index of the PSU-fan of which to query speed
        :return: An integer, value of PSU-fan speed in rpm if PSU-fan is good, else zero
        """
        if index is None:
            raise RuntimeError("index shouldn't be None")
        if fan_index > self.MAX_PSU_FAN:
            raise RuntimeError("fan_index ({}) shouldn't be greater than {}".format(fan_index, self.MAX_PSU_FAN))
        if not self.get_psu_presence(index) or not self.get_psu_status(index):
            return 0

        fan_speed = self._read_file(self.fan_speed[index - 1], index)

        return fan_speed
