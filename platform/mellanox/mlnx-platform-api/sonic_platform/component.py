#!/usr/bin/env python

#############################################################################
# Mellanox
#
# implementation of new platform api
#############################################################################

try:
    from sonic_platform_base.component_base import ComponentBase
    from glob import glob
    import subprocess
    import io
    import re
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")

#components definitions
COMPONENT_BIOS = "BIOS"
COMPONENT_FIRMWARE = "ASIC-FIRMWARE"
COMPONENT_CPLD = "CPLD"

FW_QUERY_VERSION_COMMAND = 'mlxfwmanager --query'
BIOS_QUERY_VERSION_COMMAND = 'dmidecode -t 11'
CPLD_VERSION_FILE_PATTERN = '/var/run/hw-management/system/cpld?_version'
CPLD_VERSION_MAX_LENGTH = 4

class Component(ComponentBase):
    def get_name(self):
        """
        Retrieves the name of the component

        Returns:
            A string containing the name of the component
        """
        return self.name


    def _read_generic_file(self, filename, len):
        """
        Read a generic file, returns the contents of the file
        """
        result = ''
        try:
            fileobj = io.open(filename)
            result = fileobj.read(len)
            fileobj.close()
            return result
        except Exception as e:
            logger.log_info("Fail to read file {} due to {}".format(filename, repr(e)))
            return '0'


    def _get_command_result(self, cmdline):
        try:
            proc = subprocess.Popen(cmdline, stdout=subprocess.PIPE, shell=True, stderr=subprocess.STDOUT)
            stdout = proc.communicate()[0]
            proc.wait()
            result = stdout.rstrip('\n')

        except OSError, e:
            result = ''

        return result


class ComponentBIOS(Component):
    def __init__(self):
        self.name = COMPONENT_BIOS


    def get_description(self):
        """
        Retrieves the description of the component

        Returns:
            A string containing the description of the component
        """
        raise NotImplementedError


    def get_firmware_version(self):
        """
        Retrieves the firmware version of the component

        Returns:
            A string containing the firmware version of the component

        BIOS version is retrieved via command 'dmidecode -t 11'
        which should return result in the following convention
            # dmidecode 3.0
            Getting SMBIOS data from sysfs.
            SMBIOS 2.7 present.

            Handle 0x0022, DMI type 11, 5 bytes
            OEM Strings
                    String 1:*0ABZS017_02.02.002*
                    String 2: To Be Filled By O.E.M.

        By using regular expression 'OEM[\s]*Strings\n[\s]*String[\s]*1:[\s]*([0-9a-zA-Z_\.]*)'
        we can extrace the version string which is marked with * in the above context
        """
        bios_ver_str = self._get_command_result(BIOS_QUERY_VERSION_COMMAND)
        try:
            m = re.search('OEM[\s]*Strings\n[\s]*String[\s]*1:[\s]*([0-9a-zA-Z_\.]*)', bios_ver_str)
            result = m.group(1)
        except:
            result = ''

        return result


class ComponentCPLD(Component):
    def __init__(self):
        self.name = COMPONENT_CPLD


    def get_description(self):
        """
        Retrieves the description of the component

        Returns:
            A string containing the description of the component
        """
        raise NotImplementedError


    def get_firmware_version(self):
        """
        Retrieves the firmware version of the component

        Returns:
            A string containing the firmware version of the component
        """
        cpld_version_file_list = glob(CPLD_VERSION_FILE_PATTERN)
        cpld_version = ''
        if cpld_version_file_list is not None and not cpld_version_file_list == []:
            cpld_version_file_list.sort()
            for version_file in cpld_version_file_list:
                version = self._read_generic_file(version_file, CPLD_VERSION_MAX_LENGTH)
                if not cpld_version == '':
                    cpld_version += '.'
                cpld_version += version.rstrip('\n')

        return cpld_version


class ComponentASIC_FW(Component):
    def __init__(self):
        self.name = COMPONENT_FIRMWARE


    def get_description(self):
        """
        Retrieves the description of the component

        Returns:
            A string containing the description of the component
        """
        raise NotImplementedError


    def get_firmware_version(self):
        """
        Retrieves the firmware version of the component

        Returns:
            A string containing the firmware version of the component

        firmware version is retrieved via command 'mlxfwmanager --query'
        which should return result in the following convention
            admin@mtbc-sonic-01-2410:~$ sudo mlxfwmanager --query
            Querying Mellanox devices firmware ...

            Device #1:
            ----------

            Device Type:      Spectrum
            Part Number:      MSN2410-CxxxO_Ax_Bx
            Description:      Spectrum based 25GbE/100GbE 1U Open Ethernet switch with ONIE; 48 SFP28 ports; 8 QSFP28 ports; x86 dual core; RoHS6
            PSID:             MT_2860111033
            PCI Device Name:  /dev/mst/mt52100_pci_cr0
            Base MAC:         98039bf3f500
            Versions:         Current        Available     
                FW         ***13.2000.1140***N/A           

            Status:           No matching image found

        By using regular expression '(Versions:.*\n[\s]+FW[\s]+)([\S]+)',
        we can extrace the version which is marked with *** in the above context
        """
        fw_ver_str = self._get_command_result(FW_QUERY_VERSION_COMMAND)
        try: 
            m = re.search('(Versions:.*\n[\s]+FW[\s]+)([\S]+)', fw_ver_str)
            result = m.group(2)
        except :
            result = ''

        return result
