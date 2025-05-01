import datetime
from typing import Any

from pydantic import BaseModel


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
    timestamp_ms: int

    def to_dict(self) -> dict[str, Any]:
        """Convert the Trade instance to a dictionary format.

        This method is used for serialization when sending trades to Kafka.

        Returns:
            dict[str, Any]: A dictionary containing all Trade attributes
        """
        result: dict[str, Any] = self.model_dump()
        return result

    @staticmethod
    def unix_seconds_to_iso_format(timestamp_sec: float) -> str:
        """
        Convert Unix timestamp in seconds to ISO 8601 format string with UTC timezone
        Example: "2025-04-24T11:35:42.856851Z"
        """
        dt = datetime.datetime.fromtimestamp(timestamp_sec, tz=datetime.UTC)
        return dt.isoformat().replace("+00:00", "Z")

    @staticmethod
    def iso_format_to_unix_seconds(iso_format: str) -> float:
        """
        Convert ISO 8601 format string with UTC timezone to Unix timestamp in seconds
        Example: "2025-04-24T11:35:42.856851Z" -> 1714084542.856851
        """
        return datetime.datetime.fromisoformat(iso_format).timestamp()

    @classmethod
    def from_kraken_websocket_response(
        cls,
        product_id: str,
        price: float,
        quantity: float,
        timestamp: str,
    ) -> "Trade":
        """
        Create a Trade object from the Kraken websocket response

        Args:
            product_id: The trading pair identifier (e.g., "BTC/USD")
            price: The price at which the trade occurred
            quantity: The amount of cryptocurrency traded
            timestamp: The time when the trade occurred in ISO format

        Returns:
            Trade: A new Trade instance
        """
        # Calculate timestamp_ms from the ISO format timestamp
        timestamp_ms = int(cls.iso_format_to_unix_seconds(timestamp) * 1000)

        return cls(
            product_id=product_id,
            price=price,
            quantity=quantity,
            timestamp=timestamp,
            timestamp_ms=timestamp_ms,
        )

    @classmethod
    def from_kraken_rest_api_response(
        cls,
        product_id: str,
        price: float,
        quantity: float,
        timestamp_sec: float,
    ) -> "Trade":
        """
        Create a Trade object from the Kraken REST API response
        """

        return cls(
            product_id=product_id,
            price=price,
            quantity=quantity,
            timestamp=cls.unix_seconds_to_iso_format(timestamp_sec),
            timestamp_ms=int(timestamp_sec * 1000),
        )
