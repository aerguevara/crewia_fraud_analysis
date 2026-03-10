from crewai.tools import BaseTool
from typing import Type, List, Dict, Any, Optional
from pydantic import BaseModel, Field
import os
import json
import firebase_admin
from firebase_admin import credentials, firestore
from dotenv import load_dotenv

load_dotenv()

class UserSearchToolInput(BaseModel):
    """Input schema for UserSearchTool."""
    search_query: Optional[str] = Field(default=None, description="Nombre o prefijo del nombre a buscar (case-sensitive en Firestore).")
    limit: int = Field(default=5, description="Máximo de usuarios a devolver.")
    list_new_users: bool = Field(default=False, description="Si es True, devuelve los usuarios registrados recientemente.")

class UserSearchTool(BaseTool):
    name: str = "Firestore User Searcher"
    description: str = (
        "Busca usuarios en Firestore por su nombre (displayName) o lista los más nuevos. "
        "Usa search_query para buscar un nombre específico. "
        "Usa list_new_users=True para ver quién se ha unido recientemente."
    )
    args_schema: Type[BaseModel] = UserSearchToolInput

    def _run(self, search_query: str = None, limit: int = 5, list_new_users: bool = False) -> str:
        """Busca usuarios en Firestore usando los campos verificados (displayName, joinedAt)."""
        try:
            if not firebase_admin._apps:
                cred_path = os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
                if not cred_path:
                    return "Error: GOOGLE_APPLICATION_CREDENTIALS not set."
                cred = credentials.Certificate(cred_path)
                firebase_admin.initialize_app(cred)

            db = firestore.client()
            users_ref = db.collection("users")

            if list_new_users:
                print("Listando usuarios nuevos (orden por joinedAt)...")
                # Verificado: el campo es 'joinedAt'
                query = users_ref.order_by("joinedAt", direction=firestore.Query.DESCENDING).limit(limit)
                docs = query.stream()
            elif search_query:
                print(f"Buscando usuario por nombre: {search_query}...")
                # Firestore prefix search (case-sensitive)
                query = users_ref.where("displayName", ">=", search_query).where("displayName", "<", search_query + "\uf8ff").limit(limit)
                docs = list(query.stream())
                
                # Si no hay resultados y la query es corta, intentamos un fallback manual
                # (Nota: En producción esto puede ser lento si hay miles de usuarios, pero para este caso ayuda)
                if not docs:
                    print("No hay coincidencias exactas. Intentando búsqueda parcial en los primeros 100...")
                    all_docs = users_ref.limit(100).stream()
                    docs = [d for d in all_docs if search_query.lower() in d.to_dict().get("displayName", "").lower()]
                    docs = docs[:limit]
            else:
                return "Error: Debes proporcionar un search_query o marcar list_new_users=True."

            results = []
            for doc in docs:
                data = doc.to_dict()
                user_info = {
                    "uid": doc.id,
                    "displayName": data.get("displayName", "N/A"),
                    "email": data.get("email", "N/A"),
                    "joinedAt": data.get("joinedAt").isoformat() if hasattr(data.get("joinedAt"), "isoformat") else str(data.get("joinedAt")),
                    "level": data.get("level", 0),
                    "totalActivities": data.get("totalActivities", 0)
                }
                results.append(user_info)

            if not results:
                return f"No se encontraron usuarios para: {search_query if search_query else 'Nuevos'}. Sugerencia: Verifica mayúsculas/minúsculas."

            return json.dumps(results, indent=2, default=str)

        except Exception as e:
            return f"Error en UserSearchTool: {str(e)}"
