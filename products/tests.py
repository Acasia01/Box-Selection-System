from decimal import Decimal
from django.test import TestCase
from django.core.exceptions import ValidationError
from django.db.utils import IntegrityError
from .models import Product


class ProductModelTests(TestCase):
    def setUp(self):
        self.product = Product.objects.create(
            sku="SPK-101",
            name="Wireless Speaker",
            length=Decimal("20.00"),
            width=Decimal("15.00"),
            height=Decimal("10.00"),
            weight=Decimal("1.200"),
            clearance=Decimal("1.00"),
            is_fragile=True,
            is_active=True,
        )

    def test_product_creation_and_str(self):
        self.assertEqual(self.product.sku, "SPK-101")
        self.assertIn("SPK-101", str(self.product))
        self.assertIn("Wireless Speaker", str(self.product))

    def test_product_sku_uniqueness(self):
        with self.assertRaises(IntegrityError):
            Product.objects.create(
                sku="SPK-101",  # duplicate
                name="Another Speaker",
                length=Decimal("10.00"),
                width=Decimal("10.00"),
                height=Decimal("10.00"),
                weight=Decimal("1.000"),
            )

    def test_volume_calculation(self):
        # 20 * 15 * 10 = 3000 cm³
        self.assertEqual(self.product.volume, Decimal("3000.00"))

    def test_effective_dimensions_with_clearance(self):
        # Clearance = 1.00 cm on every side => + 2.00 cm per axis
        # L = 22.00, W = 17.00, H = 12.00
        eff_l, eff_w, eff_h = self.product.effective_dimensions
        self.assertEqual(eff_l, Decimal("22.00"))
        self.assertEqual(eff_w, Decimal("17.00"))
        self.assertEqual(eff_h, Decimal("12.00"))

        # Effective volume: 22 * 17 * 12 = 4488 cm³
        self.assertEqual(self.product.effective_volume, Decimal("4488.00"))

    def test_zero_clearance(self):
        p2 = Product.objects.create(
            sku="BOOK-01",
            name="Paperback Book",
            length=Decimal("20.00"),
            width=Decimal("12.00"),
            height=Decimal("3.00"),
            weight=Decimal("0.400"),
            clearance=Decimal("0.00"),
        )
        eff_l, eff_w, eff_h = p2.effective_dimensions
        self.assertEqual((eff_l, eff_w, eff_h), (Decimal("20.00"), Decimal("12.00"), Decimal("3.00")))
        self.assertEqual(p2.effective_volume, Decimal("720.00"))

    def test_positive_dimension_constraints(self):
        # Check invalid non-positive length validation
        invalid_p = Product(
            sku="INV-01",
            name="Invalid Dimensions",
            length=Decimal("0.00"),
            width=Decimal("10.00"),
            height=Decimal("10.00"),
            weight=Decimal("1.000"),
        )
        with self.assertRaises(ValidationError):
            invalid_p.full_clean()
