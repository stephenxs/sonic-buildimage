# Mellanox SAI

MLNX_SAI_VERSION = SAIRel1.14.1-master
# 
# MLNX_SAI_REVISION = 80e08e8f12746801d683730a5e147cd6e77becfb
# Stephen Sun comments this out for new SAI integration
# We use the following commit
#
MLNX_SAI_REVISION = 76ced9d4a147163098054a717ecce56d58478b35

export MLNX_SAI_VERSION MLNX_SAI_REVISION

MLNX_SAI = mlnx-sai_1.mlnx.$(MLNX_SAI_VERSION)_amd64.deb
$(MLNX_SAI)_SRC_PATH = $(PLATFORM_PATH)/mlnx-sai
$(MLNX_SAI)_DEPENDS += $(MLNX_SDK_DEBS)
$(MLNX_SAI)_RDEPENDS += $(MLNX_SDK_RDEBS) $(MLNX_SDK_DEBS)
SONIC_MAKE_DEBS += $(MLNX_SAI)
