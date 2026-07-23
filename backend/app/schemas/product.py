from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field


class IngredientResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str | None = None
    form: str | None = None
    category: str | None = None
    amount_per_serving_mg: float | None = None
    is_proprietary_blend: bool = False
    recommended_daily_mg: float | None = None
    upper_safety_limit_mg: float | None = None
    pubchem_cid: int | None = None
    molecular_formula: str | None = None
    molecular_weight: float | None = None
    inchikey: str | None = None
    canonical_smiles: str | None = None


class ServingSizeResponse(BaseModel):
    count: float | None = None
    unit: str | None = None


class ProductSourceResponse(BaseModel):
    dsld_label_id: int | None = None
    url: str | None = None
    dataset_version: str | None = None


class ProductCreate(BaseModel):
    brand: str = Field(min_length=1, max_length=120)
    name: str = Field(min_length=1, max_length=240)
    upc_barcode: str | None = Field(default=None, max_length=80)
    form_type: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    category: str | None = Field(default=None, max_length=120)
    price: float = Field(ge=0)
    currency: str = Field(default="MAD", pattern=r"^[A-Z]{3}$")
    stock: int = Field(default=0, ge=0)
    is_active: bool = True
    images: list[str] = Field(default_factory=list, max_length=12)
    serving_size: ServingSizeResponse | None = None
    servings_per_container: float | None = Field(default=None, ge=0)
    ingredients: list[IngredientResponse] = Field(default_factory=list)
    seo_title: str | None = Field(default=None, max_length=70)
    seo_description: str | None = Field(default=None, max_length=180)
    seo_keywords: list[str] = Field(default_factory=list, max_length=12)
    tags: list[str] = Field(default_factory=list, max_length=12)


class ProductUpdate(BaseModel):
    brand: str | None = Field(default=None, min_length=1, max_length=120)
    name: str | None = Field(default=None, min_length=1, max_length=240)
    upc_barcode: str | None = Field(default=None, max_length=80)
    form_type: str | None = Field(default=None, max_length=120)
    description: str | None = Field(default=None, max_length=4000)
    category: str | None = Field(default=None, max_length=120)
    price: float | None = Field(default=None, ge=0)
    currency: str | None = Field(default=None, pattern=r"^[A-Z]{3}$")
    stock: int | None = Field(default=None, ge=0)
    is_active: bool | None = None
    images: list[str] | None = Field(default=None, max_length=12)
    serving_size: ServingSizeResponse | None = None
    servings_per_container: float | None = Field(default=None, ge=0)
    ingredients: list[IngredientResponse] | None = None
    seo_title: str | None = Field(default=None, max_length=70)
    seo_description: str | None = Field(default=None, max_length=180)
    seo_keywords: list[str] | None = Field(default=None, max_length=12)
    tags: list[str] | None = Field(default=None, max_length=12)


class ProductStockUpdate(BaseModel):
    stock: int = Field(ge=0)


class ProductImageResponse(BaseModel):
    url: str


class ProductImagesOrder(BaseModel):
    images: list[str] = Field(max_length=12)


class ProductResponse(BaseModel):
    model_config = ConfigDict(extra="ignore")

    product_id: int
    brand: str | None = None
    name: str | None = None
    upc_barcode: str | None = None
    form_type: str | None = None
    description: str | None = None
    category: str | None = None
    price: float | None = None
    currency: str = "MAD"
    stock: int = 0
    is_active: bool = True
    images: list[str] = Field(default_factory=list)
    serving_size: ServingSizeResponse | None = None
    servings_per_container: float | None = None
    source: ProductSourceResponse | None = None
    ingredients: list[IngredientResponse] = Field(default_factory=list)
    seo_title: str | None = None
    seo_description: str | None = None
    seo_keywords: list[str] = Field(default_factory=list)
    tags: list[str] = Field(default_factory=list)
    ai_model: str | None = None
    ai_generated_at: datetime | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None


class ProductListResponse(BaseModel):
    items: list[ProductResponse]
    total: int
    page: int
    page_size: int
    total_pages: int
