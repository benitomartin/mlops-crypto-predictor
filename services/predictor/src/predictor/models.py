import os

import mlflow
import numpy as np
import optuna
import pandas as pd
from lazypredict.Supervised import LazyRegressor
from loguru import logger
from sklearn.impute import SimpleImputer
from sklearn.linear_model import HuberRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import StandardScaler


class BaselineModel:
    def __init__(self) -> None:
        """
        Provide initial parameters to initialize the model.
        """
        pass

    def fit(self, X: pd.DataFrame, y: pd.Series) -> None:
        """
        Fit the model to the data.
        """
        # Baseline model doesn't need to use X or y
        pass

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """
        Predict the target variable.
        """
        return X["close"]


# Define a custom type that can be either a string or a HuberRegressorWithHyperparameterTuning
# Model = Union[HuberRegressorWithHyperparameterTuning]


def get_best_model_candidate(model_candidates_from_best_to_worst: list[str]) -> "HuberRegressorWithHyperparameterTuning":
    """
    Factory function that returns a model from the given list of model candidates.
    It returns the first model that is found, which means the best model candidate.

    Args:
        model_candidates_from_best_to_worst: list[str], the list of model candidates from best to worst

    Returns:
        Model, the model
    """

    def _get_one_model(model_name: str) -> "HuberRegressorWithHyperparameterTuning":
        if model_name == "HuberRegressor":
            return HuberRegressorWithHyperparameterTuning()
        else:
            raise ValueError(f"Model {model_name} not found")

    model = None
    for model_name in model_candidates_from_best_to_worst:
        try:
            model = _get_one_model(model_name)
            break
        except Exception as e:
            logger.error(f"Model {model_name} not found: {e}")
            continue

    # TODO: we probably need to handle the edge case where no model is found

    if model is None:
        raise ValueError("No valid model found in the provided candidates")
    return model


class HuberRegressorWithHyperparameterTuning:
    """
    Fits a HuberRegressor with hyperparameter tuning.
    """

    def __init__(
        self,
        # hyperparameter_search_trials: Optional[int] = 0,
        # hyperparameter_splits: Optional[int] = 3
    ) -> None:
        """
        Initialize the model.
        """
        self.pipeline = self._get_pipeline()
        self.hyperparam_search_trials: int | None = None
        self.hyperparam_splits: int | None = None

    def fit(
        self,
        X: pd.DataFrame,
        y: pd.Series,
        hyperparameter_search_trials: int | None = 0,
        hyperparameter_splits: int | None = 3,
    ) -> None:
        """
        Fit the model to the data, possibly with hyperparameter tuning.

        Args:
            X: pd.DataFrame, the training data
            y: pd.Series, the target variable
            hyperparameter_search_trials: Optional[int], number of trials for hyperparameter search
            hyperparameter_splits: Optional[int], number of splits for cross-validation
        """
        self.hyperparam_search_trials = (
            int(hyperparameter_search_trials) if hyperparameter_search_trials is not None else None
        )
        self.hyperparam_splits = hyperparameter_splits

        # Filter out non-numeric columns
        X_numeric = X.select_dtypes(include=["number"])
        logger.info(f"Using {X_numeric.shape[1]} numeric features out of {X.shape[1]} total features")

        if self.hyperparam_search_trials == 0:
            logger.info("No hyperparameter search trials provided, fitting the model with default hyperparameters")
            self.pipeline.fit(X_numeric, y)

        else:
            logger.info(f"Let's find the best hyperparameters for the model with {self.hyperparam_search_trials} trials")
            best_hyperparameters = self._find_best_hyperparams(X, y)
            logger.info(f"Best hyperparameters: {best_hyperparameters}")
            self.pipeline = self._get_pipeline(best_hyperparameters)
            logger.info("Fitting the model with the best hyperparameters")
            self.pipeline.fit(X_numeric, y)

    def _get_pipeline(self, model_hyperparams: dict | None = None) -> Pipeline:
        """
        Get the pipeline with imputation for missing values.
        """
        if model_hyperparams is None:
            pipeline = Pipeline(
                steps=[
                    ("imputer", SimpleImputer(strategy="mean")),
                    ("preprocessor", StandardScaler()),
                    ("model", HuberRegressor()),
                ]
            )
        else:
            pipeline = Pipeline(
                steps=[
                    ("imputer", SimpleImputer(strategy="mean")),
                    ("preprocessor", StandardScaler()),
                    ("model", HuberRegressor(**model_hyperparams)),
                ]
            )
        return pipeline

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """
        Predict the target variable.
        """
        return self.pipeline.predict(X)

    def _find_best_hyperparams(
        self,
        X_train: pd.DataFrame,
        y_train: pd.Series,
    ) -> dict[str, float | int | bool]:
        """
        Finds the best hyperparameters for the model using Bayesian optimization.

        Args:
            X_train: pd.DataFrame, the training data
            y_train: pd.Series, the target variable

        Returns:
            dict[str, float | int | bool], the best hyperparameters
        """
        # Filter out non-numeric columns before starting optimization
        X_train_numeric = X_train.select_dtypes(include=["number"])
        logger.info(f"Using {X_train_numeric.shape[1]} numeric features out of {X_train.shape[1]} total features")

        def objective(trial: optuna.Trial) -> float:
            """
            Objective function for Optuna that returns the mean absolute error we
            want to minimize.

            Args:
                trial: optuna.Trial, the trial object

            Returns:
                float, the mean absolute error
            """
            # we ask Optuna to sample the next set of hyperparameters for the HuberRegressor
            # these are our candidates for this trial
            params = {
                "epsilon": trial.suggest_float("epsilon", 1.0, 99999999),
                "alpha": trial.suggest_float("alpha", 0.01, 1.0),
                "max_iter": trial.suggest_int("max_iter", 100, 1000),
                "tol": trial.suggest_float("tol", 1e-4, 1e-2),
                "fit_intercept": trial.suggest_categorical("fit_intercept", [True, False]),
            }

            # let's split our X_train into n_splits folds with a time-series split
            # we want to keep the time-series order in each fold
            # we will use the time-series split from sklearn
            from sklearn.model_selection import TimeSeriesSplit

            tscv = TimeSeriesSplit(n_splits=self.hyperparam_splits)
            mae_scores = []
            for train_index, val_index in tscv.split(X_train_numeric):
                # split the data into training and validation sets
                X_train_fold, X_val_fold = (
                    X_train_numeric.iloc[train_index],
                    X_train_numeric.iloc[val_index],
                )
                y_train_fold, y_val_fold = (
                    y_train.iloc[train_index],
                    y_train.iloc[val_index],
                )

                # build a pipeline with preprocessing and model steps
                self.pipeline = self._get_pipeline(model_hyperparams=params)

                # train the model on the training set
                self.pipeline.fit(X_train_fold, y_train_fold)

                # evaluate the model on the validation set
                y_pred = self.pipeline.predict(X_val_fold)
                mae = mean_absolute_error(y_val_fold, y_pred)
                mae_scores.append(mae)

            # return the average MAE across all folds
            return float(np.mean(mae_scores))

        # we create a study object that minimizes the objective function
        study = optuna.create_study(direction="minimize")

        # we run the trials
        logger.info(f"Running {self.hyperparam_search_trials} trials")
        study.optimize(objective, n_trials=self.hyperparam_search_trials)

        # we return the best hyperparameters
        return dict(study.best_trial.params)  # Convert to dict to ensure correct type


def get_model_candidates(
    X_train: pd.DataFrame,
    y_train: pd.Series,
    X_test: pd.DataFrame,
    y_test: pd.Series,
    n_candidates: int,
) -> list[str]:
    """
    Uses lazypredict to fit N models with default hyperparameters for the given
    (X_train, y_train), and evaluate them with (X_test, y_test)

    It returns a list of model names, from best to worst.

    Args:
        X_train: pd.DataFrame, the training data
        y_train: pd.Series, the target variable
        X_test: pd.DataFrame, the test data
        y_test: pd.Series, the target variable
        n_candidates: int, the number of candidates to return

    Returns:
        list[str], the list of model names from best to worst
    """
    # unset the MLFLOW_TRACKING_URI
    mlflow_tracking_uri = os.environ["MLFLOW_TRACKING_URI"]
    del os.environ["MLFLOW_TRACKING_URI"]

    # fit N models with default hyperparameters
    reg = LazyRegressor(verbose=0, ignore_warnings=False, custom_metric=mean_absolute_error)
    models, _ = reg.fit(X_train, X_test, y_train, y_test)

    # reset the index so that the model names are in the first column
    models.reset_index(inplace=True)

    # log table to mlflow experiment
    mlflow.log_table(models, "model_candidates_with_default_hyperparameters.json")

    # set the MLFLOW_TRACKING_URI back to its original value
    os.environ["MLFLOW_TRACKING_URI"] = mlflow_tracking_uri

    # list of top n_candidates model names
    model_candidates = models["Model"].tolist()[:n_candidates]

    return list(map(str, model_candidates))


# TODO: create a custom type called Model and use it to annotate things like the output of this function
def get_model_obj(model_name: str) -> "HuberRegressorWithHyperparameterTuning":
    """
    Factory function that returns a model object from the given model name.
    """
    if model_name == "HuberRegressor":
        return HuberRegressorWithHyperparameterTuning()
    else:
        raise ValueError(f"Model {model_name} not found")
