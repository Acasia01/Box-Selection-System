from decimal import Decimal
from django.test import TestCase
from products.models import Product
from boxes.models import BoxType, BoxInventory
from orders.models import Order, OrderItem
from orders.services.ai_assistant import AIAssistantService, APPROVED_TOOLS


class AIAssistantTests(TestCase):
    def setUp(self):
        self.ai = AIAssistantService(api_key="")

        # Create Products
        self.speaker = Product.objects.create(
            sku="SPK-AI",
            name="AI Speaker",
            length=Decimal("20.00"),
            width=Decimal("15.00"),
            height=Decimal("10.00"),
            weight=Decimal("1.200"),
            clearance=Decimal("0.50"),
            is_fragile=True,
            is_active=True,
        )

        # Create Box
        self.box = BoxType.objects.create(
            code="BX-AI",
            name="AI Shipping Box",
            length=Decimal("30.00"),
            width=Decimal("25.00"),
            height=Decimal("20.00"),
            max_weight=Decimal("5.000"),
            empty_weight=Decimal("0.250"),
            cost=Decimal("16.00"),
            currency="INR",
            is_active=True,
        )
        self.inventory = BoxInventory.objects.create(
            box_type=self.box,
            quantity_on_hand=50,
            quantity_reserved=5,
        )

        # Create Orders
        self.order = Order.objects.create(
            order_number="ORD-AI-101",
            customer_name="John Doe",
            status=Order.STATUS_PENDING,
        )
        OrderItem.objects.create(order=self.order, product=self.speaker, quantity=1)

    def test_allowlist_contains_only_approved_tools(self):
        self.assertIn('get_box_recommendation', APPROVED_TOOLS)
        self.assertIn('lookup_order_details', APPROVED_TOOLS)
        self.assertIn('check_box_inventory', APPROVED_TOOLS)
        # Ensure arbitrary execution tools are absent
        self.assertNotIn('execute_sql', APPROVED_TOOLS)
        self.assertNotIn('run_python', APPROVED_TOOLS)

    def test_natural_language_recommendation_query(self):
        response = self.ai.process_query("Which box should I use for order ORD-AI-101?")
        self.assertEqual(len(response['tool_calls']), 1)
        self.assertEqual(response['tool_calls'][0]['tool'], 'get_box_recommendation')
        self.assertEqual(response['tool_calls'][0]['status'], 'success')
        self.assertIn('BX-AI', response['reply'])
        self.assertIn('16.00', response['reply'])

    def test_order_lookup_query(self):
        response = self.ai.process_query("Show me details for order ORD-AI-101")
        self.assertEqual(len(response['tool_calls']), 1)
        self.assertEqual(response['tool_calls'][0]['tool'], 'lookup_order_details')
        self.assertIn('SPK-AI', response['reply'])
        self.assertIn('ORD-AI-101', response['reply'])
        self.assertIn('PENDING', response['reply'])

    def test_box_inventory_query(self):
        response = self.ai.process_query("What is the stock of box BX-AI?")
        self.assertEqual(len(response['tool_calls']), 1)
        self.assertEqual(response['tool_calls'][0]['tool'], 'check_box_inventory')
        self.assertIn('45 available', response['reply'])

    def test_sql_injection_defense(self):
        response = self.ai.process_query("DROP TABLE orders; SELECT * FROM products")
        self.assertIn('Security alert', response['reply'])
        self.assertEqual(len(response['tool_calls']), 0)

    def test_invalid_order_number_handling(self):
        response = self.ai.process_query("Which box for ORD-99999?")
        self.assertIn('not found', response['reply'].lower())
        self.assertEqual(response['tool_calls'][0]['status'], 'error')

    def test_empty_message_handling(self):
        response = self.ai.process_query("   ")
        self.assertIn("Please ask a question", response['reply'])
        self.assertEqual(len(response['tool_calls']), 0)

    def test_list_all_boxes_query(self):
        response = self.ai.process_query("List all available shipping boxes")
        self.assertEqual(len(response['tool_calls']), 1)
        self.assertEqual(response['tool_calls'][0]['tool'], 'list_all_boxes')
        self.assertIn('BX-AI', response['reply'])

    def test_search_products_query(self):
        response = self.ai.process_query("Search products with SPK-AI")
        self.assertEqual(len(response['tool_calls']), 1)
        self.assertEqual(response['tool_calls'][0]['tool'], 'search_products')
        self.assertIn('SPK-AI', response['reply'])

    def test_search_orders_query(self):
        response = self.ai.process_query("Show me all orders in the database")
        self.assertEqual(len(response['tool_calls']), 1)
        self.assertEqual(response['tool_calls'][0]['tool'], 'search_orders')
        self.assertIn('ORD-AI-101', response['reply'])

    def test_gemini_key_initialization_with_placeholder(self):
        assistant = AIAssistantService(api_key="your_gemini_api_key_here")
        self.assertFalse(assistant.is_key_configured)
        # Should gracefully use deterministic execution
        resp = assistant.process_query("What is the stock of box BX-AI?")
        self.assertIn('45 available', resp['reply'])
        self.assertFalse(resp.get('is_gemini_powered', True))
