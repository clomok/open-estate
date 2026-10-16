.PHONY: estates adopt build up down restart logs shell seed wipe test clean guard estate-guard

# One stack serves every estate; the estates themselves are listed in
# instance/estates.json and switched from the sidebar. Commands that act on
# ONE estate's data name it, and there is no default:
#
#   make seed ESTATE=demo
#
# Picking the wrong estate by omission is the one mistake that cannot happen.
ESTATE ?=
# Linux hosts often have only python3; Windows dev boxes use ops.ps1.
PYTHON ?= python3
SITE_ENV = datasets/site.env
COMPOSE = docker compose --env-file $(SITE_ENV)

guard:
	@test -f $(SITE_ENV) || { \
		echo "No $(SITE_ENV). Copy datasets/site.env.example and fill it in."; \
		echo "Upgrading an install from the one-container-per-dataset layout?"; \
		echo "Stop it, then run 'make adopt DATASET=<name>' once per dataset."; exit 1; }

estate-guard: guard
	@test -n "$(ESTATE)" || { \
		echo "Name the estate, e.g. 'make $(MAKECMDGOALS) ESTATE=demo'. Estates here:"; \
		$(PYTHON) scripts/estate_admin.py list; exit 1; }

# Show every estate this install holds
estates:
	@$(PYTHON) scripts/estate_admin.py list

# Move an old instance/<name>/ dataset into instance/estates/<name>/ (run on
# the host with the old stack stopped; DATASET=legacy for instance/estate.db)
adopt:
	@test -n "$(DATASET)" || { echo "Usage: make adopt DATASET=<old dataset name>"; exit 1; }
	$(PYTHON) scripts/estate_admin.py adopt $(DATASET)

build: guard
	$(COMPOSE) build

up: guard
	$(COMPOSE) up -d

down: guard
	$(COMPOSE) down

restart: guard
	$(COMPOSE) restart web

logs: guard
	$(COMPOSE) logs -f web

shell: guard
	$(COMPOSE) exec web /bin/bash

# Load demo data into one estate. The script itself refuses a protected
# estate; this target only makes you name it.
seed: estate-guard
	$(COMPOSE) exec web python scripts/$(or $(FILE),seed_example.py) --estate $(ESTATE)

# Empty one estate. Its old database moves to its backups/ folder; protected
# estates are refused. Restart drops the workers' connections to the old file.
wipe: estate-guard
	$(COMPOSE) exec web python scripts/estate_admin.py wipe $(ESTATE)
	$(COMPOSE) restart web

# Tests need no container and no estate
test:
	$(PYTHON) -m pytest tests/ -q

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
