#!/usr/bin/env python3
"""
Vector embedding layer for the VR/AUDIT RAG.

Uses ONNX Runtime directly (no PyTorch required).
Downloads all-MiniLM-L6-v2 ONNX model from HuggingFace Hub.

Run:  python3 scripts/rag/embed.py
"""

import json, sys, os
import numpy as np
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = ROOT / "data" / "rag"
CHROMA_DIR = DATA_DIR / "chroma_db"
CHUNKS_FILE = DATA_DIR / "chunks.jsonl"
MODEL_DIR = DATA_DIR / "model"
COLLECTION_NAME = "vr_corpus"
BATCH_SIZE = 64

def download_model():
    """Download ONNX model files if not cached."""
    MODEL_DIR.mkdir(parents=True, exist_ok=True)
    onnx_path = MODEL_DIR / "onnx" / "model.onnx"
    tok_path = MODEL_DIR / "tokenizer.json"

    if onnx_path.exists() and tok_path.exists():
        return

    import subprocess
    repo_base = "https://huggingface.co/sentence-transformers/all-MiniLM-L6-v2/resolve/main"
    (MODEL_DIR / "onnx").mkdir(exist_ok=True)

    for remote, local in [
        ("onnx/model.onnx", onnx_path),
        ("tokenizer.json", tok_path),
        ("tokenizer_config.json", MODEL_DIR / "tokenizer_config.json"),
    ]:
        if not local.exists():
            print(f"Downloading {remote}...")
            subprocess.run(["curl", "-L", "-o", str(local), f"{repo_base}/{remote}"],
                           check=True, capture_output=True)

def mean_pooling(token_embeddings, attention_mask):
    mask_expanded = np.expand_dims(attention_mask, -1).astype(np.float32)
    sum_embeddings = np.sum(token_embeddings * mask_expanded, axis=1)
    sum_mask = np.clip(np.sum(mask_expanded, axis=1), a_min=1e-9, a_max=None)
    return sum_embeddings / sum_mask

def normalize(embeddings):
    norms = np.linalg.norm(embeddings, axis=1, keepdims=True)
    return embeddings / np.clip(norms, 1e-9, None)

class OnnxEmbedder:
    def __init__(self, model_dir):
        import onnxruntime as ort
        from tokenizers import Tokenizer

        onnx_path = model_dir / "model.onnx"
        if not onnx_path.exists():
            onnx_path = model_dir / "onnx" / "model.onnx"

        self.session = ort.InferenceSession(str(onnx_path))
        self.tokenizer = Tokenizer.from_file(str(model_dir / "tokenizer.json"))
        self.tokenizer.enable_padding(pad_id=0, pad_token="[PAD]", length=128)
        self.tokenizer.enable_truncation(max_length=128)

    def encode(self, texts):
        encodings = self.tokenizer.encode_batch(texts)
        input_ids = np.array([e.ids for e in encodings], dtype=np.int64)
        attention_mask = np.array([e.attention_mask for e in encodings], dtype=np.int64)
        token_type_ids = np.zeros_like(input_ids)

        outputs = self.session.run(
            None,
            {"input_ids": input_ids, "attention_mask": attention_mask,
             "token_type_ids": token_type_ids},
        )
        embeddings = mean_pooling(outputs[0], attention_mask)
        return normalize(embeddings)

def load_chunks():
    chunks = []
    with open(CHUNKS_FILE) as f:
        for line in f:
            if line.strip():
                chunks.append(json.loads(line))
    return chunks

def run():
    download_model()

    chunks = load_chunks()
    print(f"Loaded {len(chunks)} chunks")

    embedder = OnnxEmbedder(MODEL_DIR)
    print("ONNX embedder ready")

    import chromadb
    client = chromadb.PersistentClient(path=str(CHROMA_DIR))
    try:
        client.delete_collection(COLLECTION_NAME)
    except Exception:
        pass
    collection = client.create_collection(
        name=COLLECTION_NAME,
        metadata={"hnsw:space": "cosine"},
    )

    for start in range(0, len(chunks), BATCH_SIZE):
        batch = chunks[start:start + BATCH_SIZE]
        docs = [c["content"][:2000] for c in batch]
        ids = [c["chunk_id"] for c in batch]
        metadatas = []
        for c in batch:
            metadatas.append({
                "vr_id": c["vr_id"],
                "section": c["section"],
                "status": c["status"],
                "date": c.get("date") or "",
                "iter": int(c.get("iter") or 0),
                "entities": ",".join(c.get("entities", [])[:20]),
                "content_hash": c.get("content_hash", ""),
            })

        embeddings = embedder.encode(docs).tolist()
        collection.add(
            ids=ids,
            embeddings=embeddings,
            documents=docs,
            metadatas=metadatas,
        )
        end = min(start + BATCH_SIZE, len(chunks))
        print(f"  Embedded {end}/{len(chunks)} chunks")

    print(f"\nChromaDB collection '{COLLECTION_NAME}' created at {CHROMA_DIR}")
    print(f"  {collection.count()} vectors stored")

if __name__ == "__main__":
    run()
