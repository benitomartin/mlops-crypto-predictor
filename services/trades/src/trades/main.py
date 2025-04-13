"""
Main module for the trades service that fetches cryptocurrency trade data from Kraken
and publishes it to a Kafka topic.

This module sets up a Kafka producer that continuously fetches real-time trade data
from the Kraken WebSocket API and publishes it to a specified Kafka topic for downstream
processing.
"""

import signal
import sys
from collections.abc import Generator
from contextlib import contextmanager
from typing import Any

from loguru import logger
from quixstreams import Application

from trades.kraken_api import KrakenAPI, Trade


class GracefulShutdown:
    """Handle graceful shutdown of the service.

    This class sets up signal handlers for SIGINT and SIGTERM to gracefully shutdown the service.
    """

    def __init__(self) -> None:
        self.shutdown = False
        signal.signal(signal.SIGINT, self._signal_handler)  # Keyboard interrupt
        signal.signal(signal.SIGTERM, self._signal_handler)  # Termination signal

    def _signal_handler(self, signum: int, frame: Any) -> None:
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}. Starting graceful shutdown...")
        self.shutdown = True

    @contextmanager
    def handle_shutdown(self) -> Generator[None, None, None]:
        """Context manager for handling shutdown."""
        try:
            yield
        finally:
            if self.shutdown:
                logger.info("Graceful shutdown completed")
                sys.exit(0)


def run(
    kafka_broker_address: str,
    kafka_topic_name: str,
    kraken_api: KrakenAPI,
) -> None:
    """Run the trades service that publishes cryptocurrency trade data to Kafka.

    This function:
    1. Creates a Kafka Application instance
    2. Sets up a producer for the specified topic
    3. Continuously fetches trade data from Kraken
    4. Serializes and publishes each trade to Kafka

    Args:
        kafka_broker_address (str): The address of the Kafka broker (e.g., "localhost:9092")
        kafka_topic_name (str): The name of the Kafka topic to publish trades to
        kraken_api (KrakenAPI): An initialized instance of the Kraken API client

    Note:
        The function runs indefinitely in a while loop until interrupted.
        Each trade is serialized as JSON before being published to Kafka.
    """
    shutdown_handler = GracefulShutdown()
    app = Application(
        broker_address=kafka_broker_address,
    )

    # Define a topic with JSON serialization
    topic = app.topic(name=kafka_topic_name, value_serializer="json")

    # Create a Producer instance and start publishing trades
    with app.get_producer() as producer:
        logger.info("Starting trades service...")

        while not shutdown_handler.shutdown:
            with shutdown_handler.handle_shutdown():
                try:
                    # 1. Fetch trades from the Kraken API
                    events: list[Trade] = kraken_api.get_trades()

                    for event in events:
                        if shutdown_handler.shutdown:
                            break

                        trade_dict = event.to_dict()
                        # Use product_id as the key for proper partitioning
                        key = trade_dict["product_id"].encode("utf-8")

                        # Serialize the trade event using the defined Topic
                        message = topic.serialize(value=trade_dict)

                        # Produce the message to Kafka topic with the key
                        producer.produce(topic=topic.name, value=message.value, key=key)
                        logger.info(f"Trade {trade_dict} pushed to Kafka")

                except Exception as e:
                    logger.error(f"Error processing trades: {e}")
                    if not shutdown_handler.shutdown:
                        continue


if __name__ == "__main__":
    from trades.config import config

    # Create Kraken API client with configured trading pairs
    api = KrakenAPI(product_ids=config.product_ids)

    # Start the service
    run(
        kafka_broker_address=config.kafka_broker_address,
        kafka_topic_name=config.kafka_topic_name,
        kraken_api=api,
    )
