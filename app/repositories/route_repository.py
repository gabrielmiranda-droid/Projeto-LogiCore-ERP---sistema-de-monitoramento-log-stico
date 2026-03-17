from app.models.entities import Route
from app.repositories.base import Repository


class RouteRepository(Repository[Route]):
    def __init__(self) -> None:
        super().__init__(Route)
