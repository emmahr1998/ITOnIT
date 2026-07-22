from fastapi import Depends
from sqlalchemy.orm import Session

from app.dependencies.database import get_db
from app.repositories.ticket import TicketRepository
from app.services.ticket_service import TicketService


def get_ticket_repository(db: Session = Depends(get_db)) -> TicketRepository:
    return TicketRepository(db)


def get_ticket_service(db: Session = Depends(get_db)) -> TicketService:
    return TicketService(db)
