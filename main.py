import json
import os

import firebase_admin
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from firebase_admin import auth, credentials


app = FastAPI()


def get_firebase_app():
    try:
        return firebase_admin.get_app()
    except ValueError:
        service_account_json = os.getenv("FIREBASE_SERVICE_ACCOUNT_JSON")

        if not service_account_json:
            raise RuntimeError("FIREBASE_SERVICE_ACCOUNT_JSON is missing")

        service_account = json.loads(service_account_json)

        return firebase_admin.initialize_app(
            credentials.Certificate(service_account)
        )


def verify_firebase_token(
    authorization: str | None = Header(default=None),
):
    if not authorization or not authorization.startswith("Bearer "):
        raise HTTPException(
            status_code=401,
            detail="Missing or invalid Authorization header",
        )

    token = authorization.split(" ", 1)[1]

    try:
        get_firebase_app()
        return auth.verify_id_token(token)
    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Invalid Firebase ID token",
        )


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


@app.get("/health-firebase")
def health_firebase():
    try:
        get_firebase_app()

        return {
            "ok": True,
            "firebase": "initialized",
        }

    except Exception as e:
        print(f"Firebase init error: {type(e).__name__}: {e}")

        raise HTTPException(
            status_code=500,
            detail="Firebase configuration error",
        )


@app.get("/me")
def me(user=Depends(verify_firebase_token)):
    return {
        "ok": True,
        "uid": user["uid"],
        "email": user.get("email"),
    } 
