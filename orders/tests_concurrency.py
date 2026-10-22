import threading
from decimal import Decimal
from django.test import TestCase, TransactionTestCase
from boxes.models import BoxType, BoxInventory
from orders.models import Order, OrderItem
from products.models import Product
from orders.services.recommendation_service import (
    OrderRecommendationService,
    InsufficientStockError,
)


class ConcurrencyReservationTests(TransactionTestCase):
    """
    Tests atomic concurrency safety and prevention of over-reservation
    when multiple concurrent requests compete for the last available box.
    """
    def setUp(self):
        self.service = OrderRecommendationService()

        self.box = BoxType.objects.create(
            code="BX-CONCUR",
            name="Limited Stock Box",
            length=Decimal("30.00"),
            width=Decimal("20.00"),
            height=Decimal("15.00"),
            max_weight=Decimal("5.000"),
            empty_weight=Decimal("0.200"),
            cost=Decimal("15.00"),
            currency="INR",
            is_active=True,
        )

        # Crucial: Exactly 1 box available in inventory!
        self.inventory = BoxInventory.objects.create(
            box_type=self.box,
            quantity_on_hand=1,
            quantity_reserved=0,
        )

        # Two competing orders
        self.order_a = Order.objects.create(
            order_number="ORD-RACE-A",
            customer_name="Competitor A",
            status=Order.STATUS_PENDING,
        )
        self.order_b = Order.objects.create(
            order_number="ORD-RACE-B",
            customer_name="Competitor B",
            status=Order.STATUS_PENDING,
        )

    def test_concurrent_reservations_cannot_over_reserve(self):
        """
        Two concurrent threads race to reserve the 1 available box.
        Exactly one must succeed, and the other must fail with InsufficientStockError.
        """
        results = []
        errors = []

        def worker(order_num):
            try:
                order, inv = self.service.reserve_and_assign_box(order_num, "BX-CONCUR")
                results.append((order_num, "SUCCESS"))
            except InsufficientStockError as e:
                errors.append((order_num, str(e)))
            except Exception as e:
                errors.append((order_num, f"Unexpected: {str(e)}"))

        thread_a = threading.Thread(target=worker, args=("ORD-RACE-A",))
        thread_b = threading.Thread(target=worker, args=("ORD-RACE-B",))

        thread_a.start()
        thread_b.start()

        thread_a.join()
        thread_b.join()

        # Exactly 1 success
        self.assertEqual(len(results), 1)
        # Exactly 1 stock rejection
        self.assertEqual(len(errors), 1)

        # Check database final state: quantity_reserved must be exactly 1, quantity_available 0
        self.inventory.refresh_from_db()
        self.assertEqual(self.inventory.quantity_reserved, 1)
        self.assertEqual(self.inventory.quantity_available, 0)
        self.assertLessEqual(self.inventory.quantity_reserved, self.inventory.quantity_on_hand)
