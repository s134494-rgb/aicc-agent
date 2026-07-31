# Setup (English)

Install Python 3.11+, Tesseract OCR and Arabic/English language packs. Create a
virtual environment, install `requirements.txt`, then run:

`uvicorn app.main:app --host 127.0.0.1 --port 8000`

Open `http://127.0.0.1:8000`; OpenAPI is at `/docs`. Demo credentials are
documented in the main README and must be replaced before production.
