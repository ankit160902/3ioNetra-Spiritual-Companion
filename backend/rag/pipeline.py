"""
RAG Pipeline for Scripture-grounded responses with LLM integration
"""
import numpy as np
from typing import List, Dict, Optional
from llm.service import get_llm_service
from llm.formatter import get_refiner, get_reformatter, ensure_paragraph_breaks

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
    from langchain.prompts import PromptTemplate
    LANGCHAIN_AVAILABLE = True
except Exception:
    RecursiveCharacterTextSplitter = None
    PromptTemplate = None
    LANGCHAIN_AVAILABLE = False


class _DummyTextSplitter:
    """Simple fallback text splitter"""
    def __init__(self, chunk_size=512, chunk_overlap=50, separators=None):
        self.chunk_size = chunk_size
        self.chunk_overlap = chunk_overlap

    def split_text(self, text: str):
        chunks = []
        i = 0
        while i < len(text):
            chunks.append(text[i:i+self.chunk_size])
            i += self.chunk_size - self.chunk_overlap
        return chunks
import logging

# Try to import torch if available; otherwise, use numpy for similarity calculations
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
    Retrieval-Augmented Generation pipeline for spiritual queries
    Implements Late Chunking and citation-based response generation
    """

    def __init__(self):
        self.embedding_model = None
        self.vector_store = None
        self.llm = None
        self.text_splitter = None
        self.initialized = False

    async def initialize(self):
        """Initialize all components"""
        try:
            logger.info("Loading embedding model...")
            if SENTENCE_TRANSFORMERS_AVAILABLE:
                self.embedding_model = SentenceTransformer(settings.EMBEDDING_MODEL)
            else:
                # Use a lightweight dummy embedding model for quick local start
                logger.warning("sentence-transformers not installed; using dummy embeddings for RAG (reduced functionality)")
                self.embedding_model = _DummyEmbeddingModel(dim=getattr(settings, 'EMBEDDING_DIM', 768))

            logger.info("Initializing text splitter...")
            if LANGCHAIN_AVAILABLE:
                self.text_splitter = RecursiveCharacterTextSplitter(
                    chunk_size=settings.CHUNK_SIZE,
                    chunk_overlap=settings.CHUNK_OVERLAP,
                    separators=["\n\n", "\n", "। ", ". ", " ", ""]
                )
            else:
                logger.warning("langchain not installed; using dummy text splitter (reduced functionality)")
                self.text_splitter = _DummyTextSplitter(
                    chunk_size=settings.CHUNK_SIZE,
                    chunk_overlap=settings.CHUNK_OVERLAP
                )

            # Initialize vector store (in-memory for POC)
            logger.info("Initializing vector store...")
            self.vector_store = self._load_vector_store()

            # Ensure embeddings are numpy arrays for compatibility when torch isn't installed
            if TORCH_AVAILABLE:
                # if torch is available keep tensors as-is
                pass
            else:
                # convert embeddings to numpy arrays
                if isinstance(self.vector_store.get("embeddings"), list):
                    # already numpy
                    pass
                else:
                    # handle the case where embeddings are torch tensors
                    try:
                        self.vector_store["embeddings"] = np.array(self.vector_store["embeddings"])
                    except Exception:
                        # leave as-is; methods below can handle arrays
                        pass

            # For POC, we'll use the embedding model for semantic similarity
            # In production, this would be a fine-tuned Airavata model
            logger.info("LLM will use embedding-based retrieval + template generation")

            self.initialized = True
            logger.info("RAG Pipeline initialized successfully")

        except Exception as e:
            logger.error(f"Failed to initialize RAG pipeline: {str(e)}")
            raise

    def _load_vector_store(self) -> Dict:
        """
        Load or create vector store with scripture embeddings
        Tries to load from processed dataset, falls back to sample data
        """
        import json
        from pathlib import Path

        # Try to load processed dataset - prefer all_scriptures over single scripture
        processed_dir = Path(__file__).parent.parent / "data" / "processed"

        # Priority order: all_scriptures > bhagavad_gita > fallback sample
        all_scriptures_file = processed_dir / "all_scriptures_processed.json"
        bhagavad_gita_file = processed_dir / "bhagavad_gita_processed.json"

        if all_scriptures_file.exists():
            processed_file = all_scriptures_file
        elif bhagavad_gita_file.exists():
            processed_file = bhagavad_gita_file
        else:
            processed_file = None

        if processed_file and processed_file.exists():
            try:
                logger.info(f"Loading processed dataset from {processed_file}")
                with open(processed_file, 'r', encoding='utf-8') as f:
                    data = json.load(f)

                verses = data.get('verses', [])
                metadata = data.get('metadata', {})

                # Extract embeddings and scriptures
                scriptures = []
                embeddings = []

                for verse in verses:
                    # Remove embedding from scripture dict
                    embedding = verse.pop('embedding', None)
                    scriptures.append(verse)

                    if embedding:
                        embeddings.append(embedding)

                if not embeddings:
                    logger.warning("No embeddings found in processed file, regenerating...")
                    texts = [v["text"] for v in scriptures]
                    embeddings = self.embedding_model.encode(texts, convert_to_tensor=False)
                else:
                    embeddings = np.array(embeddings)

                texts = [item["text"] for item in scriptures]

                vector_store = {
                    "scriptures": scriptures,
                    "embeddings": embeddings,
                    "texts": texts
                }

                # Log scripture breakdown if available
                scripture_counts = {}
                for s in scriptures:
                    scripture_name = s.get('scripture', 'Unknown')
                    scripture_counts[scripture_name] = scripture_counts.get(scripture_name, 0) + 1

                logger.info(f"✅ Loaded {len(scriptures)} verses from {processed_file.name}")
                logger.info(f"   Embedding dimension: {metadata.get('embedding_dim', 'unknown')}")
                if len(scripture_counts) > 1:
                    logger.info(f"   Scriptures loaded: {scripture_counts}")
                return vector_store

            except Exception as e:
                logger.error(f"Failed to load processed dataset: {e}")
                logger.warning("Falling back to sample data...")

        # Fallback: Sample Bhagavad Gita verses
        logger.warning("⚠️  Using sample data (8 verses only)")
        logger.warning("   Run: python3 scripts/ingest_bhagavad_gita.py to load full dataset")

        sample_scriptures = [
            {
                "text": "You have a right to perform your prescribed duties, but you are not entitled to the fruits of your actions. Never consider yourself to be the cause of the results of your activities, nor be attached to inaction.",
                "reference": "Bhagavad Gita 2.47",
                "scripture": "Bhagavad Gita",
                "chapter": 2,
                "verse": 47,
                "topic": "Karma Yoga",
                "language": "en"
            },
            {
                "text": "The mind is restless, turbulent, obstinate and very strong, O Krishna, and to subdue it, I think, is more difficult than controlling the wind.",
                "reference": "Bhagavad Gita 6.34",
                "scripture": "Bhagavad Gita",
                "chapter": 6,
                "verse": 34,
                "topic": "Mind Control",
                "language": "en"
            },
            {
                "text": "It is undoubtedly very difficult to curb the restless mind, but it is possible by suitable practice and by detachment.",
                "reference": "Bhagavad Gita 6.35",
                "scripture": "Bhagavad Gita",
                "chapter": 6,
                "verse": 35,
                "topic": "Mind Control",
                "language": "en"
            },
            {
                "text": "Perform your duty equipoised, O Arjuna, abandoning all attachment to success or failure. Such equanimity is called Yoga.",
                "reference": "Bhagavad Gita 2.48",
                "scripture": "Bhagavad Gita",
                "chapter": 2,
                "verse": 48,
                "topic": "Equanimity",
                "language": "en"
            },
            {
                "text": "Those who are free from anger and all material desires, who are self-realized, self-disciplined and constantly endeavoring for perfection, are assured of liberation in the Supreme in the very near future.",
                "reference": "Bhagavad Gita 5.26",
                "scripture": "Bhagavad Gita",
                "chapter": 5,
                "verse": 26,
                "topic": "Liberation",
                "language": "en"
            },
            {
                "text": "One who sees the Supersoul accompanying the individual soul in all bodies, and who understands that neither the soul nor the Supersoul within the destructible body is ever destroyed, actually sees.",
                "reference": "Bhagavad Gita 13.28",
                "scripture": "Bhagavad Gita",
                "chapter": 13,
                "verse": 28,
                "topic": "Soul",
                "language": "en"
            },
            {
                "text": "Abandon all varieties of dharmas and simply surrender unto Me alone. I shall liberate you from all sinful reactions; do not fear.",
                "reference": "Bhagavad Gita 18.66",
                "scripture": "Bhagavad Gita",
                "chapter": 18,
                "verse": 66,
                "topic": "Surrender",
                "language": "en"
            },
            {
                "text": "कर्मण्येवाधिकारस्ते मा फलेषु कदाचन। मा कर्मफलहेतुर्भूर्मा ते सङ्गोऽस्त्वकर्मणि॥",
                "reference": "Bhagavad Gita 2.47",
                "scripture": "Bhagavad Gita",
                "chapter": 2,
                "verse": 47,
                "topic": "Karma Yoga",
                "language": "hi"
            }
        ]

        # Generate embeddings
        texts = [item["text"] for item in sample_scriptures]
        embeddings = self.embedding_model.encode(texts, convert_to_tensor=False)

        vector_store = {
            "scriptures": sample_scriptures,
            "embeddings": embeddings,
            "texts": texts
        }

        logger.info(f"Loaded {len(sample_scriptures)} sample scripture passages")
        return vector_store

    async def generate_embeddings(self, text: str) -> np.ndarray:
        """Generate embeddings for text"""
        if not self.initialized:
            raise RuntimeError("Pipeline not initialized")

        embeddings = self.embedding_model.encode(text, convert_to_tensor=False)
        return embeddings

    async def search(
        self,
        query: str,
        scripture_filter: Optional[str] = None,
        language: str = "en",
        top_k: int = 5
    ) -> List[Dict]:
        """
        Search for relevant scripture passages
        """
        if not self.initialized:
            raise RuntimeError("Pipeline not initialized")

        # Generate query embedding (numpy by default)
        query_embedding = self.embedding_model.encode(query, convert_to_tensor=False)

        # Calculate cosine similarity using Torch if available, else NumPy
        if TORCH_AVAILABLE and hasattr(self.vector_store.get("embeddings"), "dtype") and "torch" in str(type(self.vector_store["embeddings"])):
            similarities = torch.nn.functional.cosine_similarity(
                torch.tensor(query_embedding).unsqueeze(0),
                self.vector_store["embeddings"]
            )
            top_indices = torch.argsort(similarities, descending=True)[:top_k]
            results = []
            for idx in top_indices:
                idx = idx.item()
                scripture = self.vector_store["scriptures"][idx]
                score = similarities[idx].item()
                # Apply filters
                if scripture_filter and scripture["scripture"] != scripture_filter:
                    continue
                if scripture["language"] != language:
                    continue
                if score >= settings.MIN_SIMILARITY_SCORE:
                    results.append({
                        **scripture,
                        "score": score
                    })
            return results
        else:
            # Ensure embeddings are a NumPy array
            embeddings = self.vector_store["embeddings"]
            if hasattr(embeddings, "cpu"):
                try:
                    embeddings = embeddings.cpu().numpy()
                except Exception:
                    pass

            # Normalize and compute cosine similarity with NumPy
            qe = np.array(query_embedding)
            # In case embeddings are tensors or lists, ensure numpy array
            emb = np.array(embeddings)

            # compute cosine similarity
            emb_norms = np.linalg.norm(emb, axis=1)
            qe_norm = np.linalg.norm(qe)
            if qe_norm == 0 or np.any(emb_norms == 0):
                similarities = np.zeros(len(emb))
            else:
                similarities = (emb @ qe) / (emb_norms * qe_norm)

            # Get top-k indices
            top_indices = np.argsort(similarities)[::-1][:top_k]

            # Retrieve results
            results = []
            for idx in top_indices:
                scripture = self.vector_store["scriptures"][idx]
                score = float(similarities[idx])

                # Apply filters
                if scripture_filter and scripture["scripture"] != scripture_filter:
                    continue
                if scripture["language"] != language:
                    continue

                if score >= settings.MIN_SIMILARITY_SCORE:
                    results.append({
                        **scripture,
                        "score": score
                    })

            return results

    async def search_with_filters(
        self,
        query: str,
        scripture_filter: Optional[List[str]] = None,
        dharmic_concepts: Optional[List[str]] = None,
        language: str = "en",
        top_k: int = 5
    ) -> List[Dict]:
        """
        Enhanced search with metadata filtering for dharmic queries.
        Used by the clarification flow for targeted retrieval.

        Args:
            query: Search query (emotion + concepts)
            scripture_filter: List of allowed scripture names
            dharmic_concepts: Concepts to boost in scoring
            language: Language filter
            top_k: Number of results

        Returns:
            List of matching scripture documents with scores
        """
        if not self.initialized:
            raise RuntimeError("Pipeline not initialized")

        # Generate query embedding
        query_embedding = self.embedding_model.encode(query, convert_to_tensor=False)

        # Get embeddings as numpy array
        embeddings = self.vector_store["embeddings"]
        if hasattr(embeddings, "cpu"):
            try:
                embeddings = embeddings.cpu().numpy()
            except Exception:
                pass
        emb = np.array(embeddings)
        qe = np.array(query_embedding)

        # Compute cosine similarity
        emb_norms = np.linalg.norm(emb, axis=1)
        qe_norm = np.linalg.norm(qe)

        if qe_norm == 0 or np.any(emb_norms == 0):
            similarities = np.zeros(len(emb))
        else:
            similarities = (emb @ qe) / (emb_norms * qe_norm)

        # Apply concept boosting if provided
        if dharmic_concepts:
            concept_set = set(c.lower() for c in dharmic_concepts)
            for idx, scripture in enumerate(self.vector_store["scriptures"]):
                text_lower = scripture.get('text', '').lower()
                topic_lower = scripture.get('topic', '').lower()

                # Check if any concept appears in text or topic
                for concept in concept_set:
                    if concept in text_lower or concept in topic_lower:
                        similarities[idx] *= 1.2  # 20% boost
                        break  # Only boost once per document

        # Get top candidates (more than needed for filtering)
        top_indices = np.argsort(similarities)[::-1][:top_k * 3]

        results = []
        for idx in top_indices:
            scripture = self.vector_store["scriptures"][idx]
            score = float(similarities[idx])

            # Apply scripture filter (list of allowed scriptures)
            scripture_name = scripture.get('scripture', '')
            if scripture_filter and scripture_name not in scripture_filter:
                continue

            # Apply language filter
            if scripture.get('language', 'en') != language:
                continue

            # Apply minimum score threshold
            if score < settings.MIN_SIMILARITY_SCORE:
                continue

            results.append({
                **scripture,
                "score": score
            })

            if len(results) >= top_k:
                break

        logger.info(f"search_with_filters: query='{query[:50]}', found={len(results)} results")
        return results

    async def query(
        self,
        query: str,
        language: str = "en",
        include_citations: bool = True,
        conversation_history: Optional[List[Dict]] = None
    ) -> Dict:
        """
        Process query and generate response with citations using LLM
        """
        if not self.initialized:
            raise RuntimeError("Pipeline not initialized")

        logger.info(f"Processing query: {query[:100]}...")

        # Optionally refine query for better RAG retrieval
        search_query = query
        refiner = get_refiner()
        if refiner and refiner.available:
            logger.info("Refining query for better scripture search...")
            search_query = await refiner.refine_query(query, language)
            logger.info(f"Refined query: '{search_query}'")

        # Retrieve relevant passages
        retrieved_docs = await self.search(
            query=search_query,
            language=language,
            top_k=settings.RETRIEVAL_TOP_K
        )

        # Even if no documents retrieved, we can still have a conversation
        # The LLM will provide empathetic guidance without scripture citations
        if not retrieved_docs:
            logger.info("No documents retrieved, but continuing conversation without scripture context")

        # Get LLM service
        llm_service = get_llm_service()

        # Generate response using LLM with retrieved context
        logger.info("Generating response with LLM...")
        answer = await llm_service.generate_response(
            query=query,
            context_docs=retrieved_docs,
            language=language,
            conversation_history=conversation_history
        )

        # Extract citations
        citations = [
            {
                "reference": doc["reference"],
                "text": doc["text"],
                "scripture": doc["scripture"],
                "chapter": doc["chapter"],
                "verse": doc["verse"],
                "score": doc["score"]
            }
            for doc in retrieved_docs
        ] if include_citations and retrieved_docs else []

        # Calculate confidence
        if retrieved_docs:
            avg_score = np.mean([doc["score"] for doc in retrieved_docs])
        else:
            avg_score = 0.0

        return {
            "answer": answer,
            "citations": citations,
            "confidence": float(avg_score)
        }

    async def query_stream(
        self,
        query: str,
        language: str = "en",
        include_citations: bool = True,
        conversation_history: Optional[List[Dict]] = None
    ):
        """
        Process query and generate streaming response with citations using LLM
        Yields chunks of text as they're generated
        """
        if not self.initialized:
            raise RuntimeError("Pipeline not initialized")

        logger.info(f"Processing streaming query: {query[:100]}...")

        # Optionally refine query for better RAG retrieval
        search_query = query
        refiner = get_refiner()
        if refiner and refiner.available:
            logger.info("Refining query for better scripture search...")
            search_query = await refiner.refine_query(query, language)
            logger.info(f"Refined query: '{search_query}'")

        # Retrieve relevant passages
        retrieved_docs = await self.search(
            query=search_query,
            language=language,
            top_k=settings.RETRIEVAL_TOP_K
        )

        # Even if no documents retrieved in streaming, continue conversation
        if not retrieved_docs:
            logger.info("No documents retrieved in streaming, but continuing conversation without scripture context")

        # Get LLM service
        llm_service = get_llm_service()

        # Generate streaming response using LLM with retrieved context
        logger.info("Generating streaming response with LLM...")

        # Collect the full response first
        full_response = ""
        async for chunk in llm_service.generate_response_stream(
            query=query,
            context_docs=retrieved_docs,
            language=language,
            conversation_history=conversation_history
        ):
            full_response += chunk

        # Use Gemini reformatter to completely rebuild the response
        logger.info(f"Reformulating response. Original: {len(full_response)} chars, Docs retrieved: {len(retrieved_docs)}")
        reformatter = get_reformatter(settings.GEMINI_API_KEY)

        if reformatter and reformatter.available:
            # Build context string for reformatter
            context_verses = self._build_verse_context(retrieved_docs)
            logger.info(f"Context verses built: {context_verses[:300]}...")

            # Reformulate using Gemini
            reformulated_response = await reformatter.reformulate_response(
                original_response=full_response,
                user_query=query,
                context_verses=context_verses
            )
            logger.info(f"✅ Reformulated! Length: {len(reformulated_response)} chars")

            yield reformulated_response
        else:
            # Fallback to simple formatting if reformatter not available
            logger.error("❌ Reformatter NOT available! Using fallback")
            formatted_response = ensure_paragraph_breaks(full_response)
            yield formatted_response

    def _build_verse_context(self, docs: List[Dict]) -> str:
        """
        Build a formatted context string with verse information for reformatter

        Args:
            docs: Retrieved documents with verses

        Returns:
            Formatted string with verse information
        """
        if not docs:
            return "No specific verses available."

        verses = []
        for i, doc in enumerate(docs[:3], 1):  # Top 3 verses
            verse_text = f"""Verse {i}:
- Reference: {doc.get('scripture', 'Bhagavad Gita')} Chapter {doc.get('chapter', '?')}, Verse {doc.get('verse', '?')}
- Text: "{doc.get('text', '')}"
- Topic: {doc.get('topic', 'General wisdom')}"""
            verses.append(verse_text)

        return "\n\n".join(verses)

    def _generate_response(
        self,
        query: str,
        retrieved_docs: List[Dict],
        language: str
    ) -> str:
        """
        Generate response from retrieved documents
        For POC, using template-based generation with modern conversational tone
        In production, this would use fine-tuned LLM
        """
        # Get the most relevant document
        top_doc = retrieved_docs[0]

        # Modern conversational template-based response
        if language == "hi":
            response = f"""हाय! {self._get_conversational_intro(query, language)}

{top_doc['scripture']} में, {top_doc['reference']} में यह बहुत खूबसूरती से बताया गया है:

"{top_doc['text']}"

सीधे शब्दों में कहें तो, {self._extract_teaching(query, top_doc)}। यह आज की दुनिया में भी उतना ही प्रासंगिक है।

आशा है यह आपकी मदद करेगा! 🙏"""
        else:
            response = f"""Hey! {self._get_conversational_intro(query, language)}

There's this beautiful verse in {top_doc['scripture']} {top_doc['reference']} that speaks to this:

"{top_doc['text']}"

Basically, {self._extract_teaching(query, top_doc)}. This ancient wisdom is super relevant even today.

Hope this helps! 🙏"""

        return response

    def _get_conversational_intro(self, query: str, language: str) -> str:
        """Generate a natural conversational intro based on the query"""
        query_lower = query.lower()

        if language == "hi":
            if "stress" in query_lower or "anxiety" in query_lower or "tension" in query_lower:
                return "मैं समझ सकता हूँ कि आप तनाव में हैं। आइए देखें कि प्राचीन ज्ञान क्या कहता है।"
            elif "mind" in query_lower or "control" in query_lower:
                return "मन को काबू करना - यह एक सार्वभौमिक संघर्ष है! यहाँ कुछ शाश्वत ज्ञान है।"
            elif "action" in query_lower or "duty" in query_lower or "work" in query_lower:
                return "अच्छा प्रश्न! काम और कर्तव्य के बारे में ज्ञान देखें।"
            elif "fear" in query_lower or "afraid" in query_lower:
                return "डर महसूस करना बिल्कुल सामान्य है। आइए देखें कि प्राचीन शिक्षाएँ क्या मार्गदर्शन देती हैं।"
            else:
                return "बढ़िया सवाल! यहाँ बताया गया है कि प्राचीन ज्ञान क्या कहता है।"
        else:
            if "stress" in query_lower or "anxiety" in query_lower or "worry" in query_lower:
                return "I get it - stress can be overwhelming. Let me share some ancient wisdom that might help."
            elif "mind" in query_lower or "control" in query_lower or "focus" in query_lower:
                return "Controlling the mind - that's a universal struggle! Here's some timeless wisdom."
            elif "action" in query_lower or "duty" in query_lower or "work" in query_lower:
                return "Great question! Let's see what the wisdom says about action and duty."
            elif "fear" in query_lower or "afraid" in query_lower:
                return "It's totally normal to feel fear. Let's see what the ancient teachings say about it."
            else:
                return "Great question! Here's what the ancient wisdom has to say about this."

    def _extract_teaching(self, query: str, doc: Dict) -> str:
        """Extract teaching based on query and document with modern conversational language"""
        query_lower = query.lower()

        # Modern conversational rule-based teaching extraction
        if "stress" in query_lower or "anxiety" in query_lower or "worry" in query_lower:
            return "focus on doing your best without obsessing over outcomes - that's where real peace comes from"
        elif "mind" in query_lower or "control" in query_lower or "focus" in query_lower:
            return "you can train your mind through regular practice and by not getting too attached to things - like mental gym training"
        elif "action" in query_lower or "duty" in query_lower or "work" in query_lower:
            return "do your work with a balanced mindset, without getting too hung up on winning or losing - that's the key to sustainable success"
        elif "fear" in query_lower or "afraid" in query_lower:
            return "when you trust in something greater than yourself, fear naturally fades away"
        elif "soul" in query_lower or "atman" in query_lower or "self" in query_lower:
            return "your true essence is eternal and can't be destroyed - once you realize this, death loses its sting"
        elif "happiness" in query_lower or "joy" in query_lower or "peace" in query_lower:
            return "true happiness comes from within, not from external circumstances or achievements"
        elif "relationships" in query_lower or "people" in query_lower or "others" in query_lower:
            return "treat everyone with compassion while staying true to your own path"
        elif "purpose" in query_lower or "meaning" in query_lower or "why" in query_lower:
            return "your purpose is to grow spiritually while fulfilling your responsibilities with integrity"
        else:
            return "this wisdom can help you live with more clarity, purpose, and inner peace"


# Export singleton instance
_rag_pipeline = None


def get_rag_pipeline() -> RAGPipeline:
    """Get or create RAG pipeline singleton"""
    global _rag_pipeline
    if _rag_pipeline is None:
        _rag_pipeline = RAGPipeline()
    return _rag_pipeline
