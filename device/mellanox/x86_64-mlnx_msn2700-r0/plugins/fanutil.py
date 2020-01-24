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
    from sonic_fan.fan_base import FanBase
except ImportError as e:
    raise ImportError (str(e) + "- required module not found")

def log_err(msg):
    syslog.openlog("fanutil")
    syslog.syslog(syslog.LOG_ERR, msg)
    syslog.closelog()

class FanUtil(FanBase):
    """Platform-specific FanUtil class"""

    PWM_MAX = 255
    MAX_FAN_PER_DRAWER = 2
    GET_HWSKU_CMD = "sonic-cfggen -d -v DEVICE_METADATA.localhost.hwsku"
    sku_with_unpluggable_fan = ['ACS-MSN2010', 'ACS-MSN2100']
    FAN_BASE_DIR_PATTERN = "/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-2/2-0048/hwmon/hwmon*"
    FAN_HOTPLUG_STATUS_BASE_DIR_PATTERN = "/sys/devices/platform/mlxplat/mlxreg-hotplug/hwmon/hwmon*"

    def __init__(self):
        FanBase.__init__(self)

        self.sku_name = self._get_sku_name()

        if self.sku_name in self.sku_with_unpluggable_fan:
            self.fan_status = None
            self.unpluggable_fan = True
        else:
            fan_hotplug_status_base_list = glob(self.FAN_HOTPLUG_STATUS_BASE_DIR_PATTERN)
            if len(fan_hotplug_status_base_list) != 1:
                raise RuntimeError("Can't find hotplug hwmon path for fan info from {}".format(self.FAN_HOTPLUG_STATUS_BASE_DIR_PATTERN))
            self.fan_status = os.path.join(fan_hotplug_status_base_list[0], "fan{}")
            self.unpluggable_fan = False
        fan_base_dir_list = glob(self.FAN_BASE_DIR_PATTERN)
        if len(fan_base_dir_list) != 1:
            raise RuntimeError("Can't find hwmon path for fan info from {}".format(self.FAN_BASE_DIR_PATTERN))

        self.fan_get_speed = os.path.join(fan_base_dir_list[0], "fan{}_input")
        self.fan_set_speed = os.path.join(fan_base_dir_list[0], "pwm1")

        self.num_of_fan, self.num_of_drawer = self._extract_num_of_fans_and_fan_drawers()

    def _get_sku_name(self):
        p = subprocess.Popen(self.GET_HWSKU_CMD, shell=True, stdout=subprocess.PIPE)
        out, err = p.communicate()
        return out.rstrip('\n')

    def _extract_num_of_fans_and_fan_drawers(self):
        # So far we don't have files representing the number of fans and drawers
        # The only way to retrieve the number is to count files.
        # for number of fans, we get it via couting the speed files.
        # for number of draws, we get it via couting the status files.
        list_of_fan_speed = glob(self.fan_get_speed.format("*"))
        num_of_fan = len(list_of_fan_speed)
        list_of_fan_status = glob(self.fan_status)
        num_of_drawer = len(list_of_fan_status)

        return num_of_fan, num_of_drawer

    def _convert_fan_index_to_drawer_index(self, index):
        return (index + self.MAX_FAN_PER_DRAWER - 1) / self.MAX_FAN_PER_DRAWER

    def _read_file(self, file_pattern, index = None):
        """
        Reads the file of the fan

        :param file_pattern: The filename convention
        :param index: An integer, 1-based index of the fan of which to query status
        :return: int
        """
        return_value = 0
        try:
            with open(os.path.join(file_pattern.format(index)), 'r') as file_to_read:
                return_value = int(file_to_read.read())
        except IOError:
            log_err("Read file {} failed".format(file_pattern.format(index)))
            return return_value

        return return_value

    def get_num_fans(self):
        """
        Retrieves the number of FANs supported on the device

        :return: An integer, the number of FANs supported on the device
        """
        return self.num_of_fan

    def get_status(self, index):
        """
        Retrieves the operational status of FAN defined
                by index 1-based <index>

        :param index: An integer, 1-based index of the PSU of which to query status
        :return: Boolean,
            - True if FAN is running with some speed 
            - False if FAN has stopped running
        """
        if not self.get_presence(index):
            return False

        return self.get_speed(index) != 0

    def get_presence(self, index):
        """
        Retrieves the presence status of a FAN defined
                by 1-based index <index>

        :param index: An integer, 1-based index of the FAN of which to query status
        :return: Boolean, True if FAN is plugged, False if not
        """
        if index > self.num_of_fan:
            raise RuntimeError("index ({}) shouldn't be greater than number of fans ({})".format(index, self.num_of_fan))

        if self.unpluggable_fan:
            return True

        draw_index = self._convert_fan_index_to_drawer_index(index)
        presence = self._read_file(self.fan_status, draw_index)

        return presence != 0

    def get_speed(self, index):
        """
        Retrieves the speed of a Front FAN in the tray in revolutions per minute defined
                by 1-based index <index>

        :param index: An integer, 1-based index of the FAN of which to query speed
        :return: integer, denoting front FAN speed
        """
        speed = self._read_file(self.fan_get_speed, self.num_of_fan - index + 1)

        return speed

    def set_speed(self, val):
        """
        Sets the speed of all the FANs to a value denoted by the duty-cycle percentage val

        :param val: An integer, <0-100> denoting FAN duty cycle percentage 
        :return: Boolean, True if operation is successful, False if not
        """
        status = True
        pwm = int(round(self.PWM_MAX*val/100.0))

        try:
            with open(os.path.join(self.fan_set_speed), 'w') as fan_pwm:
                fan_pwm.write(str(pwm))
        except (ValueError, IOError):
            log_err("Read file {} failed".format(self.fan_set_speed))
            status = False

        return status
