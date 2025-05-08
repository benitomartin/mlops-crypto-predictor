"""
The training script for the predictor service.

Has the following steps:
1. Fetch data from RisingWave
2. Add target column
3. Validate the data
4. Profile it
5. Split into train/test
6. Baseline model
7. XGBoost model with default hyperparameters
8. Validate final model
9. Push model
"""

import os

import mlflow
import pandas as pd
from loguru import logger
from risingwave import OutputFormat, RisingWave, RisingWaveConnOptions
from sklearn.metrics import mean_absolute_error
from ydata_profiling import ProfileReport

from predictor.data_validation import validate_data
from predictor.models import (
    BaselineModel,
    get_model_candidates,
    get_model_obj,
)
from predictor.names import get_experiment_name


def load_ts_data_from_risingwave(
    host: str,
    port: int,
    user: str,
    password: str,
    database: str,
    pair: str,
    training_data_horizon_days: int,
    candle_seconds: int,
) -> pd.DataFrame:
    """
    Fetches time-series data from a RisingWave database for a specified trading pair and time range.

    Args:
        host (str): Hostname or IP address of the RisingWave server.
        port (int): Port number for the database connection.
        user (str): Username for database authentication.
        password (str): Password for database authentication.
        database (str): Name of the database to connect to.
        pair (str): Trading pair symbol (e.g., 'BTC_USDT').
        training_data_horizon_days (int): Number of days of historical data to retrieve.
        candle_seconds (int): Candle interval in seconds (e.g., 60 for 1-minute candles).

    Returns:
        pd.DataFrame: DataFrame containing the fetched time-series data.
    """

    logger.info("Establishing connection to RisingWave")
    rw = RisingWave(
        RisingWaveConnOptions.from_connection_info(host=host, port=port, user=user, password=password, database=database)
    )
    query = f"""
            SELECT *
            FROM technical_indicators
            WHERE pair = '{pair}'
            AND candle_seconds = {candle_seconds}
            AND to_timestamp(window_start_ms / 1000) > now() - interval '{training_data_horizon_days} days'
            ORDER BY window_start_ms;
            """

    ts_data = rw.fetch(query, format=OutputFormat.DATAFRAME)

    logger.info(f"Fetched {len(ts_data)} rows of data for {pair} in the last {training_data_horizon_days} days")

    return ts_data


# def validate_data(ts_data: pd.DataFrame) -> None:
#     """
#     Validates the integrity of time-series data using Great Expectations.

#     Currently checks:
#         - 'close' column has all values >= 0

#     Raises:
#         Exception: If any validation check fails.

#     TODO:
#         - Check for null values in important columns
#         - Ensure there are no duplicate timestamps
#         - Confirm data is sorted by time (e.g., 'window_start_ms')
#         - Validate data types and expected ranges for other columns
#     """

#     ge_df = ge.from_pandas(ts_data)

#     validation_result = ge_df.expect_column_values_to_be_between(
#         column="close",
#         min_value=0,
#     )

#     if not validation_result.success:
#         raise Exception('Column "close" has values less than 0')

#     # TODO: Add more validation checks


def generate_exploratory_data_analysis_report(
    ts_data: pd.DataFrame,
    output_html_path: str,
) -> None:
    """
    Generates an Exploratory Data Analysis (EDA) report for time-series data using pandas-profiling.

    Creates a visual HTML report that summarizes the dataset's statistics, missing values,
    distributions, correlations, and time-based trends.

    Args:
        ts_data (pd.DataFrame): The time-series data to analyze.
        output_html_path (str): Path to save the generated HTML report.

    Returns:
        None
    """

    profile = ProfileReport(ts_data, tsmode=True, sortby="window_start_ms", title="Technical indicators EDA")

    profile.to_file(output_html_path)


def prepare_data(
    ts_data: pd.DataFrame,
    prediction_horizon_seconds: int,
    candle_seconds: int,
    train_test_split_ratio: float,
    features: list[str],
) -> tuple[pd.DataFrame, pd.Series, pd.DataFrame, pd.Series]:
    """
    Prepares time-series data for supervised learning by creating a prediction target and
    splitting the dataset into training and testing sets.

    The target is defined as the future 'close' value at the given prediction horizon.

    Args:
        ts_data (pd.DataFrame): Time-series data containing at least a 'close' column.
        prediction_horizon_seconds (int): Number of seconds into the future to predict.
        candle_seconds (int): Time interval of each candle/bar in seconds.
        train_test_split_ratio (float): Ratio of data to use for training (e.g., 0.8 for 80%).

    Returns:
        tuple: (X_train, y_train, X_test, y_test) where:
            - X_train (pd.DataFrame): Training features
            - y_train (pd.Series): Training targets
            - X_test (pd.DataFrame): Testing features
            - y_test (pd.Series): Testing targets
    """
    # Add target column by shifting 'close' into the future
    steps_ahead = prediction_horizon_seconds // candle_seconds
    ts_data = ts_data[features]  # Keep only the features we need
    ts_data["target"] = ts_data["close"].shift(-steps_ahead)

    # Drop rows with NaN target (due to shifting)
    ts_data = ts_data.dropna(subset=["target"])

    # Split into train/test sets
    train_size = int(len(ts_data) * train_test_split_ratio)
    train_data = ts_data.iloc[:train_size]
    test_data = ts_data.iloc[train_size:]

    # Split into features and target
    X_train = train_data.drop(columns=["target"])
    y_train = train_data["target"]
    X_test = test_data.drop(columns=["target"])
    y_test = test_data["target"]

    return X_train, y_train, X_test, y_test


def train(
    mlflow_tracking_uri: str,
    risingwave_host: str,
    risingwave_port: int,
    risingwave_user: str,
    risingwave_password: str,
    risingwave_database: str,
    pair: str,
    training_data_horizon_days: int,
    candle_seconds: int,
    prediction_horizon_seconds: int,
    train_test_split_ratio: float,
    features: list[str],
    hyperparam_search_trials: int = 5,
    model_name: str | None = None,
    n_model_candidates: int | None = 1,
    n_rows_for_data_profiling: int | None = None,
    eda_report_html_path: str | None = "./eda_report.html",
) -> None:
    """
    Orchestrates the ML training pipeline for a time-series forecasting task using technical indicators.

    The pipeline includes:
        - Data loading from RisingWave
        - Data validation and profiling
        - MLflow experiment tracking
        - Baseline model training and evaluation
        - (TODO) Advanced model training, validation, and registry push

    Args:
        mlflow_tracking_uri (str): URI for MLflow tracking server.
        risingwave_host (str): Hostname for RisingWave database.
        risingwave_port (int): Port number for RisingWave.
        risingwave_user (str): Username for RisingWave authentication.
        risingwave_password (str): Password for RisingWave authentication.
        risingwave_database (str): Database name in RisingWave.
        pair (str): Trading pair (e.g., 'BTC_USDT').
        training_data_horizon_days (int): Number of past days to fetch data for.
        candle_seconds (int): Candle size in seconds.
        prediction_horizon_seconds (int): Prediction horizon in seconds.
        train_test_split_ratio (float): Ratio of data for training vs testing.
        n_rows_for_data_profiling (int | None): Number of rows to use for profiling (default: all).
        eda_report_html_path (str | None): Output path for EDA HTML report (default: './eda_report.html').

    Returns:
        None
    """

    logger.info("Starting training process")

    # Setup MLflow
    logger.info("Setting up MLflow tracking URI")
    mlflow.set_tracking_uri(mlflow_tracking_uri)

    experiment_name = get_experiment_name(pair, candle_seconds, prediction_horizon_seconds)
    logger.info(f"Setting up MLflow experiment: {experiment_name}")
    mlflow.set_experiment(experiment_name)

    with mlflow.start_run():
        logger.info("Starting MLflow run")
        mlflow.log_param("features", features)
        mlflow.log_param("pair", pair)
        mlflow.log_param("training_data_horizon_days", training_data_horizon_days)
        mlflow.log_param("candle_seconds", candle_seconds)
        mlflow.log_param("prediction_horizon_seconds", prediction_horizon_seconds)
        mlflow.log_param("train_test_split_ratio", train_test_split_ratio)
        # mlflow.log_param('data_profiling_n_rows', data_profiling_n_rows)
        if model_name:
            mlflow.log_param("model_name", model_name)
        # mlflow.log_param(
        #     'max_percentage_diff_mae_wrt_baseline', max_percentage_diff_mae_wrt_baseline
        # )

        # Step 1. Load technical indicators data from RisingWave
        ts_data = load_ts_data_from_risingwave(
            host=risingwave_host,
            port=risingwave_port,
            user=risingwave_user,
            password=risingwave_password,
            database=risingwave_database,
            pair=pair,
            training_data_horizon_days=training_data_horizon_days,
            candle_seconds=candle_seconds,
        )

        # Log the dataset
        dataset = mlflow.data.from_pandas(ts_data)
        mlflow.log_input(dataset, context="training")

        # Log parameters
        mlflow.log_params(
            {
                "ts_data_shape": ts_data.shape,
                "pair": pair,
                "training_data_horizon_days": training_data_horizon_days,
                "candle_seconds": candle_seconds,
                "prediction_horizon_seconds": prediction_horizon_seconds,
                "train_test_split_ratio": train_test_split_ratio,
            }
        )

        # Step 2 & 5. Prepare data (add target column and split)
        X_train, y_train, X_test, y_test = prepare_data(
            ts_data,
            prediction_horizon_seconds,
            candle_seconds,
            train_test_split_ratio,
            features,
        )

        # Log dataset info
        mlflow.log_params(
            {
                "ts_data_shape": ts_data.shape,
                "X_train_shape": X_train.shape,
                "y_train_shape": y_train.shape,
                "X_test_shape": X_test.shape,
                "y_test_shape": y_test.shape,
            }
        )

        # Log the data to MLflow
        ts_data_csv_path = "./ts_data.csv"
        ts_data.to_csv(ts_data_csv_path, index=False)
        mlflow.log_artifact(ts_data_csv_path, artifact_path="training_data")
        os.remove(ts_data_csv_path)  # Clean up

        # Step 3. Validate the data
        validate_data(ts_data, max_percentage_rows_with_missing_values=5)  # Example value

        # Step 4. Profile the data
        if eda_report_html_path is not None:
            ts_data_to_profile = ts_data.head(n_rows_for_data_profiling) if n_rows_for_data_profiling else ts_data

            generate_exploratory_data_analysis_report(ts_data_to_profile, output_html_path=eda_report_html_path)

            logger.info("Pushing EDA report to MLflow")
            mlflow.log_artifact(local_path=eda_report_html_path, artifact_path="eda_report")

        # Step 6. Build a baseline model
        logger.info("Training baseline model")
        baseline_model = BaselineModel()
        baseline_model.fit(X_train, y_train)
        y_pred_baseline = baseline_model.predict(X_test)

        test_mae_baseline = mean_absolute_error(y_test, y_pred_baseline)
        mlflow.log_metric("test_mae_baseline", test_mae_baseline)
        logger.info(f"Test MAE for Baseline model: {test_mae_baseline:.4f}")

        # Step 8. Find the best candidate model, if `model_name` is not provided.
        if model_name is None:
            # We fit N models with default hyperparameters for the given
            # (X_train, y_train), and evaluate them with (X_test, y_test)
            # to find the best `n_model_candidates` models
            if n_model_candidates is None:
                raise ValueError("n_model_candidates cannot be None")

            model_names = get_model_candidates(X_train, y_train, X_test, y_test, n_candidates=n_model_candidates)

            # TODO: this is a hack that works when we have only one candidate model
            # How would you modify this code to use a list of candiate models, and adjust
            # their hyperparameters in the next step?
            model_name = model_names[0]

        model = get_model_obj(model_name)

        # Step 9. Train the choosen model with hyperparameter search.
        logger.info(f"Start training model {model} with hyperparameter search")
        model.fit(X_train, y_train, hyperparameter_search_trials=hyperparam_search_trials)

        # Step 10. Validate the model
        y_pred = model.predict(X_test)
        test_mae = mean_absolute_error(y_test, y_pred)
        mlflow.log_metric("test_mae", test_mae)
        logger.info(f"Test MAE for model {model}: {test_mae:.4f}")

        # # Step 11. Push the model to the model registry
        # mae_diff = (test_mae - test_mae_baseline) / test_mae_baseline
        # if mae_diff <= max_percentage_diff_mae_wrt_baseline:
        #     logger.info(
        #         f'Model MAE is {mae_diff:.4f} < {max_percentage_diff_mae_wrt_baseline}'
        #     )
        #     logger.info('Pushing model to the registry')
        #     model_name = get_model_name(
        #         pair, candle_seconds, prediction_horizon_seconds
        #     )
        #     push_model(model, X_test, model_name)
        # else:
        #     logger.info(
        #         f'The model {model_name} MAE is {mae_diff:.4f} > {max_percentage_diff_mae_wrt_baseline}'
        #     )
        #     logger.info('Model NOT PUSHED to the registry')


if __name__ == "__main__":
    from predictor.config import training_config as config

    train(
        mlflow_tracking_uri=config.mlflow_tracking_uri,
        risingwave_host=config.risingwave_host,
        risingwave_port=config.risingwave_port,
        risingwave_user=config.risingwave_user,
        risingwave_password=config.risingwave_password,
        risingwave_database=config.risingwave_database,
        pair=config.pair,
        training_data_horizon_days=config.training_data_horizon_days,
        candle_seconds=config.candle_seconds,
        prediction_horizon_seconds=config.prediction_horizon_seconds,
        train_test_split_ratio=config.train_test_split_ratio,
        features=config.features,
        hyperparam_search_trials=config.hyperparam_search_trials,
        model_name=config.model_name,
        n_model_candidates=config.n_model_candidates,
        n_rows_for_data_profiling=config.n_rows_for_data_profiling,
        eda_report_html_path=config.eda_report_html_path,
    )
