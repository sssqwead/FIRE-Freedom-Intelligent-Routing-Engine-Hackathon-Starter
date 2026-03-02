from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship
from sqlalchemy import String, Integer, Text, DateTime, ForeignKey, Float
from datetime import datetime

class Base(DeclarativeBase):
    pass

class BusinessUnit(Base):
    __tablename__ = "business_units"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    office: Mapped[str] = mapped_column(String(120), unique=True, index=True)
    address: Mapped[str] = mapped_column(String(255), default="")

class Manager(Base):
    __tablename__ = "managers"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    full_name: Mapped[str] = mapped_column(String(160), index=True)
    position: Mapped[str] = mapped_column(String(80), default="Spec")  
    skills: Mapped[str] = mapped_column(String(120), default="")       
    business_unit: Mapped[str] = mapped_column(String(120), index=True)
    current_load: Mapped[int] = mapped_column(Integer, default=0)

class Ticket(Base):
    __tablename__ = "tickets"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    client_guid: Mapped[str] = mapped_column(String(64), index=True)
    segment: Mapped[str] = mapped_column(String(40), default="Mass")  
    description: Mapped[str] = mapped_column(Text, default="")
    attachment: Mapped[str] = mapped_column(String(255), default="")
    country: Mapped[str] = mapped_column(String(80), default="")
    region: Mapped[str] = mapped_column(String(120), default="")
    city: Mapped[str] = mapped_column(String(120), default="")
    street: Mapped[str] = mapped_column(String(120), default="")
    house: Mapped[str] = mapped_column(String(40), default="")

    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ai: Mapped["TicketAI"] = relationship(back_populates="ticket", uselist=False)
    assignment: Mapped["Assignment"] = relationship(back_populates="ticket", uselist=False)

class TicketAI(Base):
    __tablename__ = "ticket_ai"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), unique=True, index=True)

    language: Mapped[str] = mapped_column(String(8), default="RU")  
    type: Mapped[str] = mapped_column(String(64), default="Consultation")
    sentiment: Mapped[str] = mapped_column(String(16), default="Neutral")
    priority: Mapped[int] = mapped_column(Integer, default=3)
    summary: Mapped[str] = mapped_column(Text, default="")
    recommendation: Mapped[str] = mapped_column(Text, default="")
    geo_lat: Mapped[str] = mapped_column(String(32), default="")
    geo_lon: Mapped[str] = mapped_column(String(32), default="")

    source: Mapped[str] = mapped_column(String(16), default="rules")  
    confidence: Mapped[int] = mapped_column(Integer, default=70)      
    reason: Mapped[str] = mapped_column(String(255), default="")

    ticket: Mapped["Ticket"] = relationship(back_populates="ai")

class Assignment(Base):
    __tablename__ = "assignments"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    ticket_id: Mapped[int] = mapped_column(ForeignKey("tickets.id"), unique=True, index=True)
    manager_id: Mapped[int] = mapped_column(ForeignKey("managers.id"), index=True)
    business_unit: Mapped[str] = mapped_column(String(120), index=True)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    ticket: Mapped["Ticket"] = relationship(back_populates="assignment")

class RRState(Base):
    __tablename__ = "rr_state"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    key: Mapped[str] = mapped_column(String(120), unique=True, index=True)  
    last_pair: Mapped[str] = mapped_column(String(64), default="")          
    toggle: Mapped[int] = mapped_column(Integer, default=0)                 


class GeoCache(Base):
    __tablename__ = "geo_cache"
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    query: Mapped[str] = mapped_column(String(512), unique=True, index=True)
    lat: Mapped[float] = mapped_column(Float)
    lon: Mapped[float] = mapped_column(Float)
    source: Mapped[str] = mapped_column(String(32), default="nominatim")
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)
