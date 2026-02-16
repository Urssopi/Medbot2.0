import json
import os
import threading
from typing import Any

from flask import Flask, jsonify, render_template, request
from openai import OpenAI

from dataset_service import DeidentifiedDataset

BASE_DIR = os.path.dirname(__file__)
CONFIG_PATH = os.path.join(BASE_DIR, "app_config.json")
ENV_PATH = os.path.join(BASE_DIR, ".env")
API_KEY_FILE_PATH = os.path.join(BASE_DIR, "PrivateKey.txt")
DATASET_CANDIDATE_PATHS = [
    r"c:\Users\jtr06\Downloads\Deidentified Data Set 2.xlsx",
    os.path.join(BASE_DIR, "Deidentified Data Set 2.xlsx"),
]


def load_config() -> dict[str, Any]:
    defaults: dict[str, Any] = {
        "models": ["gpt-4.1-mini"],
        "defaults": {"top_k_matches": 5},
        "rag": {
            "embedding_model": "text-embedding-3-small",
            "chunk_size_chars": 800,
            "chunk_overlap_chars": 120,
            "embedding_batch_size": 64,
            "rebuild_index_on_startup": False,
        },
    }
    if not os.path.exists(CONFIG_PATH):
        return defaults
    try:
        with open(CONFIG_PATH, "r", encoding="utf-8") as f:
            cfg = json.load(f)
        for key, value in defaults.items():
            if key not in cfg:
                cfg[key] = value
        return cfg
    except Exception:
        return defaults


def load_local_env(path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            for raw_line in f:
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key and key not in os.environ:
                    os.environ[key] = value
    except Exception:
        pass


def load_api_key_file(path: str) -> None:
    if not os.path.exists(path):
        return
    try:
        with open(path, "r", encoding="utf-8") as f:
            content = f.read().strip()
        if not content:
            return
        if "=" in content:
            for raw_line in content.splitlines():
                line = raw_line.strip()
                if not line or line.startswith("#") or "=" not in line:
                    continue
                key, value = line.split("=", 1)
                key = key.strip()
                value = value.strip().strip('"').strip("'")
                if key:
                    os.environ[key] = value
        else:
            os.environ["OPENAI_API_KEY"] = content
    except Exception:
        pass


load_local_env(ENV_PATH)
load_api_key_file(API_KEY_FILE_PATH)
CONFIG = load_config()
MODEL = CONFIG["models"][0] if CONFIG["models"] else "gpt-4.1-mini"
TOP_K = max(1, min(10, int(CONFIG["defaults"].get("top_k_matches", 5))))
RAG_CONFIG = CONFIG.get("rag", {})

DATASET = DeidentifiedDataset(
    DATASET_CANDIDATE_PATHS,
    faiss_index_path=os.path.join(BASE_DIR, "medbot_faiss.index"),
    embedding_model=str(RAG_CONFIG.get("embedding_model", "text-embedding-3-small")),
    chunk_size_chars=int(RAG_CONFIG.get("chunk_size_chars", 800)),
    chunk_overlap_chars=int(RAG_CONFIG.get("chunk_overlap_chars", 120)),
    embedding_batch_size=int(RAG_CONFIG.get("embedding_batch_size", 64)),
)
DATASET_OK, DATASET_MESSAGE = DATASET.load(
    api_key=os.getenv("OPENAI_API_KEY", "").strip(),
    rebuild_index=bool(RAG_CONFIG.get("rebuild_index_on_startup", False)),
)
DATASET_LOCK = threading.Lock()
REINDEXING = False

app = Flask(__name__)


@app.get("/")
def home():
    return render_template("index.html")


@app.get("/api/status")
def status():
    return jsonify(
        {
            "ok": True,
            "dataset_loaded": DATASET_OK,
            "dataset_message": DATASET_MESSAGE,
            "records": len(DATASET.records),
            "rag_ready": DATASET.vector_ready,
            "indexed_chunks": DATASET.indexed_chunks,
            "rag_error": DATASET.last_error,
            "reindexing": REINDEXING,
            "model": MODEL,
        }
    )


@app.post("/api/reindex")
def reindex():
    global DATASET_OK, DATASET_MESSAGE, REINDEXING

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return jsonify({"ok": False, "error": "Missing API key in PrivateKey.txt."}), 500

    with DATASET_LOCK:
        if REINDEXING:
            return jsonify({"ok": False, "error": "Reindex already in progress."}), 409
        REINDEXING = True

    try:
        ok, message = DATASET.load(api_key=api_key, rebuild_index=True)
        DATASET_OK = ok
        DATASET_MESSAGE = message
        return jsonify(
            {
                "ok": ok,
                "dataset_loaded": DATASET_OK,
                "dataset_message": DATASET_MESSAGE,
                "records": len(DATASET.records),
                "rag_ready": DATASET.vector_ready,
                "indexed_chunks": DATASET.indexed_chunks,
                "rag_error": DATASET.last_error,
            }
        ), (200 if ok else 500)
    finally:
        with DATASET_LOCK:
            REINDEXING = False


@app.post("/api/chat")
def chat():
    body = request.get_json(silent=True) or {}
    message = str(body.get("message", "")).strip()
    if not message:
        return jsonify({"ok": False, "error": "Message is required."}), 400

    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    if not api_key:
        return jsonify({"ok": False, "error": "Missing API key in PrivateKey.txt."}), 500
    if REINDEXING:
        return jsonify({"ok": False, "error": "RAG reindex in progress. Try again in a moment."}), 503
    if not DATASET.vector_ready:
        return jsonify({"ok": False, "error": f"RAG index is not ready. {DATASET_MESSAGE}"}), 500

    matches = DATASET.search(message, top_k=TOP_K)
    context = DATASET.build_context(matches)

    try:
        client = OpenAI(api_key=api_key)
        result = client.responses.create(
            model=MODEL,
            instructions=(
                "You are a medical information assistant. Provide general information only and suggest "
                "seeing a licensed clinician for diagnosis or treatment decisions. "
                "Use the provided de-identified reference cases as decision-support context."
            ),
            input=(
                "Reference cases from local de-identified dataset:\n"
                f"{context}\n\n"
                "User question:\n"
                f"{message}"
            ),
        )
        text = result.output_text or "No response text returned."
        return jsonify({"ok": True, "response": text, "matches": matches})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True, use_reloader=False, load_dotenv=False)
