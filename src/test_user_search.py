import os
import json
from firebase_admin import credentials, firestore, initialize_app, _apps
from crewai_fraud_analysis.tools.user_search_tool import UserSearchTool
from dotenv import load_dotenv

load_dotenv()

def test_user_search():
    print("--- Test: Listar Usuarios Nuevos ---")
    tool = UserSearchTool()
    res_new = tool._run(list_new_users=True, limit=2)
    print(res_new)

    print("\n--- Test: Buscar por Nombre (Antonio) ---")
    # Nota: Firestore es case-sensitive. Si el usuario está como 'Antonio', 'antonio' fallará.
    res_name = tool._run(search_query="Antonio")
    print(res_name)

if __name__ == "__main__":
    test_user_search()
