import os
from pathlib import Path
from dotenv import load_dotenv
load_dotenv()
ROOT=Path(__file__).resolve().parents[1]
DATA_DIR=Path(os.getenv('DATA_DIR',ROOT/'data')); DATA_DIR.mkdir(parents=True,exist_ok=True)
SQLITE_PATH=Path(os.getenv('SQLITE_PATH',DATA_DIR/'retail.db'))
CHROMA_DIR=Path(os.getenv('CHROMA_DIR',DATA_DIR/'chroma'))
DOCS_DIR=DATA_DIR/'documents'; AUDIT_PATH=DATA_DIR/'audit.jsonl'
OLLAMA_BASE_URL=os.getenv('OLLAMA_BASE_URL','http://localhost:11434')
OLLAMA_MODEL=os.getenv('OLLAMA_MODEL','llama3.1:8b')
MOCK_LLM=os.getenv('MOCK_LLM','false').lower()=='true'
RETRIEVAL_TOP_K=int(os.getenv('RETRIEVAL_TOP_K','5'))
ADMIN_PASSWORD=os.getenv('ADMIN_PASSWORD','1234')
