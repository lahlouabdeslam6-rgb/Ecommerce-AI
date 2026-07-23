from pydantic import BaseModel, Field

from app.schemas.product import ProductResponse


class AIInfrastructureStatus(BaseModel):
    redis: str
    qdrant: str
    ollama: str
    chat_model: str
    embedding_model: str
    installed_models: list[str]
    models_ready: bool


class AIInfrastructureTestResponse(BaseModel):
    redis_cache: bool
    embedding_dimensions: int
    qdrant_collection: str
    qdrant_collection_ready: bool
    generation: str


class ProductAISuggestion(BaseModel):
    description: str = Field(min_length=40, max_length=1500)
    category: str = Field(min_length=2, max_length=120)
    seo_title: str = Field(min_length=10, max_length=70)
    seo_description: str = Field(min_length=40, max_length=180)
    seo_keywords: list[str] = Field(min_length=3, max_length=12)
    tags: list[str] = Field(min_length=2, max_length=12)


class ProductAISuggestionResponse(ProductAISuggestion):
    product_id: int
    model: str
    cached: bool = False


class ProductAIApplyResponse(BaseModel):
    product: ProductResponse
    indexed: bool
