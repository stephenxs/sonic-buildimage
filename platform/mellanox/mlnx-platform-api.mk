# SONIC_PLATFORM_API_PY2 package

SONIC_PLATFORM_API_PY2 = mlnx_platform_api-1.0-py2-none-any.whl
$(SONIC_PLATFORM_API_PY2)_SRC_PATH = $(PLATFORM_PATH)/mlnx-platform-api
$(SONIC_PLATFORM_API_PY2)_PYTHON_VERSION = 2
SONIC_PYTHON_WHEELS += $(SONIC_PLATFORM_API_PY2)

export mlnx_platform_api_py2_wheel_path="$(addprefix $(PYTHON_WHEELS_PATH)/,$(SONIC_PLATFORM_API_PY2))"
