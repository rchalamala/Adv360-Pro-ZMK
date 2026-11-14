DOCKER := $(shell { command -v podman || command -v docker; })

.PHONY: all left clean_firmware clean_image clean

all:
	DOCKER="$(DOCKER)" bash bin/build-local.sh all

left:
	DOCKER="$(DOCKER)" bash bin/build-local.sh left

clean_firmware:
	rm -f firmware/*.uf2 firmware/build-info.txt firmware/west-manifest.yml firmware/west-active-manifest.yml firmware/SHA256SUMS firmware/config-SHA256SUMS

clean_image:
	$(DOCKER) image rm adv360-zmk

clean: clean_firmware clean_image
