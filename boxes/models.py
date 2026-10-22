from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator


class BoxType(models.Model):
    """
    Represents a standard shipping box specification.
    Dimensions are internal measurements in centimetres (cm).
    Weights are in kilograms (kg).
    """
    code = models.CharField(max_length=32, unique=True, db_index=True, help_text="Unique box code, e.g. BX-101")
    name = models.CharField(max_length=255, help_text="Display name of the box")
    length = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Internal length in centimetres (cm)"
    )
    width = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Internal width in centimetres (cm)"
    )
    height = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.01'))],
        help_text="Internal height in centimetres (cm)"
    )
    max_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        validators=[MinValueValidator(Decimal('0.001'))],
        help_text="Maximum permitted total packed weight in kilograms (kg)"
    )
    empty_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000'),
        validators=[MinValueValidator(Decimal('0.000'))],
        help_text="Weight of the empty box itself in kilograms (kg)"
    )
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        validators=[MinValueValidator(Decimal('0.00'))],
        help_text="Cost per box unit"
    )
    currency = models.CharField(
        max_length=3,
        default='INR',
        help_text="ISO currency code (e.g., INR, USD)"
    )
    is_active = models.BooleanField(
        default=True,
        db_index=True,
        help_text="Whether this box is available for recommendations"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['cost', 'code']
        verbose_name = 'Box Type'
        verbose_name_plural = 'Box Types'
        constraints = [
            models.CheckConstraint(condition=models.Q(length__gt=0), name='box_length_gt_0'),
            models.CheckConstraint(condition=models.Q(width__gt=0), name='box_width_gt_0'),
            models.CheckConstraint(condition=models.Q(height__gt=0), name='box_height_gt_0'),
            models.CheckConstraint(condition=models.Q(max_weight__gt=0), name='box_max_weight_gt_0'),
            models.CheckConstraint(condition=models.Q(empty_weight__gte=0), name='box_empty_weight_gte_0'),
            models.CheckConstraint(condition=models.Q(cost__gte=0), name='box_cost_gte_0'),
        ]

    def __str__(self):
        return f"{self.code} - {self.name} ({self.length}x{self.width}x{self.height} cm, max {self.max_weight} kg, {self.currency} {self.cost})"

    @property
    def internal_volume(self) -> Decimal:
        """Internal volume of the box in cubic centimetres (cm³)."""
        return self.length * self.width * self.height

    @property
    def dimensions_tuple(self) -> tuple[Decimal, Decimal, Decimal]:
        return (self.length, self.width, self.height)


class BoxInventory(models.Model):
    """
    Live warehouse inventory track for a specific box type.
    """
    box_type = models.OneToOneField(
        BoxType,
        on_delete=models.CASCADE,
        related_name='inventory',
        help_text="Associated box type"
    )
    quantity_on_hand = models.PositiveIntegerField(
        default=0,
        help_text="Total physical boxes currently in warehouse"
    )
    quantity_reserved = models.PositiveIntegerField(
        default=0,
        help_text="Boxes allocated to confirmed orders but not yet shipped"
    )
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        verbose_name = 'Box Inventory'
        verbose_name_plural = 'Box Inventories'
        constraints = [
            models.CheckConstraint(
                condition=models.Q(quantity_reserved__lte=models.F('quantity_on_hand')),
                name='reserved_cannot_exceed_on_hand'
            )
        ]

    def __str__(self):
        return f"Inventory for {self.box_type.code}: {self.quantity_available} available ({self.quantity_on_hand} on hand, {self.quantity_reserved} reserved)"

    @property
    def quantity_available(self) -> int:
        """Available quantity = on_hand - reserved."""
        return max(0, self.quantity_on_hand - self.quantity_reserved)
