from datetime import datetime

from sqlalchemy import DateTime, Enum, Float, ForeignKey, Integer, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.enums import AlertType, OrderStatus


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class Customer(TimestampMixin, Base):
    __tablename__ = "customers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    tax_id: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(120), nullable=False)
    address: Mapped[str] = mapped_column(String(255), nullable=False)
    city: Mapped[str] = mapped_column(String(80), nullable=False)
    state: Mapped[str] = mapped_column(String(2), nullable=False)

    orders: Mapped[list["Order"]] = relationship(back_populates="customer")


class Product(TimestampMixin, Base):
    __tablename__ = "products"

    id: Mapped[int] = mapped_column(primary_key=True)
    sku: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    description: Mapped[str] = mapped_column(Text, default="")
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    stock_quantity: Mapped[int] = mapped_column(Integer, default=0)
    weight_kg: Mapped[float] = mapped_column(Float, default=0.0)

    order_items: Mapped[list["OrderItem"]] = relationship(back_populates="product")


class Driver(TimestampMixin, Base):
    __tablename__ = "drivers"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    license_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="driver")


class Route(TimestampMixin, Base):
    __tablename__ = "routes"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    origin_name: Mapped[str] = mapped_column(String(120), nullable=False)
    destination_name: Mapped[str] = mapped_column(String(120), nullable=False)
    origin_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    origin_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    destination_latitude: Mapped[float] = mapped_column(Float, nullable=False)
    destination_longitude: Mapped[float] = mapped_column(Float, nullable=False)
    estimated_distance_km: Mapped[float] = mapped_column(Float, nullable=False)
    expected_duration_minutes: Mapped[int] = mapped_column(Integer, nullable=False)
    path_points_json: Mapped[str] = mapped_column(Text, nullable=False)

    vehicles: Mapped[list["Vehicle"]] = relationship(back_populates="route")
    telemetry_events: Mapped[list["TelemetryEvent"]] = relationship(back_populates="route")


class Vehicle(TimestampMixin, Base):
    __tablename__ = "vehicles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    license_plate: Mapped[str] = mapped_column(String(10), unique=True, nullable=False)
    model: Mapped[str] = mapped_column(String(80), nullable=False)
    capacity_kg: Mapped[float] = mapped_column(Float, nullable=False)
    status: Mapped[str] = mapped_column(String(40), default="DISPONIVEL")
    driver_id: Mapped[int | None] = mapped_column(ForeignKey("drivers.id"), nullable=True)
    route_id: Mapped[int | None] = mapped_column(ForeignKey("routes.id"), nullable=True)

    driver: Mapped["Driver | None"] = relationship(back_populates="vehicles")
    route: Mapped["Route | None"] = relationship(back_populates="vehicles")
    orders: Mapped[list["Order"]] = relationship(back_populates="vehicle")
    telemetry_events: Mapped[list["TelemetryEvent"]] = relationship(back_populates="vehicle")


class Order(TimestampMixin, Base):
    __tablename__ = "orders"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    customer_id: Mapped[int] = mapped_column(ForeignKey("customers.id"), nullable=False)
    vehicle_id: Mapped[int | None] = mapped_column(ForeignKey("vehicles.id"), nullable=True)
    route_id: Mapped[int | None] = mapped_column(ForeignKey("routes.id"), nullable=True)
    status: Mapped[OrderStatus] = mapped_column(Enum(OrderStatus), default=OrderStatus.PENDING, nullable=False)
    total_amount: Mapped[float] = mapped_column(Numeric(12, 2), default=0)
    expected_delivery_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    shipped_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    delivered_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)

    customer: Mapped["Customer"] = relationship(back_populates="orders")
    vehicle: Mapped["Vehicle | None"] = relationship(back_populates="orders")
    route: Mapped["Route | None"] = relationship()
    items: Mapped[list["OrderItem"]] = relationship(back_populates="order", cascade="all, delete-orphan")
    invoices: Mapped[list["Invoice"]] = relationship(back_populates="order", cascade="all, delete-orphan")


class OrderItem(Base):
    __tablename__ = "order_items"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    product_id: Mapped[int] = mapped_column(ForeignKey("products.id"), nullable=False)
    quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    unit_price: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="items")
    product: Mapped["Product"] = relationship(back_populates="order_items")


class TelemetryEvent(Base):
    __tablename__ = "telemetry_events"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False)
    timestamp: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    latitude: Mapped[float] = mapped_column(Float, nullable=False)
    longitude: Mapped[float] = mapped_column(Float, nullable=False)
    speed_kmh: Mapped[float] = mapped_column(Float, nullable=False)
    fuel_level: Mapped[float] = mapped_column(Float, nullable=False)
    cargo_occupancy: Mapped[float] = mapped_column(Float, nullable=False)

    vehicle: Mapped["Vehicle"] = relationship(back_populates="telemetry_events")
    route: Mapped["Route"] = relationship(back_populates="telemetry_events")
    alerts: Mapped[list["Alert"]] = relationship(back_populates="telemetry_event")


class Alert(TimestampMixin, Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(primary_key=True)
    vehicle_id: Mapped[int] = mapped_column(ForeignKey("vehicles.id"), nullable=False)
    route_id: Mapped[int] = mapped_column(ForeignKey("routes.id"), nullable=False)
    telemetry_event_id: Mapped[int] = mapped_column(ForeignKey("telemetry_events.id"), nullable=False)
    alert_type: Mapped[AlertType] = mapped_column(Enum(AlertType), nullable=False)
    severity: Mapped[str] = mapped_column(String(20), nullable=False)
    message: Mapped[str] = mapped_column(String(255), nullable=False)
    resolved: Mapped[bool] = mapped_column(default=False)

    telemetry_event: Mapped["TelemetryEvent"] = relationship(back_populates="alerts")


class Invoice(TimestampMixin, Base):
    __tablename__ = "invoices"

    id: Mapped[int] = mapped_column(primary_key=True)
    order_id: Mapped[int] = mapped_column(ForeignKey("orders.id"), nullable=False)
    invoice_number: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    issue_date: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
    pdf_path: Mapped[str] = mapped_column(String(255), nullable=False)
    xml_path: Mapped[str] = mapped_column(String(255), nullable=False)

    order: Mapped["Order"] = relationship(back_populates="invoices")

    @property
    def customer_name(self) -> str:
        return self.order.customer.name

    @property
    def customer_document(self) -> str:
        return self.order.customer.tax_id

    @property
    def product_description(self) -> str:
        return ", ".join(item.product.name for item in self.order.items)

    @property
    def quantity(self) -> int:
        return sum(item.quantity for item in self.order.items)

    @property
    def unit_price(self) -> float:
        quantity = self.quantity
        if quantity <= 0:
            return 0.0
        return float(self.order.total_amount) / quantity

    @property
    def total_value(self) -> float:
        return float(self.order.total_amount)

    @property
    def status(self) -> str:
        return "EMITIDA"

    @property
    def pdf_file_path(self) -> str:
        return self.pdf_path
