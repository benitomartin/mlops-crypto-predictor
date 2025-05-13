import time
from datetime import UTC, datetime

import mlflow
import pandas as pd
from loguru import logger
from risingwave import OutputFormat, RisingWave, RisingWaveConnOptions

from predictor.model_registry import get_model_name, load_model


def predict(
    mlflow_tracking_uri: str,
    risingwave_host: str,
    risingwave_port: int,
    risingwave_user: str,
    risingwave_password: str,
    risingwave_database: str,
    risingwave_schema: str,
    risingwave_input_table: str,
    risingwave_output_table: str,
    pair: str,
    prediction_horizon_seconds: int,
    candle_seconds: int,
    model_version: str | None = "latest",
    poll_interval_seconds: int = 5,
) -> None:
    """
    Generates a new prediction as soon as new data is available in the `risingwave_input_table`.

    Steps:
    1. Load the model from the MLflow model registry with the given `model_version`, if provided,
    otherwise load the latest model.
    2. Poll for new data in the `risingwave_input_table`.
    3. For each new or updated row, generate a prediction.
    4. Write the prediction to the `risingwave_output_table`.

    Args:
        mlflow_tracking_uri: The URI of the MLflow tracking server.
        risingwave_host: The host of the RisingWave server.
        risingwave_port: The port of the RisingWave server.
        risingwave_user: The user of the RisingWave server.
        risingwave_password: The password of the RisingWave server.
        risingwave_database: The database of the RisingWave server.
        risingwave_schema: The schema of the RisingWave server.
        risingwave_input_table: The input table of the RisingWave server.
        risingwave_output_table: The output table of the RisingWave server.
        pair: The pair of the asset to predict.
        prediction_horizon_seconds: The prediction horizon in seconds.
        candle_seconds: The candle seconds of the asset to predict.
        model_version: The version of the model to load from the MLflow model registry.
        poll_interval_seconds: The interval in seconds to poll for new data.
    """
    # Set MLflow tracking URI
    mlflow.set_tracking_uri(mlflow_tracking_uri)
    logger.info(f"Set MLflow tracking URI to {mlflow_tracking_uri}")

    # Step 1. Load the model from the MLflow model registry
    model_name = get_model_name(pair, candle_seconds, prediction_horizon_seconds)
    logger.info(f"Loading model {model_name} with version {model_version}")
    model, features = load_model(model_name, model_version)
    logger.info(f"Model loaded: {model}")

    # Step 2. Connect to RisingWave
    rw = RisingWave(
        RisingWaveConnOptions.from_connection_info(
            host=risingwave_host,
            port=risingwave_port,
            user=risingwave_user,
            password=risingwave_password,
            database=risingwave_database,
        )
    )

    # Use fully qualified table name if schema is provided
    fully_qualified_input_table = (
        f"{risingwave_schema}.{risingwave_input_table}" if risingwave_schema else risingwave_input_table
    )

    # Keep track of the latest timestamp we've processed
    last_processed_ts = 0

    logger.info(f"Starting polling loop for new data in {fully_qualified_input_table}")

    try:
        while True:
            # Query for new data
            query = f"""
            SELECT * FROM {fully_qualified_input_table}
            WHERE pair = '{pair}'
            AND candle_seconds = {candle_seconds}
            AND window_start_ms > {last_processed_ts}
            ORDER BY window_start_ms
            """

            data = rw.fetch(query, format=OutputFormat.DATAFRAME)

            if not data.empty:
                logger.info(f"Received {len(data)} new rows from {fully_qualified_input_table}")

                # Update the last processed timestamp
                last_processed_ts = data["window_start_ms"].max()

                # Filter for recent data only
                current_ms = int(datetime.now(UTC).timestamp() * 1000)
                data = data[data["window_start_ms"] > current_ms - 1000 * candle_seconds * 2]

                # Keep only the features columns
                prediction_data = data[features]

                if not prediction_data.empty:
                    # Generate predictions
                    predictions = model.predict(prediction_data)

                    # Prepare the output dataframe
                    output = pd.DataFrame()
                    output["predicted_price"] = predictions
                    output["pair"] = pair
                    output["ts_ms"] = int(datetime.now(UTC).timestamp() * 1000)
                    output["model_name"] = model_name
                    output["model_version"] = model_version

                    output["predicted_ts_ms"] = (
                        data["window_start_ms"] + (candle_seconds + prediction_horizon_seconds) * 1000
                    ).to_list()

                    logger.info(f"Writing {len(output)} predictions to table {risingwave_output_table}")

                    # Write dataframe to the output table
                    rw.insert(table_name=risingwave_output_table, data=output)

            # Sleep for the poll interval
            time.sleep(poll_interval_seconds)

    except KeyboardInterrupt:
        logger.info("Received keyboard interrupt, shutting down...")
    except Exception as e:
        logger.exception(f"Error in prediction loop: {e}")
        raise


if __name__ == "__main__":
    from predictor.config import predictor_config as config

    predict(
        mlflow_tracking_uri=config.mlflow_tracking_uri,
        risingwave_host=config.risingwave_host,
        risingwave_port=config.risingwave_port,
        risingwave_user=config.risingwave_user,
        risingwave_password=config.risingwave_password,
        risingwave_database=config.risingwave_database,
        risingwave_schema=config.risingwave_schema,
        risingwave_input_table=config.risingwave_input_table,
        risingwave_output_table=config.risingwave_output_table,
        pair=config.pair,
        prediction_horizon_seconds=config.prediction_horizon_seconds,
        candle_seconds=config.candle_seconds,
        model_version=config.model_version,
    )
