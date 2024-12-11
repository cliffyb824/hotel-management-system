from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from typing import List, Optional
from sqlalchemy.orm import Mapped, mapped_column, relationship

db = SQLAlchemy()

class User(UserMixin, db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    username: Mapped[str] = mapped_column(unique=True, nullable=False)
    password: Mapped[str] = mapped_column(nullable=False)
    is_admin: Mapped[bool] = mapped_column(default=False)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)

class Room(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    room_number: Mapped[str] = mapped_column(unique=True, nullable=False)
    room_type: Mapped[str] = mapped_column(nullable=False)
    price: Mapped[float] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default='available')
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    reservations: Mapped[List["Reservation"]] = relationship(back_populates="room")
    housekeeping_tasks: Mapped[List["HousekeepingTask"]] = relationship(back_populates="room")

    def __repr__(self) -> str:
        return f'<Room {self.room_number}>'

class OTAChannel(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(nullable=False)
    api_key: Mapped[Optional[str]] = mapped_column()
    api_secret: Mapped[Optional[str]] = mapped_column()
    is_active: Mapped[bool] = mapped_column(default=True)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    
    reservations: Mapped[List["OTAReservation"]] = relationship(back_populates="ota_channel")

class OTAReservation(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(db.ForeignKey('reservation.id'), nullable=False)
    ota_channel_id: Mapped[int] = mapped_column(db.ForeignKey('ota_channel.id'), nullable=False)
    ota_booking_id: Mapped[str] = mapped_column(nullable=False)
    ota_booking_status: Mapped[Optional[str]] = mapped_column()
    commission_amount: Mapped[Optional[float]] = mapped_column()
    net_amount: Mapped[Optional[float]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    
    reservation: Mapped["Reservation"] = relationship(back_populates="ota_reservation")
    ota_channel: Mapped["OTAChannel"] = relationship(back_populates="reservations")

class Reservation(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    guest_name: Mapped[str] = mapped_column(nullable=False)
    guest_email: Mapped[Optional[str]] = mapped_column()
    guest_phone: Mapped[Optional[str]] = mapped_column()
    guest_address: Mapped[Optional[str]] = mapped_column()
    id_type: Mapped[Optional[str]] = mapped_column()
    id_number: Mapped[Optional[str]] = mapped_column()
    room_id: Mapped[int] = mapped_column(db.ForeignKey('room.id'), nullable=False)
    check_in: Mapped[datetime] = mapped_column(nullable=False)
    check_out: Mapped[datetime] = mapped_column(nullable=False)
    actual_check_in: Mapped[Optional[datetime]] = mapped_column()
    actual_check_out: Mapped[Optional[datetime]] = mapped_column()
    status: Mapped[str] = mapped_column(default='reserved')
    total_amount: Mapped[float] = mapped_column(nullable=False, default=0.0)
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    updated_at: Mapped[datetime] = mapped_column(default=datetime.utcnow, onupdate=datetime.utcnow)
    special_requests: Mapped[Optional[str]] = mapped_column()
    number_of_guests: Mapped[int] = mapped_column(default=1)
    booking_source: Mapped[str] = mapped_column(default='direct')
    booking_notes: Mapped[Optional[str]] = mapped_column()
    is_ota_booking: Mapped[bool] = mapped_column(default=False)
    
    room: Mapped["Room"] = relationship(back_populates="reservations")
    payments: Mapped[List["Payment"]] = relationship(back_populates="reservation")
    ota_reservation: Mapped[Optional["OTAReservation"]] = relationship(back_populates="reservation", uselist=False)

    def __repr__(self) -> str:
        return f'<Reservation {self.id} - {self.guest_name}>'

class Payment(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    reservation_id: Mapped[int] = mapped_column(db.ForeignKey('reservation.id'), nullable=False)
    amount: Mapped[float] = mapped_column(nullable=False)
    payment_date: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    payment_method: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default='completed')
    transaction_id: Mapped[Optional[str]] = mapped_column(unique=True)
    notes: Mapped[Optional[str]] = mapped_column()
    
    reservation: Mapped["Reservation"] = relationship(back_populates="payments")

class HousekeepingTask(db.Model):
    id: Mapped[int] = mapped_column(primary_key=True)
    room_id: Mapped[int] = mapped_column(db.ForeignKey('room.id'), nullable=False)
    task_type: Mapped[str] = mapped_column(nullable=False)
    status: Mapped[str] = mapped_column(default='pending')
    assigned_to: Mapped[Optional[str]] = mapped_column()
    created_at: Mapped[datetime] = mapped_column(default=datetime.utcnow)
    completed_at: Mapped[Optional[datetime]] = mapped_column()
    notes: Mapped[Optional[str]] = mapped_column()
    
    room: Mapped["Room"] = relationship(back_populates="housekeeping_tasks")
