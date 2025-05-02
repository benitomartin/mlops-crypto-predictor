def get_experiment_name(pair: str, candle_seconds: int, prediction_horizon_seconds: int) -> str:
    """
    Returns the experiment name for the given pair, candle seconds, and prediction horizon
    seconds.
    """
    return f"{pair}_{candle_seconds}_{prediction_horizon_seconds}"
