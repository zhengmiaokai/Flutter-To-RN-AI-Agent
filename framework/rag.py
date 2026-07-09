"""framework/rag — RAG infrastructure for context-aware code conversion.

Provides a LangChain-powered RAG engine that indexes Dart source files
and (optionally) past conversion examples, then retrieves semantically
relevant context at conversion time.

Architecture:
  RAGEngine
    ├─ Indexer     (build/refresh vector store from files)
    ├─ Retriever   (query → relevant Document chunks)
    └─ Formatter   (Documents → compact prompt context)

This is a drop-in enhancement for ConvertAgent: it replaces the
filename-based find_companion_context() with semantic retrieval.
"""

from __future__ import annotations

import hashlib
from pathlib import Path
from typing import Optional

from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_core.documents import Document

from framework.config import Config


# =============================================================================
# LangChain Document loader: Dart source file → split Documents
# =============================================================================

# Dart-specific separators for the recursive splitter.
# Prioritizes class/function boundaries, then blank-line blocks, then lines.
_DART_SEPARATORS = [
    "\nclass ",
    "\nmixin ",
    "\nenum ",
    "\ntypedef ",
    "\nextension ",
    "\nvoid ",
    "\nWidget ",
    "\n@override",
    "\n}",
    "\n\n",
    "\n",
    " ",
]

# For Dart code, we use the generic separator list above.
# For converted RN code (TypeScript), use LangChain's TS separator list.
_TSX_SEPARATORS = RecursiveCharacterTextSplitter.get_separators_for_language(
    "ts"  # TSX shares the same structural boundaries as TS
)


def _code_chunker(file_path: Path, source_code: str) -> list[Document]:
    """Split a single source file into chunked Documents with metadata."""
    # Choose splitter based on file type
    if file_path.suffix == ".dart":
        splitter = RecursiveCharacterTextSplitter(
            separators=_DART_SEPARATORS,
            chunk_size=600,
            chunk_overlap=80,
            keep_separator=True,
        )
    else:
        splitter = RecursiveCharacterTextSplitter(
            separators=_TSX_SEPARATORS,
            chunk_size=800,
            chunk_overlap=100,
            keep_separator=True,
        )

    chunks = splitter.create_documents(
        texts=[source_code],
        metadatas=[{"source": str(file_path), "file": file_path.name}],
    )

    # Add chunk index metadata for traceability
    for i, doc in enumerate(chunks):
        doc.metadata["chunk"] = i
        source_hash = hashlib.md5(source_code.encode()).hexdigest()[:8]
        doc.metadata["source_hash"] = source_hash

    return chunks


def _file_to_documents(file_path: Path, category: str | None = None) -> list[Document]:
    """Read a source file and return chunked Documents with metadata."""
    if not file_path.exists():
        return []
    try:
        code = file_path.read_text(encoding="utf-8")
    except Exception:
        return []

    docs = _code_chunker(file_path, code)
    for doc in docs:
        if category:
            doc.metadata["category"] = category
    return docs


# =============================================================================
# RAG Engine
# =============================================================================


class RAGEngine:
    """LangChain-powered RAG engine for code context retrieval.

    Usage:
        engine = RAGEngine(config)
        engine.build_index(dart_files)       # one-time index build
        context = engine.retrieve_context(query, k=5)  # at convert time
    """

    def __init__(self, config: Config):
        self._config = config

        # Lazy-init: vector store is created on first index/retrieve call
        self._vectorstore: Optional["Chroma"] = None  # noqa: F821
        self._initialized = False

        # Embedding dimension tracking
        self._embedding_dim: int | None = None

    # ── Initialization (deferred) ──────────────────────────────────────────

    def _ensure_init(self):
        """Lazy-init the embedding model and vector store.

        Embedding strategy:
          1. If the provider is OpenAI (api.openai.com), use OpenAIEmbeddings
             directly (text-embedding-3-small).
          2. Otherwise, fall back to a local HuggingFace model. This avoids
             API calls to providers (e.g. DeepSeek, Ollama) that don't have
             an /embeddings endpoint.
          3. If neither is available, disable RAG with a warning.
        """
        if self._initialized:
            return
        self._initialized = True

        base_url = (self._config.base_url or "").lower()
        is_openai = "api.openai.com" in base_url or not base_url

        self._embeddings = None
        if is_openai:
            self._embeddings = self._init_openai_embeddings()
        else:
            self._embeddings = self._init_local_embeddings()

        if self._embeddings is None:
            return

        persist_dir = Path(self._config.target_dir) / ".rag_cache"
        persist_dir.mkdir(parents=True, exist_ok=True)

        try:
            from langchain_chroma import Chroma

            self._vectorstore = Chroma(
                collection_name="flutter_to_rn",
                embedding_function=self._embeddings,
                persist_directory=str(persist_dir),
            )
        except ImportError:
            try:
                from langchain_chroma import Chroma

                self._vectorstore = Chroma(
                    collection_name="flutter_to_rn",
                    embedding_function=self._embeddings,
                )
            except ImportError:
                import warnings
                warnings.warn(
                    "langchain-chroma not installed. RAG will be disabled. "
                    "Install with: pip install langchain-chroma"
                )
                self._vectorstore = None

    def _init_openai_embeddings(self):
        """Initialize OpenAI embedding model."""
        try:
            from langchain_openai import OpenAIEmbeddings

            kwargs: dict = {}
            if self._config.base_url:
                kwargs["base_url"] = self._config.base_url
            if self._config.api_key:
                kwargs["api_key"] = self._config.api_key

            return OpenAIEmbeddings(
                model="text-embedding-3-small",
                **kwargs,
            )
        except Exception as exc:
            import warnings
            warnings.warn(
                f"Failed to initialize OpenAI embeddings: {exc}. "
                "RAG will be disabled."
            )
            return None

    def _init_local_embeddings(self):
        """Initialize a local HuggingFace embedding model.

        Uses sentence-transformers/all-MiniLM-L6-v2 (~80MB, downloaded once).
        This avoids any external API call for embeddings.
        """
        try:
            from langchain_huggingface import HuggingFaceEmbeddings

            return HuggingFaceEmbeddings(
                model_name="all-MiniLM-L6-v2",
                model_kwargs={"device": "cpu"},
                encode_kwargs={"normalize_embeddings": True},
            )
        except ImportError:
            import warnings
            warnings.warn(
                "Local embedding dependencies not installed. "
                "Install with: pip install sentence-transformers langchain-huggingface "
                "(~80MB for local embedding model). "
                "Until then, RAG will be disabled — conversion will use "
                "filename-based companion context as fallback."
            )
            return None
        except Exception as exc:
            import warnings
            warnings.warn(
                f"Failed to initialize local embeddings: {exc}. "
                "RAG will be disabled."
            )
            return None

    # ── Index building ────────────────────────────────────────────────────

    def build_index(
        self,
        dart_files: list[tuple[Path, str]],
    ) -> int:
        """Build the vector index from Dart source files.

        Args:
            dart_files: List of (file_path, category) tuples.

        Returns:
            Number of Documents indexed.
        """
        self._ensure_init()
        if self._vectorstore is None:
            return 0

        all_docs: list[Document] = []

        for file_path, category in dart_files:
            docs = _file_to_documents(file_path, category)
            all_docs.extend(docs)

        if not all_docs:
            return 0

        ids = self._vectorstore.add_documents(all_docs)
        return len(ids)

    # ── TS output file indexing (for VerifyAgent type retrieval) ──────────

    def index_ts_files(self, output_dir: str) -> int:
        """Index all .ts/.tsx files in the output directory.

        This is called after conversion is complete, so that VerifyAgent
        can retrieve type definitions from the generated RN code when
        fixing tsc errors.

        Args:
            output_dir: Target output directory (e.g. config.target_dir).

        Returns:
            Number of Documents indexed.
        """
        self._ensure_init()
        if self._vectorstore is None:
            return 0

        base = Path(output_dir)
        if not base.exists():
            return 0

        all_docs: list[Document] = []
        for fp in base.rglob("*"):
            if fp.suffix not in (".ts", ".tsx"):
                continue
            # Skip node_modules, .rag_cache, etc.
            rel = fp.relative_to(base)
            if any(p.startswith(".") or p == "node_modules" for p in rel.parts):
                continue
            docs = _file_to_documents(fp)
            for doc in docs:
                doc.metadata["type"] = "ts_output"
            all_docs.extend(docs)

        if not all_docs:
            return 0

        ids = self._vectorstore.add_documents(all_docs)
        return len(ids)

    # ── Issue pattern storage (for ReflectAgent + VerifyAgent) ────────────

    def add_issue_pattern(
        self,
        flutter_file: str,
        issue_description: str,
        issue_category: str,
        severity: str = "warning",
        filename: str = "",
    ):
        """Store a reflection/verification issue as a retrievable pattern.

        Args:
            flutter_file: Source file name where the issue was found.
            issue_description: Human-readable description of the issue.
            issue_category: Category (widget, state, import, type, etc.).
            severity: critical / warning / info.
            filename: Short display name for the file.
        """
        self._ensure_init()
        if self._vectorstore is None:
            return
        doc = Document(
            page_content=f"[{severity.upper()}] {issue_category}: {issue_description}",
            metadata={
                "source": flutter_file,
                "file": filename or flutter_file,
                "type": "issue_pattern",
                "issue_category": issue_category,
                "severity": severity,
            },
        )
        self._vectorstore.add_documents([doc])

    def retrieve_issue_patterns(
        self,
        query: str,
        k: int = 3,
        score_threshold: float | None = 0.25,
    ) -> list[dict]:
        """Retrieve similar issue patterns from previous reflections.

        Args:
            query: The issue context (e.g. source code snippet or category).
            k: Number of patterns to retrieve.
            score_threshold: Minimum relevance score.

        Returns:
            List of dicts with 'content', 'issue_category', 'severity', 'source'.
        """
        self._ensure_init()
        if self._vectorstore is None:
            return []
        retriever = self._vectorstore.as_retriever(
            search_type="similarity_score_threshold" if score_threshold else "similarity",
            search_kwargs={"k": k, "score_threshold": score_threshold}
            if score_threshold
            else {"k": k},
        )
        try:
            docs = retriever.invoke(query)
        except Exception:
            return []

        results = []
        for doc in docs:
            results.append({
                "content": doc.page_content,
                "issue_category": doc.metadata.get("issue_category", "other"),
                "severity": doc.metadata.get("severity", "warning"),
                "source": doc.metadata.get("source", "unknown"),
            })
        return results

    # ── Generic context retrieval ─────────────────────────────────────────

    def retrieve_context(
        self,
        query_code: str,
        filename: str | None = None,
        k: int = 5,
        score_threshold: float | None = 0.3,
    ) -> list[dict]:
        """Retrieve semantically relevant code context for a conversion query.

        Args:
            query_code: The Dart source code to find context for.
            filename: Optional filename for filtering.
            k: Number of documents to retrieve.
            score_threshold: Minimum relevance score (None = no threshold).

        Returns:
            List of dicts with 'content', 'source', 'score', 'category'.
        """
        self._ensure_init()
        if self._vectorstore is None:
            return []
        retriever = self._vectorstore.as_retriever(
            search_type="similarity_score_threshold" if score_threshold else "similarity",
            search_kwargs={"k": k, "score_threshold": score_threshold}
            if score_threshold
            else {"k": k},
        )

        try:
            docs = retriever.invoke(query_code)
        except Exception:
            return []

        results = []
        for doc in docs:
            results.append({
                "content": doc.page_content,
                "source": doc.metadata.get("source", "unknown"),
                "file": doc.metadata.get("file", "unknown"),
                "chunk": doc.metadata.get("chunk", 0),
                "category": doc.metadata.get("category", "other"),
                "type": doc.metadata.get("type", "source"),
            })

        return results

    def format_retrieved_context(self, results: list[dict], current_file: str) -> str:
        """Format retrieved results into a compact prompt context block."""
        if not results:
            return ""

        # Filter out chunks from the current file itself (self-context is noise)
        external = [r for r in results if r["file"] != current_file]
        if not external:
            return ""

        lines = [
            "## Semantically related code from other files (RAG-enhanced context):",
        ]
        for r in external[:6]:
            source_label = r["source"]
            if r.get("type") == "ts_output":
                lines.append(f"\n[Type definition: {source_label}]:")
            else:
                lines.append(f"\n[Related file: {source_label}]:")
            content = r["content"]
            if len(content) > 400:
                content = content[:400] + "\n// ... (truncated)"
            lines.append(f"```dart\n{content}\n```")

        lines.append(
            "\nNOTE: The code above is from related files. "
            "Use them for cross-file context — import their converted RN "
            "counterparts instead of redefining types."
        )
        return "\n".join(lines)

    def format_issue_patterns(self, results: list[dict]) -> str:
        """Format retrieved issue patterns into a reflection prompt warning block."""
        if not results:
            return ""
        lines = [
            "## ⚠️ Known issue patterns from other files in this project:",
        ]
        for r in results:
            lines.append(f"- [{r['severity'].upper()}] ({r['issue_category']}) {r['content']}")
            lines.append(f"  (occurred in: {r['source']})")
        lines.append(
            "\nPay extra attention to these patterns — they were flagged in "
            "other files and may also apply here."
        )
        return "\n".join(lines)

    def format_type_context(self, results: list[dict]) -> str:
        """Format retrieved type definitions for verify fix prompt."""
        if not results:
            return ""
        lines = [
            "## RAG-retrieved type definitions from the project (semantic match):",
        ]
        seen = set()
        for r in results:
            key = r["content"][:100]
            if key in seen:
                continue
            seen.add(key)
            lines.append(f"\n[From: {r['source']}]")
            content = r["content"]
            if len(content) > 500:
                content = content[:500] + "\n// ..."
            lines.append(f"```typescript\n{content}\n```")
        return "\n".join(lines[:15])

    # ── Lifecycle ──────────────────────────────────────────────────────────

    def persist(self):
        """Persist the vector store to disk (if supported by the backend)."""
        if self._vectorstore is not None:
            try:
                self._vectorstore.persist()
            except (AttributeError, NotImplementedError):
                pass

    @property
    def is_indexed(self) -> bool:
        """Check if the index has been built."""
        return self._initialized
