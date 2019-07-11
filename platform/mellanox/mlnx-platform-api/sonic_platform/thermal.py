#!/usr/bin/env python

#############################################################################
# Mellanox
#
# Module contains an implementation of SONiC Platform Base API and
# provides the thermals data which are available in the platform
#
#############################################################################

import os.path

try:
    from sonic_platform_base.thermal_base import ThermalBase
    from sonic_daemon_base.daemon_base import Logger
    from os import listdir
    from os.path import isfile, join
    import io
except ImportError as e:
    raise ImportError (str(e) + "- required module not found")

# Global logger class instance
SYSLOG_IDENTIFIER = "mlnx-thermal"
logger = Logger(SYSLOG_IDENTIFIER)

THERMAL_DEV_CATEGORY_CPU_CORE = "cpu_core"
THERMAL_DEV_CATEGORY_CPU_PACK = "cpu_pack"
THERMAL_DEV_CATEGORY_ASIC = "asic"
THERMAL_DEV_CATEGORY_MODULE = "module"
THERMAL_DEV_CATEGORY_PSU = "psu"

THERMAL_API_GET_TEMPERATURE = "get_temperature"
THERMAL_API_GET_HIGH_THRESHOLD = "get_high_threshold"

HW_MGMT_THERMAL_ROOT = "/var/run/hw-management/thermal/"

thermal_api_handler_cpu_core = {
    THERMAL_API_GET_TEMPERATURE:"cpu_core{}",
    THERMAL_API_GET_HIGH_THRESHOLD:"cpu_core{}_max"
}
thermal_api_handler_cpu_pack = {
    THERMAL_API_GET_TEMPERATURE:"cpu_pack",
    THERMAL_API_GET_HIGH_THRESHOLD:"cpu_pack_max"
}
thermal_api_handler_asic = {
    THERMAL_API_GET_TEMPERATURE:"asic",
    THERMAL_API_GET_HIGH_THRESHOLD:"mlxsw/temp_trip_high"
}
thermal_api_handler_module = {
    THERMAL_API_GET_TEMPERATURE:"temp_input_module{}",
    THERMAL_API_GET_HIGH_THRESHOLD:"temp_crit_module{}"
}
thermal_api_handler_psu = {
    THERMAL_API_GET_TEMPERATURE:"psu{}",
    THERMAL_API_GET_HIGH_THRESHOLD:"psu{}_max"
}
thermal_api_handlers = {
    THERMAL_DEV_CATEGORY_CPU_CORE : thermal_api_handler_cpu_core, 
    THERMAL_DEV_CATEGORY_CPU_PACK : thermal_api_handler_cpu_pack,
    THERMAL_DEV_CATEGORY_ASIC : thermal_api_handler_asic,
    THERMAL_DEV_CATEGORY_MODULE : thermal_api_handler_module,
    THERMAL_DEV_CATEGORY_PSU : thermal_api_handler_psu
}

thermal_device_categories_all = [
    THERMAL_DEV_CATEGORY_CPU_CORE,
    THERMAL_DEV_CATEGORY_CPU_PACK,
    THERMAL_DEV_CATEGORY_ASIC,
    THERMAL_DEV_CATEGORY_MODULE,
    THERMAL_DEV_CATEGORY_PSU
]

thermal_device_categories_siglton = [
    THERMAL_DEV_CATEGORY_CPU_PACK,
    THERMAL_DEV_CATEGORY_ASIC
]
thermal_api_names = [
    THERMAL_API_GET_TEMPERATURE,
    THERMAL_API_GET_HIGH_THRESHOLD
]

hwsku_dict_thermal = {'ACS-MSN2700': 0, "LS-SN2700":0, 'ACS-MSN2740': 3, 'ACS-MSN2100': 1, 'ACS-MSN2410': 2, 'ACS-MSN2010': 4, 'ACS-MSN3700': 5, 'ACS-MSN3700C': 0, 'Mellanox-SN2700': 0, 'Mellanox-SN2700-D48C8': 0}
thermal_profile_list = [
    #for 2700,3700c,
    {
        THERMAL_DEV_CATEGORY_ASIC:(0,1),
        THERMAL_DEV_CATEGORY_CPU_CORE:(0, 2),
        THERMAL_DEV_CATEGORY_MODULE:(1, 32),
        THERMAL_DEV_CATEGORY_PSU:(1, 2),
        THERMAL_DEV_CATEGORY_CPU_PACK:(0,1)
    },
    #for 2100
    {
        THERMAL_DEV_CATEGORY_ASIC:(0,1),
        THERMAL_DEV_CATEGORY_CPU_CORE:(0, 4),
        THERMAL_DEV_CATEGORY_MODULE:(1, 15),
        THERMAL_DEV_CATEGORY_PSU:(1, 2),
        THERMAL_DEV_CATEGORY_CPU_PACK:(0,1)
    },
    #for 2410
    {
        THERMAL_DEV_CATEGORY_ASIC:(0,1),
        THERMAL_DEV_CATEGORY_CPU_CORE:(0, 2),
        THERMAL_DEV_CATEGORY_MODULE:(1, 56),
        THERMAL_DEV_CATEGORY_PSU:(1, 2),
        THERMAL_DEV_CATEGORY_CPU_PACK:(0,1)
    },
    #for 2740
    {
        THERMAL_DEV_CATEGORY_ASIC:(0,1),
        THERMAL_DEV_CATEGORY_CPU_CORE:(0, 4),
        THERMAL_DEV_CATEGORY_MODULE:(1, 32),
        THERMAL_DEV_CATEGORY_PSU:(1, 2),
        THERMAL_DEV_CATEGORY_CPU_PACK:(0,0)
    },
    #for 2010
    {
        THERMAL_DEV_CATEGORY_ASIC:(0,1),
        THERMAL_DEV_CATEGORY_CPU_CORE:(0, 4),
        THERMAL_DEV_CATEGORY_MODULE:(1, 22),
        THERMAL_DEV_CATEGORY_PSU:(0, 0),
        THERMAL_DEV_CATEGORY_CPU_PACK:(0,0)
    },
    #for 3700
    {
        THERMAL_DEV_CATEGORY_ASIC:(0,1),
        THERMAL_DEV_CATEGORY_CPU_CORE:(0, 4),
        THERMAL_DEV_CATEGORY_MODULE:(1, 32),
        THERMAL_DEV_CATEGORY_PSU:(1, 2),
        THERMAL_DEV_CATEGORY_CPU_PACK:(0,1)
    },
]

def initialize_thermals(sku, thermal_list):
    tp_index = hwsku_dict_thermal[sku]
    thermal_profile = thermal_profile_list[tp_index]
    for category in thermal_device_categories_all:
        start, count = 0, 0
        if category in thermal_profile:
            start, count = thermal_profile[category]
            if count == 0:
                continue
        if count == 1:
            thermal = Thermal(category, 0, False)
            thermal_list.append(thermal)
        else:
            for index in range(count):
                thermal = Thermal(category, start + index, True)
                thermal_list.append(thermal)

class Thermal(ThermalBase):
    def __init__(self, category, index, has_index):
        if has_index:
            self.name = category + str(index)
            self.index = index
        else:
            self.name = category
            self.index = 0

        self.category = category
        self.temperature = self._get_file_from_api(THERMAL_API_GET_TEMPERATURE)
        self.high_threshold = self._get_file_from_api(THERMAL_API_GET_HIGH_THRESHOLD)

    def get_name(self):
        """
        Retrieves the name of the device

        Returns:
            string: The name of the device
        """
        return self.name

    def _read_generic_file(self, filename, len):
        """
        Read a generic file, returns the contents of the file
        """
        result = ''
        try:
            with open(filename, 'r') as fileobj:
                result = fileobj.read()
        except:
            logger.log_warning("Fail to read file {}, maybe it doesn't exist".format(filename))
            result = ''
        return result

    def _get_file_from_api(self, api_name):
        handler = thermal_api_handlers[self.category][api_name]
        if self.category in thermal_device_categories_siglton:
            filename = handler
        else:
            filename = handler.format(self.index)
        return join(HW_MGMT_THERMAL_ROOT, filename)

    def get_temperature(self):
        """
        Retrieves current temperature reading from thermal

        Returns:
            A float number of current temperature in Celsius up to nearest thousandth
            of one degree Celsius, e.g. 30.125 
        """
        value_str = self._read_generic_file(self.temperature, 0)
        value_float = float(value_str)
        return value_float / 1000.0

    def get_high_threshold(self):
        """
        Retrieves the high threshold temperature of thermal

        Returns:
            A float number, the high threshold temperature of thermal in Celsius
            up to nearest thousandth of one degree Celsius, e.g. 30.125
        """
        value_str = self._read_generic_file(self.high_threshold, 0)
        value_float = float(value_str)
        return value_float / 1000.0
