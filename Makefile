# File: Makefile

.PHONY: help install test lint format validate deploy-local clean dev-install

help: ## Show this help message
	@echo "DAG Factory Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $1, $2}'

install: ## Install package for production
	uv pip install .

dev-install: ## Install development dependencies with uv
	uv pip install -e ".[dev]"

test: ## Run all tests
	pytest tests/ -v --cov=src --cov-report=html

test-fast: ## Run tests without coverage
	pytest tests/ -v -x

lint: ## Run linting with ruff
	ruff check src/ tests/
	mypy src/

format: ## Format code with black and ruff
	black src/ tests/ --line-length=120
	ruff --fix src/ tests/

validate: ## Validate all configurations
	@echo "Validating DAG configurations..."
	@for config in dags/configs/*.yaml; do \
		echo "Validating $$config..."; \
		python -m src.cli validate "$$config" || exit 1; \
	done
	@echo "✅ All configurations are valid"

generate-test: ## Test DAG generation
	@echo "Testing DAG generation..."
	@python -m src.cli list-templates --verbose

security-scan: ## Run security scans
	ruff check --select S src/ tests/
	bandit -r src/ -ll

build: ## Build package
	uv build

publish: ## Publish to PyPI
	uv publish

deploy-local: ## Deploy to local Docker environment
	docker-compose -f docker/docker-compose.dag-factory.yml up -d
	@echo "🚀 Local Airflow with DAG Factory is starting..."
	@echo "   Web UI: http://localhost:8080"
	@echo "   Username: admin"
	@echo "   Password: admin"

stop-local: ## Stop local Docker environment
	docker-compose -f docker/docker-compose.dag-factory.yml down

clean: ## Clean up build artifacts
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	find . -type d -name "*.egg-info" -exec rm -rf {} +
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/ .ruff_cache/

build-docs: ## Build documentation with mkdocs
	mkdocs build

serve-docs: ## Serve documentation locally
	mkdocs serve