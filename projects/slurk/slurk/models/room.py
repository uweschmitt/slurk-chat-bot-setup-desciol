from slurk.extensions.database import Base
from sqlalchemy import Column, ForeignKey, asc
from sqlalchemy.orm import relationship
from sqlalchemy.sql.sqltypes import JSON, Boolean, Integer, String

from .common import Common, user_room


class Room(Common):
    __tablename__ = "Room"

    layout_id = Column(Integer, ForeignKey("Layout.id"), nullable=False)
    read_only = Column(Boolean, nullable=False)
    users = relationship("User", secondary=user_room, back_populates="rooms")
    logs = relationship(
        "Log", backref="room", order_by=asc("date_modified"), passive_deletes=True
    )
    openvidu_session_id = Column(String, ForeignKey("Session.id"))


class Session(Base):
    __tablename__ = "Session"

    id = Column(String, primary_key=True)
    rooms = relationship("Room", backref="session")
    parameters = Column(JSON)
