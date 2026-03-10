import os
from firebase_admin import credentials, firestore, initialize_app, _apps
from dotenv import load_dotenv

load_dotenv()

def inspect_firestore():
    if not _apps:
        cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
        cred = credentials.Certificate(cred_path)
        initialize_app(cred)

    db = firestore.client()
    print("--- Colecciones ---")
    collections = db.collections()
    for coll in collections:
        print(f"Collection: {coll.id}")
        # Ver un documento de 'users' si existe
        if coll.id == "users":
            print("  --- Muestra de 'users' ---")
            docs = coll.limit(1).stream()
            for doc in docs:
                print(f"  ID: {doc.id}")
                print(f"  Data: {doc.to_dict()}")

if __name__ == "__main__":
    inspect_firestore()
