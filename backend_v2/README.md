# JobNexus `backend_v2` — gợi ý việc làm

Ứng dụng FastAPI tối giản: chỉ các endpoint **candidates**, **jobs**, **matching** (cùng contract với `backend`).

- Dùng chung **PostgreSQL** và **ChromaDB** (`cv_chunks` / `jd_chunks`) với backend chính nếu trỏ cùng `DATABASE_URL`, `CHROMA_*`.
- Upload file mặc định: `backend_v2/uploads/`. Nếu chạy song song với backend cũ và cần cùng file CV/JD đã lưu, trỏ thư mục upload chung (ví dụ bind volume hoặc sao chép `uploads`).

## Chạy

```bash
cd backend_v2
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:fastapi_app --host 0.0.0.0 --port 8001
```

API: `http://localhost:8001/api/v1/...` — ví dụ `/api/v1/candidates`, `/api/v1/jobs`, `/api/v1/match/...`.

Biến môi trường: file `.env` ở **root repo** (cùng pattern `backend`). Cần tối thiểu `DATABASE_URL`, `CHROMA_HOST`/`CHROMA_PORT`, `NEXUSRAG_EMBEDDING_MODEL`, `NEXUSRAG_RERANKER_MODEL`, và LLM (`GOOGLE_AI_API_KEY` nếu `LLM_PROVIDER=gemini`, hoặc Ollama).

## Ghi chú

- **Không** có LightRAG / KG trong bản này; ingestion CV/JD vẫn dùng Docling + LLM trích xuất + embedding vào Chroma.
- `AUTO_CREATE_TABLES=true` (mặc định): tạo bảng job-domain khi khởi động. Với DB đã có từ backend đầy đủ, thao tác idempotent.
