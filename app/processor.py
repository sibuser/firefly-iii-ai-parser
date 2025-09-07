import json
import tempfile
import base64
from pathlib import Path
from typing import List

import numpy as np
import fitz  # PyMuPDF
import cv2
from PIL import Image, ImageOps

from app.log import get_logger
from app.firefly import create_and_attach
from app.ai import extract_firefly_payload

log = get_logger(__name__)

# --------- PDF → IMAGES ---------
def render_pdf(pdf_path: Path, dpi=300) -> List[Path]:
    tmpdir = Path(tempfile.mkdtemp())
    doc = fitz.open(pdf_path)
    paths = []

    log.info("pdf_render_start", file=str(pdf_path), dpi=dpi)

    for i, page in enumerate(doc):
        pix = page.get_pixmap(matrix=fitz.Matrix(dpi / 72, dpi / 72))
        out_path = tmpdir / f"{pdf_path.stem}_p{i+1}.png"
        pix.save(str(out_path))
        paths.append(out_path)
        log.info("pdf_page_rendered", page=i + 1, output=str(out_path))

    log.info("pdf_render_complete", pages=len(paths))
    return paths

# --------- IMAGE PREPROCESSING ---------
def preprocess_image(path: Path, long_side=1800) -> Path:
    log.info("preprocess_start", image=str(path))
    pil = Image.open(path)
    pil = ImageOps.exif_transpose(pil).convert("RGB")

    img = cv2.cvtColor(np.array(pil), cv2.COLOR_RGB2BGR)
    h, w = img.shape[:2]
    scale = min(1.0, long_side / max(h, w))

    if scale < 1.0:
        img = cv2.resize(img, (int(w * scale), int(h * scale)), interpolation=cv2.INTER_LANCZOS4)
        log.info("image_resized", original_size=(w, h), scaled_size=(int(w * scale), int(h * scale)))

    lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
    l, a, b = cv2.split(lab)
    l = cv2.createCLAHE(2.0, (8, 8)).apply(l)
    img = cv2.cvtColor(cv2.merge((l, a, b)), cv2.COLOR_LAB2BGR)

    out_path = path.with_stem(path.stem + "_prepped")
    cv2.imwrite(str(out_path), img)

    log.info("preprocess_complete", output=str(out_path))
    return out_path

# --------- IMAGE TO BASE64 ---------
def image_to_data_url(path: Path) -> str:
    with open(path, "rb") as f:
        img_bytes = f.read()
    mime = "image/png" if path.suffix.lower() == ".png" else "image/jpeg"
    b64 = base64.b64encode(img_bytes).decode("utf-8")
    return f"data:{mime};base64,{b64}"

# --------- MAIN PROCESSING FUNCTION ---------
def process_file(path: Path, send_firefly=False):
    log.info("process_file_start", path=str(path), firefly=send_firefly)

    is_pdf = path.suffix.lower() == ".pdf"
    pages = render_pdf(path) if is_pdf else [path]

    full_payload = {
        "fire_webhooks": True,
        "group_title": None,
        "transactions": []
    }

    for pg in pages:
        prepped = preprocess_image(pg)
        result = extract_firefly_payload(prepped)
        transactions = result.get("transactions", [])
        full_payload["transactions"].extend(transactions)
        full_payload["group_title"] = result.get("group_title") or full_payload["group_title"]
        log.info("page_processed", image=str(pg), transactions=len(transactions))

    if send_firefly:
        create_and_attach(full_payload, receipt_path=path, notes="Uploaded via bot")
        log.info("firefly_sent", total_transactions=len(full_payload["transactions"]))

    log.info(
        "process_file_complete",
        total_transactions=len(full_payload["transactions"]),
        payload_pretty=json.dumps(full_payload, indent=2, ensure_ascii=False)
    )

    return full_payload