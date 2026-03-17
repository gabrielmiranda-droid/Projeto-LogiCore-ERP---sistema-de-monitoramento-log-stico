from app.models.entities import Customer
from app.repositories.base import Repository


class CustomerRepository(Repository[Customer]):
    def __init__(self) -> None:
        super().__init__(Customer)
