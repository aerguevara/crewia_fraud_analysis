import os
from dotenv import load_dotenv, find_dotenv
load_dotenv(find_dotenv())

# Tracing de CrewAI
os.environ["CREWAI_TRACING_ENABLED"] = "false"  # Desactiva el prompt de traces

from crewai import Agent, Crew, Process, Task, LLM
from crewai.memory.unified_memory import Memory
from crewai.rag.embeddings.factory import build_embedder
from crewai.project import CrewBase, agent, crew, task
from crewai_fraud_analysis.tools.firestore_tool import FirestoreTool
from crewai_fraud_analysis.tools.user_search_tool import UserSearchTool

# Configuración de Gemini 2.0 Flash
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

gemini_llm = LLM(
    model="gemini/gemini-2.5-flash-lite",
    api_key=GEMINI_API_KEY
)

# Alias para compatibilidad
local_llm = gemini_llm

# Configuración de embedder reutilizable
EMBEDDER_CONFIG = {
    "provider": "ollama",
    "config": {
        "model_name": "nomic-embed-text",
        "url": "http://localhost:11434/api/embeddings",
    }
}

class FastMemory(Memory):
    """Memory sin LLM: solo embeddings para guardar y buscar.
    
    Bypasses todo el EncodingFlow (que usa el LLM para analizar scope,
    categorías, importancia y consolidación). En su lugar, embebe el
    contenido directamente con nomic-embed-text y lo guarda en LanceDB
    con valores por defecto.
    
    Resultado: 0 llamadas al LLM en todo el ciclo de memoria.
    """
    
    def extract_memories(self, content: str) -> list[str]:
        """Salta la extracción LLM. Guarda el contenido truncado."""
        if not (content or "").strip():
            return []
        return [content[:500]]

    def remember(self, content, scope=None, categories=None, metadata=None,
                 importance=None, source=None, private=False, agent_role=None):
        """Guarda directamente sin LLM: embed → store."""
        if self._read_only or not (content or "").strip():
            return None
        from crewai.memory.types import MemoryRecord, embed_text
        embedding = embed_text(self._embedder, content)
        record = MemoryRecord(
            content=content,
            scope=scope or "/",
            categories=categories or [],
            metadata=metadata or {},
            importance=importance or 0.5,
            embedding=embedding if embedding else None,
            source=source,
            private=private,
        )
        self._storage.save([record])
        return record

    def remember_many(self, contents, scope=None, categories=None, metadata=None,
                      importance=None, source=None, private=False, agent_role=None):
        """Guarda múltiples directamente sin LLM."""
        if not contents or self._read_only:
            return []
        from crewai.memory.types import MemoryRecord, embed_texts
        embeddings = embed_texts(self._embedder, contents)
        records = []
        for content, emb in zip(contents, embeddings):
            records.append(MemoryRecord(
                content=content,
                scope=scope or "/",
                categories=categories or [],
                metadata=metadata or {},
                importance=importance or 0.5,
                embedding=emb if emb else None,
                source=source,
                private=private,
            ))
        if records:
            self._storage.save(records)
        return records


def _build_local_memory():
    """Construye FastMemory: memoria sin LLM, solo embeddings."""
    embedder = build_embedder(EMBEDDER_CONFIG)
    return FastMemory(
        llm=local_llm,
        embedder=embedder,
        exploration_budget=0,            # Solo búsqueda vectorial, sin LLM recall
        query_analysis_threshold=999999, # Nunca analiza la query con LLM 
        consolidation_threshold=1.0,     # Desactiva consolidación con LLM
    )

@CrewBase
class CrewaiFraudAnalysis():
    """CrewaiFraudAnalysis crew"""

    @agent
    def user_data_specialist(self) -> Agent:
        return Agent(
            config=self.agents_config['user_data_specialist'],
            tools=[UserSearchTool()],
            llm=gemini_llm,
            verbose=True
        )

    @agent
    def adventure_streak_orchestrator(self) -> Agent:
        return Agent(
            config=self.agents_config['adventure_streak_orchestrator'],
            llm=gemini_llm,
            verbose=True
        )

    @task
    def handle_user_request_task(self) -> Task:
        return Task(
            config=self.tasks_config['handle_user_request_task'],
        )

    @task
    def manage_user_queries_task(self) -> Task:
        return Task(
            config=self.tasks_config['manage_user_queries_task'],
        )

    @crew
    def crew(self) -> Crew:
        """Creates the CrewaiFraudAnalysis crew (Versión completa para reportes)"""
        return Crew(
            agents=[self.adventure_streak_orchestrator(), self.user_data_specialist()],
            tasks=[self.manage_user_queries_task(), self.handle_user_request_task()],
            process=Process.sequential,
            verbose=True,
        )

    def crew_for_chat(self) -> Crew:
        """Versión de chat: Orquestador al mando con poder de delegación."""
        return Crew(
            agents=[self.adventure_streak_orchestrator(), self.user_data_specialist()],
            tasks=[self.handle_user_request_task()],
            process=Process.sequential,
            verbose=True,
        )
