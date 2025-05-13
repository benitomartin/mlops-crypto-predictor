# Makefile

.PHONY: dev all ruff mypy clean help

service ?= trades


################################################################################
## Kind Cluster
################################################################################

start-kind-cluster: ## Start the Kind cluster
	@echo "Starting the Kind cluster..."
	docker start rwml-34fa-control-plane
	@echo "Kind cluster started."

stop-kind-cluster: ## Stop the Kind cluster
	@echo "Stopping the Kind cluster..."
	docker stop rwml-34fa-control-plane
	@echo "Kind cluster stopped."


################################################################################
## Port Forwarding
################################################################################

tmux-port-forward-kafka: ## Port forward the Kafka UI with tmux
	@echo "Port forwarding the Kafka UI with tmux..."
	tmux new-session -d 'kubectl port-forward -n kafka svc/kafka-ui 8182:8080'
	@echo "Port forwarding complete. You can access the Kafka UI at http://localhost:8182"

tmux-port-forward-risingwave: ## Port forward the RisingWave UI with tmux
	@echo "Port forwarding the RisingWave UI with tmux..."
	tmux new-session -d 'kubectl port-forward svc/risingwave -n risingwave 4567:4567'
	@echo "Port forwarding complete. You can access the RisingWave UI at http://localhost:4567"

tmux-port-forward-grafana: ## Port forward the Grafana UI with tmux
	@echo "Port forwarding the Grafana UI with tmux..."
	tmux new-session -d 'kubectl port-forward -n monitoring svc/grafana 3000:80'
	@echo "Port forwarding complete. You can access the Grafana UI at http://localhost:3000"

tmux-port-forward-minio: ## Port forward the Minio UI with tmux
	@echo "Port forwarding the Minio UI with tmux..."
	tmux new-session -d 'kubectl port-forward -n risingwave svc/risingwave-minio 9001:9001'
	@echo "Port forwarding complete. You can access the Minio UI at http://localhost:9001"

tmux-port-forward-mlflow: ## Port forward the MLflow UI with tmux
	@echo "Port forwarding the MLflow UI with tmux..."
	tmux new-session -d 'kubectl port-forward -n mlflow svc/mlflow-tracking 8889:80'
	@echo "Port forwarding complete. You can access the MLflow UI at http://localhost:8889"

# ################################################################################
# ## Development Trades/Candles
# ################################################################################

dev-live: ## Run the service (default is live)
	uv run services/${service}/src/${service}/main.py

dev-historical: ## Run the service in historical mode
	KAFKA_TOPIC_NAME=trades_historical \
	LIVE_OR_HISTORICAL=historical \
	uv run services/${service}/src/${service}/main.py

build-for-dev: ## Build the service for development
	@echo "Building ${service} service..."
	docker build --build-arg SERVICE_NAME=${service} -t ${service}:dev -f docker/Dockerfile .
	@echo "Build complete for ${service}:dev"

push-for-dev: ## Push the service to the docker registry of the Kind cluster
	@echo "Pushing ${service} service to the docker registry of the Kind cluster..."
	kind load docker-image ${service}:dev --name rwml-34fa
	@echo "Push complete for ${service}:dev"

deploy-for-dev: build-for-dev push-for-dev ## Deploy the service to the Kind cluster
	@echo "Deploying ${service} service to the Kind cluster..."
	kubectl delete -f deployments/dev/${service}/${service}.yaml --ignore-not-found
	@echo "Deployment deleted for ${service}"
	sleep 5
	@echo "Waiting 5 seconds..."

	@echo "Deploying ${service} service to the Kind cluster..."
	kubectl apply -f deployments/dev/${service}/${service}.yaml
	@echo "Deployment complete for ${service}"


################################################################################
## Production Trades/Candles
################################################################################

## NOTE: # The linux/arm64 platform is not supported with non-root users creation as the Dockerfile is currently defined

# build-and-push-for-prod: ## Build and push the service for production
# 	@echo "Building ${service} service for production..."
# 	@export BUILD_DATE=$$(date +%s) && \
# 	docker buildx build --push \
# 		--platform linux/amd64 \
# 		--build-arg SERVICE_NAME=${service} \
# 		-t ghcr.io/benitomartin/${service}:latest \
# 		-t ghcr.io/benitomartin/${service}:0.1.5-beta.$${BUILD_DATE} \
# 		-f docker/Dockerfile .

build-and-push-for-prod: ## Build and push the service for production
	@echo "Building ${service} service for production..."
	@BUILD_DATE=$$(date +%s) && \
	CREATED=$$(date -u +%Y-%m-%dT%H:%M:%SZ) && \
	GIT_REVISION=$$(git rev-parse HEAD) && \
	docker buildx build --push \
		--platform linux/amd64 \
		--build-arg SERVICE_NAME=${service} \
		-t ghcr.io/benitomartin/${service}:latest \
		-t ghcr.io/benitomartin/${service}:0.1.5-beta.$$BUILD_DATE \
		-t ghcr.io/benitomartin/${service}:sha-$$GIT_REVISION \
		--label org.opencontainers.image.revision=$$GIT_REVISION \
		--label org.opencontainers.image.created=$$CREATED \
		--label org.opencontainers.image.url="https://github.com/benitomartin/mlops-llm-crypto-predictor/docker/Dockerfile" \
		--label org.opencontainers.image.title="${service}" \
		--label org.opencontainers.image.description="${service} Dockerfile" \
		--label org.opencontainers.image.licenses="MIT" \
		--label org.opencontainers.image.source="https://github.com/benitomartin/mlops-llm-crypto-predictor" \
		-f docker/Dockerfile .


deploy-for-prod: ## Deploy the service to production
	@echo "Deploying ${service} service to production..."
	kubectl delete -f deployments/prod/${service}/${service}.yaml --ignore-not-found
	@echo "Deployment deleted for ${service}"
	sleep 5
	@echo "Waiting 5 seconds..."

	@echo "Deploying ${service} service to production..."
	kubectl apply -f deployments/prod/${service}/${service}.yaml
	@echo "Deployment complete for ${service}"

# ################################################################################
# ## Development Technical Indicators
# ################################################################################

dev-ti: ## Run the technical indicators service
	uv run services/technical_indicators/src/technical_indicators/main.py

build-for-dev-ti: ## Build the technical indicators service for development
	@echo "Building technical indicators service..."
	docker build --build-arg SERVICE_NAME=technical_indicators -t technical-indicators:dev -f docker/ti.Dockerfile .
	@echo "Build complete for technical-indicators:dev"

push-for-dev-ti: ## Push the technical indicators service to the docker registry of the Kind cluster
	@echo "Pushing technical indicators service to the docker registry of the Kind cluster..."
	kind load docker-image technical-indicators:dev --name rwml-34fa
	@echo "Push complete for technical-indicators:dev"

deploy-for-dev-ti: build-for-dev-ti push-for-dev-ti ## Deploy the technical indicators service to the Kind cluster
	@echo "Deploying technical_indicators service to the Kind cluster..."
	kubectl delete -f deployments/dev/technical_indicators/technical-indicators-d.yaml --ignore-not-found
	@echo "Deployment deleted for technical_indicators"
	sleep 5
	@echo "Waiting 5 seconds..."

	@echo "Deploying technical_indicators service to the Kind cluster..."
	kubectl apply -f deployments/dev/technical_indicators/technical-indicators-d.yaml
	@echo "Deployment complete for technical indicators"


# ################################################################################
# ## Production Technical Indicators
# ################################################################################

# ## NOTE: # The linux/arm64 platform is not supported with non-root users creation as the Dockerfile is currently defined

# build-and-push-for-prod: ## Build and push the trades service for production
# 	@echo "Building ${service} service for production..."
# 	@export BUILD_DATE=$$(date +%s) && \
# 	docker buildx build --push \
# 		--platform linux/amd64 \
# 		--build-arg SERVICE_NAME=${service} \
# 		-t ghcr.io/benitomartin/${service}:latest \
# 		-t ghcr.io/benitomartin/${service}:0.1.5-beta.$${BUILD_DATE} \
# 		-f docker/Dockerfile .

build-and-push-for-prod-ti: ## Build and push the service for production
	@echo "Building ${service} service for production..."
	@BUILD_DATE=$$(date +%s) && \
	CREATED=$$(date -u +%Y-%m-%dT%H:%M:%SZ) && \
	GIT_REVISION=$$(git rev-parse HEAD) && \
	docker buildx build --push \
		--platform linux/amd64 \
		--build-arg SERVICE_NAME=${service} \
		-t ghcr.io/benitomartin/${service}:latest \
		-t ghcr.io/benitomartin/${service}:0.1.5-beta.$$BUILD_DATE \
		-t ghcr.io/benitomartin/${service}:sha-$$GIT_REVISION \
		--label org.opencontainers.image.revision=$$GIT_REVISION \
		--label org.opencontainers.image.created=$$CREATED \
		--label org.opencontainers.image.url="https://github.com/benitomartin/mlops-llm-crypto-predictor/docker/ti.Dockerfile" \
		--label org.opencontainers.image.title="${service}" \
		--label org.opencontainers.image.description="${service} Dockerfile" \
		--label org.opencontainers.image.licenses="MIT" \
		--label org.opencontainers.image.source="https://github.com/benitomartin/mlops-llm-crypto-predictor" \
		-f docker/Dockerfile .

# deploy-for-prod: ## Deploy the service to production
# 	@echo "Deploying ${service} service to production..."
# 	kubectl delete -f deployments/prod/${service}/${service}.yaml --ignore-not-found
# 	@echo "Deployment deleted for ${service}"
# 	sleep 5
# 	@echo "Waiting 5 seconds..."

# 	@echo "Deploying ${service} service to production..."
# 	kubectl apply -f deployments/prod/${service}/${service}.yaml
# 	@echo "Deployment complete for ${service}"


################################################################################
## Backfill
################################################################################

deploy-backfill: ## Deploy the backfill service to the Kind cluster
	@echo "Deploying ${service} service to the Kind cluster..."
	kubectl delete -f deployments/dev/${service}/${service}.yaml --ignore-not-found
	@echo "Deployment deleted for ${service}"
	sleep 5
	@echo "Waiting 5 seconds..."

	@echo "Deploying ${service} service to the Kind cluster..."
	kubectl apply -f deployments/dev/${service}/${service}.yaml
	@echo "Deployment complete for ${service}"

#################################################################################
## Training
#################################################################################

build-for-dev-training: ## Build the training service for development
	@echo "Building training service..."
	docker build --build-arg SERVICE_NAME=predictor -t training-pipeline:dev -f docker/training-pipeline.Dockerfile .
	@echo "Build complete for training-pipeline:dev"

push-for-dev-training: build-for-dev-training ## Push the training service to the docker registry of the Kind cluster
	@echo "Pushing training service to the docker registry of the Kind cluster..."
	kind load docker-image training-pipeline:dev --name rwml-34fa
	@echo "Push complete for training-pipeline:dev"



cron-kustomize: ## Deploy the training service to the Kind cluster
	@echo "Deploying training service to the Kind cluster..."
	kubectl apply -k deployments/dev/training-pipeline
	@echo "Deployment complete for training service"


################################################################################
## Minio Secret
################################################################################

minio-secret: ## Create the Minio secret
	@echo "Creating the Minio secret..."
	kubectl apply -f deployments/dev/kind/manifests/mlflow-minio-secret.yaml
	@echo "Minio secret created."

################################################################################
## Linting and Formatting
################################################################################

all: ruff mypy clean ## Run all linting and formatting commands

ruff: ## Run Ruff linter
	@echo "Running Ruff linter..."
	uv run ruff check . --fix --exit-non-zero-on-fix
	@echo "Ruff linter complete."

mypy: ## Run MyPy static type checker
	@echo "Running MyPy static type checker..."
	uv run mypy
	@echo "MyPy static type checker complete."

clean: ## Clean up cached generated files
	@echo "Cleaning up generated files..."
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	@echo "Cleanup complete."


################################################################################
## Help Command
################################################################################

help: ## Display this help message
	@echo "Default target: $(.DEFAULT_GOAL)"
	@echo "Available targets:"
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "\033[36m%-30s\033[0m %s\n", $$1, $$2}' $(MAKEFILE_LIST)

.DEFAULT_GOAL := help
