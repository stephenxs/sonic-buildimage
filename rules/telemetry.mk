# SONiC telemetry package

SONIC_TELEMETRY = sonic-telemetry_0.1_$(CONFIGURED_ARCH).deb
$(SONIC_TELEMETRY)_SRC_PATH = $(SRC_PATH)/telemetry
SONIC_DPKG_DEBS += $(SONIC_TELEMETRY)
