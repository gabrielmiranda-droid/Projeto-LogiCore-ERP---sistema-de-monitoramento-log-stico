from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.entities import Customer, Driver, Order, Product, Route, Vehicle
from app.models.enums import OrderStatus
from app.services.routing_service import routing_service
from app.utils.geo import serialize_points


class SeedService:
    def seed(self, db: Session) -> None:
        if db.scalar(select(Customer.id).limit(1)):
            self.sync_routes(db)
            db.commit()
            return

        customers = [
            Customer(name="Mercantil Aurora", tax_id="12345678901", email="compras@aurora.com", address="Av. Paulista, 1500", city="Sao Paulo", state="SP"),
            Customer(name="Rede Vale Norte", tax_id="10987654321", email="suprimentos@valenorte.com", address="Rua das Flores, 80", city="Campinas", state="SP"),
        ]
        products = [
            Product(sku="LGC-001", name="Controlador Industrial", description="Modulo de controle embarcado", unit_price=899.90, stock_quantity=120, weight_kg=4.5),
            Product(sku="LGC-002", name="Sensor de Vibração", description="Sensor para linha logistica", unit_price=149.90, stock_quantity=400, weight_kg=0.6),
            Product(sku="LGC-003", name="Gateway IoT", description="Gateway para telemetria", unit_price=1299.90, stock_quantity=80, weight_kg=3.2),
        ]
        drivers = [
            Driver(name="Marcos Silva", license_number="SP1234567", phone="11999990001"),
            Driver(name="Ana Ribeiro", license_number="SP7654321", phone="11999990002"),
        ]
        fallback_route_points = {
            "R-SP-CPS": [
                (-23.55052, -46.633308),
                (-23.50012, -46.671448),
                (-23.420999, -46.736111),
                (-23.282145, -46.851223),
                (-23.142303, -46.975651),
                (-23.060113, -47.021324),
                (-22.984313, -47.066842),
                (-22.909938, -47.062633),
            ],
            "R-SP-SJC": [
                (-23.55052, -46.633308),
                (-23.492644, -46.566115),
                (-23.449347, -46.497665),
                (-23.420104, -46.396281),
                (-23.397895, -46.292389),
                (-23.341913, -46.171283),
                (-23.275613, -46.033218),
                (-23.223701, -45.900907),
            ],
        }
        routes = [
            Route(
                code="R-SP-CPS",
                name="Sao Paulo para Campinas",
                origin_name="Centro de Distribuicao SP",
                destination_name="Hub Campinas",
                origin_latitude=-23.55052,
                origin_longitude=-46.633308,
                destination_latitude=-22.909938,
                destination_longitude=-47.062633,
                estimated_distance_km=98,
                expected_duration_minutes=110,
                path_points_json=serialize_points(fallback_route_points["R-SP-CPS"]),
            ),
            Route(
                code="R-SP-SJC",
                name="Sao Paulo para Sao Jose dos Campos",
                origin_name="Centro de Distribuicao SP",
                destination_name="Hub SJC",
                origin_latitude=-23.55052,
                origin_longitude=-46.633308,
                destination_latitude=-23.223701,
                destination_longitude=-45.900907,
                estimated_distance_km=91,
                expected_duration_minutes=95,
                path_points_json=serialize_points(fallback_route_points["R-SP-SJC"]),
            ),
        ]

        db.add_all(customers + products + drivers + routes)
        db.flush()
        self.sync_routes(db, fallback_route_points=fallback_route_points, routes=routes)

        vehicles = [
            Vehicle(code="TRK-101", license_plate="ABC1D23", model="Volvo FH 540", capacity_kg=18000, status="DISPONIVEL", driver_id=drivers[0].id, route_id=routes[0].id),
            Vehicle(code="TRK-202", license_plate="XYZ9K87", model="Scania R450", capacity_kg=16000, status="DISPONIVEL", driver_id=drivers[1].id, route_id=routes[1].id),
        ]
        db.add_all(vehicles)
        db.flush()

        order = Order(
            order_number="ORD-BOOTSTRAP",
            customer_id=customers[0].id,
            vehicle_id=vehicles[0].id,
            route_id=routes[0].id,
            status=OrderStatus.PROCESSING,
            total_amount=1049.80,
            expected_delivery_at=datetime.utcnow() + timedelta(hours=6),
        )
        db.add(order)
        db.flush()
        order.order_number = f"ORD-{datetime.utcnow():%Y%m%d}-{order.id:05d}"

        from app.models.entities import OrderItem

        db.add_all(
            [
                OrderItem(order_id=order.id, product_id=products[0].id, quantity=1, unit_price=products[0].unit_price),
                OrderItem(order_id=order.id, product_id=products[1].id, quantity=1, unit_price=products[1].unit_price),
            ]
        )
        db.commit()

    def sync_routes(
        self,
        db: Session,
        fallback_route_points: dict[str, list[tuple[float, float]]] | None = None,
        routes: list[Route] | None = None,
    ) -> None:
        fallback_route_points = fallback_route_points or {
            "R-SP-CPS": [
                (-23.55052, -46.633308),
                (-23.50012, -46.671448),
                (-23.420999, -46.736111),
                (-23.282145, -46.851223),
                (-23.142303, -46.975651),
                (-23.060113, -47.021324),
                (-22.984313, -47.066842),
                (-22.909938, -47.062633),
            ],
            "R-SP-SJC": [
                (-23.55052, -46.633308),
                (-23.492644, -46.566115),
                (-23.449347, -46.497665),
                (-23.420104, -46.396281),
                (-23.397895, -46.292389),
                (-23.341913, -46.171283),
                (-23.275613, -46.033218),
                (-23.223701, -45.900907),
            ],
        }
        routes_to_sync = routes or list(db.scalars(select(Route)).all())
        for route in routes_to_sync:
            fallback_points = fallback_route_points.get(route.code)
            if fallback_points:
                routing_service.hydrate_route_path(db, route, fallback_points)
        db.flush()
