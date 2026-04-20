import re
import sys
import time
from pathlib import Path
from tempfile import NamedTemporaryFile

import torch
from docling.datamodel.base_models import InputFormat
from docling.datamodel.pipeline_options import PdfPipelineOptions
from docling.document_converter import DocumentConverter, PdfFormatOption
from sentence_transformers import SentenceTransformer

APP_ROOT = Path(__file__).resolve().parents[1]
if str(APP_ROOT) not in sys.path:
    sys.path.insert(0, str(APP_ROOT))

from config import EMBEDDING_MODEL_NAME

MAX_DOWNLOAD_ATTEMPTS = 4
DEFAULT_RETRY_DELAY_SECONDS = 120
RETRY_AFTER_RE = re.compile(r"Retry after (\d+) seconds", re.IGNORECASE)

DOCLING_WARMUP_PDF_BYTES = b"""%PDF-1.1
1 0 obj
<< /Type /Catalog /Pages 2 0 R >>
endobj
2 0 obj
<< /Type /Pages /Kids [3 0 R] /Count 1 >>
endobj
3 0 obj
<< /Type /Page /Parent 2 0 R /MediaBox [0 0 300 144] /Contents 4 0 R /Resources << /Font << /F1 5 0 R >> >> >>
endobj
4 0 obj
<< /Length 40 >>
stream
BT
/F1 18 Tf
72 72 Td
(Docling warmup) Tj
ET
endstream
endobj
5 0 obj
<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>
endobj
xref
0 6
0000000000 65535 f 
0000000010 00000 n 
0000000063 00000 n 
0000000122 00000 n 
0000000248 00000 n 
0000000338 00000 n 
trailer
<< /Root 1 0 R /Size 6 >>
startxref
408
%%EOF
"""


def configure_torch_runtime() -> None:
    cpu_capability_getter = getattr(torch._C, "_get_cpu_capability", None)
    cpu_capability = cpu_capability_getter() if callable(cpu_capability_getter) else "unknown"

    if cpu_capability == "NO AVX" and torch.backends.mkldnn.enabled:
        torch.backends.mkldnn.enabled = False
        print(
            "Disabled torch MKLDNN backend for model warmup because the host CPU "
            f"capability is {cpu_capability}"
        )


def build_converter() -> DocumentConverter:
    pipeline_options = PdfPipelineOptions()
    pipeline_options.do_ocr = False
    pipeline_options.do_table_structure = False

    return DocumentConverter(
        format_options={
            InputFormat.PDF: PdfFormatOption(
                pipeline_options=pipeline_options,
            )
        }
    )


def get_retry_delay_seconds(error: Exception) -> int:
    match = RETRY_AFTER_RE.search(str(error))
    if match is not None:
        return int(match.group(1))
    return DEFAULT_RETRY_DELAY_SECONDS


def is_rate_limited(error: Exception) -> bool:
    message = str(error)
    return "429" in message or "rate limit" in message.lower()


def warm_with_retries(label: str, func, nonfatal_error_match: str | None = None) -> None:
    for attempt in range(1, MAX_DOWNLOAD_ATTEMPTS + 1):
        try:
            func()
            print(f"{label} warmed into image cache")
            return
        except Exception as error:
            message = str(error).lower()
            is_last_attempt = attempt == MAX_DOWNLOAD_ATTEMPTS
            is_nonfatal = nonfatal_error_match is not None and nonfatal_error_match in message

            if is_nonfatal:
                print(
                    f"{label} assets downloaded, but warmup hit a non-fatal inference "
                    "error; continuing with cached assets"
                )
                return

            if not is_rate_limited(error) or is_last_attempt:
                raise

            delay_seconds = get_retry_delay_seconds(error)
            print(
                f"{label} preload hit a Hugging Face rate limit on attempt "
                f"{attempt}/{MAX_DOWNLOAD_ATTEMPTS}; retrying in {delay_seconds}s"
            )
            time.sleep(delay_seconds)


def warm_docling_assets() -> None:
    converter = build_converter()

    with NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
        temp_file.write(DOCLING_WARMUP_PDF_BYTES)
        warmup_path = Path(temp_file.name)

    try:
        warm_with_retries(
            label="Docling",
            func=lambda: converter.convert(str(warmup_path)),
            nonfatal_error_match="could not create a primitive",
        )
    finally:
        warmup_path.unlink(missing_ok=True)


def warm_embedding_assets() -> None:
    warm_with_retries(
        label=f"Embedding model {EMBEDDING_MODEL_NAME}",
        func=lambda: SentenceTransformer(EMBEDDING_MODEL_NAME),
    )


def main() -> None:
    configure_torch_runtime()
    warm_docling_assets()
    warm_embedding_assets()


if __name__ == "__main__":
    main()
