# FastAPI PDF Generator

This FastAPI application accepts a JSON POST request, validates input data, and generates a formatted PDF report using ReportLab.  
It includes API key protection using environment variables, ensuring only authorized services (like Zapier) can trigger the PDF generation.

A simple FastAPI application that:

- Accepts JSON input via API (`POST` request).
- Validates the input using **Pydantic**.
- Generates a formatted **PDF** report (with name, age, scores, total, average).
- Saves the PDF locally (in `/output`) or returns it directly as a download.
- Includes metadata, optional logo, tables, and a chart.
- Secure endpoint requiring API key authentication (`X-API-KEY`)
- Integrates easily with Zapier, Typeform, and ngrok 

---

## Features

- FastAPI with Swagger UI (`/docs`)
- Input validation (clear error messages if wrong/missing data)
- PDF generation with **ReportLab**
- Option to:
  - Save PDF to local folder + return URL (`/generate-pdf`)
  - Directly download PDF file (`/download-pdf`)
- Logging & error handling
- PEP8-compliant and clean Pythonic style

---

## Requirements

- Python 3.9+
- [FastAPI](https://fastapi.tiangolo.com/)
- [Uvicorn](https://www.uvicorn.org/)
- [ReportLab](https://www.reportlab.com/dev/)
- [PyPDF2](https://pypi.org/project/pypdf2/) (for PDF metadata)
- (Optional) [Postman](https://www.postman.com/downloads/) for API testing
- python-dotenv

Install dependencies:

```bash
pip install -r requirements.txt
```

## Requirements
```bash
uvicorn main:app --reload
```
- Swagger UI: http://127.0.0.1:8000/docs
- Root health check: http://127.0.0.1:8000/

## Environment Variables (.env File)
```
API_KEY=your_secret_key_here
```

## Running the Application
### Option 1 — Using .env File
If you have a .env file in your project root, simply run:
```
uvicorn main:app --reload
```
The python-dotenv package automatically loads your .env variables when the app starts.

### Option 2 — Manually Export Environment Variable
You can also set the variable manually before running FastAPI:
```
export API_KEY=your_secret_key_here
uvicorn main:app --reload
```

## API Endpoint
### URL
```
POST /generate-pdf
```

### Headers
```
Content-Type: application/json
X-API-KEY: your_secret_key_here
```

## Example Requests
### /generate-pdf (save + return URL)
Request JSON:
```json
{
  "name": "Alice Example",
  "age": 30,
  "score1": 88.5,
  "score2": 92.0,
  "filename": "alice_report.pdf"
}
```
Response JSON:
```json
{
  "success": true,
  "file_path": "output/alice_report.pdf",
  "download_url": "/output/alice_report.pdf"
}
```
Open the returned URL in your browser:
http://127.0.0.1:8000/output/alice_report.pdf

### /download-pdf (direct file download)
```bash
curl -X POST "http://127.0.0.1:8000/download-pdf" \
  -H "Content-Type: application/json" \
  -d '{
    "name": "Alice Example",
    "age": 30,
    "score1": 88.5,
    "score2": 92.0
  }' --output alice_report.pdf
```
This saves the PDF directly as alice_report.pdf.

## Zapier Configuration (Webhook Integration)
To connect this API with Zapier:
1. Create a new Zap in your Zapier account.
2. Choose a Trigger (Typeform submission).
3. Add an Action → “Webhooks by Zapier”.
4. Select POST request.
5. In the URL field, paste your public FastAPI URL (from ngrok):
```
https://your-app.ngrok-free.dev/generate-pdf
```
6. In the Headers section, add:
```
X-API-KEY: your_secret_key_here
```
7. In the Body, provide your JSON data fields:
```
name, age, score1, score2
```
8. Test your Zap.
If the key is correct, you’ll receive a 200 OK response and the PDF will be generated successfully inside your output/ folder.

## Testing with Postman

Open Postman → New Request.

Method: POST

URL: http://127.0.0.1:8000/generate-pdf

Body → raw → JSON → paste request JSON.

Click Send → see JSON response with download_url.

Try http://127.0.0.1:8000/download-pdf with Send and Download to save the PDF directly.