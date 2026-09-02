# product.py
from dataclasses import dataclass
from typing import Optional


@dataclass
class Product:
    """A priced product as the till shows it.  `weight` is the pack label
    ("75g"); the measured mass lives in the database as weight_g."""
    id: str
    name: str
    price: float
    category: str
    barcode: Optional[str] = None
    stock: int = 0
    description: Optional[str] = None
    weight: Optional[str] = None
    restricted: str = "none"

    def __str__(self):
        return f"{self.name} - ฿{self.price:.2f}"

    def is_in_stock(self) -> bool:
        """Check if product is in stock"""
        return self.stock > 0

    def to_dict(self):
        """Convert to dictionary"""
        return {
            'id': self.id,
            'name': self.name,
            'price': self.price,
            'category': self.category,
            'barcode': self.barcode,
            'stock': self.stock,
            'description': self.description,
            'weight': self.weight,
            'restricted': self.restricted,
        }
