"""
Module for interacting with the Kraken WebSocket API to fetch real-time cryptocurrency trade data.

This module provides classes and functionality to connect to Kraken's WebSocket API,
subscribe to trade channels, and process incoming trade data.
"""

import json
from typing import Any

from loguru import logger
from pydantic import BaseModel
from websocket import create_connection


class Trade(BaseModel):
    """A model representing a single cryptocurrency trade from the Kraken API.

    This class inherits from Pydantic's BaseModel to provide data validation and serialization.

    Attributes:
        product_id (str): The trading pair identifier (e.g., "BTC/USD", "ETH/EUR")
        price (float): The price at which the trade occurred
        quantity (float): The amount of cryptocurrency traded
        timestamp (str): The time when the trade occurred
    """

    product_id: str
    price: float
    quantity: float
    timestamp: str

    def to_dict(self) -> dict[str, Any]:
        """Convert the Trade instance to a dictionary format.

        This method is used for serialization when sending trades to Kafka.

        Returns:
            dict[str, Any]: A dictionary containing all Trade attributes
        """
        result: dict[str, Any] = self.model_dump()
        return result


class KrakenAPI:
    """A client for interacting with the Kraken WebSocket API.

    This class manages the WebSocket connection to Kraken's API and handles
    subscribing to trade channels and processing trade messages.

    Attributes:
        URL (str): The WebSocket endpoint URL for Kraken's API
        product_ids (list[str]): List of trading pairs to subscribe to
        _ws_client: WebSocket connection instance
    """

    URL = "wss://ws.kraken.com/v2"  # See Channel: https://docs.kraken.com/api/docs/websocket-v2/trade

    def __init__(
        self,
        product_ids: list[str],
    ) -> None:
        """Initialize the Kraken API client.

        Args:
            product_ids (list[str]): List of trading pairs to subscribe to (e.g., ["BTC/USD", "ETH/EUR"])
        """
        self.product_ids = product_ids

        # Create a WebSocket connection
        self._ws_client = create_connection(self.URL)

        # Subscribe to trade channels for the specified trading pairs
        self._subscribe(product_ids)

    def get_trades(self) -> list[Trade]:
        """Fetch and process the next batch of trades from the WebSocket connection."""
        try:
            data: str = self._ws_client.recv()
        except Exception as e:
            if "timed out" in str(e):
                return []
            logger.error(f"Error receiving data from WebSocket: {e}")
            return []

        if "heartbeat" in data:
            logger.info("Heartbeat received")
            return []

        # Parse the received message as a JSON object
        try:
            parsed_data: dict[str, Any] = json.loads(data)
        except json.JSONDecodeError as e:
            logger.error(f"Error decoding JSON: {e}")
            return []

        # Extract the trade data from the parsed message
        try:
            trades_data: list[dict[str, Any]] = parsed_data["data"]
        except KeyError as e:
            logger.error(f"No `data` field with trades in the message {e}")
            return []

        # Convert the trade data into Trade objects
        trades = [
            Trade(
                product_id=str(trade["symbol"]),
                price=float(trade["price"]),
                quantity=float(trade["qty"]),
                timestamp=str(trade["timestamp"]),
            )
            for trade in trades_data
        ]

        return trades

    def _subscribe(self, product_ids: list[str]) -> None:
        """Subscribe to trade channels for the specified trading pairs.

        This method sends a subscription message to the WebSocket connection for the
        specified trading pairs and handles the initial response messages.

        Args:
            product_ids (list[str]): List of trading pairs to subscribe to

        Note:
            The method discards the first two messages for each product_id as they
            contain no trade data (they are subscription confirmation messages).
        """
        # send a subscribe message to the websocket
        self._ws_client.send(
            json.dumps(
                {
                    "method": "subscribe",
                    "params": {
                        "channel": "trade",
                        "symbol": product_ids,
                        "snapshot": False,
                    },
                }
            )
        )

        # Discard the first two messages for each product_id as they contain no trade data
        for _ in product_ids:
            _ = self._ws_client.recv()
            _ = self._ws_client.recv()
