import pandas as pd


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
        pass

    def predict(self, X: pd.DataFrame) -> pd.Series:
        """
        Predict the target variable.
        """
        return X["close"]
