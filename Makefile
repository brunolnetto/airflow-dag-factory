# File: Makefile

.PHONY: help install test lint format validate deploy-local clean

help: ## Show this help message
	@echo "DAG Factory Development Commands:"
	@echo ""
	@grep -E '^[a-zA-Z_-]+:.*?## .*$' $(MAKEFILE_LIST) | sort | awk 'BEGIN {FS = ":.*?## "}; {printf "  %-20s %s\n", $1, $2}'

install: ## Install development dependencies
	pip install -r requirements-dev.txt
	pip install -e .

test: ## Run all tests
	pytest dags/tests/ -v --cov=dag_factory --cov-report=html

test-fast: ## Run tests without coverage
	pytest dags/tests/ -v -x

lint: ## Run linting
	flake8 dags/ --max-line-length=120 --exclude=tests/
	pylint dags/dag_factory.py dags/functions/

format: ## Format code
	black dags/ --line-length=120
	isort dags/ --profile=black

validate: ## Validate all configurations
	@echo "Validating DAG configurations..."
	@for config in dags/configs/*.yaml; do \
		echo "Validating $config..."; \
		python dags/scripts/validate_config.py "$config" || exit 1; \
	done
	@echo "✅ All configurations are valid"

generate-test: ## Test DAG generation
	@echo "Testing DAG generation..."
	@cd dags && python -c "from dag_factory import DAGFactory; factory = DAGFactory('configs'); dags = list(factory.generate_dags_from_directory()); print(f'✅ Generated {len(dags)} DAGs')"

security-scan: ## Run security scans
	bandit -r dags/ -ll
	safety check

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
	rm -rf build/ dist/ .coverage htmlcov/ .pytest_cache/

build-docs: ## Build documentation
	cd docs && make html

serve-docs: ## Serve documentation locally
	cd docs/_build/html && python -m http.server 8000