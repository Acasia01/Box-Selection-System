import json
from decimal import Decimal
from django.test import TestCase, Client
from django.urls import reverse
from products.models import Product
from boxes.models import BoxType, BoxInventory
from orders.models import Order, OrderItem, RecommendationRun


class EndToEndWorkflowAPITests(TestCase):
    def setUp(self):
        self.client = Client()

        # Create Catalog Product
        self.speaker = Product.objects.create(
            sku="SPK-E2E",
            name="E2E Speaker",
            length=Decimal("20.00"),
            width=Decimal("15.00"),
            height=Decimal("10.00"),
            weight=Decimal("1.200"),
            clearance=Decimal("0.50"),
            is_fragile=True,
            is_active=True,
        )

        # Create Boxes
        self.box_small = BoxType.objects.create(
            code="BX-E2E-SM",
            name="E2E Small Box",
            length=Decimal("15.00"),
            width=Decimal("15.00"),
            height=Decimal("10.00"),
            max_weight=Decimal("2.000"),
            cost=Decimal("10.00"),
            currency="INR",
            is_active=True,
        )
        BoxInventory.objects.create(box_type=self.box_small, quantity_on_hand=20, quantity_reserved=0)

        self.box_med = BoxType.objects.create(
            code="BX-E2E-MED",
            name="E2E Medium Box",
            length=Decimal("30.00"),
            width=Decimal("25.00"),
            height=Decimal("20.00"),
            max_weight=Decimal("6.000"),
            empty_weight=Decimal("0.300"),
            cost=Decimal("18.00"),
            currency="INR",
            is_active=True,
        )
        BoxInventory.objects.create(box_type=self.box_med, quantity_on_hand=50, quantity_reserved=5)

        # Create Orders
        self.order = Order.objects.create(
            order_number="ORD-E2E-001",
            customer_name="Test Recipient",
            status=Order.STATUS_PENDING,
        )
        OrderItem.objects.create(order=self.order, product=self.speaker, quantity=2)

    def test_full_warehouse_journey(self):
        """
        Tests the end-to-end journey:
        1. Access main dashboard page
        2. Query API for orders list
        3. Query API for order recommendation
        4. Reserve recommended box atomically
        5. Verify state changes across database
        """
        # 1. Access dashboard
        resp = self.client.get('/')
        self.assertEqual(resp.status_code, 200)

        # 2. Query Orders
        resp = self.client.get('/api/orders/')
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('orders', data)
        self.assertTrue(any(o['order_number'] == 'ORD-E2E-001' for o in data['orders']))

        # 3. Query Recommendation for ORD-E2E-001
        resp = self.client.get('/api/recommendation/ORD-E2E-001/')
        self.assertEqual(resp.status_code, 200)
        rec_data = resp.json()
        self.assertTrue(rec_data['success'])
        self.assertEqual(rec_data['recommendation']['best_box']['code'], 'BX-E2E-MED')
        self.assertEqual(len(rec_data['recommendation']['best_box']['placements']), 2)

        # Recommendation Run must be recorded
        self.assertGreaterEqual(RecommendationRun.objects.filter(order=self.order).count(), 1)

        # 4. Explicit Reservation
        reserve_payload = {
            'order_number': 'ORD-E2E-001',
            'box_code': 'BX-E2E-MED',
        }
        resp = self.client.post(
            '/api/reserve/',
            data=json.dumps(reserve_payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        res_data = resp.json()
        self.assertTrue(res_data['success'])
        self.assertEqual(res_data['inventory']['quantity_reserved'], 6)
        self.assertEqual(res_data['inventory']['quantity_available'], 44)

        # Check Order state
        self.order.refresh_from_db()
        self.assertTrue(self.order.is_assigned)
        self.assertEqual(self.order.assigned_box.code, 'BX-E2E-MED')

    def test_chat_api_interaction(self):
        """
        Tests the natural language AI chat endpoint.
        """
        payload = {'message': 'Which box should I use for order ORD-E2E-001?'}
        resp = self.client.post(
            '/api/chat/',
            data=json.dumps(payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertIn('BX-E2E-MED', data['reply'])
        self.assertEqual(data['tool_calls'][0]['tool'], 'get_box_recommendation')

    def test_error_handling_for_nonexistent_order(self):
        resp = self.client.get('/api/recommendation/ORD-NONEXISTENT/')
        self.assertEqual(resp.status_code, 404)
        data = resp.json()
        self.assertFalse(data['success'])
        self.assertEqual(data['code'], 'NOT_FOUND')

    def test_box_create_and_update_api(self):
        # 1. Create a new box
        create_payload = {
            'code': 'BX-NEW-99',
            'name': 'Brand New Box',
            'length': 40.0,
            'width': 30.0,
            'height': 20.0,
            'max_weight': 8.0,
            'empty_weight': 0.4,
            'cost': 22.50,
            'currency': 'INR',
            'quantity_on_hand': 75,
            'is_active': True,
        }
        resp = self.client.post(
            '/api/boxes/create/',
            data=json.dumps(create_payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        data = resp.json()
        self.assertTrue(data['success'])

        box = BoxType.objects.get(code='BX-NEW-99')
        self.assertEqual(box.name, 'Brand New Box')
        self.assertEqual(box.inventory.quantity_on_hand, 75)
        self.assertEqual(box.inventory.quantity_available, 75)

        # 2. Update the box dimensions and cost
        update_payload = {
            'name': 'Updated New Box',
            'cost': 25.00,
            'quantity_on_hand': 90,
            'length': 42.0,
        }
        resp = self.client.post(
            '/api/boxes/BX-NEW-99/update/',
            data=json.dumps(update_payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        box.refresh_from_db()
        self.assertEqual(box.name, 'Updated New Box')
        self.assertEqual(box.cost, Decimal('25.00'))
        self.assertEqual(box.length, Decimal('42.00'))
        self.assertEqual(box.inventory.quantity_on_hand, 90)

    def test_order_create_and_update_api(self):
        # 1. Create an order with line items
        create_payload = {
            'order_number': 'ORD-CREATED-01',
            'customer_name': 'Meera Sen',
            'status': 'PENDING',
            'items': [
                {'sku': 'SPK-E2E', 'quantity': 3}
            ]
        }
        resp = self.client.post(
            '/api/orders/create/',
            data=json.dumps(create_payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        order = Order.objects.get(order_number='ORD-CREATED-01')
        self.assertEqual(order.customer_name, 'Meera Sen')
        self.assertEqual(order.items.count(), 1)
        self.assertEqual(order.items.first().quantity, 3)

        # 2. Update order customer name and status
        update_payload = {
            'customer_name': 'Meera Sen-Gupta',
            'status': 'PACKED',
            'items': [
                {'sku': 'SPK-E2E', 'quantity': 4}
            ]
        }
        resp = self.client.post(
            '/api/orders/ORD-CREATED-01/update/',
            data=json.dumps(update_payload),
            content_type='application/json'
        )
        self.assertEqual(resp.status_code, 200)
        order.refresh_from_db()
        self.assertEqual(order.customer_name, 'Meera Sen-Gupta')
        self.assertEqual(order.status, 'PACKED')
        self.assertEqual(order.items.first().quantity, 4)

