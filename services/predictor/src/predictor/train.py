# """
# The training script for the predictor service.

# Has the following steps:
# 1. Fetch data from RisingWave
# 2. Add target column
# 3. Validate the data
# 4. Profile it
# 5. Split into train/test
# 6. Baseline model
# 7. XGBoost model with default hyperparameters
# 8. Validate final model
# 9. Push model
# """

# from typing import Optional

# import mlflow
# import pandas as pd
# from loguru import logger
# from risingwave import OutputFormat, RisingWave, RisingWaveConnOptions


# def generate_exploratory_data_analysis_report(
#     ts_data: pd.DataFrame,
#     output_html_path: str,
# ):
#     """
#     Genearates an HTML file exploratory data analysis charts for the given `ts_data` and
#     saves it locally to the given `output_html_path`

#     Args:
#         ts_data:
#         output_html_file:
#     """
#     from ydata_profiling import ProfileReport

#     profile = ProfileReport(
#         ts_data, tsmode=True, sortby='window_start_ms', title='Technical indicators EDA'
#     )
#     profile.to_file(output_html_path)


# def validate_data(ts_data: pd.DataFrame):
#     """
#     Runs a battery of validation checks on the data.
#     If any of the checks fail, it raises an exception, so the training process can be aborted.
#     This way we ensure no model trained on bad data is pushed to the model registry.
#     """
#     import great_expectations as ge

#     ge_df = ge.from_pandas(ts_data)

#     validation_result = ge_df.expect_column_values_to_be_between(
#         column='close',
#         min_value=0,
#     )

#     if not validation_result.success:
#         raise Exception('Column "close" has values less than 0')

#     # TODO: Add more validation checks
#     # For example:
#     # - Check for null values
#     # - Check for duplicates
#     # - Check the data is sorted by timestamp
#     # - ...


# def load_ts_data_from_risingwave(
#     host: str,
#     port: int,
#     user: str,
#     password: str,
#     database: str,
#     pair: str,
#     days_in_past: int,
#     candle_seconds: int,
# ) -> pd.DataFrame:
#     """
#     Fetches technical indicators data from RisingWave for the given pair and time range.

#     Args:
#         host: str: The host of the RisingWave instance.
#         port: int: The port of the RisingWave instance.
#         user: str: The user to connect to RisingWave.
#         password: str: The password to connect to RisingWave.
#         database: str: The database to connect to RisingWave.
#         pair: str: The trading pair to fetch data for.
#         days_in_past: int: The number of days in the past to fetch data for.
#         candle_seconds: int: The candle duration in seconds.

#     Returns:
#         pd.DataFrame: A DataFrame containing the technical indicators data for the given pair.
#     """
#     logger.info('Establishing connection to RisingWave')
#     rw = RisingWave(
#         RisingWaveConnOptions.from_connection_info(
#             host=host, port=port, user=user, password=password, database=database
#         )
#     )
#     query = f"""
#     select
#         *
#     from
#         public.technical_indicators
#     where
#         pair='{pair}'
#         and candle_seconds='{candle_seconds}'
#         and to_timestamp(window_start_ms / 1000) > now() - interval '{days_in_past} days'
#     order by
#         window_start_ms;
#     """

#     ts_data = rw.fetch(query, format=OutputFormat.DATAFRAME)

#     logger.info(
#         f'Fetched {len(ts_data)} rows of data for {pair} in the last {days_in_past} days'
#     )

#     return ts_data


# def train(
#     mlflow_tracking_uri: str,
#     risingwave_host: str,
#     risingwave_port: int,
#     risingwave_user: str,
#     risingwave_password: str,
#     risingwave_database: str,
#     pair: str,
#     days_in_past: int,
#     candle_seconds: int,
#     prediction_horizon_seconds: int,
#     train_test_split_ratio: float,
#     n_rows_for_data_profiling: Optional[int] = None,
#     eda_report_html_path: Optional[str] = './eda_report.html',
# ):
#     """
#     Trains a predictor for the given pair and data, and if the model is good, it pushes
#     it to the model registry.
#     """
#     logger.info('Starting training process')

#     logger.info('Setting up MLflow tracking URI')
#     mlflow.set_tracking_uri(mlflow_tracking_uri)

#     logger.info('Setting up MLflow experiment')
#     from predictor.names import get_experiment_name

#     mlflow.set_experiment(
#         get_experiment_name(pair, candle_seconds, prediction_horizon_seconds)
#     )

#     # Things we want to log to MLflow:
#     # - The data we used to train the model
#     # - Parameters
#     # - EDA report
#     # - Model performance metrics

#     with mlflow.start_run():
#         logger.info('Starting MLflow run')

#         # Step 1. Load technical indicators data from RisingWave
#         ts_data = load_ts_data_from_risingwave(
#             host=risingwave_host,
#             port=risingwave_port,
#             user=risingwave_user,
#             password=risingwave_password,
#             database=risingwave_database,
#             pair=pair,
#             days_in_past=days_in_past,
#             candle_seconds=candle_seconds,
#         )

#         # Step 2. Add target column
#         ts_data['target'] = ts_data['close'].shift(
#             -prediction_horizon_seconds // candle_seconds
#         )
#         # drop rows for which the target is NaN
#         ts_data = ts_data.dropna(subset=['target'])

#         # log the data to MLflow
#         dataset = mlflow.data.from_pandas(ts_data)
#         mlflow.log_input(dataset, context='training')

#         # log dataset size
#         mlflow.log_param('ts_data_shape', ts_data.shape)

#         # Step 3. Validate the data
#         validate_data(ts_data)

#         # Step 4. Profile the data
#         # after the break
#         ts_data_to_profile = (
#             ts_data.head(n_rows_for_data_profiling)
#             if n_rows_for_data_profiling
#             else ts_data
#         )
#         generate_exploratory_data_analysis_report(
#             ts_data_to_profile, output_html_path=eda_report_html_path
#         )
#         logger.info('Pushing EDA report to MLflow')
#         mlflow.log_artifact(local_path=eda_report_html_path, artifact_path='eda_report')

#         # Step 5. Split into train/test
#         train_size = int(len(ts_data) * train_test_split_ratio)
#         train_data = ts_data[:train_size]
#         test_data = ts_data[train_size:]
#         mlflow.log_param('train_data_shape', train_data.shape)
#         mlflow.log_param('test_data_shape', test_data.shape)

#         # Step 6. Split data into features and target
#         X_train = train_data.drop(columns=['target'])
#         y_train = train_data['target']
#         X_test = test_data.drop(columns=['target'])
#         y_test = test_data['target']
#         mlflow.log_param('X_train_shape', X_train.shape)
#         mlflow.log_param('y_train_shape', y_train.shape)
#         mlflow.log_param('X_test_shape', X_test.shape)
#         mlflow.log_param('y_test_shape', y_test.shape)

#         # Step 7. Build a dummy baseline model
#         from predictor.models import BaselineModel

#         model = BaselineModel()
#         y_pred = model.predict(X_test)

#         from sklearn.metrics import mean_absolute_error

#         test_mae_baseline = mean_absolute_error(y_test, y_pred)
#         mlflow.log_metric('test_mae_baseline', test_mae_baseline)
#         logger.info(f'Test MAE for Baseline model: {test_mae_baseline:.4f}')


# if __name__ == '__main__':
#     train(
#         mlflow_tracking_uri='http://localhost:8283',
#         risingwave_host='localhost',
#         risingwave_port=4567,
#         risingwave_user='root',
#         risingwave_password='',
#         risingwave_database='dev',
#         pair='BTC/USD',
#         days_in_past=10,  # TODO: give a better name to this, for example training_data_horizon_days
#         candle_seconds=60,
#         prediction_horizon_seconds=300,
#         train_test_split_ratio=0.8,
#         n_rows_for_data_profiling=100,
#         eda_report_html_path='./eda_report.html',
#     # )
