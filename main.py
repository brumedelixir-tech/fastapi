import json
import os

import firebase_admin
import psycopg
from fastapi import Depends, FastAPI, Header, HTTPException
from firebase_admin import auth, credentials

app = FastAPI()


def get_database_url():
    database_url = os.getenv("DATABASE_URL")

    if not database_url:
        raise RuntimeError("DATABASE_URL is missing")

    return database_url


def init_db():
    database_url = get_database_url()

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS "Utilisateur" (
                    "idUtilisateur" TEXT PRIMARY KEY,
                    "prenom" TEXT NOT NULL,
                    "nom" TEXT NOT NULL,
                    "email" TEXT NOT NULL
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS "Cabinet" (
                    "idCabinet" TEXT PRIMARY KEY,
                    "nomCabinet" TEXT NOT NULL,
                    "adresseCabinet" TEXT NOT NULL
                );
                """
            )

            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS "AccesCabinet" (
                    "idAcces" TEXT PRIMARY KEY,
                    "idUtilisateur" TEXT NOT NULL
                        REFERENCES "Utilisateur" ("idUtilisateur"),
                    "idCabinet" TEXT NOT NULL
                        REFERENCES "Cabinet" ("idCabinet"),
                    "role" TEXT NOT NULL,
                    "dateDebut" TIMESTAMPTZ NOT NULL,
                    "dateFin" TIMESTAMPTZ,
                    "statut" TEXT NOT NULL
                );
                """
            )


@app.on_event("startup")
def startup():
    init_db()


def get_firebase_app():
    try:
        return firebase_admin.get_app()

    except ValueError:
        service_account_json = os.getenv(
            "FIREBASE_SERVICE_ACCOUNT_JSON"
        )

        if not service_account_json:
            raise RuntimeError(
                "FIREBASE_SERVICE_ACCOUNT_JSON is missing"
            )

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
    database_url = get_database_url()

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
        print(
            f"Firebase init error: "
            f"{type(e).__name__}: {e}"
        )

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
@app.get("/me/context")
def me_context(user=Depends(verify_firebase_token)):
    uid = user["uid"]
    database_url = get_database_url()

    with psycopg.connect(database_url) as connection:
        with connection.cursor() as cursor:
            cursor.execute(
                """
                SELECT
                    "idUtilisateur",
                    "prenom",
                    "nom",
                    "email"
                FROM "Utilisateur"
                WHERE "idUtilisateur" = %s;
                """,
                (uid,),
            )

            utilisateur = cursor.fetchone()

            if utilisateur is None:
                raise HTTPException(
                    status_code=404,
                    detail="Utilisateur introuvable",
                )

            cursor.execute(
                """
                SELECT
                    c."idCabinet",
                    c."nomCabinet",
                    c."adresseCabinet"
                FROM "AccesCabinet" a
                JOIN "Cabinet" c
                    ON c."idCabinet" = a."idCabinet"
                WHERE a."idUtilisateur" = %s
                  AND LOWER(a."statut") = 'actif'
                  AND a."dateDebut" <= NOW()
                  AND (
                      a."dateFin" IS NULL
                      OR a."dateFin" >= NOW()
                  )
                ORDER BY c."nomCabinet";
                """,
                (uid,),
            )

            cabinets = cursor.fetchall()

    return {
        "utilisateur": {
            "idUtilisateur": utilisateur[0],
            "prenom": utilisateur[1],
            "nom": utilisateur[2],
            "email": utilisateur[3],
        },
        "cabinetsAccessibles": [
            {
                "idCabinet": cabinet[0],
                "nomCabinet": cabinet[1],
                "adresseCabinet": cabinet[2],
            }
            for cabinet in cabinets
        ],
    } 
