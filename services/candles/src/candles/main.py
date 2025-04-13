from loguru import logger
from quixstreams import Application


def init_candle(trade: dict) -> dict:
    """
    Initialize a candle with the first trade.

    Args:
        trade (dict): The first trade containing price, quantity and product_id

    Returns:
        dict: The initial candle state with open, high, low, close, volume and pair
    """
    return {
        "open": trade["price"],
        "high": trade["price"],
        "low": trade["price"],
        "close": trade["price"],
        "volume": trade["quantity"],
        "pair": trade["product_id"],
    }


def update_candle(candle: dict, trade: dict) -> dict:
    """
    Update an existing candle with a new trade.

    Args:
        candle (dict): The current candle state containing OHLCV data
        trade (dict): The new trade to incorporate into the candle

    Returns:
        dict: The updated candle state
    """
    # Update the candle with the new trade. Open price remains the same
    candle["high"] = max(candle["high"], trade["price"])
    candle["low"] = min(candle["low"], trade["price"])
    candle["close"] = trade["price"]
    candle["volume"] += trade["quantity"]

    return candle


def run(
    kafka_broker_address: str,
    kafka_input_topic: str,
    kafka_output_topic: str,
    kafka_consumer_group: str,
    # candles parameters
    candle_seconds: int,
    emit_intermediate_candles: bool = True,
) -> None:
    """
    Transform a stream of trades into OHLCV candles using Kafka streams.

    This function:
    1. Ingests trades from the `kafka_input_topic`
    2. Aggregates trades into candles using tumbling windows
    3. Produces candles to the `kafka_output_topic`

    Args:
        kafka_broker_address (str): Address of the Kafka broker
        kafka_input_topic (str): Topic to consume trades from
        kafka_output_topic (str): Topic to produce candles to
        kafka_consumer_group (str): Consumer group ID for Kafka
        candle_seconds (int): Duration of each candle in seconds
        emit_intermediate_candles (bool, optional): Whether to emit partial candles. Defaults to True.

    Returns:
        None
    """
    app = Application(
        broker_address=kafka_broker_address,
        consumer_group=kafka_consumer_group,
    )

    # Input topic
    trades_topic = app.topic(kafka_input_topic, value_deserializer="json")

    # Output topic
    candles_topic = app.topic(kafka_output_topic, value_serializer="json")

    # Step 1. Ingest trades from the input kafka topic
    # Create a Streaming DataFrame connected to the input Kafka topic
    sdf = app.dataframe(topic=trades_topic)

    # Step 2. Aggregate trades into candles
    # TODO: at the moment I am just printing it, to make sure this thing works.
    # sdf = sdf.update(lambda message: logger.info(f'Input:  {message}'))

    # Aggregation of trades into candles using tumbling windows
    from datetime import timedelta

    sdf = (
        # Define a tumbling window of 10 minutes
        sdf.tumbling_window(timedelta(seconds=candle_seconds))
        # Create a "reduce" aggregation with "reducer" and "initializer" functions
        .reduce(reducer=update_candle, initializer=init_candle)
    )

    # Get the current state of the aggregation (intermediate candles)
    sdf = sdf.current()

    # Extract open, high, low, close, volume, timestamp_ms, pair from the dataframe
    sdf["open"] = sdf["value"]["open"]
    sdf["high"] = sdf["value"]["high"]
    sdf["low"] = sdf["value"]["low"]
    sdf["close"] = sdf["value"]["close"]
    sdf["volume"] = sdf["value"]["volume"]
    # sdf['timestamp_ms'] = sdf['value']['timestamp_ms']
    sdf["pair"] = sdf["value"]["pair"]

    # Extract window start and end timestamps
    sdf["window_start_ms"] = sdf["start"]
    sdf["window_end_ms"] = sdf["end"]

    # Keep only the relevant columns
    sdf = sdf[
        [
            "pair",
            # 'timestamp_ms',
            "open",
            "high",
            "low",
            "close",
            "volume",
            "window_start_ms",
            "window_end_ms",
        ]
    ]

    sdf["candle_seconds"] = candle_seconds

    # Logging on the console
    sdf = sdf.update(lambda value: logger.debug(f"Candle: {value}"))

    # Step 3. Produce the candles to the output kafka topic
    sdf = sdf.to_topic(candles_topic)

    # Starts the streaming app
    app.run()


if __name__ == "__main__":
    from candles.config import config

    run(
        kafka_broker_address=config.kafka_broker_address,
        kafka_input_topic=config.kafka_input_topic,
        kafka_output_topic=config.kafka_output_topic,
        kafka_consumer_group=config.kafka_consumer_group,
        candle_seconds=config.candle_seconds,
    )
