from decimal import Decimal
from django.test import TestCase
from products.models import Product
from boxes.models import BoxType, BoxInventory
from orders.models import Order, OrderItem, RecommendationRun, RecommendationCandidate
from orders.services.recommendation_service import (
    OrderRecommendationService,
    OrderNotFoundError,
    EmptyOrderError,
    OrderStatusError,
    InactiveProductInOrderError,
    InsufficientStockError,
)


class OrderWorkflowTests(TestCase):
    def setUp(self):
        self.service = OrderRecommendationService()

        # Create Products
        self.speaker = Product.objects.create(
            sku="SPK-TEST",
            name="Test Speaker",
            length=Decimal("20.00"),
            width=Decimal("15.00"),
            height=Decimal("10.00"),
            weight=Decimal("1.200"),
            clearance=Decimal("0.50"),
            is_fragile=True,
            is_active=True,
        )
        self.book = Product.objects.create(
            sku="BOOK-TEST",
            name="Test Book",
            length=Decimal("20.00"),
            width=Decimal("14.00"),
            height=Decimal("3.00"),
            weight=Decimal("0.500"),
            clearance=Decimal("0.00"),
            is_fragile=False,
            is_active=True,
        )

        # Create Boxes
        self.small_box = BoxType.objects.create(
            code="BX-S",
            name="Small Test Box",
            length=Decimal("22.00"),
            width=Decimal("16.00"),
            height=Decimal("6.00"),
            max_weight=Decimal("3.000"),
            empty_weight=Decimal("0.100"),
            cost=Decimal("10.00"),
            currency="INR",
            is_active=True,
        )
        BoxInventory.objects.create(
            box_type=self.small_box,
            quantity_on_hand=50,
            quantity_reserved=0,
        )

        self.med_box = BoxType.objects.create(
            code="BX-M",
            name="Medium Test Box",
            length=Decimal("30.00"),
            width=Decimal("25.00"),
            height=Decimal("20.00"),
            max_weight=Decimal("8.000"),
            empty_weight=Decimal("0.300"),
            cost=Decimal("18.00"),
            currency="INR",
            is_active=True,
        )
        BoxInventory.objects.create(
            box_type=self.med_box,
            quantity_on_hand=50,
            quantity_reserved=5,  # 45 available
        )

        # Create Order ORD-01
        self.order1 = Order.objects.create(
            order_number="ORD-01",
            customer_name="Alice",
            status=Order.STATUS_PENDING,
        )
        OrderItem.objects.create(order=self.order1, product=self.speaker, quantity=1)

    def test_valid_order_recommendation_and_persistence(self):
        """
        Valid order generates a recommendation based on DB records,
        persists run and candidate history, but does NOT reserve stock.
        """
        initial_avail = self.med_box.inventory.quantity_available
        order, run, result = self.service.get_recommendation_for_order("ORD-01")

        self.assertTrue(result.is_successful)
        self.assertEqual(result.best_candidate.code, "BX-M")

        # Verify RecommendationRun persistence
        self.assertEqual(RecommendationRun.objects.filter(order=order).count(), 1)
        db_run = RecommendationRun.objects.get(order=order)
        self.assertEqual(db_run.best_box, self.med_box)
        self.assertTrue(db_run.is_successful)
        self.assertEqual(db_run.algorithm_version, 'v1.0.0-3D-EXTREME-POINTS')

        # Verify Candidates persistence
        self.assertGreaterEqual(RecommendationCandidate.objects.filter(run=db_run).count(), 2)
        eligible_cand = RecommendationCandidate.objects.get(run=db_run, box_type=self.med_box)
        self.assertTrue(eligible_cand.is_eligible)
        self.assertEqual(eligible_cand.rank, 1)

        # CRITICAL: Verify stock was NOT reserved automatically
        self.med_box.inventory.refresh_from_db()
        self.assertEqual(self.med_box.inventory.quantity_available, initial_avail)
        order.refresh_from_db()
        self.assertFalse(order.is_assigned)

    def test_missing_order_raises_not_found(self):
        with self.assertRaises(OrderNotFoundError):
            self.service.get_recommendation_for_order("ORD-NON-EXISTENT")

    def test_empty_order_raises_empty_error(self):
        empty_order = Order.objects.create(
            order_number="ORD-EMPTY-01",
            status=Order.STATUS_PENDING,
        )
        with self.assertRaises(EmptyOrderError):
            self.service.get_recommendation_for_order("ORD-EMPTY-01")

    def test_cancelled_order_raises_status_error(self):
        cancelled_order = Order.objects.create(
            order_number="ORD-CANCEL-01",
            status=Order.STATUS_CANCELLED,
        )
        OrderItem.objects.create(order=cancelled_order, product=self.book, quantity=1)
        with self.assertRaises(OrderStatusError):
            self.service.get_recommendation_for_order("ORD-CANCEL-01")

    def test_inactive_product_in_order(self):
        inactive_prod = Product.objects.create(
            sku="INACTIVE-01",
            name="Discontinued Item",
            length=Decimal("10.00"),
            width=Decimal("10.00"),
            height=Decimal("10.00"),
            weight=Decimal("1.000"),
            is_active=False,
        )
        order = Order.objects.create(
            order_number="ORD-INACT-PROD",
            status=Order.STATUS_PENDING,
        )
        OrderItem.objects.create(order=order, product=inactive_prod, quantity=1)

        with self.assertRaises(InactiveProductInOrderError):
            self.service.get_recommendation_for_order("ORD-INACT-PROD")

    def test_explicit_authorized_reservation(self):
        """
        Explicit reservation atomicity check:
        Increments reserved stock and marks order assigned.
        """
        initial_reserved = self.med_box.inventory.quantity_reserved
        initial_avail = self.med_box.inventory.quantity_available

        order, inv = self.service.reserve_and_assign_box("ORD-01", "BX-M")

        self.assertTrue(order.is_assigned)
        self.assertEqual(order.assigned_box, self.med_box)
        self.assertIsNotNone(order.assigned_at)

        inv.refresh_from_db()
        self.assertEqual(inv.quantity_reserved, initial_reserved + 1)
        self.assertEqual(inv.quantity_available, initial_avail - 1)
