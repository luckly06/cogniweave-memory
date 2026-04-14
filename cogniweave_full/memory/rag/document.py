from __future__ import annotations

import uuid
from typing import Dict, List

from ..utils import simple_keyword_summary


class DocumentIngestionService:
    def chunk_text(self, text: str, chunk_size: int = 600, overlap: int = 80) -> List[str]:
        text = text or ""
        if len(text) <= chunk_size:
            return [text]
        chunks = []
        start = 0
        while start < len(text):
            end = start + chunk_size
            chunks.append(text[start:end])
            if end >= len(text):
                break
            start = max(0, end - overlap)
        return chunks

    def make_document_payloads(self, source_id: str, text: str, source_type: str = "document") -> List[Dict]:
        chunks = self.chunk_text(text)
        payloads = []
        for idx, chunk in enumerate(chunks):
            payloads.append(
                {
                    "source_id": source_id,
                    "chunk_id": str(uuid.uuid5(uuid.NAMESPACE_URL, f"{source_id}::chunk::{idx}")),
                    "source_type": source_type,
                    "content": chunk,
                    "summary": simple_keyword_summary(chunk, 240),
                }
            )
        return payloads
