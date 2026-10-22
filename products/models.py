from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator


class Product(models.Model):
    """
    Represents an authoritative catalog product with verified physical specifications.
    All dimensions are in centimetres (cm), and weight is in kilograms (kg).
    """
    sku = models.CharField(max_length=64, unique=True, db_index=True, help_text="Unique Stock Keeping Unit")
    name = models.CharField(max_length=255, help_text="Product display name")
    length = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Length in centimetres (cm)"
    )
    width = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Width in centimetres (cm)"
    )
    height = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Height in centimetres (cm)"
    )
    weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text="Product weight in kilograms (kg)"
    )
    clearance = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00'),
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Additional clearance required on each side in centimetres (cm)"
    )
    is_fragile = models.BooleanField(default=False, help_text="Indicates if item requires fragile handling/protective packaging")
    is_active = models.BooleanField(default=True, db_index=True, help_text="Whether this product is currently active in the catalog")
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['sku']
        verbose_name = 'Product'
        verbose_name_plural = 'Products'
        constraints = [
            models.CheckConstraint(condition=models.Q(length__gt=0), name='product_length_gt_0'),
            models.CheckConstraint(condition=models.Q(width__gt=0), name='product_width_gt_0'),
            models.CheckConstraint(condition=models.Q(height__gt=0), name='product_height_gt_0'),
            models.CheckConstraint(condition=models.Q(weight__gt=0), name='product_weight_gt_0'),
            models.CheckConstraint(condition=models.Q(clearance__gte=0), name='product_clearance_gte_0'),
        ]

    def __str__(self):
        return f"{self.sku} - {self.name} ({self.length}x{self.width}x{self.height} cm, {self.weight} kg)"

    @property
    def volume(self) -> Decimal:
        """Physical volume of the product in cubic centimetres (cm³)."""
        return self.length * self.width * self.height

    @property
    def effective_dimensions(self) -> tuple[Decimal, Decimal, Decimal]:
        """
        Dimensions including clearance on each side:
        axis_effective = axis + 2 * clearance
        """
        extra = self.clearance * Decimal('2')
        return (self.length + extra, self.width + extra, self.height + extra)

    @property
    def effective_volume(self) -> Decimal:
        """Required volume including clearance in cm³."""
        l, w, h = self.effective_dimensions
        return l * w * h
