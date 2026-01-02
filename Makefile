.PHONY: build up down logs restart clean test

# Docker commands
build:
	docker-compose build

up:
	docker-compose up -d

down:
	docker-compose down

logs:
	docker-compose logs -f

restart:
	docker-compose restart

# Clean up
clean:
	docker-compose down -v
	rm -rf data/

# Test run (without docker)
test:
	python3 monitor.py

# Build and push to Docker Hub manually
docker-build:
	docker build -t website-monitoring:latest .

docker-push:
	@read -p "Docker Hub username: " username; \
	read -p "Docker Hub repository: " repo; \
	docker tag website-monitoring:latest $$username/$$repo:latest; \
	docker push $$username/$$repo:latest

# Help
help:
	@echo "Available commands:"
	@echo "  make build      - Build Docker image"
	@echo "  make up         - Start containers"
	@echo "  make down       - Stop containers"
	@echo "  make logs       - View logs"
	@echo "  make restart    - Restart containers"
	@echo "  make clean      - Remove containers and data"
	@echo "  make test       - Run monitor.py locally"
	@echo "  make docker-build - Build image manually"
	@echo "  make docker-push  - Push image to Docker Hub"

