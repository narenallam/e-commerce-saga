import os
import httpx
import json
from dotenv import load_dotenv
from retry import retry

load_dotenv()


class ServiceCommunicator:
    def __init__(self):
        self.base_urls = {
            "order": os.getenv("ORDER_SERVICE_URL", "http://order-service:8000"),
            "inventory": os.getenv(
                "INVENTORY_SERVICE_URL", "http://inventory-service:8001"
            ),
            "payment": os.getenv("PAYMENT_SERVICE_URL", "http://payment-service:8002"),
            "shipping": os.getenv(
                "SHIPPING_SERVICE_URL", "http://shipping-service:8003"
            ),
            "notification": os.getenv(
                "NOTIFICATION_SERVICE_URL", "http://notification-service:8004"
            ),
        }

    @retry(tries=3, delay=1, backoff=2)
    async def send_request(
        self, service, endpoint, method="GET", data=None, params=None
    ):
        """Send HTTP request to another service with retry capability"""
        if service not in self.base_urls:
            raise ValueError(f"Unknown service: {service}")

        url = f"{self.base_urls[service]}/{endpoint}"

        async with httpx.AsyncClient(timeout=10.0) as client:
            try:
                if method == "GET":
                    response = await client.get(url, params=params)
                elif method == "POST":
                    response = await client.post(url, json=data)
                elif method == "PUT":
                    response = await client.put(url, json=data)
                elif method == "DELETE":
                    response = await client.delete(url, json=data)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")

                response.raise_for_status()
                return response.json()
            except httpx.HTTPStatusError as e:
                print(f"HTTP error: {e}")
                raise
            except httpx.RequestError as e:
                print(f"Request error: {e}")
                raise
