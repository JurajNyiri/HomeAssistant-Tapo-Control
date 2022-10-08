.DEFAULT_GOAL := help
SHELL := /bin/bash

help: ## Shows help message.
	@printf "\033[1m%s\033[36m %s\033[32m %s\033[0m \n\n" "Development environment for" "Tapo Control" "Integration";
	@awk 'BEGIN {FS = ":.*##";} /^[a-zA-Z_-]+:.*?##/ { printf " \033[36m make %-25s\033[0m %s\n", $$1, $$2 } /^##@/ { printf "\n\033[1m%s\033[0m\n", substr($$0, 5) } ' $(MAKEFILE_LIST);
	@echo

init: requirements homeassistant-install## Install requirements

requirements:
	sudo apt update && sudo apt install -y libxml2-dev libxslt-dev bash curl jq libpcap0.8 ffmpeg

lint: ## Run linters
	set -e
	jq -r -e -c . tests/fixtures/*.json
	pre-commit install-hooks --config .github/pre-commit-config.yaml;
	pre-commit run --hook-stage manual --all-files --config .github/pre-commit-config.yaml;
	bellybutton lint
	vulture . --min-confidence 75 --ignore-names policy

homeassistant-install: ## Install the latest dev version of Home Assistant
	python3 -m pip --disable-pip-version-check install -U "pip<22.3,>=21.0";
	python3 -m pip --disable-pip-version-check install -U setuptools wheel aiohttp_cors;
	python3 -m pip --disable-pip-version-check \
		install --upgrade git+https://github.com/home-assistant/home-assistant.git@dev;

homeassistant-install-old: ## Install the oldest version of Home Assistant
	python3 -m pip --disable-pip-version-check install -U "pip<22.3,>=21.0";
	python3 -m pip --disable-pip-version-check install -U setuptools wheel aiohttp_cors;
	python3 -m pip --disable-pip-version-check \
		install --upgrade git+https://github.com/home-assistant/home-assistant.git@2022.8.0;

homeassistant-update: homeassistant-install ## Alias for 'homeassistant-install'