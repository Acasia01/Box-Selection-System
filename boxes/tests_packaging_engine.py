from decimal import Decimal
from django.test import TestCase
from boxes.services.packing_engine import (
    ItemToPack,
    PackagingEngine,
    CandidateResult,
)


class PackagingEngineTests(TestCase):
    def setUp(self):
        self.engine = PackagingEngine(fragile_material_buffer_kg=Decimal('0.050'))

        self.sample_boxes = [
            {
                'id': 1,
                'code': 'BX-SMALL',
                'name': 'Small Box',
                'length': Decimal('20.00'),
                'width': Decimal('15.00'),
                'height': Decimal('10.00'),
                'max_weight': Decimal('3.000'),
                'empty_weight': Decimal('0.150'),
                'cost': Decimal('12.00'),
                'currency': 'INR',
                'quantity_available': 20,
                'is_active': True,
            },
            {
                'id': 2,
                'code': 'BX-MED',
                'name': 'Medium Box',
                'length': Decimal('30.00'),
                'width': Decimal('25.00'),
                'height': Decimal('20.00'),
                'max_weight': Decimal('6.000'),
                'empty_weight': Decimal('0.300'),
                'cost': Decimal('18.00'),
                'currency': 'INR',
                'quantity_available': 50,
                'is_active': True,
            },
            {
                'id': 3,
                'code': 'BX-LARGE',
                'name': 'Large Box',
                'length': Decimal('45.00'),
                'width': Decimal('35.00'),
                'height': Decimal('25.00'),
                'max_weight': Decimal('12.000'),
                'empty_weight': Decimal('0.500'),
                'cost': Decimal('30.00'),
                'currency': 'INR',
                'quantity_available': 15,
                'is_active': True,
            },
        ]

    def test_orientation_rotation_fit(self):
        """
        Item of dimensions (28, 9, 7) does not fit without rotation into box of (10, 30, 8),
        but fits when rotated to (9, 28, 7).
        """
        item = ItemToPack(
            sku="ITEM-ROT",
            name="Rotatable Item",
            length=Decimal("28.00"),
            width=Decimal("9.00"),
            height=Decimal("7.00"),
            weight=Decimal("1.000"),
            clearance=Decimal("0.00"),
        )
        box = {
            'code': 'BX-ROT',
            'name': 'Rotated Box',
            'length': Decimal('10.00'),
            'width': Decimal('30.00'),
            'height': Decimal('8.00'),
            'max_weight': Decimal('5.000'),
            'empty_weight': Decimal('0.200'),
            'cost': Decimal('15.00'),
            'currency': 'INR',
            'quantity_available': 10,
            'is_active': True,
        }

        result = self.engine.evaluate_candidates([item], [box])
        self.assertTrue(result.is_successful)
        self.assertEqual(result.best_candidate.code, 'BX-ROT')
        self.assertEqual(len(result.best_candidate.placements), 1)

    def test_clearance_application(self):
        """
        Product 10x10x10 cm with 1.0 cm clearance on each side requires 12x12x12 cm.
        It must fail in an 11x11x11 cm box and succeed in a 12x12x12 cm box.
        """
        item = ItemToPack(
            sku="ITEM-CLR",
            name="Clearance Item",
            length=Decimal("10.00"),
            width=Decimal("10.00"),
            height=Decimal("10.00"),
            weight=Decimal("0.500"),
            clearance=Decimal("1.00"),  # adds +2.00 cm per axis -> 12x12x12
        )
        too_small_box = {
            'code': 'BX-11',
            'name': '11cm Box',
            'length': Decimal('11.00'),
            'width': Decimal('11.00'),
            'height': Decimal('11.00'),
            'max_weight': Decimal('5.000'),
            'empty_weight': Decimal('0.100'),
            'cost': Decimal('10.00'),
            'quantity_available': 5,
            'is_active': True,
        }
        exact_box = {
            'code': 'BX-12',
            'name': '12cm Box',
            'length': Decimal('12.00'),
            'width': Decimal('12.00'),
            'height': Decimal('12.00'),
            'max_weight': Decimal('5.000'),
            'empty_weight': Decimal('0.100'),
            'cost': Decimal('12.00'),
            'quantity_available': 5,
            'is_active': True,
        }

        result = self.engine.evaluate_candidates([item], [too_small_box, exact_box])
        self.assertTrue(result.is_successful)
        self.assertEqual(result.best_candidate.code, 'BX-12')
        self.assertIn('BX-11', [b.code for b in result.rejected_candidates])

    def test_packed_weight_limit(self):
        """
        Total packed weight includes product weight + empty box weight.
        If product weight 2.9 kg + empty weight 0.2 kg = 3.1 kg > 3.0 kg max_weight,
        the box must be rejected.
        """
        item = ItemToPack(
            sku="HEAVY-01",
            name="Heavy Item",
            length=Decimal("15.00"),
            width=Decimal("10.00"),
            height=Decimal("5.00"),
            weight=Decimal("2.900"),
            clearance=Decimal("0.00"),
        )
        box = {
            'code': 'BX-LIGHT',
            'name': 'Light Capacity Box',
            'length': Decimal('20.00'),
            'width': Decimal('15.00'),
            'height': Decimal('10.00'),
            'max_weight': Decimal('3.000'),  # 3.100 > 3.000
            'empty_weight': Decimal('0.200'),
            'cost': Decimal('10.00'),
            'quantity_available': 10,
            'is_active': True,
        }

        result = self.engine.evaluate_candidates([item], [box])
        self.assertFalse(result.is_successful)
        self.assertEqual(len(result.rejected_candidates), 1)
        self.assertTrue(any('capacity' in r.lower() for r in result.rejected_candidates[0].rejection_reasons))

    def test_inactive_and_out_of_stock_boxes_excluded(self):
        """
        Inactive boxes or boxes with quantity_available <= 0 must be rejected.
        """
        item = ItemToPack(
            sku="BOOK-01",
            name="Book",
            length=Decimal("10.00"),
            width=Decimal("10.00"),
            height=Decimal("5.00"),
            weight=Decimal("0.500"),
        )
        inactive_box = {
            'code': 'BX-INACT',
            'name': 'Inactive Box',
            'length': Decimal('20.00'),
            'width': Decimal('20.00'),
            'height': Decimal('20.00'),
            'max_weight': Decimal('5.000'),
            'cost': Decimal('5.00'),
            'quantity_available': 10,
            'is_active': False,
        }
        no_stock_box = {
            'code': 'BX-NOSTOCK',
            'name': 'No Stock Box',
            'length': Decimal('20.00'),
            'width': Decimal('20.00'),
            'height': Decimal('20.00'),
            'max_weight': Decimal('5.000'),
            'cost': Decimal('6.00'),
            'quantity_available': 0,
            'is_active': True,
        }

        result = self.engine.evaluate_candidates([item], [inactive_box, no_stock_box])
        self.assertFalse(result.is_successful)
        self.assertEqual(len(result.rejected_candidates), 2)

    def test_lexicographic_ranking_criteria(self):
        """
        Rank order:
        1. Lowest cost
        2. Least unused internal volume
        3. Highest available stock
        """
        item = ItemToPack(
            sku="ITEM-01",
            name="Test Item",
            length=Decimal("10.00"),
            width=Decimal("10.00"),
            height=Decimal("10.00"),
            weight=Decimal("0.500"),
        )
        # Box A: Cost 20, volume 2000
        box_a = {
            'code': 'BOX-A',
            'name': 'Box A',
            'length': Decimal('20.00'),
            'width': Decimal('10.00'),
            'height': Decimal('10.00'),  # vol 2000
            'max_weight': Decimal('5.000'),
            'empty_weight': Decimal('0.100'),
            'cost': Decimal('20.00'),
            'quantity_available': 10,
            'is_active': True,
        }
        # Box B: Cost 15, volume 3000 (cheaper than A, so should beat A)
        box_b = {
            'code': 'BOX-B',
            'name': 'Box B',
            'length': Decimal('30.00'),
            'width': Decimal('10.00'),
            'height': Decimal('10.00'),  # vol 3000
            'max_weight': Decimal('5.000'),
            'empty_weight': Decimal('0.100'),
            'cost': Decimal('15.00'),
            'quantity_available': 5,
            'is_active': True,
        }
        # Box C: Cost 15, volume 2500 (same cost as B, but smaller unused volume, should beat B)
        box_c = {
            'code': 'BOX-C',
            'name': 'Box C',
            'length': Decimal('25.00'),
            'width': Decimal('10.00'),
            'height': Decimal('10.00'),  # vol 2500
            'max_weight': Decimal('5.000'),
            'empty_weight': Decimal('0.100'),
            'cost': Decimal('15.00'),
            'quantity_available': 5,
            'is_active': True,
        }

        result = self.engine.evaluate_candidates([item], [box_a, box_b, box_c])
        self.assertTrue(result.is_successful)
        # BOX-C should rank #1 (Cost 15, unused vol 1500)
        self.assertEqual(result.best_candidate.code, 'BOX-C')
        # BOX-B should rank #2 (Cost 15, unused vol 2000)
        self.assertEqual(result.alternatives[0].code, 'BOX-B')
        # BOX-A should rank #3 (Cost 20)
        self.assertEqual(result.alternatives[1].code, 'BOX-A')

    def test_multi_item_physical_arrangement_fits(self):
        """
        Two items of 15x10x8 cm placed together into a 30x10x8 cm box.
        They must be placed side-by-side with no overlaps.
        """
        item1 = ItemToPack("ITM-1", "Item 1", Decimal("15.00"), Decimal("10.00"), Decimal("8.00"), Decimal("0.500"))
        item2 = ItemToPack("ITM-2", "Item 2", Decimal("15.00"), Decimal("10.00"), Decimal("8.00"), Decimal("0.500"))

        box = {
            'code': 'BX-DUAL',
            'name': 'Dual Box',
            'length': Decimal('30.00'),
            'width': Decimal('10.00'),
            'height': Decimal('8.00'),
            'max_weight': Decimal('5.000'),
            'cost': Decimal('15.00'),
            'quantity_available': 10,
            'is_active': True,
        }

        result = self.engine.evaluate_candidates([item1, item2], [box])
        self.assertTrue(result.is_successful)
        self.assertEqual(len(result.best_candidate.placements), 2)
        p1, p2 = result.best_candidate.placements
        self.assertFalse(p1.overlaps_with(p2))

    def test_volume_sufficient_but_no_physical_arrangement_exists(self):
        """
        CRITICAL ARCHITECTURE REQUIREMENT:
        Multi-item test where total volume is sufficient, but no physical arrangement exists.
        Box: 10 x 10 x 10 cm (internal volume 1000 cm³).
        Item 1: 10 x 10 x 6 cm (volume 600 cm³).
        Item 2: 10 x 6 x 5 cm (volume 300 cm³).
        Total volume = 900 cm³ <= 1000 cm³ (enough volume!).
        However:
        Item 1 occupies height 0 to 6 cm across entire length and width.
        Remaining space is 10 x 10 x 4 cm.
        Item 2 has smallest dimension 5 cm, which cannot fit into the remaining 4 cm height!
        Hence, physically impossible despite volume <= box internal volume.
        """
        item1 = ItemToPack("ITM-A", "Item A", Decimal("10.00"), Decimal("10.00"), Decimal("6.00"), Decimal("0.400"))
        item2 = ItemToPack("ITM-B", "Item B", Decimal("10.00"), Decimal("6.00"), Decimal("5.00"), Decimal("0.300"))

        box = {
            'code': 'BX-CUBE10',
            'name': '10cm Cube Box',
            'length': Decimal('10.00'),
            'width': Decimal('10.00'),
            'height': Decimal('10.00'),  # 1000 cm³
            'max_weight': Decimal('5.000'),
            'cost': Decimal('10.00'),
            'quantity_available': 5,
            'is_active': True,
        }

        result = self.engine.evaluate_candidates([item1, item2], [box])
        self.assertFalse(result.is_successful)
        self.assertIn('BX-CUBE10', [b.code for b in result.rejected_candidates])
        rejection_reason = result.rejected_candidates[0].rejection_reasons[0]
        self.assertIn("cannot physically fit", rejection_reason)

    def test_fragile_buffer_weight(self):
        """
        Fragile items add protective buffer to total packed weight.
        """
        fragile_item = ItemToPack(
            "MUG-01", "Fragile Mug",
            Decimal("10.00"), Decimal("10.00"), Decimal("10.00"),
            Decimal("0.400"), is_fragile=True
        )
        box = {
            'code': 'BX-TEST',
            'name': 'Test Box',
            'length': Decimal('20.00'),
            'width': Decimal('20.00'),
            'height': Decimal('20.00'),
            'max_weight': Decimal('5.000'),
            'empty_weight': Decimal('0.200'),
            'cost': Decimal('12.00'),
            'quantity_available': 10,
            'is_active': True,
        }

        result = self.engine.evaluate_candidates([fragile_item], [box])
        self.assertTrue(result.is_successful)
        # Expected packed weight: 0.400 (product) + 0.050 (buffer) + 0.200 (empty) = 0.650 kg
        self.assertEqual(result.best_candidate.total_packed_weight, Decimal("0.650"))
