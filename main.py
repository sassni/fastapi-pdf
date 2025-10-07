from datetime import datetime
import logging
import os
import re
import uuid
import hmac
from datetime import datetime
from typing import Optional

# FastAPI imports
from fastapi import FastAPI, HTTPException, Header, Depends, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse, FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field, validator

# ReportLab for PDF generation
from reportlab.lib.pagesizes import LETTER
from reportlab.pdfgen.canvas import Canvas
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, Image
from reportlab.lib import colors
from reportlab.lib.styles import getSampleStyleSheet
from reportlab.graphics.shapes import Drawing
from reportlab.graphics.charts.barcharts import VerticalBarChart

# Add metadatas
from PyPDF2 import PdfReader, PdfWriter

from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Configuration & Logging
OUTPUT_DIR = "output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("fastapi-pdf")

app = FastAPI(
    title="PDF Generator API",
    description="Accept JSON, validate, require X-API-KEY, generate PDF and save locally or return file.",
    version="1.0.0",
)

# Serve generated PDF files at /output/<filename>.pdf
app.mount("/output", StaticFiles(directory=OUTPUT_DIR), name="output")


# Pydantic request model
class PDFRequest(BaseModel):
    name: str = Field(..., min_length=1, example="Alice Example")
    age: int = Field(..., ge=0, le=150, example=30)
    score1: float = Field(..., ge=0.0, example=88.5)
    score2: float = Field(..., ge=0.0, example=92.0)
    filename: Optional[str] = Field(
        None, description="Optional filename ending with .pdf", example="alice_report.pdf"
    )

    @validator("name")
    def _strip_name(cls, v: str) -> str:
        cleaned = v.strip()
        if not cleaned:
            raise ValueError("name must not be empty or whitespace")
        return cleaned

    @validator("filename")
    def _validate_filename(cls, v: Optional[str]) -> Optional[str]:
        if v is None:
            return v
        # Prevent path traversal or weird characters
        if "/" in v or "\\" in v:
            raise ValueError("filename must not include path separators")
        if not v.lower().endswith(".pdf"):
            raise ValueError("filename must end with .pdf")
        # allow letters, numbers, underscores, dashes, dots
        if re.search(r"[^A-Za-z0-9_.-]", v):
            raise ValueError(
                "filename contains invalid characters (allowed: letters, numbers, '-', '_', '.')"
            )
        return v


# Helpers
def make_safe_filename(requested: Optional[str], base_name: str) -> str:
    if requested:
        filename = os.path.basename(requested)
        filename = re.sub(r"[^A-Za-z0-9_.-]", "_", filename)
        if not filename.lower().endswith(".pdf"):
            filename += ".pdf"
        return filename
    name_clean = re.sub(r"[^A-Za-z0-9_.-]", "_", base_name.strip() or "report")
    return f"{name_clean}_{uuid.uuid4().hex[:8]}.pdf"


def generate_pdf_file(payload: PDFRequest, output_path: str, logo_path: Optional[str] = None) -> None:
    try:
        # Create PDF document
        doc = SimpleDocTemplate(output_path, pagesize=LETTER)
        styles = getSampleStyleSheet()
        story = []

        # Add title
        story.append(Paragraph("Generated Report", styles["Title"]))
        story.append(Spacer(1, 12))

        # Logo
        if logo_path and os.path.exists(logo_path):
            img = Image(logo_path, width=120, height=60)
            story.append(img)
            story.append(Spacer(1, 12))

        # Add user details as table
        data = [
            ["Name", payload.name],
            ["Age", str(payload.age)],
            ["Score 1", str(payload.score1)],
            ["Score 2", str(payload.score2)],
            ["Total", str(payload.score1 + payload.score2)],
            ["Average", f"{(payload.score1 + payload.score2) / 2:.2f}"],
        ]

        table = Table(data, colWidths=[100, 300])
        table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, 0), colors.lightgrey),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.black),
            ("GRID", (0, 0), (-1, -1), 1, colors.black),
            ("FONTNAME", (0, 0), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 0), (-1, -1), 10),
            ("BACKGROUND", (0, 1), (-1, -1), colors.whitesmoke),
        ]))
        story.append(table)
        story.append(Spacer(1, 20))

        # Add a simple bar chart
        drawing = Drawing(400, 200)
        bc = VerticalBarChart()
        bc.x = 50
        bc.y = 50
        bc.height = 125
        bc.width = 300
        bc.data = [[payload.score1, payload.score2]]
        bc.strokeColor = colors.black
        bc.valueAxis.valueMin = 0
        bc.valueAxis.valueMax = max(payload.score1, payload.score2) + 10
        bc.valueAxis.valueStep = max(1, (int(bc.valueAxis.valueMax) // 5))
        bc.categoryAxis.categoryNames = ["Score 1", "Score 2"]
        bc.categoryAxis.labels.boxAnchor = "ne"
        bc.barWidth = 20
        bc.groupSpacing = 15
        drawing.add(bc)
        story.append(drawing)

        # Build PDF
        doc.build(story)


        # Re-open to add metadata
        reader = PdfReader(output_path)
        writer = PdfWriter()
        for page in reader.pages:
            writer.add_page(page)

        writer.add_metadata({
            "/Title": "User Report",
            "/Author": "FastAPI PDF Generator",
            "/Subject": "Generated PDF with user data",
        })

        with open(output_path, "wb") as f_out:
            writer.write(f_out)

    except Exception as exc:
        logger.exception("PDF generation error: %s", exc)
        raise RuntimeError(f"Failed to create PDF: {exc}") from exc

# API key verification dependency
def verify_api_key(x_api_key: Optional[str] = Header(None)):

    expected = os.getenv("API_KEY")
    if not expected:
        logger.error("API_KEY is not set in environment.")
        raise HTTPException(status_code=500, detail="Server misconfiguration: API key not configured")

    if x_api_key is None:
        logger.warning("Missing X-API-KEY header")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: missing API key")

    # Use constant-time compare for safety
    if not hmac.compare_digest(x_api_key, expected):
        logger.warning("Invalid X-API-KEY provided")
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Forbidden: invalid API key")

    return True

# Exception handler for validation errors
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request, exc: RequestValidationError):
    errors = []
    for err in exc.errors():
        errors.append({"loc": err.get("loc", []), "msg": err.get("msg", ""), "type": err.get("type", "")})
    return JSONResponse(status_code=422, content={"detail": "Input validation error", "errors": errors})

# Endpoints
@app.post("/generate-pdf")
async def generate_pdf_endpoint(payload: PDFRequest, authorized: bool = Depends(verify_api_key)):
    try:
        filename = make_safe_filename(payload.filename, payload.name)
        output_path = os.path.join(OUTPUT_DIR, filename)

        logger.info("Generating PDF for %s -> %s", payload.name, output_path)
        generate_pdf_file(payload, output_path, logo_path="logo.png")

        download_url = f"/{OUTPUT_DIR}/{filename}"
        logger.info("PDF generation completed: %s", output_path)

        return {"success": True, "file_path": output_path, "download_url": download_url}
    except RuntimeError as rte:
        logger.error("Runtime error while generating PDF: %s", rte)
        raise HTTPException(status_code=500, detail=str(rte))
    except Exception as exc:
        logger.exception("Unexpected error in /generate-pdf")
        raise HTTPException(status_code=500, detail="Unexpected server error") from exc

# New endpoint: return FileResponse
@app.post("/download-pdf")
async def download_pdf_endpoint(payload: PDFRequest, authorized: bool = Depends(verify_api_key)):
    try:
        filename = make_safe_filename(payload.filename, payload.name)
        output_path = os.path.join(OUTPUT_DIR, filename)

        logo_path = "logo.png"
        generate_pdf_file(payload, output_path, logo_path=logo_path)

        logger.info("PDF ready for download: %s", output_path)
        return FileResponse(
            output_path,
            media_type="application/pdf",
            filename=filename
        )
    except Exception as exc:
        logger.exception("Error in /download-pdf")
        raise HTTPException(status_code=500, detail=f"Could not generate PDF: {exc}")

@app.get("/")
async def root():
    return {
        "message": "PDF Generator API is running. See /docs for Swagger UI.",
        "docs": "/docs",
    }
