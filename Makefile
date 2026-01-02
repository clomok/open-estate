.PHONY: run build clean init-db

# Build the docker container
build:
	docker-compose build

# Run the stack in detached mode
run:
	docker-compose up -d

# View logs
logs:
	docker-compose logs -f

# Stop containers
stop:
	docker-compose down

# Remove Python cache and temp files
clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +

# One-time setup command (Copies env example)
init:
	cp .env.example .env
	@echo "Created .env file. PLEASE EDIT IT with your secrets."