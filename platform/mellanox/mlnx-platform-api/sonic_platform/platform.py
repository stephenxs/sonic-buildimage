#!/usr/bin/env python

#############################################################################
# Mellanox
#
# implementation of new platform api
#############################################################################

try:
    from sonic_platform_base.platform_base import PlatformBase
#    from sonic_platform.chassis import Chassis
except ImportError as e:
    raise ImportError(str(e) + "- required module not found")

class Platform(PlatformBase):
    def __init__(self, daemon = None):
        PlatformBase.__init__(self)
        if daemon is None:
            from sonic_platform.chassis_host import Chassis
            self._chassis = Chassis()
        else:
            from sonic_platform.chassis import Chassis
            self._chassis = Chassis()
