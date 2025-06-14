import os
import httpx
import json
from typing import Dict
from dotenv import load_dotenv
from retry import retry

load_dotenv()


class ServiceCommunicator:
    def __init__(self):
        self.service_ports = {
            "order": 8000,
            "inventory": 8001,
            "payment": 8002,
            "shipping": 8003,
            "notification": 8004,
        }
        self.base_urls = self._initialize_base_urls()

    def _initialize_base_urls(self) -> Dict[str, str]:
        """Initialize service base URLs based on the environment."""
        base_urls = {}
        is_kubernetes = os.getenv("KUBERNETES_SERVICE_HOST") is not None

        for service, port in self.service_ports.items():
            # Check for service-specific URL override first
            url_override = os.getenv(f"{service.upper()}_SERVICE_URL")
            if url_override:
                base_urls[service] = url_override
                continue

            if is_kubernetes:
                # In Kubernetes, services are accessible via their names
                # The default namespace is 'e-commerce-saga'
                namespace = os.getenv("KUBERNETES_NAMESPACE", "e-commerce-saga")
                service_name = f"{service}-service"
                base_urls[
                    service
                ] = f"http://{service_name}.{namespace}.svc.cluster.local:{port}"
            else:
                # For local development, use localhost
                base_urls[service] = f"http://localhost:{port}"
        return base_urls

    @retry(tries=3, delay=1, backoff=2)
    async def send_request(
        self, service, endpoint, method="GET", data=None, params=None, timeout=30.0
    ):
        """Send HTTP request to another service with enhanced error handling"""
        if service not in self.base_urls:
            raise ValueError(f"Unknown service: {service}")

        url = f"{self.base_urls[service]}/{endpoint}"

        print(f"Sending {method} request to {service}: {url}")
        if data:
            print(f"Request data: {json.dumps(data, indent=2)}")

        async with httpx.AsyncClient(timeout=httpx.Timeout(timeout)) as client:
            try:
                # Send the request based on method
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

                # Check for HTTP errors
                response.raise_for_status()

                # Parse response
                result = response.json()
                print(f"Response from {service}: {response.status_code}")

                return result

            except httpx.HTTPStatusError as e:
                error_detail = f"HTTP {e.response.status_code} error from {service}: {e.response.text}"
                print(f"HTTP error: {error_detail}")

                # Try to extract error details from response
                try:
                    error_response = e.response.json()
                    if "detail" in error_response:
                        error_detail = f"{error_detail} - {error_response['detail']}"
                except:
                    pass

                raise Exception(f"Service {service} error: {error_detail}")

            except httpx.TimeoutException as e:
                error_msg = (
                    f"Timeout calling {service} service at {url} (timeout: {timeout}s)"
                )
                print(f"Timeout error: {error_msg}")
                raise Exception(error_msg)

            except httpx.RequestError as e:
                error_msg = f"Request error calling {service} service: {str(e)}"
                print(f"Request error: {error_msg}")
                raise Exception(error_msg)

            except Exception as e:
                error_msg = f"Unexpected error calling {service} service: {str(e)}"
                print(f"Unexpected error: {error_msg}")
                raise Exception(error_msg)

    async def health_check(self, service: str) -> bool:
        """Check if a service is healthy"""
        try:
            await self.send_request(service, "health", method="GET", timeout=5.0)
            return True
        except Exception as e:
            print(f"Health check failed for {service}: {str(e)}")
            return False

    async def check_all_services_health(self) -> Dict[str, bool]:
        """Check health of all services"""
        health_results = {}

        for service in self.base_urls.keys():
            health_results[service] = await self.health_check(service)

        return health_results
