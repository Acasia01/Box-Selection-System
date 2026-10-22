from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from .models import BoxType, BoxInventory


class BoxModelTests(TestCase):
    def setUp(self):
        self.box = BoxType.objects.create(
            code="BX-102",
            name="Medium Shipping Box",
            length=Decimal("30.00"),
            width=Decimal("25.00"),
            height=Decimal("20.00"),
            max_weight=Decimal("5.000"),
            empty_weight=Decimal("0.300"),
            cost=Decimal("18.00"),
            currency="INR",
            is_active=True,
        )
        self.inventory = BoxInventory.objects.create(
            box_type=self.box,
            quantity_on_hand=100,
            quantity_reserved=12,
        )

    def test_box_creation_and_str(self):
        self.assertEqual(self.box.code, "BX-102")
        self.assertIn("BX-102", str(self.box))
        self.assertIn("Medium Shipping Box", str(self.box))

    def test_box_volume(self):
        # 30 * 25 * 20 = 15000 cm³
        self.assertEqual(self.box.internal_volume, Decimal("15000.00"))

    def test_inventory_quantity_available(self):
        # 100 - 12 = 88 available
        self.assertEqual(self.inventory.quantity_available, 88)

    def test_code_uniqueness(self):
        with self.assertRaises(IntegrityError):
            BoxType.objects.create(
                code="BX-102",
                name="Duplicate Code",
                length=Decimal("15.00"),
                width=Decimal("15.00"),
                height=Decimal("15.00"),
                max_weight=Decimal("2.000"),
                cost=Decimal("10.00"),
            )

    def test_reserved_cannot_exceed_on_hand_constraint(self):
        with self.assertRaises(IntegrityError):
            BoxInventory.objects.create(
                box_type=BoxType.objects.create(
                    code="BX-OVER",
                    name="Overbox",
                    length=Decimal("10.00"),
                    width=Decimal("10.00"),
                    height=Decimal("10.00"),
                    max_weight=Decimal("2.000"),
                    cost=Decimal("10.00"),
                ),
                quantity_on_hand=5,
                quantity_reserved=10,  # exceeds on_hand
            )

    def test_negative_cost_validation(self):
        invalid_box = BoxType(
            code="BX-NEG",
            name="Negative Cost",
            length=Decimal("10.00"),
            width=Decimal("10.00"),
            height=Decimal("10.00"),
            max_weight=Decimal("2.000"),
            cost=Decimal("-5.00"),
        )
        with self.assertRaises(ValidationError):
            invalid_box.full_clean()
