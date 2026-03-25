from fastapi import FastAPI


app = FastAPI(title="Distributed Semantic Retrieval System")


@app.get("/health")
def health_check() -> dict[str, str]:
    return {"status": "ok"}
