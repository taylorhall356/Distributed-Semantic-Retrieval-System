from db import initialize_database, wait_for_database
from semantic_search import ensure_qdrant_collection
from storage import ensure_storage_ready


def main() -> None:
    wait_for_database()
    initialize_database()
    ensure_storage_ready()
    ensure_qdrant_collection()


if __name__ == "__main__":
    main()
