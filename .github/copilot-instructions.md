# AI coding agent guidelines for airflow-dag-factory

Purpose: make productive edits fast by following existing patterns and validating configs early.

## Big picture
- Code-first DAG factory for Apache Airflow. Generates DAGs from YAML/JSON and exposes them via globals so Airflow discovers on import.
- Core (see `dag_factory.py`): OperatorRegistry (maps `dummy|bash|python|email` -> operator classes, validates params); ConfigurationValidator (JSON Schema + business rules incl. cycles); TaskBuilder (builds tasks; resolves `python_callable` from import string); AssetManager (Airflow Datasets for `consumes/produces`); DAGFactory (env-var substitution, DAG creation, dependencies/groups/assets, metrics).
- Enhanced features: TemplateManager (`template_management.py`) for inheritance; EnvironmentManager for dev/staging/prod overrides; SecurityManager (`security_manager.py`) for encryption/access control/audit logging; Self-service UI (`self_service_ui.py`) for non-technical users.
- Monitoring (`dag_factory_monitor.py`): Prometheus metrics + health-check DAG `dag_factory_health_monitoring`.

## Conventions
- Config dir: `dags/configs` (files: `.yaml|.yml|.json`). Templates: `dags/templates`. Security: `dags/security`.
- Template inheritance: `template.extends: "base_template"` + `template.overrides` for specific changes.
- Environment overrides: `environments.dev|staging|prod` sections with env-specific configs.
- Env var substitution in configs: `${VAR}` or `${VAR:-default}`; applied recursively to strings.
- DAG ID preferred prefixes: `etl_`, `ml_`, `reporting_`, `data_quality_` (non-blocking warning).
- Schedule: `@...`, `cron(...)`, or crontab. If `assets.consumes` set, schedule uses Datasets.
- Task fields: `task_id`, `operator`; optional `depends_on`, `parameters`, `retries`, `retry_delay` (seconds), `pool`, `priority_weight`.
- Operator params: bash→`bash_command`; python→`python_callable` (import path ok); email→`to`,`subject`.
- Task groups: define in `task_groups` and list `tasks` to assign.
- Assets: `assets.consumes|produces` become `Dataset`s; produced assets set on `task.outlets`.

## Workflows (PowerShell examples)
- Setup: `pip install -r requirements-dev.txt`; then `pip install -e .` (or `make install` on Unix).
- Enhanced CLI: `python .\enhanced_dag_factory_cli.py [command] [options]`.
- Validate with environment: `python .\enhanced_dag_factory_cli.py validate .\dags\configs\my_dag.yaml --environment prod --username alice`.
- Generate with template: `python .\enhanced_dag_factory_cli.py generate .\dags\configs\my_dag.yaml --dry-run --environment staging`.
- List templates: `python .\enhanced_dag_factory_cli.py list-templates --verbose`.
- Security management: `python .\enhanced_dag_factory_cli.py security list-users`.
- Self-service UI: `python .\enhanced_dag_factory_cli.py ui --port 5000`.
- Tests/lint/format: `pytest dags/tests -v`; `flake8 dags/ --max-line-length=120`; `black dags/ --line-length=120`; `isort dags/ --profile=black`.
- Local Airflow (if docker compose file present): `docker-compose -f docker/docker-compose.dag-factory.yml up -d` (UI http://localhost:8080).

## Extending
- New template: create `.yaml` in `dags/templates/` with `description`, `tags`, `tasks`, and optional `template.extends`.
- New operator: `from dag_factory import factory; factory.register_custom_operator('custom_python', PythonOperator, ['python_callable'], ['op_args','op_kwargs'])`; config uses `operator: custom_python` with `parameters.python_callable: 'pkg.mod.func'`.
- Security roles: edit `dags/security/roles.yaml` to add users/roles/permissions.
- New config fields: add to `CONFIG_SCHEMA` and consume in `DAGFactory.create_dag` or `TaskBuilder._process_parameters`.

## Minimal template example
```yaml
# dags/templates/simple_etl.yaml
description: "Simple ETL template"
tags: [etl, template]
tasks:
  - task_id: extract
    operator: python
    parameters: { python_callable: "etl.extract" }
  - task_id: load
    operator: python
    parameters: { python_callable: "etl.load" }
    depends_on: [extract]
```

## Minimal config with inheritance
```yaml
# dags/configs/my_etl.yaml
template:
  extends: simple_etl
dag_id: etl_example
schedule: "@daily"
start_date: "2024-01-01"
environments:
  dev: { schedule: "@once" }
  prod: { email: ["ops@company.com"] }
```

## Gotchas
- Template cycles fail validation; use `template.extends` chain carefully.
- Environment configs completely override arrays (use `template.overrides` for merging).
- Dependency cycles/missing `depends_on` targets fail validation.
- `email_on_failure: true` without `email` only warns; add recipients to notify.
- `python_callable` import path must resolve in the runtime.
- Import-time DAG registration via `globals()`; avoid heavy side effects in modules referenced at import.
- Security features require `--enable-security` flag and proper `dags/security/roles.yaml`.

Key files: `dag_factory.py` (core), `template_management.py` (inheritance), `security_manager.py` (security), `self_service_ui.py` (web UI), `enhanced_dag_factory_cli.py` (CLI), `dag_factory_monitor.py` (monitoring), `requirements-*.txt`.
