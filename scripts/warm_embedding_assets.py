from sentence_transformers import SentenceTransformer

from config import EMBEDDING_MODEL_NAME


def main() -> None:
    SentenceTransformer(EMBEDDING_MODEL_NAME)


if __name__ == "__main__":
    main()
