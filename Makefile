.PHONY: up down restart logs test lint happy-path chaos-slow chaos-error chaos-flaky chaos-kill reset-chaos load-test

up:
	docker compose up --build -d

down:
	docker compose down

restart:
	docker compose restart

logs:
	docker compose logs -f

test:
	cd services/orders-service && pip install -q -r requirements.txt && pytest tests/ -v
	cd services/inventory-service && pip install -q -r requirements.txt && pytest tests/ -v

lint:
	ruff check services/orders-service/app services/inventory-service/app

happy-path:
	bash scripts/run_happy_path.sh

chaos-slow:
	bash scripts/chaos_slow_dependency.sh

chaos-error:
	bash scripts/chaos_error_dependency.sh

chaos-flaky:
	bash scripts/chaos_flaky_dependency.sh

chaos-kill:
	bash scripts/chaos_kill_inventory.sh

reset-chaos:
	bash scripts/reset_chaos.sh

load-test:
	bash scripts/load_test.sh
