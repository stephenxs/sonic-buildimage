# mellanox firmware

# Stephen Sun comments out for sdk/sai integration
# MLNX_FW_VERSION = 13.2000.1420
#
MLNX_FW_VERSION = 13.2000.2104

MLNX_FW_FILE = fw-SPC-rel-$(subst .,_,$(MLNX_FW_VERSION))-EVB.mfa
$(MLNX_FW_FILE)_URL = $(MLNX_SDK_BASE_URL)/$(MLNX_FW_FILE)
SONIC_ONLINE_FILES += $(MLNX_FW_FILE)

export MLNX_FW_VERSION
export MLNX_FW_FILE
