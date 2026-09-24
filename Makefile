.PHONY: list new adopt build up down restart logs shell seed wipe test clean guard protected-guard

# Every command targets exactly one dataset:
#
#   make up DATASET=demo
#
# There is no default. Picking the wrong estate by omission is the one mistake
# this layout exists to prevent.
DATASET ?=
ENV_FILE = datasets/$(DATASET).env
COMPOSE = docker compose --env-file $(ENV_FILE)

guard:
	@test -n "$(DATASET)" || { \
		echo "Set DATASET, e.g. 'make up DATASET=demo'."; \
		echo "Available datasets:"; $(MAKE) --no-print-directory list; exit 1; }
	@test -f $(ENV_FILE) || { \
		echo "No such dataset: $(ENV_FILE)"; \
		echo "Create it with 'make new DATASET=$(DATASET)'."; exit 1; }

# Destructive commands stop dead at a dataset holding real data.
protected-guard: guard
	@if grep -q '^DATASET_PROTECTED=1' $(ENV_FILE); then \
		echo "REFUSED: '$(DATASET)' is marked DATASET_PROTECTED=1 - it holds real data."; \
		echo "Take a backup from the Settings page first, then clear the flag by hand."; \
		exit 1; fi

# Show every dataset this checkout knows about
list:
	@if ls datasets/*.env >/dev/null 2>&1; then \
		ls datasets/*.env | sed 's|datasets/||; s|\.env$$||; s|^|  |'; \
	else \
		echo "  (none yet - run 'make new DATASET=demo')"; \
	fi

# Create a new dataset from the template
new:
	@test -n "$(DATASET)" || { echo "Usage: make new DATASET=<name>"; exit 1; }
	@test ! -f $(ENV_FILE) || { echo "$(ENV_FILE) already exists - refusing to overwrite."; exit 1; }
	cp datasets/demo.env.example $(ENV_FILE)
	@mkdir -p instance/$(DATASET)
	@echo "Created $(ENV_FILE) and instance/$(DATASET)/."
	@echo "EDIT IT: set DATASET=$(DATASET), a unique PORT, and a fresh SECRET_KEY + ADMIN_PASSWORD."

# Move a pre-dataset install (instance/estate.db + .env) into a named dataset
adopt:
	@test -n "$(DATASET)" || { echo "Usage: make adopt DATASET=<name>"; exit 1; }
	@test -f instance/estate.db || { echo "Nothing to adopt: instance/estate.db not found."; exit 1; }
	mkdir -p instance/$(DATASET)
	mv instance/estate.db* instance/$(DATASET)/
	@test ! -f .env || cp .env $(ENV_FILE)
	@echo "Moved the old database into instance/$(DATASET)/ and seeded $(ENV_FILE) from .env."
	@echo "EDIT IT: add DATASET=$(DATASET), COMPOSE_PROJECT_NAME, PORT and DATASET_PROTECTED."

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

# Load demo data. Refused on a protected dataset - seeds overwrite nothing by
# accident only because this guard is here.
seed: protected-guard
	$(COMPOSE) exec web python scripts/$(or $(FILE),seed_example.py)

# Delete this dataset's database and rebuild it empty.
wipe: protected-guard
	@echo "This DELETES every record in dataset '$(DATASET)'."
	@read -p "Type the dataset name to confirm: " reply; \
		test "$$reply" = "$(DATASET)" || { echo "Cancelled."; exit 1; }
	$(COMPOSE) exec web rm -f instance/estate.db
	$(COMPOSE) exec web flask db upgrade
	$(COMPOSE) restart web
	@echo "Dataset '$(DATASET)' is clean and empty."

# Tests need no container and no dataset
test:
	python -m pytest tests/ -q

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
