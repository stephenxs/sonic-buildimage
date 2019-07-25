#!/usr/bin/env python

#############################################################################
# Mellanox
#
# implementation of new platform api
#############################################################################

try:
    from sonic_platform_base.platform_base import PlatformBase
    from sonic_platform.chassis import Chassis
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")

class Platform(PlatformBase):
    def __init__(self, is_host = False):
        PlatformBase.__init__(self)
        if is_host:
            self._chassis = Chassis()
            self._chassis.initialize_watchdog()
        else:
            self._chassis = Chassis()
            self._chassis.initialize_psu()
            self._chassis.initialize_fan()
            self._chassis.initialize_sfp()
            self._chassis.initialize_eeprom()
            self._chassis.initialize_components_list()
