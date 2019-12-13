#!/usr/bin/env python

#############################################################################
# Mellanox
#
# Module contains an implementation of SONiC Platform Base API and
# provides the FANs status which are available in the platform
#
#############################################################################

import os.path

try:
    from sonic_platform_base.fan_base import FanBase
except ImportError as e:
    raise ImportError (str(e) + "- required module not found")

LED_ON = 1
LED_OFF = 0

PWM_MAX = 255

FAN_PATH = "/var/run/hw-management/thermal/"
LED_PATH = "/var/run/hw-management/led/"

class Fan(FanBase):
    """Platform-specific Fan class"""
    def __init__(self, fan_index, drawer_index = 1, psu_fan = False):
        # API index is starting from 0, Mellanox platform index is starting from 1
        self.index = fan_index + 1
        self.drawer_index = drawer_index + 1

        self.is_psu_fan = psu_fan
        
        self.fan_min_speed_path = "fan{}_min".format(self.index)
        if not self.is_psu_fan:
            self.fan_speed_get_path = "fan{}_speed_get".format(self.index)
            self.fan_speed_set_path = "fan{}_speed_set".format(self.index)
            self.fan_presence_path = "fan{}_status".format(self.drawer_index)
            self.fan_max_speed_path = "fan{}_max".format(self.index)
            self._name = "fan{}".format(fan_index + 1)
        else:
            self.fan_speed_get_path = "psu{}_fan1_speed_get".format(self.index)
            self.fan_presence_path = "psu{}_fan1_speed_get".format(self.index)
            self._name = "fan(PSU{})".format(fan_index)
            self.fan_max_speed_path = None
        self.fan_status_path = "fan{}_fault".format(self.index)
        self.fan_green_led_path = "led_fan{}_green".format(self.drawer_index)
        self.fan_red_led_path = "led_fan{}_red".format(self.drawer_index)
        self.fan_orange_led_path = "led_fan{}_orange".format(self.drawer_index)
        self.fan_pwm_path = "pwm1"
        self.fan_led_cap_path = "led_fan{}_capability".format(self.drawer_index)

    def get_name(self):
        return self._name

    def get_status(self):
        """
        Retrieves the operational status of fan

        Returns:
            bool: True if fan is operating properly, False if not
        """
        status = 0
        if self.is_psu_fan:
            status = 1
        else:
            try:
                with open(os.path.join(FAN_PATH, self.fan_status_path), 'r') as fault_status:
                    status = int(fault_status.read())
            except (ValueError, IOError):
                status = 0

        return status == 1

    def get_presence(self):
        """
        Retrieves the presence status of fan

        Returns:
            bool: True if fan is present, False if not
        """
        status = 0
        if self.is_psu_fan:
            if os.path.exists(os.path.join(FAN_PATH, self.fan_presence_path)):
                status = 1
            else:
                status = 0
        else:
            try:
                with open(os.path.join(FAN_PATH, self.fan_presence_path), 'r') as presence_status:
                    status = int(presence_status.read())
            except (ValueError, IOError):
                status = 0

        return status == 1
    
    def _get_min_speed_in_rpm(self):
        speed = 0
        try:
            with open(os.path.join(FAN_PATH, self.fan_min_speed_path), 'r') as min_fan_speed:
                speed = int(min_fan_speed.read())
        except (ValueError, IOError):
            speed = 0
        
        return speed
    
    def _get_max_speed_in_rpm(self):
        speed = 0
        try:
            with open(os.path.join(FAN_PATH, self.fan_max_speed_path), 'r') as max_fan_speed:
                speed = int(max_fan_speed.read())
        except (ValueError, IOError):
            speed = 0
        
        return speed

    def get_speed(self):
        """
        Retrieves the speed of fan

        Returns:
            int: percentage of the max fan speed
        """
        speed = 0
        try:
            with open(os.path.join(FAN_PATH, self.fan_speed_get_path), 'r') as fan_curr_speed:
                speed_in_rpm = int(fan_curr_speed.read())
        except (ValueError, IOError):
            speed_in_rpm = 0

        if self.fan_max_speed_path is None:
            # in case of max speed unsupported, we just return speed in unit of RPM.
            return speed_in_rpm

        max_speed_in_rpm = self._get_max_speed_in_rpm()
        speed = 100*speed_in_rpm/max_speed_in_rpm

        return speed

    def get_target_speed(self):
        """
        Retrieves the expected speed of fan

        Returns:
            int: percentage of the max fan speed
        """
        if self.is_psu_fan:
            # Not like system fan, psu fan speed can not be modified, so target speed is N/A 
            return self.get_speed()

        try:
            with open(os.path.join(FAN_PATH, self.fan_speed_set_path), 'r') as fan_pwm:
                pwm = int(fan_pwm.read())
        except (ValueError, IOError):
            pwm = 0
        
        speed = int(round(pwm*100.0/PWM_MAX))
        
        return speed

    def set_speed(self, speed):
        """
        Set fan speed to expected value

        Args:
            speed: An integer, the percentage of full fan speed to set fan to,
                   in the range 0 (off) to 100 (full speed)

        Returns:
            bool: True if set success, False if fail. 
        """
        status = True
        pwm = int(round(PWM_MAX*speed/100.0))

        if self.is_psu_fan:
            #PSU fan speed is not setable.
            return False
        
        try:
            with open(os.path.join(FAN_PATH, self.fan_speed_set_path), 'w') as fan_pwm:
                fan_pwm.write(str(pwm))
        except (ValueError, IOError):
            status = False

        return status
    
    def _get_led_capability(self):
        cap_list = None
        try:
            with open(os.path.join(LED_PATH, self.fan_led_cap_path), 'r') as fan_led_cap:
                    caps = fan_led_cap.read()
                    cap_list = caps.split()
        except (ValueError, IOError):
            status = 0
        
        return cap_list

    def set_status_led(self, color):
        """
        Set led to expected color

        Args:
            color: A string representing the color with which to set the
                   fan module status LED

        Returns:
            bool: True if set success, False if fail. 
        """
        led_cap_list = self._get_led_capability()
        if led_cap_list is None:
            return False

        if self.is_psu_fan:
            # PSU fan led status is not able to set
            return False
        status = False
        try:
            if color == 'green':
                with open(os.path.join(LED_PATH, self.fan_green_led_path), 'w') as fan_led:
                    fan_led.write(str(LED_ON))
            elif color == 'red':
                # Some fan don't support red led but support orange led, in this case we set led to orange
                if 'red' in led_cap_list:
                    led_path = os.path.join(LED_PATH, self.fan_red_led_path)
                elif 'orange' in led_cap_list:
                    led_path = os.path.join(LED_PATH, self.fan_orange_led_path)
                else:
                    return False
                with open(led_path, 'w') as fan_led:
                    fan_led.write(str(LED_ON))

            elif color == 'off':
                with open(os.path.join(LED_PATH, self.fan_green_led_path), 'w') as fan_led:
                    fan_led.write(str(LED_OFF))

                with open(os.path.join(LED_PATH, self.fan_red_led_path), 'w') as fan_led:
                    fan_led.write(str(LED_OFF))
            else:
                status = False
        except (ValueError, IOError):
                    status = False
        return status

    def get_speed_tolerance(self):
        """
        Retrieves the speed tolerance of the fan

        Returns:
            An integer, the percentage of variance from target speed which is
                 considered tolerable
        """
        # The tolerance value is fixed as 20% for all the Mellanox platform
        return 20
