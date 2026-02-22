import json
import PyPDF2
import os

pdf_path = "../Microsoft_Senior_PM_Study_Guide_v2.pdf"
output_path = "../data/interview_corpus/microsoft_pm_pdf.json"

text = ""
try:
    with open(pdf_path, "rb") as f:
        reader = PyPDF2.PdfReader(f)
        for page in reader.pages:
            extracted = page.extract_text()
            if extracted:
                text += extracted + "\n"

    record = {
        "company": "Microsoft",
        "role": "Senior Product Manager",
        "difficulty": "hard",
        "outcome": "offer",
        "date": "2026-01-01",
        "experience": f"OFFICIAL EXCLUSIVE STUDY GUIDE EXTRACT:\n\n{text}"
    }

    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        json.dump([record], f, indent=4)
    print(f"Successfully processed PDF into {output_path}")

except Exception as e:
    print(f"Failed to process PDF: {e}")
