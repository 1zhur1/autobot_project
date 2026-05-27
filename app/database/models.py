from datetime import datetime
from sqlalchemy import Integer, String, Boolean, DateTime, ForeignKey, Text
from sqlalchemy.orm import declarative_base, Mapped, mapped_column, relationship

Base = declarative_base()

class Car(Base):
    __tablename__ = "cars"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    brand: Mapped[str] = mapped_column(String(50))
    model: Mapped[str] = mapped_column(String(50))
    year: Mapped[int] = mapped_column(Integer)
    engine: Mapped[str] = mapped_column(String(50))
    gearbox: Mapped[str] = mapped_column(String(50))
    mileage: Mapped[int] = mapped_column(Integer)
    
    ads: Mapped[list["ParsedAd"]] = relationship("ParsedAd", back_populates="car")

class ParsedAd(Base):
    __tablename__ = "parsed_ads"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    external_id: Mapped[str] = mapped_column(String(100), unique=True, index=True)
    source: Mapped[str] = mapped_column(String(50))
    url: Mapped[str] = mapped_column(String(255), unique=True)
    price: Mapped[int] = mapped_column(Integer)
    currency: Mapped[str] = mapped_column(String(10))
    city: Mapped[str] = mapped_column(String(100))
    photo_url: Mapped[str] = mapped_column(String(255))
    
    car_id: Mapped[int] = mapped_column(ForeignKey("cars.id"))
    car: Mapped["Car"] = relationship("Car", back_populates="ads")
    
    published_ad: Mapped["PublishedAd"] = relationship("PublishedAd", back_populates="ad", uselist=False)
    
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class PublishedAd(Base):
    __tablename__ = "published_ads"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    ad_id: Mapped[int] = mapped_column(ForeignKey("parsed_ads.id"), unique=True)
    message_id: Mapped[int] = mapped_column(Integer)
    
    ad: Mapped["ParsedAd"] = relationship("ParsedAd", back_populates="published_ad")
    published_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

class ParserLog(Base):
    __tablename__ = "parser_logs"
    
    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    source: Mapped[str] = mapped_column(String(50))
    status: Mapped[str] = mapped_column(String(50))
    message: Mapped[str] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)