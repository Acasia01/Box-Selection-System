from decimal import Decimal
from django.db import models
from django.core.validators import MinValueValidator
from products.models import Product
from boxes.models import BoxType


class Order(models.Model):
    """
    Represents an ecommerce customer order to be packed in the warehouse.
    """
    STATUS_PENDING = 'PENDING'
    STATUS_PACKED = 'PACKED'
    STATUS_SHIPPED = 'SHIPPED'
    STATUS_CANCELLED = 'CANCELLED'

    STATUS_CHOICES = [
        (STATUS_PENDING, 'Pending Packing'),
        (STATUS_PACKED, 'Packed'),
        (STATUS_SHIPPED, 'Shipped'),
        (STATUS_CANCELLED, 'Cancelled'),
    ]

    order_number = models.CharField(
        max_length=64,
        unique=True,
        db_index=True,
        help_text="Unique customer order identifier, e.g. ORD-1001"
    )
    customer_name = models.CharField(
        max_length=255,
        blank=True,
        help_text="Customer or recipient name"
    )
    status = models.CharField(
        max_length=20,
        choices=STATUS_CHOICES,
        default=STATUS_PENDING,
        db_index=True,
    )
    assigned_box = models.ForeignKey(
        BoxType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='assigned_orders',
        help_text="Box explicitly assigned and reserved for this order"
    )
    is_assigned = models.BooleanField(
        default=False,
        help_text="Whether a box has been officially assigned and stock reserved"
    )
    assigned_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp of box assignment and stock reservation"
    )
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Order'
        verbose_name_plural = 'Orders'

    def __str__(self):
        return f"Order {self.order_number} ({self.get_status_display()})"

    @property
    def total_items_quantity(self) -> int:
        return sum(item.quantity for item in self.items.all())

    @property
    def total_weight(self) -> Decimal:
        return sum(item.product.weight * item.quantity for item in self.items.all())


class OrderItem(models.Model):
    """
    Line item belonging to an order, linking to a catalog product with quantity.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='items'
    )
    product = models.ForeignKey(
        Product,
        on_delete=models.PROTECT,
        related_name='order_items'
    )
    quantity = models.PositiveIntegerField(
        default=1,
        validators=[MinValueValidator(1)],
        help_text="Units of this product in the order"
    )

    class Meta:
        verbose_name = 'Order Item'
        verbose_name_plural = 'Order Items'
        constraints = [
            models.UniqueConstraint(fields=['order', 'product'], name='unique_product_per_order')
        ]

    def __str__(self):
        return f"{self.quantity}x {self.product.sku} for {self.order.order_number}"

    @property
    def total_weight(self) -> Decimal:
        return self.product.weight * self.quantity


class RecommendationRun(models.Model):
    """
    Audit and history log of a recommendation calculation for an order.
    """
    order = models.ForeignKey(
        Order,
        on_delete=models.CASCADE,
        related_name='recommendation_runs'
    )
    algorithm_version = models.CharField(
        max_length=64,
        default='v1.0.0-3D-EXTREME-POINTS',
        help_text="Version of packaging logic used"
    )
    requester = models.CharField(
        max_length=150,
        default='warehouse_operator',
        help_text="User or system service that requested the recommendation"
    )
    is_successful = models.BooleanField(
        default=False,
        help_text="Whether at least one eligible box was found"
    )
    best_box = models.ForeignKey(
        BoxType,
        null=True,
        blank=True,
        on_delete=models.SET_NULL,
        related_name='recommended_runs'
    )
    total_items_count = models.PositiveIntegerField(default=0)
    total_products_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000')
    )
    protective_material_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000')
    )
    summary = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        ordering = ['-created_at']
        verbose_name = 'Recommendation Run'
        verbose_name_plural = 'Recommendation Runs'

    def __str__(self):
        status = "Success" if self.is_successful else "No Fit"
        box_code = self.best_box.code if self.best_box else "None"
        return f"Recommendation for {self.order.order_number} [{status}: {box_code}] at {self.created_at:%Y-%m-%d %H:%M}"


class RecommendationCandidate(models.Model):
    """
    Evaluation record for each candidate box checked during a recommendation run.
    """
    run = models.ForeignKey(
        RecommendationRun,
        on_delete=models.CASCADE,
        related_name='candidates'
    )
    box_type = models.ForeignKey(
        BoxType,
        on_delete=models.PROTECT,
        related_name='candidate_evaluations'
    )
    is_eligible = models.BooleanField(default=False)
    rank = models.PositiveIntegerField(null=True, blank=True)
    total_packed_weight = models.DecimalField(
        max_digits=10,
        decimal_places=3,
        default=Decimal('0.000')
    )
    cost = models.DecimalField(
        max_digits=10,
        decimal_places=2,
        default=Decimal('0.00')
    )
    unused_volume = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        default=Decimal('0.00')
    )
    rejection_reasons = models.JSONField(
        default=list,
        help_text="List of reasons why this box failed eligibility checks"
    )
    placements_json = models.JSONField(
        default=list,
        help_text="3D spatial coordinates and orientations of packed items"
    )
    explanation = models.TextField(blank=True)

    class Meta:
        ordering = ['rank', 'cost']
        verbose_name = 'Recommendation Candidate'
        verbose_name_plural = 'Recommendation Candidates'

    def __str__(self):
        status = f"Eligible (Rank #{self.rank})" if self.is_eligible else "Rejected"
        return f"{self.box_type.code} in Run #{self.run_id}: {status}"
