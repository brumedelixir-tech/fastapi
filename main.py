import os

import psycopg
from fastapi import FastAPI

app = FastAPI()


@app.get("/")
def root():
    return {"message": "BRUME IDEL API DEV"}


@app.get("/health-db")
def health_db():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        return {
            "ok": False,
            "database": "missing DATABASE_URL",
        }

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1;")
            result = cursor.fetchone()

    return {
        "ok": result == (1,),
        "database": "connected",
    } 
