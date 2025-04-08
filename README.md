# mlops-llm-crypto-predictor

## Initialize the Project

Initialize the project from the root directory. This will create the main `pyproject.toml` file.

```bash
uv init
```

Create a `trades` workspace in the `services` directory. This will create a `pyproject.toml` file in the `trades` workspace, with the `src` layout, and incllude the `hatchling` build-system.

```bash
cd services
uv init --lib trades
```

### Adding Dependencies

To add dependencies to the main project, use the following command:

```bash
uv add quixstreams
```

To add local dependencies for development (`dependency-groups`) use the following command:

```bash
uv add --group tests pytest
```

### Synchronize the Project

To synchronize the project without installing the dependency groups, use the following command:

```bash
uv sync --all-groups 
```

To synchronize the project and install the dependency groups, use the following command:

```bash
uv sync --all
```

## Setting up Kafka

To setup Kafka, we need first to create a Kind cluster with port mapping.

There are several scripts and folders in the `deployments/dev/kind` directory.

* `kind-with-portmapping.yaml`: This is the Kind configuration file. It includes the port mapping for Kafka.
* `manifests`: This folder contains the Kafka configuration files.
  * `kafka-e11b.yaml`: This is the Kafka configuration file. It includes the port mapping for Kafka.
  * `kafka-ui-all-in-one.yaml`: This is the Kafka UI configuration file. It includes the port mapping for Kafka UI.
* `install_kafka.sh`: This script installs Kafka using [Strimzi](https://strimzi.io/quickstarts/) that allows to use Kafka in Kubernetes. It uses the `kafka-e11b.yaml` configuration file.
* `install_kafka_ui.sh`: This script installs Kafka UI to make it easier to manage Kafka in a Web UI. It uses the `kafka-ui-all-in-one.yaml` configuration file.
* `create_cluster.sh`: This script runs all the previous scripts in order to create the Kind cluster with Kafka and Kafka UI.

Once you run the `create_cluster.sh` script (with docker running), you should see the following output in the `k9s` terminal:

```bash
chmod +x create_cluster.sh
./create_cluster.sh
```

![create cluster](images/create_cluster_k9s.png)

If we type `svc` in the `k9s` terminal, we should see the following output and the port mapping for Kafka and Kafka UI `8080`:

![kafka ui k9s](images/kafka_ui_k9s.png)

To visualize the Kafka UI, it is necessary to forward the port `8080` from the `kafka-ui` service (which communicates internally with the Kafka cluster on port `9092`) to port `8182` (or any other free port) on your local machine. This means that any traffic sent to `http://localhost:8182` on your local machine will be forwarded to the `kafka-ui` service running inside the Kubernetes cluster on port `8080`.

```bash
kubectl -n kafka port-forward svc/kafka-ui 8182:8080 
```

Now you can access the Kafka UI in your local machine at `http://localhost:8182` or `http://127.0.0.1:8182`.

![kafka ui web](images/kafka_ui_web.png)

You can test the connection to the Kafka broker on TCP port `31234` with the following command:

```bash
nc -vvv localhost 31234
```

nc -vvv 172.100.0.2 31092
