import json
from pathlib import Path

from pypdf import PdfReader


root = Path(r"input/SCAN BỔ SUNG THÊM VĂN BẰNG CHỨNG CHỈ")
summary = []
failures = []

for person_dir in sorted(path for path in root.iterdir() if path.is_dir()):
    pages = 0
    files = 0
    for pdf in sorted(person_dir.glob("*.pdf")):
        try:
            reader = PdfReader(pdf)
            pages += len(reader.pages)
            files += 1
        except Exception as error:
            failures.append({"person": person_dir.name, "file": pdf.name, "error": type(error).__name__})
    summary.append({"person": person_dir.name, "pdf_files": files, "pages": pages})

print(json.dumps({"summary": summary, "failures": failures}, ensure_ascii=False))
