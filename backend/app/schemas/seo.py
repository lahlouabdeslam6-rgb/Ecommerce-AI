from datetime import datetime

from pydantic import BaseModel, Field


class SEOAuditItem(BaseModel):
    product_id: int
    name: str
    brand: str | None = None
    score: int = Field(ge=0, le=100)
    issues: list[str]
    slug: str | None = None


class SEOAuditSummary(BaseModel):
    products: int
    excellent: int
    needs_work: int
    critical: int
    average_score: float


class SEOAuditReport(BaseModel):
    generated_at: datetime
    summary: SEOAuditSummary
    items: list[SEOAuditItem]
    read_only: bool = True


class SEOFaqItem(BaseModel):
    question: str = Field(min_length=5, max_length=180)
    answer: str = Field(min_length=10, max_length=500)


class SEOProposal(BaseModel):
    product_id: int
    slug: str = Field(pattern=r"^[a-z0-9]+(?:-[a-z0-9]+)*$", max_length=180)
    seo_title: str = Field(min_length=10, max_length=70)
    seo_description: str = Field(min_length=40, max_length=180)
    seo_keywords: list[str] = Field(min_length=3, max_length=12)
    image_alt: str = Field(min_length=5, max_length=180)
    seo_faq: list[SEOFaqItem] = Field(min_length=2, max_length=5)
    model: str = "SEO Agent local"
    read_only: bool = True


class SEOApplyResponse(BaseModel):
    product_id: int
    applied_fields: list[str]
    score_before: int
    score_after: int

