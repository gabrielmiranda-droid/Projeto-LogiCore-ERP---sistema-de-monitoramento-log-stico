from app.db.init_db import init_db
from app.db.session import SessionLocal
from app.services.seed_service import SeedService


def main() -> None:
    init_db()
    with SessionLocal() as db:
        SeedService().seed(db)
    print("Seed concluido.")


if __name__ == "__main__":
    main()
