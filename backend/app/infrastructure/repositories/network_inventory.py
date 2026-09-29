from datetime import datetime

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class NetworkInterfaceInventoryRow(Base):
    __tablename__ = "network_interface_inventory"
    __table_args__ = (
        UniqueConstraint("device_id", "interface_name", name="uq_network_interface_device_name"),
    )

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[str] = mapped_column(ForeignKey("devices.id"), nullable=False)
    interface_name: Mapped[str] = mapped_column(String(128), nullable=False)
    mac_address: Mapped[str | None] = mapped_column(String(64))
    operational_status: Mapped[str] = mapped_column(String(16), nullable=False)
    mtu: Mapped[int | None]
    speed_bps: Mapped[int | None] = mapped_column(BigInteger)
    vlan_id: Mapped[int | None]
    ip_addresses: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    gateways: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    dns_servers: Mapped[list[str]] = mapped_column(JSON, nullable=False, default=list)
    source: Mapped[str] = mapped_column(String(64), nullable=False)
    present: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    first_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_seen: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    last_changed_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
