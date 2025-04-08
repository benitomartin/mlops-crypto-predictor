# mlops-llm-crypto-predictor

## Initialize the Project

Initialize the project from the root directory. This will create the main `pyproject.toml` file.

```bash
uv init
```

Create a workspace in the `services` directory. This will create a `pyproject.toml` file in the `trades` workspace, with the `src` layout. And incllude the `hatchling` build-system in the main `pyproject.toml`.

```bash
cd services
uv init --lib trades
```

## Setting up Kafka

To setup Kafka, we need first to create a Kind cluster with port mapping.

There are several scripts and folders in the `deployments/dev/kind` directory.

* `kind-with-portmapping.yaml`: This is the Kind configuration file. It includes the port mapping for Kafka.
* `manifests`: This folder contains the Kafka configuration files.
  * `kafka-e11b.yaml`: This is the Kafka configuration file. It includes the port mapping for Kafka.
  * `kafka-ui-all-in-one.yaml`: This is the Kafka UI configuration file. It includes the port mapping for Kafka UI.
* `install_kafka.sh`: This script installs Kafka using [Strimzi](https://strimzi.io/quickstarts/) that allows to use Kafka in Kubernetes. It uses the `kafka-e11b.yaml` configuration file.
* `install_kafka_ui.sh`: This script installs Kafka UI. It uses the `kafka-ui-all-in-one.yaml` configuration file.
* `create_cluster.sh`: This script runs all the previous scripts in order to create the Kind cluster with Kafka and Kafka UI.


![Image](https://github.com/user-attachments/assets/e8061fa6-3e64-4240-9e9a-5694d4ced178)