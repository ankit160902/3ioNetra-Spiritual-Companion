"""
RAG Pipeline for Scripture-grounded responses with LLM integration
"""
import numpy as np
from typing import List, Dict, Optional
from llm.service import get_llm_service
from llm.formatter import get_refiner, get_reformatter, ensure_paragraph_breaks
import logging

try:
    from sentence_transformers import SentenceTransformer
    SENTENCE_TRANSFORMERS_AVAILABLE = True
except Exception:
    SentenceTransformer = None
    SENTENCE_TRANSFORMERS_AVAILABLE = False


class _DummyEmbeddingModel:
    """Fallback embedding model when sentence-transformers is not installed"""
    def __init__(self, dim: int = 768):
        self.dim = dim

    def encode(self, texts, convert_to_tensor=False):
        if isinstance(texts, (list, tuple)):
            return np.zeros((len(texts), self.dim))
        return np.zeros(self.dim)


try:
    from langchain.text_splitter import RecursiveCharacterTextSplitter
    LANGCHAIN_AVAILABLE = True
except Exception:
    RecursiveCharacterTextSplitter = None
    LANGCHAIN_AVAILABLE = False


class _DummyTextSplitter:
    def __init__(self, chunk_size=512, chunk_overlap=50):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str):
        chunks = []
        i = 0
        while i < len(text):
            chunks.append(text[i:i + self.chunk_size])
            i += self.chunk_size - self.chunk_overlap
        return chunks


try:
    import torch
    TORCH_AVAILABLE = True
except Exception:
    torch = None
    TORCH_AVAILABLE = False


from config import settings

logger = logging.getLogger(__name__)


class RAGPipeline:
    """
    Retrieval-Augmented Generation pipeline for spiritual queries (English-only)
    """

    def __init__(self):
        self.embedding_model = None
        self.vector_store = None
        self.text_splitter = None
        self.initialized = False

    async def initialize(self):
        try:
            logger.info("Initializing RAG pipeline...")

            if SENTENCE_TRANSFORMERS_AVAILABLE:
                self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
            else:
                logger.warning("Using dummy embeddings")
                self.embedding_model = _DummyEmbeddingModel(
                    dim=getattr(settings, "EMBEDDING_DIM", 768)
                )

            if LANGCHAIN_AVAILABLE:
                self.text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=settings.CHUNK_SIZE,
                    chunk_overlap=settings.CHUNK_OVERLAP,
                    separators=["\n\n", "\n", ". ", " ", ""]
                )
            else:
                self.text_splitter = _DummyTextSplitter(
                    chunk_size=settings.CHUNK_SIZE,
                    chunk_overlap=settings.CHUNK_OVERLAP
                )

            self.vector_store = self._load_vector_store()
            self.initialized = True
            logger.info("✅ RAG Pipeline initialized")

        except Exception as e:
            logger.error(f"Failed to initialize RAG pipeline: {e}")
            raise

    def _load_vector_store(self) -> Dict:
        """
        Load scripture embeddings (English only)
        """
        import json
        from pathlib import Path

        processed_dir = Path(__file__).parent.parent / "data" / "processed"
        processed_file = processed_dir / "all_scriptures_processed.json"

        if processed_file.exists():
            with open(processed_file, "r", encoding="utf-8") as f:
                data = json.load(f)

            scriptures = []
            embeddings = []

            for verse in data.get("verses", []):
                embedding = verse.pop("embedding", None)
                scriptures.append(verse)
                if embedding:
                    embeddings.append(embedding)

            if not embeddings:
                texts = [v["text"] for v in scriptures]
                embeddings = self.embedding_model.encode(texts, convert_to_tensor=False)
            else:
                embeddings = np.array(embeddings)

            return {
                "scriptures": scriptures,
                "embeddings": embeddings,
                "texts": [v["text"] for v in scriptures]
            }

        # Fallback English-only sample data
        logger.warning("⚠️ Using fallback English-only scripture samples")

        sample_scriptures = [
            {
                "text": "You have a right to perform your prescribed duties, but you are not entitled to the fruits of your actions.",
                "reference": "Bhagavad Gita 2.47",
                "scripture": "Bhagavad Gita",
                "chapter": 2,
                "verse": 47,
                "topic": "Karma Yoga",
                "language": "en"
            },
            {
                "text": "The mind is restless and difficult to control, but it can be mastered by practice and detachment.",
                "reference": "Bhagavad Gita 6.35",
                "scripture": "Bhagavad Gita",
                "chapter": 6,
                "verse": 35,
                "topic": "Mind Control",
                "language": "en"
            },
            {
                "text": "Abandon all varieties of duty and surrender unto Me alone. Do not fear.",
                "reference": "Bhagavad Gita 18.66",
                "scripture": "Bhagavad Gita",
                "chapter": 18,
                "verse": 66,
                "topic": "Surrender",
                "language": "en"
            }
        ]

        texts = [s["text"] for s in sample_scriptures]
        embeddings = self.embedding_model.encode(texts, convert_to_tensor=False)

        return {
            "scriptures": sample_scriptures,
            "embeddings": embeddings,
            "texts": texts
        }

    async def search(
        self,
        query: str,
        scripture_filter: Optional[str] = None,
        language: str = "en",
        top_k: int = 5
    ) -> List[Dict]:

        query_embedding = self.embedding_model.encode(query, convert_to_tensor=False)
        embeddings = np.array(self.vector_store["embeddings"])
        qe = np.array(query_embedding)

        norms = np.linalg.norm(embeddings, axis=1) * np.linalg.norm(qe)
        similarities = np.zeros(len(embeddings)) if np.any(norms == 0) else (embeddings @ qe) / norms

        top_indices = np.argsort(similarities)[::-1][:top_k]
        results = []

        for idx in top_indices:
            scripture = self.vector_store["scriptures"][idx]
            if scripture_filter and scripture["scripture"] != scripture_filter:
                continue
            results.append({**scripture, "score": float(similarities[idx])})

        return results

    async def query(
        self,
        query: str,
        language: str = "en",
        include_citations: bool = True,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:

        refiner = get_refiner()
        search_query = await refiner.refine_query(query, language) if refiner and refiner.available else query

        retrieved_docs = await self.search(
            query=search_query,
            language=language,
            top_k=settings.RETRIEVAL_TOP_K
        )

        llm = get_llm_service()
        answer = await llm.generate_response(
            query=query,
            context_docs=retrieved_docs,
            language=language,
            conversation_history=conversation_history
        )

        citations = [
            {
                "reference": d["reference"],
                "scripture": d["scripture"],
                "chapter": d["chapter"],
                "verse": d["verse"],
                "score": d["score"]
            }
            for d in retrieved_docs
        ] if include_citations else []

        confidence = float(np.mean([d["score"] for d in retrieved_docs])) if retrieved_docs else 0.0

        return {
            "answer": answer,
            "citations": citations,
            "confidence": confidence
        }


# Singleton
_rag_pipeline = None


def get_rag_pipeline() -> RAGPipeline:
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline
