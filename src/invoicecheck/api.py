"""HTTP API for the verification layer: POST an extracted invoice, get an approve / review decision with reasons.

  INVOICECHECK_REGISTRY=data/registry/registry.sqlite uvicorn invoicecheck.api:app      # real NTA snapshot (local cache)
  uvicorn invoicecheck.api:app                                                         # synthetic registry from data/synth

The extractor is not part of this service: it checks whatever extraction a model (or a person) produces. Nothing is trusted.
"""
import json
import os
from pathlib import Path

from fastapi import FastAPI
from pydantic import BaseModel, Field

from .registry import Record, Registry
from .verify import LAYERS, verify

app = FastAPI(title="Invoice-Check JP", version="0.1.0",
              description="Verifies extracted Japanese qualified-invoice fields: check digit, NTA registry, issuer name, tax arithmetic.")
_registry = None


def get_registry():
    global _registry
    if _registry is None:
        path = os.environ.get("INVOICECHECK_REGISTRY")
        if path and path.endswith(".sqlite"):
            _registry = Registry(path)
        else:
            src = Path(path or "data/synth/registry_synthetic.jsonl")
            _registry = Registry.from_records([Record(**json.loads(l)) for l in src.read_text(encoding="utf-8").splitlines() if l.strip()])
    return _registry


class VerifyRequest(BaseModel):
    extraction: dict = Field(..., description="Extracted invoice: issuer_name, registration_number, issue_date (ISO), recipient_name, invoice_number, "
                                              "tax_included, items[], totals[], grand_total")
    layers: list[str] = Field(default_factory=lambda: list(LAYERS), description=f"Checks to run, any of {LAYERS}")


class VerifyResponse(BaseModel):
    decision: str            # "approve" or "review"
    approved: bool
    reasons: list[str]
    detail: dict


@app.get("/health")
def health():
    return {"status": "ok", "registry_size": get_registry().count(), "layers": LAYERS}


@app.post("/verify", response_model=VerifyResponse)
def verify_endpoint(req: VerifyRequest):
    layers = [l for l in req.layers if l in LAYERS] or list(LAYERS)
    v = verify(req.extraction, get_registry(), layers)
    return VerifyResponse(decision="approve" if v.approved else "review", approved=v.approved, reasons=v.reasons, detail=v.detail)
