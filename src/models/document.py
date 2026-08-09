from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator


class CanonicalDocument(BaseModel):
    doc_id: str

    source: str
    source_type: str

    title: str
    heading_path: Optional[str] = None

    content: str

    url: Optional[str] = None
    page: Optional[int] = None

    metadata: dict[str, Any] = Field(default_factory=dict)

    @field_validator("content")
    @classmethod
    def validate_content(cls, value: str) -> str:
        value = value.strip()

        if not value:
            raise ValueError("Document content cannot be empty")

        return value