#!/usr/bin/env python

#############################################################################
# Mellanox
#
# Module contains an implementation of SONiC Thermal Base API and
# provides the thermal sensor status which are available in the platform
#
#############################################################################

try:
    from os.path import join, dirname, basename
    from glob import glob
    import syslog
    import subprocess
    from sonic_thermal.thermal_base import ThermalBase
except ImportError as e:
    raise ImportError (str(e) + "- required module not found")

def log_info(msg):
    syslog.openlog("thermalutil")
    syslog.syslog(syslog.LOG_INFO, msg)
    syslog.closelog()


THERMAL_DEV_CATEGORY_CPU_CORE = "cpu_core"
THERMAL_DEV_CATEGORY_CPU_PACK = "cpu_pack"
THERMAL_DEV_CATEGORY_MODULE = "module"
THERMAL_DEV_CATEGORY_PSU = "psu"
THERMAL_DEV_CATEGORY_AMBIENT = "ambient"
THERMAL_PATH_INDEX_PORT_AMBIENT = "port ambient path"
THERMAL_PATH_INDEX_FAN_AMBIENT = "fan ambient path"

THERMAL_DEV_ASIC_AMBIENT = "asic_amb"
THERMAL_DEV_FAN_AMBIENT = "fan_amb"
THERMAL_DEV_PORT_AMBIENT = "port_amb"

THERMAL_API_BASE_DIR = "base_dir"
THERMAL_API_GET_TEMPERATURE = "get_temperature"
THERMAL_API_GET_HIGH_THRESHOLD = "get_high_threshold"
THERMAL_API_GET_HIGH_CRITICAL_THRESHOLD = "get_high_critical_threshold"

THERMAL_API_INVALID_HIGH_THRESHOLD = 0.0

HW_MGMT_THERMAL_ROOT = "/var/run/hw-management/thermal/"

thermal_api_handler_cpu_core = {
    THERMAL_API_GET_TEMPERATURE:"/sys/devices/platform/coretemp.0/hwmon/hwmon*/temp{}_input",
    THERMAL_API_GET_HIGH_THRESHOLD:"/sys/devices/platform/coretemp.0/hwmon/hwmon*/temp{}_max",
    THERMAL_API_GET_HIGH_CRITICAL_THRESHOLD:"/sys/devices/platform/coretemp.0/hwmon/hwmon*/temp{}_crit"
}
thermal_api_handler_cpu_pack = {
    THERMAL_API_GET_TEMPERATURE:"/sys/devices/platform/coretemp.0/hwmon/hwmon*/temp1_input",
    THERMAL_API_GET_HIGH_THRESHOLD:"/sys/devices/platform/coretemp.0/hwmon/hwmon*/temp1_max",
    THERMAL_API_GET_HIGH_CRITICAL_THRESHOLD:"/sys/devices/platform/coretemp.0/hwmon/hwmon*/temp1_crit"
}
thermal_api_handler_module = {
    THERMAL_API_GET_TEMPERATURE:"/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-2/2-0048/hwmon/hwmon*/temp{}_input",
    THERMAL_API_GET_HIGH_THRESHOLD:"/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-2/2-0048/hwmon/hwmon*/temp{}_crit",
    THERMAL_API_GET_HIGH_CRITICAL_THRESHOLD:"/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-2/2-0048/hwmon/hwmon*/temp{}_emergency"
}
thermal_api_handler_psu = {
    THERMAL_API_GET_TEMPERATURE:"/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-10/10-00{}/hwmon/hwmon*/temp1_input",
    THERMAL_API_GET_HIGH_THRESHOLD:"/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-10/10-00{}/hwmon/hwmon*/temp1_max",
    THERMAL_API_GET_HIGH_CRITICAL_THRESHOLD:None
}
thermal_ambient_apis = {
    THERMAL_DEV_ASIC_AMBIENT : "/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-2/2-0048/hwmon/hwmon*/temp1_input",
    THERMAL_DEV_PORT_AMBIENT : "/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-7/7-00{}/hwmon/hwmon*/temp1_input",
    THERMAL_DEV_FAN_AMBIENT : "/sys/devices/platform/mlxplat/i2c_mlxcpld.1/i2c-1/i2c-{}/{}-00{}/hwmon/hwmon*/temp1_input"
}
thermal_psu_indexes = ["59", "58"]
thermal_cpu_core_index_start = 2
thermal_module_index_start = 2

thermal_ambient_name = {
    THERMAL_DEV_ASIC_AMBIENT : "Ambient ASIC Temp",
    THERMAL_DEV_PORT_AMBIENT : "Ambient Port Side Temp",
    THERMAL_DEV_FAN_AMBIENT : "Ambient Fan Side Temp"
}
thermal_api_handlers = {
    THERMAL_DEV_CATEGORY_CPU_CORE : thermal_api_handler_cpu_core, 
    THERMAL_DEV_CATEGORY_CPU_PACK : thermal_api_handler_cpu_pack,
    THERMAL_DEV_CATEGORY_MODULE : thermal_api_handler_module,
    THERMAL_DEV_CATEGORY_PSU : thermal_api_handler_psu
}
thermal_name = {
    THERMAL_DEV_CATEGORY_CPU_CORE : "CPU Core {} Temp", 
    THERMAL_DEV_CATEGORY_CPU_PACK : "CPU Pack Temp",
    THERMAL_DEV_CATEGORY_MODULE : "xSFP module {} Temp",
    THERMAL_DEV_CATEGORY_PSU : "PSU-{} Temp"
}

thermal_device_categories_all = [
    THERMAL_DEV_CATEGORY_CPU_CORE,
    THERMAL_DEV_CATEGORY_CPU_PACK,
    THERMAL_DEV_CATEGORY_MODULE,
    THERMAL_DEV_CATEGORY_PSU,
    THERMAL_DEV_CATEGORY_AMBIENT
]

thermal_device_categories_singleton = [
    THERMAL_DEV_CATEGORY_CPU_PACK,
    THERMAL_DEV_CATEGORY_AMBIENT
]
thermal_api_names = [
    THERMAL_API_GET_TEMPERATURE,
    THERMAL_API_GET_HIGH_THRESHOLD
]

hwsku_dict_thermal = {'ACS-MSN2700': 0, 'LS-SN2700':0, 'ACS-MSN2740': 3, 'ACS-MSN2100': 1, 'ACS-MSN2410': 2, 'ACS-MSN2010': 4, 'Mellanox-SN2700': 0, 'Mellanox-SN2700-D48C8': 0}
thermal_profile_list = [
    # 2700
    {
        THERMAL_DEV_CATEGORY_CPU_CORE:(0, 2),
        THERMAL_DEV_CATEGORY_MODULE:(1, 32),
        THERMAL_DEV_CATEGORY_PSU:(1, 2),
        THERMAL_DEV_CATEGORY_CPU_PACK:(0,1),
        THERMAL_DEV_CATEGORY_AMBIENT:(0,
            [
                THERMAL_DEV_ASIC_AMBIENT,
                THERMAL_DEV_PORT_AMBIENT,
                THERMAL_DEV_FAN_AMBIENT
            ]
        ),
        THERMAL_PATH_INDEX_PORT_AMBIENT: "4a",
        THERMAL_PATH_INDEX_FAN_AMBIENT: ("17", "17", "49")
    },
    # 2100
    {
        THERMAL_DEV_CATEGORY_CPU_CORE:(0, 4),
        THERMAL_DEV_CATEGORY_MODULE:(1, 16),
        THERMAL_DEV_CATEGORY_PSU:(0, 0),
        THERMAL_DEV_CATEGORY_CPU_PACK:(0,0),
        THERMAL_DEV_CATEGORY_AMBIENT:(0,
            [
                THERMAL_DEV_ASIC_AMBIENT,
                THERMAL_DEV_PORT_AMBIENT,
                THERMAL_DEV_FAN_AMBIENT,
            ]
        ),
        THERMAL_PATH_INDEX_PORT_AMBIENT: "4a",
        THERMAL_PATH_INDEX_FAN_AMBIENT: ("7", "7", "4b")
    },
    # 2410
    {
        THERMAL_DEV_CATEGORY_CPU_CORE:(0, 2),
        THERMAL_DEV_CATEGORY_MODULE:(1, 56),
        THERMAL_DEV_CATEGORY_PSU:(1, 2),
        THERMAL_DEV_CATEGORY_CPU_PACK:(0,1),
        THERMAL_DEV_CATEGORY_AMBIENT:(0,
            [
                THERMAL_DEV_ASIC_AMBIENT,
                THERMAL_DEV_PORT_AMBIENT,
                THERMAL_DEV_FAN_AMBIENT,
            ]
        ),
        THERMAL_PATH_INDEX_PORT_AMBIENT: "4a",
        THERMAL_PATH_INDEX_FAN_AMBIENT: ("17", "17", "49")
    },
    # 2740
    {
        THERMAL_DEV_CATEGORY_CPU_CORE:(0, 4),
        THERMAL_DEV_CATEGORY_MODULE:(1, 32),
        THERMAL_DEV_CATEGORY_PSU:(1, 2),
        THERMAL_DEV_CATEGORY_CPU_PACK:(0,0),
        THERMAL_DEV_CATEGORY_AMBIENT:(0,
            [
                THERMAL_DEV_ASIC_AMBIENT,
                THERMAL_DEV_PORT_AMBIENT,
                THERMAL_DEV_FAN_AMBIENT,
            ]
        ),
        THERMAL_PATH_INDEX_PORT_AMBIENT: "48",
        THERMAL_PATH_INDEX_FAN_AMBIENT: ("6", "6", "49")
    },
    # 2010
    {
        THERMAL_DEV_CATEGORY_CPU_CORE:(0, 4),
        THERMAL_DEV_CATEGORY_MODULE:(1, 22),
        THERMAL_DEV_CATEGORY_PSU:(0, 0),
        THERMAL_DEV_CATEGORY_CPU_PACK:(0,0),
        THERMAL_DEV_CATEGORY_AMBIENT:(0,
            [
                THERMAL_DEV_ASIC_AMBIENT,
                THERMAL_DEV_PORT_AMBIENT,
                THERMAL_DEV_FAN_AMBIENT,
            ]
        ),
        THERMAL_PATH_INDEX_PORT_AMBIENT: "4a",
        THERMAL_PATH_INDEX_FAN_AMBIENT: ("7", "7", "4b")
    }
]


class Thermal(object):
    def __init__(self, category, index, has_index, file_index = None):
        """
        index should be a string for category ambient and int for other categories
        """
        if category == THERMAL_DEV_CATEGORY_AMBIENT:
            self.name = thermal_ambient_name[index]
            self.index = index
        elif has_index:
            self.name = thermal_name[category].format(index)
            self.index = index
        else:
            self.name = thermal_name[category]
            self.index = 0

        self.category = category
        self.temperature = self._get_file_from_api(THERMAL_API_GET_TEMPERATURE, file_index)
        self.high_threshold = self._get_file_from_api(THERMAL_API_GET_HIGH_THRESHOLD, file_index)
        self.high_critical_threshold = self._get_file_from_api(THERMAL_API_GET_HIGH_CRITICAL_THRESHOLD, file_index)

    def _get_real_hwmon_path(self, hwmon_pattern):
        dirpattern = dirname(hwmon_pattern)
        filename = basename(hwmon_pattern)
        hwmon_list = glob(dirpattern)
        if len(hwmon_list) != 1:
            log_info("unable to get real path from hwmon path pattern {}".format(hwmon_pattern))
            return hwmon_pattern
        return join(hwmon_list[0], filename)

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
        result = None
        try:
            with open(filename, 'r') as fileobj:
                result = fileobj.read()
        except Exception as e:
            log_info("Fail to read file {} due to {}".format(filename, repr(e)))
        return result

    def _get_file_from_api(self, api_name, index):
        if self.category == THERMAL_DEV_CATEGORY_AMBIENT:
            if api_name == THERMAL_API_GET_TEMPERATURE:
                filename = thermal_ambient_apis[self.index]
            else:
                return None, None
        else:
            handler = thermal_api_handlers[self.category][api_name]
            if self.category in thermal_device_categories_singleton:
                filename = handler
            else:
                if handler:
                    filename = handler.format(index)
                else:
                    return None, None
        return self._get_real_hwmon_path(filename), filename

    def get_temperature(self):
        """
        Retrieves current temperature reading from thermal

        Returns:
            A float number of current temperature in Celsius up to nearest thousandth
            of one degree Celsius, e.g. 30.125 
        """
        value_str = self._read_generic_file(self.temperature[0], 0)
        if value_str is None:
            # Probably the sensor was replugged and the path has been changed
            self.temperature = self._get_real_hwmon_path(self.temperature[0]), self.temperature[1]
            return None
        value_float = float(value_str)
        if self.category == THERMAL_DEV_CATEGORY_MODULE and value_float == THERMAL_API_INVALID_HIGH_THRESHOLD:
            return None
        return value_float / 1000.0

    def get_high_threshold(self):
        """
        Retrieves the high threshold temperature of thermal

        Returns:
            A float number, the high threshold temperature of thermal in Celsius
            up to nearest thousandth of one degree Celsius, e.g. 30.125
        """
        if self.high_threshold[0] is None:
            return None
        value_str = self._read_generic_file(self.high_threshold[0], 0)
        if value_str is None:
            self.high_threshold = self._get_real_hwmon_path(self.high_threshold[0]), self.high_threshold[1]
            return None
        value_float = float(value_str)
        if self.category == THERMAL_DEV_CATEGORY_MODULE and value_float == THERMAL_API_INVALID_HIGH_THRESHOLD:
            return None
        return value_float / 1000.0

    def get_high_critical_threshold(self):
        """
        Retrieves the high critical threshold temperature of thermal

        Returns:
            A float number, the high critical threshold temperature of thermal in Celsius
            up to nearest thousandth of one degree Celsius, e.g. 30.125
        """
        if self.high_critical_threshold[0] is None:
            return None
        value_str = self._read_generic_file(self.high_critical_threshold[0], 0)
        if value_str is None:
            self.high_critical_threshold = self._get_real_hwmon_path(self.high_critical_threshold[0]), self.high_critical_threshold[1]
            return None
        value_float = float(value_str)
        if self.category == THERMAL_DEV_CATEGORY_MODULE and value_float == THERMAL_API_INVALID_HIGH_THRESHOLD:
            return None
        return value_float / 1000.0


class ThermalUtil(ThermalBase):
    """Platform-specific Thermalutil class"""

    MAX_PSU_FAN = 1
    MAX_NUM_PSU = 2
    GET_HWSKU_CMD = "sonic-cfggen -d -v DEVICE_METADATA.localhost.hwsku"
    number_of_thermals = 0
    thermal_list = []

    def _get_sku_name(self):
        p = subprocess.Popen(self.GET_HWSKU_CMD, shell=True, stdout=subprocess.PIPE)
        out, err = p.communicate()
        return out.rstrip('\n')

    def __init__(self):
        sku = self._get_sku_name()
        # create thermal objects for all categories of sensors
        tp_index = hwsku_dict_thermal[sku]
        thermal_profile = thermal_profile_list[tp_index]
        for category in thermal_device_categories_all:
            if category == THERMAL_DEV_CATEGORY_AMBIENT:
                count, ambient_list = thermal_profile[category]
                for ambient in ambient_list:
                    path_pattern = thermal_ambient_apis[ambient]
                    if ambient == THERMAL_DEV_PORT_AMBIENT:
                        # Generate the real path
                        param1 = thermal_profile[THERMAL_PATH_INDEX_PORT_AMBIENT]
                        path_pattern = path_pattern.format(param1)
                        thermal_ambient_apis[THERMAL_DEV_PORT_AMBIENT] = path_pattern
                    elif ambient == THERMAL_DEV_FAN_AMBIENT:
                        param1, param2, param3 = thermal_profile[THERMAL_PATH_INDEX_FAN_AMBIENT]
                        path_pattern = path_pattern.format(param1, param2, param3)
                        thermal_ambient_apis[THERMAL_DEV_FAN_AMBIENT] = path_pattern
                    thermal = Thermal(category, ambient, True)
                    self.thermal_list.append(thermal)
            else:
                start, count = 0, 0
                if category in thermal_profile:
                    start, count = thermal_profile[category]
                    if count == 0:
                        continue
                if count == 1:
                    thermal = Thermal(category, 0, False)
                    self.thermal_list.append(thermal)
                else:
                    for index in range(count):
                        if category == THERMAL_DEV_CATEGORY_PSU:
                            fileindex = thermal_psu_indexes[index]
                        elif category == THERMAL_DEV_CATEGORY_MODULE or category == THERMAL_DEV_CATEGORY_CPU_CORE:
                            fileindex = index + 2
                        else:
                            fileindex = None
                        thermal = Thermal(category, start + index, True, fileindex)
                        self.thermal_list.append(thermal)
        self.number_of_thermals = len(self.thermal_list)

    def get_num_thermals(self):
        """
        Retrieves the number of thermal sensors supported on the device

        :return: An integer, the number of thermal sensors supported on the device
        """
        return self.number_of_thermals

    def get_name(self, index):
        """
        Retrieves the human-readable name of a thermal sensor by 1-based index

        Returns:
        :param index: An integer, 1-based index of the thermal sensor of which to query status
        :return: String,
            A string representing the name of the thermal sensor. 
        """
        if index >= self.number_of_thermals:
            raise RuntimeError("index ({}) shouldn't be greater than {}".format(index, self.number_of_thermals))
        return self.thermal_list[index].get_name()

    def get_temperature(self, index):
        """
        Retrieves current temperature reading from thermal sensor by 1-based index

        :param index: An integer, 1-based index of the thermal sensor of which to query status
        :return: Float,
            A float number of current temperature in Celsius up to nearest thousandth
            of one degree Celsius, e.g. 30.125 
        """
        if index >= self.number_of_thermals:
            raise RuntimeError("index ({}) shouldn't be greater than {}".format(index, self.number_of_thermals))
        return self.thermal_list[index].get_temperature()

    def get_high_threshold(self, index):
        """
        Retrieves the high threshold temperature of thermal by 1-based index
        Actions should be taken if the temperature becomes higher than the threshold.

        :param index: An integer, 1-based index of the thermal sensor of which to query status
        :return: A float number, the high threshold temperature of thermal in Celsius
                 up to nearest thousandth of one degree Celsius, e.g. 30.125
        """
        if index >= self.number_of_thermals:
            raise RuntimeError("index ({}) shouldn't be greater than {}".format(index, self.number_of_thermals))
        return self.thermal_list[index].get_high_threshold()

    def get_high_critical_threshold(self, index):
        """
        Retrieves the high critical threshold temperature of thermal by 1-based index
        Actions should be taken immediately if the temperature becomes higher than the high critical
        threshold otherwise the device will be damaged.

        :param index: An integer, 1-based index of the thermal sensor of which to query status
        :return: A float number, the high critical threshold temperature of thermal in Celsius
                 up to nearest thousandth of one degree Celsius, e.g. 30.125
        """
        if index >= self.number_of_thermals:
            raise RuntimeError("index ({}) shouldn't be greater than {}".format(index, self.number_of_thermals))
        return self.thermal_list[index].get_high_critical_threshold()
