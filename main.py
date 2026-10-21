from fastapi import FastAPI

from database import Base, SessionLocal, engine
from schema import graphql_app
from seed import seed_database

Base.metadata.create_all(bind=engine)
with SessionLocal() as session:
    seed_database(session)

app = FastAPI(title="Sistema General de Ingresos", version="2.0.0")
app.include_router(graphql_app, prefix="/graphql")


@app.get("/")
def inicio():
    return {"mensaje": "API GraphQL lista. Abre /graphql"}
