.PHONY: up down backend-test web-test agent-test protocol-test

up:
	docker compose -f infra/docker/docker-compose.yml up --build

down:
	docker compose -f infra/docker/docker-compose.yml down

backend-test:
	cd backend && python -m pytest

web-test:
	cd web && npm test -- --run

agent-test:
	dotnet test agents/windows/DeviceMesh.Agent.sln

protocol-test:
	cd backend && python -m pytest tests/contract
