from agents.embedding_engine.base import IEmbeddingEngine
from agents.embedding_engine.ollama import OllamaEmbeddingEngine


def create_embedding_engine() -> IEmbeddingEngine:
    return OllamaEmbeddingEngine()
