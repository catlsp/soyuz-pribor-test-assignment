"""Russian B2B product-card copy generation."""

from .models import validate_product
from .service import generate, generate_demo

__all__ = ["validate_product", "generate", "generate_demo"]
