from fastapi import FastAPI

app = FastAPI(title="Ikimina API", version="0.1.0")


@app.get("/")
def health() -> dict[str, str]:
    return {"status": "ok"}
