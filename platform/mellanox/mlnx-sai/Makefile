.ONESHELL:
SHELL = /bin/bash
.SHELLFLAGS += -e

MAIN_TARGET = mlnx-sai_1.mlnx.$(MLNX_SAI_VERSION)_amd64.deb

$(addprefix $(DEST)/, $(MAIN_TARGET)): $(DEST)/% :
	# get sources
	rm -rf SAI-Implementation
#
#	Stephen Sun comment this out for new SAI integration
#
#	git clone https://github.com/Mellanox/SAI-Implementation.git
#
#	It should be cloned from our internal git as following
#
	git clone file:////auto/mswg/git/switchx/sai_interface.git SAI-Implementation

	# build
	pushd SAI-Implementation
	git checkout $(MLNX_SAI_REVISION)
	pushd mlnx_sai
	chmod a+x autogen.sh
	debuild -e 'make_extra_flags="DEFS=-DACS_OS"' -us -uc -d -b
	popd

	mv $* $(DEST)/
	popd
