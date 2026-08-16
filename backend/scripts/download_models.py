#!/usr/bin/env python3
"""CrawlRAG - Hugging Face Model Downloader Utility.

Downloads and caches Embedding and LLM models locally for offline inference,
fast vector generation, and local RAG chatbot execution.

Usage:
    python scripts/download_models.py --embedding-model BAAI/bge-small-en-v1.5 --verify
    python scripts/download_models.py --embedding-model sentence-transformers/all-MiniLM-L6-v2
    python scripts/download_models.py --llm-model Qwen/Qwen2.5-0.5B-Instruct
    python scripts/download_models.py --all --verify
"""

import argparse
import os
import sys
from pathlib import Path

# Ensure UTF-8 output on Windows terminals
if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except AttributeError:
        pass

# Add project root to sys.path
BASE_DIR = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BASE_DIR))

from huggingface_hub import snapshot_download


def sanitize_model_name(repo_id: str) -> str:
    """Convert HF repo_id (e.g. 'BAAI/bge-small-en-v1.5') to a valid folder name ('bge-small-en-v1.5')."""
    return repo_id.replace("/", "--")


def download_embedding_model(
    repo_id: str = "BAAI/bge-small-en-v1.5",
    target_dir: Path = BASE_DIR / "models" / "embeddings",
    token: str = None,
    verify: bool = True
) -> Path:
    """Download a sentence embedding model from Hugging Face."""
    print(f"\n========================================================")
    print(f"📦 [Embeddings] Downloading: {repo_id}")
    print(f"📁 [Target Directory]: {target_dir}")
    print(f"========================================================")

    model_folder_name = sanitize_model_name(repo_id)
    local_model_path = target_dir / model_folder_name
    local_model_path.mkdir(parents=True, exist_ok=True)

    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(local_model_path),
            token=token,
            local_dir_use_symlinks=False,
            ignore_patterns=["*.msgpack", "*.h5", "*.ot"]
        )
        print(f"✅ Successfully downloaded embedding model to:\n   -> {local_model_path}")

        if verify:
            print("\n🔍 Verifying embedding model with SentenceTransformers...")
            from sentence_transformers import SentenceTransformer
            model = SentenceTransformer(str(local_model_path))
            test_query = "CrawlRAG: Automated web scraping and RAG pipeline."
            embeddings = model.encode([test_query])
            print(f"✅ Embedding verification passed! (Vector dimension: {embeddings.shape[1]})")

        return local_model_path
    except Exception as e:
        print(f"❌ Failed to download embedding model {repo_id}: {e}", file=sys.stderr)
        raise


def download_llm_model(
    repo_id: str = "Qwen/Qwen2.5-0.5B-Instruct",
    target_dir: Path = BASE_DIR / "models" / "llm",
    token: str = None,
    verify: bool = True
) -> Path:
    """Download an LLM model and tokenizer from Hugging Face."""
    print(f"\n========================================================")
    print(f"🤖 [LLM / Chatbot] Downloading: {repo_id}")
    print(f"📁 [Target Directory]: {target_dir}")
    print(f"========================================================")

    model_folder_name = sanitize_model_name(repo_id)
    local_model_path = target_dir / model_folder_name
    local_model_path.mkdir(parents=True, exist_ok=True)

    try:
        snapshot_download(
            repo_id=repo_id,
            local_dir=str(local_model_path),
            token=token,
            local_dir_use_symlinks=False,
            ignore_patterns=["*.msgpack", "*.h5", "*.ot"]
        )
        print(f"✅ Successfully downloaded LLM model to:\n   -> {local_model_path}")

        if verify:
            print("\n🔍 Verifying LLM tokenizer...")
            from transformers import AutoTokenizer
            tokenizer = AutoTokenizer.from_pretrained(str(local_model_path))
            tokens = tokenizer.encode("Hello CrawlRAG!")
            print(f"✅ Tokenizer verification passed! (Token count: {len(tokens)})")

        return local_model_path
    except Exception as e:
        print(f"❌ Failed to download LLM model {repo_id}: {e}", file=sys.stderr)
        raise


def main():
    parser = argparse.ArgumentParser(
        description="CrawlRAG: Download and cache Hugging Face models locally for offline RAG & Embeddings."
    )
    parser.add_argument(
        "--embedding-model",
        type=str,
        default=None,
        help="Hugging Face repo ID for embedding model (e.g. 'BAAI/bge-small-en-v1.5' or 'sentence-transformers/all-MiniLM-L6-v2')"
    )
    parser.add_argument(
        "--llm-model",
        type=str,
        default=None,
        help="Hugging Face repo ID for LLM model (e.g. 'Qwen/Qwen2.5-0.5B-Instruct')"
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Download default embedding model AND default lightweight LLM model"
    )
    parser.add_argument(
        "--token",
        type=str,
        default=os.environ.get("HF_TOKEN", None),
        help="Hugging Face Access Token (optional, for gated/private models)"
    )
    parser.add_argument(
        "--verify",
        action="store_true",
        default=True,
        help="Run inference verification on the downloaded model (default: True)"
    )
    parser.add_argument(
        "--no-verify",
        dest="verify",
        action="store_false",
        help="Skip verification test after download"
    )

    args = parser.parse_args()

    # If no flags passed, default to downloading the default embedding model
    if not args.embedding_model and not args.llm_model and not args.all:
        args.embedding_model = "BAAI/bge-small-en-v1.5"

    embeddings_target = BASE_DIR / "models" / "embeddings"
    llm_target = BASE_DIR / "models" / "llm"

    if args.all:
        download_embedding_model("BAAI/bge-small-en-v1.5", embeddings_target, args.token, args.verify)
        download_llm_model("Qwen/Qwen2.5-0.5B-Instruct", llm_target, args.token, args.verify)
    else:
        if args.embedding_model:
            download_embedding_model(args.embedding_model, embeddings_target, args.token, args.verify)
        if args.llm_model:
            download_llm_model(args.llm_model, llm_target, args.token, args.verify)

    print("\n🎉 All requested models are ready for offline use in CrawlRAG!")


if __name__ == "__main__":
    main()
