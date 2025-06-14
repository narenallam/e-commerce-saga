#!/usr/bin/env python3
"""
E-Commerce Saga Test Data Generator
Generates realistic test data for functional and technical testing scenarios.
"""

import json
import random
import uuid
from datetime import datetime, timedelta
from typing import List, Dict, Any
import argparse
from faker import Faker

fake = Faker()


class TestDataGenerator:
    def __init__(self):
        self.customers = []
        self.products = []
        self.orders = []
        self.test_scenarios = {}

    def generate_customers(self, count: int = 1000) -> List[Dict[str, Any]]:
        """Generate realistic customer data"""
        customer_tiers = ["STANDARD", "VIP", "ENTERPRISE"]

        for i in range(count):
            customer = {
                "id": f"CUST{i+1:06d}",
                "name": fake.name(),
                "email": fake.email(),
                "phone": fake.phone_number(),
                "tier": random.choice(customer_tiers),
                "registration_date": fake.date_between(
                    start_date="-2y", end_date="today"
                ).isoformat(),
                "billing_address": {
                    "street": fake.street_address(),
                    "city": fake.city(),
                    "state": fake.state_abbr(),
                    "zip": fake.zipcode(),
                    "country": "US",
                },
                "shipping_address": {
                    "street": fake.street_address(),
                    "city": fake.city(),
                    "state": fake.state_abbr(),
                    "zip": fake.zipcode(),
                    "country": "US",
                },
                "credit_limit": (
                    random.randint(1000, 50000) if random.random() > 0.3 else None
                ),
                "loyalty_points": random.randint(0, 10000),
            }
            self.customers.append(customer)

        return self.customers

    def generate_products(self, count: int = 500) -> List[Dict[str, Any]]:
        """Generate product inventory data"""
        categories = [
            "electronics",
            "accessories",
            "clothing",
            "home",
            "books",
            "sports",
            "toys",
            "beauty",
            "automotive",
            "health",
        ]

        for i in range(count):
            category = random.choice(categories)
            base_price = random.uniform(9.99, 2999.99)

            product = {
                "id": f"PROD{i+1:06d}",
                "name": f"{fake.catch_phrase()} {category.title()}",
                "description": fake.text(max_nb_chars=200),
                "category": category,
                "price": round(base_price, 2),
                "cost": round(base_price * 0.6, 2),  # 40% margin
                "stock": random.randint(0, 1000),
                "sku": f"SKU-{i+1:06d}",
                "weight": round(random.uniform(0.1, 10.0), 2),
                "dimensions": {
                    "length": round(random.uniform(1, 50), 1),
                    "width": round(random.uniform(1, 30), 1),
                    "height": round(random.uniform(1, 20), 1),
                },
                "supplier": fake.company(),
                "is_active": random.random() > 0.05,  # 95% active
                "tags": [fake.word() for _ in range(random.randint(1, 5))],
                "rating": round(random.uniform(3.0, 5.0), 1),
                "review_count": random.randint(0, 1000),
            }
            self.products.append(product)

        return self.products

    def generate_orders(self, count: int = 10000) -> List[Dict[str, Any]]:
        """Generate realistic order data"""
        if not self.customers or not self.products:
            raise ValueError("Must generate customers and products first")

        order_statuses = [
            "PENDING",
            "PROCESSING",
            "SHIPPED",
            "DELIVERED",
            "CANCELLED",
            "FAILED",
        ]
        payment_methods = [
            "credit_card",
            "debit_card",
            "paypal",
            "apple_pay",
            "google_pay",
        ]

        for i in range(count):
            customer = random.choice(self.customers)
            items_count = random.randint(1, 5)
            items = []
            total_amount = 0

            for _ in range(items_count):
                product = random.choice([p for p in self.products if p["is_active"]])
                quantity = random.randint(1, 3)
                item_total = product["price"] * quantity

                items.append(
                    {
                        "product_id": product["id"],
                        "name": product["name"],
                        "quantity": quantity,
                        "unit_price": product["price"],
                        "total_price": item_total,
                        "sku": product["sku"],
                    }
                )
                total_amount += item_total

            # Add random discount
            discount = 0
            if random.random() > 0.7:  # 30% chance of discount
                discount = round(total_amount * random.uniform(0.05, 0.25), 2)

            # Add shipping cost
            shipping_cost = (
                round(random.uniform(5.99, 19.99), 2) if total_amount < 100 else 0
            )

            order = {
                "id": f"ORD-2025-{i+1:06d}",
                "customer_id": customer["id"],
                "customer_name": customer["name"],
                "customer_email": customer["email"],
                "order_date": fake.date_time_between(
                    start_date="-30d", end_date="now"
                ).isoformat(),
                "status": random.choice(order_statuses),
                "items": items,
                "subtotal": round(total_amount, 2),
                "discount": discount,
                "shipping_cost": shipping_cost,
                "tax": round(total_amount * 0.0875, 2),  # 8.75% tax
                "total_amount": round(
                    total_amount - discount + shipping_cost + (total_amount * 0.0875), 2
                ),
                "payment_method": random.choice(payment_methods),
                "shipping_address": customer["shipping_address"],
                "billing_address": customer["billing_address"],
                "tracking_number": (
                    f"TRK{random.randint(1000000, 9999999)}"
                    if random.random() > 0.3
                    else None
                ),
                "expected_delivery": (
                    datetime.now() + timedelta(days=random.randint(1, 14))
                ).isoformat(),
                "notes": fake.sentence() if random.random() > 0.8 else None,
                "priority": "HIGH" if customer["tier"] == "VIP" else "NORMAL",
            }
            self.orders.append(order)

        return self.orders

    def generate_test_scenarios(self) -> Dict[str, Any]:
        """Generate specific test scenario data"""
        scenarios = {
            "happy_path_orders": [],
            "failure_scenarios": [],
            "edge_cases": [],
            "load_test_data": [],
            "stress_test_data": [],
        }

        # Happy Path Orders
        for i in range(100):
            scenarios["happy_path_orders"].append(
                {
                    "order_id": f"HAPPY-{i+1:03d}",
                    "customer_id": f"CUST{random.randint(1, min(100, len(self.customers))):06d}",
                    "items": [
                        {
                            "product_id": f"PROD{random.randint(1, min(50, len(self.products))):06d}",
                            "quantity": random.randint(1, 3),
                            "expected_result": "SUCCESS",
                        }
                    ],
                    "payment_method": "credit_card",
                    "expected_outcome": "ORDER_COMPLETED",
                }
            )

        # Failure Scenarios
        failure_types = [
            {
                "type": "PAYMENT_FAILURE",
                "service": "payment",
                "error_code": "INSUFFICIENT_FUNDS",
            },
            {
                "type": "INVENTORY_SHORTAGE",
                "service": "inventory",
                "error_code": "OUT_OF_STOCK",
            },
            {
                "type": "SHIPPING_UNAVAILABLE",
                "service": "shipping",
                "error_code": "NO_DELIVERY_ZONE",
            },
            {"type": "SERVICE_TIMEOUT", "service": "random", "error_code": "TIMEOUT"},
        ]

        for i, failure in enumerate(failure_types * 25):  # 25 of each type
            scenarios["failure_scenarios"].append(
                {
                    "order_id": f"FAIL-{i+1:03d}",
                    "failure_type": failure["type"],
                    "target_service": failure["service"],
                    "expected_error": failure["error_code"],
                    "compensation_required": True,
                    "expected_outcome": "ORDER_FAILED",
                }
            )

        # Edge Cases
        edge_cases = [
            {
                "type": "ZERO_AMOUNT_ORDER",
                "total": 0.00,
                "description": "Promotional order",
            },
            {
                "type": "HIGH_VALUE_ORDER",
                "total": 50000.00,
                "description": "Enterprise bulk order",
            },
            {
                "type": "SINGLE_ITEM_BULK",
                "quantity": 1000,
                "description": "Large quantity single item",
            },
            {
                "type": "DUPLICATE_ORDER",
                "duplicate_count": 3,
                "description": "Test idempotency",
            },
            {
                "type": "INVALID_CUSTOMER",
                "customer_id": "INVALID",
                "description": "Non-existent customer",
            },
        ]

        for i, case in enumerate(edge_cases * 20):  # 20 of each type
            scenarios["edge_cases"].append(
                {
                    "order_id": f"EDGE-{i+1:03d}",
                    "edge_case_type": case["type"],
                    "test_description": case["description"],
                    "special_handling": True,
                }
            )

        # Load Test Data
        user_loads = [10, 25, 50, 100, 200, 500]
        for load in user_loads:
            scenarios["load_test_data"].append(
                {
                    "test_name": f"load_test_{load}_users",
                    "concurrent_users": load,
                    "duration_minutes": 30,
                    "orders_per_user_per_minute": 2,
                    "expected_total_orders": load * 30 * 2,
                    "success_rate_threshold": 99.5,
                }
            )

        # Stress Test Data
        stress_scenarios = [
            {
                "name": "gradual_ramp",
                "start_users": 10,
                "end_users": 1000,
                "duration": 60,
            },
            {
                "name": "spike_test",
                "normal_users": 50,
                "spike_users": 500,
                "spike_duration": 5,
            },
            {
                "name": "sustained_load",
                "users": 200,
                "duration": 120,
                "chaos_enabled": True,
            },
        ]

        scenarios["stress_test_data"] = stress_scenarios

        self.test_scenarios = scenarios
        return scenarios

    def generate_chaos_scenarios(self) -> List[Dict[str, Any]]:
        """Generate chaos engineering test scenarios"""
        chaos_scenarios = [
            {
                "name": "pod_restart_chaos",
                "description": "Randomly restart service pods during load",
                "target_services": [
                    "order-service",
                    "payment-service",
                    "inventory-service",
                ],
                "failure_rate": 20,  # 20% of pods
                "duration_minutes": 30,
                "recovery_validation": True,
            },
            {
                "name": "network_latency_chaos",
                "description": "Introduce network delays between services",
                "latency_ms": [100, 250, 500, 1000],
                "affected_connections": [
                    "order->payment",
                    "order->inventory",
                    "saga->all",
                ],
                "duration_minutes": 15,
            },
            {
                "name": "resource_exhaustion",
                "description": "Simulate CPU/Memory pressure",
                "resource_limits": {
                    "cpu": "50m",  # Reduced CPU
                    "memory": "128Mi",  # Reduced Memory
                },
                "target_services": ["payment-service"],
                "duration_minutes": 20,
            },
            {
                "name": "database_connection_chaos",
                "description": "Simulate database connectivity issues",
                "connection_drop_rate": 30,
                "duration_minutes": 10,
                "auto_recovery_test": True,
            },
        ]
        return chaos_scenarios

    def save_data_to_files(self, output_dir: str = "./test-data"):
        """Save generated data to JSON files"""
        import os

        os.makedirs(output_dir, exist_ok=True)

        # Save main data sets
        with open(f"{output_dir}/customers.json", "w") as f:
            json.dump(self.customers, f, indent=2)

        with open(f"{output_dir}/products.json", "w") as f:
            json.dump(self.products, f, indent=2)

        with open(f"{output_dir}/orders.json", "w") as f:
            json.dump(self.orders, f, indent=2)

        with open(f"{output_dir}/test_scenarios.json", "w") as f:
            json.dump(self.test_scenarios, f, indent=2)

        # Save chaos scenarios
        chaos_data = self.generate_chaos_scenarios()
        with open(f"{output_dir}/chaos_scenarios.json", "w") as f:
            json.dump(chaos_data, f, indent=2)

        # Generate summary report
        summary = {
            "generation_timestamp": datetime.now().isoformat(),
            "data_summary": {
                "customers_count": len(self.customers),
                "products_count": len(self.products),
                "orders_count": len(self.orders),
                "test_scenarios_count": sum(
                    len(v) for v in self.test_scenarios.values()
                ),
                "chaos_scenarios_count": len(chaos_data),
            },
            "data_files": [
                "customers.json",
                "products.json",
                "orders.json",
                "test_scenarios.json",
                "chaos_scenarios.json",
            ],
        }

        with open(f"{output_dir}/generation_summary.json", "w") as f:
            json.dump(summary, f, indent=2)

        print(f"✅ Test data generated successfully!")
        print(f"📁 Output directory: {output_dir}")
        print(f"👥 Customers: {len(self.customers)}")
        print(f"📦 Products: {len(self.products)}")
        print(f"🛒 Orders: {len(self.orders)}")
        print(f"🧪 Test scenarios: {sum(len(v) for v in self.test_scenarios.values())}")
        print(f"💥 Chaos scenarios: {len(chaos_data)}")


def main():
    parser = argparse.ArgumentParser(
        description="Generate test data for e-commerce saga system"
    )
    parser.add_argument(
        "--customers", type=int, default=1000, help="Number of customers to generate"
    )
    parser.add_argument(
        "--products", type=int, default=500, help="Number of products to generate"
    )
    parser.add_argument(
        "--orders", type=int, default=10000, help="Number of orders to generate"
    )
    parser.add_argument(
        "--output-dir", default="./test-data", help="Output directory for test data"
    )
    parser.add_argument("--seed", type=int, help="Random seed for reproducible data")

    args = parser.parse_args()

    if args.seed:
        random.seed(args.seed)
        fake.seed_instance(args.seed)

    print("🚀 Starting test data generation...")
    generator = TestDataGenerator()

    print(f"👥 Generating {args.customers} customers...")
    generator.generate_customers(args.customers)

    print(f"📦 Generating {args.products} products...")
    generator.generate_products(args.products)

    print(f"🛒 Generating {args.orders} orders...")
    generator.generate_orders(args.orders)

    print("🧪 Generating test scenarios...")
    generator.generate_test_scenarios()

    print("💾 Saving data to files...")
    generator.save_data_to_files(args.output_dir)


if __name__ == "__main__":
    main()
