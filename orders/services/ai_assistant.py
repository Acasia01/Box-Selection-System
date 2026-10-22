"""
AI Assistant Service for natural-language warehouse queries.
Integrates with Google Gemini (via google-genai) and strictly grounded database tools:
1. Only approved allowlisted tools can be called to query the database.
2. AI never executes arbitrary SQL, Python, or mutations.
3. Authoritative order workflow and deterministic 3D packing engine are the sole sources of truth.
4. Explanations are derived exclusively from verified engine results and live database records.
5. If Google Gemini key is not configured or encounters an issue, falls back seamlessly to deterministic rule engine.
"""

import os
import re
import json
import logging
from typing import Dict, Any, List, Optional
from django.conf import settings
from django.db.models import Q

from orders.services.recommendation_service import (
    OrderRecommendationService,
    OrderNotFoundError,
    EmptyOrderError,
    OrderStatusError,
    InactiveProductInOrderError,
)
from orders.models import Order, OrderItem, RecommendationRun
from boxes.models import BoxType, BoxInventory
from products.models import Product

logger = logging.getLogger(__name__)

# Explicit Allowlist of Approved Tools
APPROVED_TOOLS = {
    'lookup_order_details': {
        'name': 'lookup_order_details',
        'description': 'Retrieve verified line items, quantities, and status for an order number.',
        'parameters': {
            'type': 'object',
            'properties': {
                'order_number': {
                    'type': 'string',
                    'description': 'The order identifier, e.g. ORD-1001'
                }
            },
            'required': ['order_number']
        }
    },
    'get_box_recommendation': {
        'name': 'get_box_recommendation',
        'description': 'Run deterministic 3D packaging engine for an order to get verified box recommendation.',
        'parameters': {
            'type': 'object',
            'properties': {
                'order_number': {
                    'type': 'string',
                    'description': 'The order identifier, e.g. ORD-1001'
                }
            },
            'required': ['order_number']
        }
    },
    'check_box_inventory': {
        'name': 'check_box_inventory',
        'description': 'Check live inventory and specifications of a shipping box by its code.',
        'parameters': {
            'type': 'object',
            'properties': {
                'box_code': {
                    'type': 'string',
                    'description': 'The box code, e.g. BX-102'
                }
            },
            'required': ['box_code']
        }
    },
    'search_orders': {
        'name': 'search_orders',
        'description': 'Search warehouse orders by order number, customer name, or status (PENDING, PACKED, CANCELLED).',
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Keyword for order number or customer name'},
                'status': {'type': 'string', 'description': 'Order status filter'}
            }
        }
    },
    'list_all_boxes': {
        'name': 'list_all_boxes',
        'description': 'List all available shipping boxes in the warehouse catalog with dimensions, cost, and stock.',
        'parameters': {
            'type': 'object',
            'properties': {}
        }
    },
    'search_products': {
        'name': 'search_products',
        'description': 'Search the warehouse product catalog by SKU or product name to get dimensions, weight, and fragile status.',
        'parameters': {
            'type': 'object',
            'properties': {
                'query': {'type': 'string', 'description': 'Product SKU or name to search'}
            }
        }
    },
    'get_recent_history': {
        'name': 'get_recent_history',
        'description': 'Retrieve recent packaging recommendation audit logs.',
        'parameters': {
            'type': 'object',
            'properties': {
                'limit': {'type': 'integer', 'description': 'Maximum number of audit records to retrieve'}
            }
        }
    }
}


class AIAssistantService:
    def __init__(self, api_key: Optional[str] = None):
        env_key = getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
        self.api_key = (api_key if api_key is not None else env_key).strip()
        # Verify key is genuinely provided and not a placeholder
        self.is_key_configured = bool(
            self.api_key 
            and self.api_key not in ('your_gemini_api_key_here', 'dummy_key', 'test_key', '')
        )
        self.model_name = os.getenv('GEMINI_MODEL', 'gemini-2.0-flash')
        self.recommendation_service = OrderRecommendationService()

    def process_query(self, message: str, requester: str = 'warehouse_operator') -> Dict[str, Any]:
        """
        Processes a user query by parsing intent, executing allowlisted database tools safely,
        and producing a verified, grounded explanation.
        """
        if not message or not message.strip():
            return {
                'reply': "Please ask a question, such as 'Which box should I use for order ORD-1001?' or 'List all shipping boxes'.",
                'tool_calls': [],
                'verified_result': None,
                'is_gemini_powered': False,
            }

        clean_msg = message.strip()

        # Security check: Disallow prompt injection / SQL execution attempts
        lower_msg = clean_msg.lower()
        forbidden_patterns = ['select * from', 'drop table', 'exec(', 'system(', '__import__', 'eval(']
        if any(pat in lower_msg for pat in forbidden_patterns):
            return {
                'reply': "Security alert: Arbitrary system commands and SQL execution are strictly prohibited.",
                'tool_calls': [],
                'verified_result': None,
                'error': 'Forbidden operation detected',
                'is_gemini_powered': False,
            }

        # If Gemini API key is configured, invoke Gemini with function calling tools
        if self.is_key_configured:
            try:
                gemini_result = self._call_gemini(clean_msg, requester)
                if gemini_result is not None:
                    return gemini_result
            except Exception as e:
                logger.warning("Gemini invocation failed (%s). Falling back to deterministic engine.", e)

        # Fallback: Deterministic tool dispatcher & response generator
        return self._process_query_deterministic(clean_msg, requester)

    def _call_gemini(self, message: str, requester: str) -> Optional[Dict[str, Any]]:
        """
        Interacts with Google Gemini using google-genai SDK and allowlisted database search tools.
        """
        try:
            from google import genai
            from google.genai import types
        except ImportError:
            logger.warning("google-genai package not found. Falling back to deterministic mode.")
            return None

        recorded_tool_calls: List[Dict[str, Any]] = []
        last_verified_result: Optional[Dict[str, Any]] = None

        # Define callable tools that capture results and route through safe execution
        def get_box_recommendation(order_number: str) -> dict:
            """Run deterministic 3D packing engine to compute optimal shipping box, coordinates, clearance, and weight."""
            res = self._execute_tool('get_box_recommendation', {'order_number': order_number}, requester)
            status = 'error' if 'error' in res else 'success'
            recorded_tool_calls.append({'tool': 'get_box_recommendation', 'arguments': {'order_number': order_number}, 'status': status})
            nonlocal last_verified_result
            last_verified_result = res
            return res

        def lookup_order_details(order_number: str) -> dict:
            """Retrieve line items, quantities, dimensions, weight, customer, and status for an order number."""
            res = self._execute_tool('lookup_order_details', {'order_number': order_number}, requester)
            status = 'error' if 'error' in res else 'success'
            recorded_tool_calls.append({'tool': 'lookup_order_details', 'arguments': {'order_number': order_number}, 'status': status})
            nonlocal last_verified_result
            last_verified_result = res
            return res

        def check_box_inventory(box_code: str) -> dict:
            """Check live warehouse stock (available, on hand, reserved) and dimensions for a box code."""
            res = self._execute_tool('check_box_inventory', {'box_code': box_code}, requester)
            status = 'error' if 'error' in res else 'success'
            recorded_tool_calls.append({'tool': 'check_box_inventory', 'arguments': {'box_code': box_code}, 'status': status})
            nonlocal last_verified_result
            last_verified_result = res
            return res

        def search_orders(query: str = '', status: str = '') -> dict:
            """Search warehouse orders in database by order number, customer name, or status (PENDING, PACKED, CANCELLED)."""
            res = self._execute_tool('search_orders', {'query': query, 'status': status}, requester)
            status_str = 'error' if 'error' in res else 'success'
            recorded_tool_calls.append({'tool': 'search_orders', 'arguments': {'query': query, 'status': status}, 'status': status_str})
            nonlocal last_verified_result
            last_verified_result = res
            return res

        def list_all_boxes() -> dict:
            """List all available shipping boxes in the warehouse catalog with dimensions, cost, and stock levels."""
            res = self._execute_tool('list_all_boxes', {}, requester)
            status = 'error' if 'error' in res else 'success'
            recorded_tool_calls.append({'tool': 'list_all_boxes', 'arguments': {}, 'status': status})
            nonlocal last_verified_result
            last_verified_result = res
            return res

        def search_products(query: str = '') -> dict:
            """Search products catalog by SKU or name to get dimensions, weight, and fragile status."""
            res = self._execute_tool('search_products', {'query': query}, requester)
            status = 'error' if 'error' in res else 'success'
            recorded_tool_calls.append({'tool': 'search_products', 'arguments': {'query': query}, 'status': status})
            nonlocal last_verified_result
            last_verified_result = res
            return res

        def get_recent_history(limit: int = 10) -> dict:
            """Retrieve recent packaging recommendation audit logs."""
            res = self._execute_tool('get_recent_history', {'limit': limit}, requester)
            status = 'error' if 'error' in res else 'success'
            recorded_tool_calls.append({'tool': 'get_recent_history', 'arguments': {'limit': limit}, 'status': status})
            nonlocal last_verified_result
            last_verified_result = res
            return res

        tools = [
            get_box_recommendation,
            lookup_order_details,
            check_box_inventory,
            search_orders,
            list_all_boxes,
            search_products,
            get_recent_history,
        ]

        client = genai.Client(api_key=self.api_key, http_options=types.HttpOptions(timeout=10000))
        chat = client.chats.create(
            model=self.model_name,
            config=types.GenerateContentConfig(
                tools=tools,
                system_instruction=(
                    "You are BoxIQ's AI Packaging Assistant for warehouse operators. "
                    "You have access to safe tools that query the warehouse database (orders, boxes, inventory, products) "
                    "and run the deterministic 3D packaging engine. "
                    "Always use the available tools to search the database and compute packaging recommendations before answering. "
                    "Ground your answers strictly on verified database and engine tool outputs. "
                    "Be professional, concise, and helpful to the warehouse operator."
                ),
                temperature=0.2,
            )
        )

        response = chat.send_message(message)
        reply_text = response.text if hasattr(response, 'text') and response.text else "Query completed."

        return {
            'reply': reply_text,
            'tool_calls': recorded_tool_calls,
            'verified_result': last_verified_result,
            'is_gemini_powered': True,
            'model': self.model_name,
        }

    def _process_query_deterministic(self, clean_msg: str, requester: str) -> Dict[str, Any]:
        """
        Deterministic intent recognition and tool execution fallback.
        """
        tool_call = self._determine_tool_call(clean_msg)
        if not tool_call:
            return {
                'reply': (
                    "I can help you search the database and find shipping boxes for orders. "
                    "For example: 'Which box should I use for ORD-1001?', 'Show details for order ORD-1002', "
                    "'What is the stock of box BX-102?', or 'List all shipping boxes'."
                ),
                'tool_calls': [],
                'verified_result': None,
                'is_gemini_powered': False,
            }

        tool_name = tool_call.get('tool')
        if tool_name not in APPROVED_TOOLS:
            return {
                'reply': f"Error: Tool '{tool_name}' is not in the approved security allowlist.",
                'tool_calls': [tool_call],
                'verified_result': None,
                'error': 'Unapproved tool',
                'is_gemini_powered': False,
            }

        execution_result = self._execute_tool(tool_name, tool_call.get('arguments', {}), requester)
        explanation = self._generate_explanation(tool_name, tool_call['arguments'], execution_result)

        return {
            'reply': explanation,
            'tool_calls': [
                {
                    'tool': tool_name,
                    'arguments': tool_call['arguments'],
                    'status': 'error' if 'error' in execution_result else 'success',
                }
            ],
            'verified_result': execution_result,
            'is_gemini_powered': False,
        }

    def _determine_tool_call(self, message: str) -> Optional[Dict[str, Any]]:
        """
        Identifies order, box, product, or catalog intents in user prompts.
        """
        order_match = re.search(r'\b(ORD(?:[-_][A-Za-z0-9]+)+|ORD\d+)\b', message, re.IGNORECASE)
        if not order_match:
            order_match = re.search(r'\border\s+(?:#\s*)?([A-Za-z0-9_-]+)\b', message, re.IGNORECASE)

        box_match = re.search(r'\b(BX[-_]?[A-Z0-9]+)\b', message, re.IGNORECASE)
        lower_msg = message.lower()

        # Recommendation intent
        if ('box' in lower_msg or 'recommend' in lower_msg or 'pack' in lower_msg or 'find' in lower_msg) and order_match:
            return {
                'tool': 'get_box_recommendation',
                'arguments': {'order_number': order_match.group(1).upper()}
            }

        # Order lookup intent
        if order_match and ('detail' in lower_msg or 'item' in lower_msg or 'status' in lower_msg or 'lookup' in lower_msg or 'show' in lower_msg or 'what is in' in lower_msg):
            return {
                'tool': 'lookup_order_details',
                'arguments': {'order_number': order_match.group(1).upper()}
            }

        # Box inventory intent (specific box code like BX-102)
        if box_match and ('stock' in lower_msg or 'inventory' in lower_msg or 'dimension' in lower_msg or 'box' in lower_msg):
            return {
                'tool': 'check_box_inventory',
                'arguments': {'box_code': box_match.group(1).upper()}
            }

        # List all boxes (general boxes query without specific box code)
        if not box_match and ('box' in lower_msg or 'boxes' in lower_msg) and any(w in lower_msg for w in ['all', 'list', 'available', 'catalog', 'types', 'every', 'shipping']):
            return {
                'tool': 'list_all_boxes',
                'arguments': {}
            }

        # Product search intent
        if 'product' in lower_msg:
            # Extract possible product query keyword
            prod_match = re.search(r'(?:product|products|item)\s+(?:named|called|for|with)?\s*[\'"]?([A-Za-z0-9_-]+)[\'"]?', message, re.IGNORECASE)
            query = prod_match.group(1) if prod_match else ''
            return {
                'tool': 'search_products',
                'arguments': {'query': query}
            }

        # Search orders intent
        if 'orders' in lower_msg and not order_match:
            return {
                'tool': 'search_orders',
                'arguments': {'query': ''}
            }

        # Audit history intent
        if 'history' in lower_msg or 'audit' in lower_msg or 'recent run' in lower_msg:
            return {
                'tool': 'get_recent_history',
                'arguments': {'limit': 10}
            }

        # Default fallback if order number exists
        if order_match:
            return {
                'tool': 'get_box_recommendation',
                'arguments': {'order_number': order_match.group(1).upper()}
            }

        return None

    def _execute_tool(self, tool_name: str, arguments: Dict[str, Any], requester: str) -> Dict[str, Any]:
        """
        Safely dispatches allowlisted tools to backend domain services and database queries.
        """
        if tool_name == 'get_box_recommendation':
            order_num = arguments.get('order_number', '')
            try:
                order, run, result = self.recommendation_service.get_recommendation_for_order(
                    order_identifier=order_num,
                    requester=requester,
                )
                return {
                    'order_number': order.order_number,
                    'status': order.status,
                    'recommendation': result.to_dict(),
                    'run_id': run.id,
                }
            except OrderNotFoundError as e:
                return {'error': str(e), 'type': 'OrderNotFoundError'}
            except EmptyOrderError as e:
                return {'error': str(e), 'type': 'EmptyOrderError'}
            except OrderStatusError as e:
                return {'error': str(e), 'type': 'OrderStatusError'}
            except InactiveProductInOrderError as e:
                return {'error': str(e), 'type': 'InactiveProductInOrderError'}
            except Exception as e:
                logger.exception("Unexpected error in get_box_recommendation")
                return {'error': f"Failed to compute recommendation: {str(e)}", 'type': 'SystemError'}

        elif tool_name == 'lookup_order_details':
            order_num = arguments.get('order_number', '')
            try:
                order = Order.objects.prefetch_related('items__product').get(order_number=order_num)
                items_data = [
                    {
                        'sku': item.product.sku,
                        'name': item.product.name,
                        'quantity': item.quantity,
                        'dimensions': f"{item.product.length}x{item.product.width}x{item.product.height} cm",
                        'weight': f"{item.product.weight} kg",
                        'is_fragile': item.product.is_fragile,
                    }
                    for item in order.items.all()
                ]
                return {
                    'order_number': order.order_number,
                    'customer_name': order.customer_name,
                    'status': order.status,
                    'is_assigned': order.is_assigned,
                    'assigned_box': order.assigned_box.code if order.assigned_box else None,
                    'items': items_data,
                    'total_items_quantity': order.total_items_quantity,
                    'total_weight': float(order.total_weight),
                }
            except Order.DoesNotExist:
                return {'error': f"Order '{order_num}' not found.", 'type': 'OrderNotFoundError'}

        elif tool_name == 'check_box_inventory':
            box_code = arguments.get('box_code', '')
            try:
                box = BoxType.objects.select_related('inventory').get(code=box_code)
                avail = box.inventory.quantity_available if hasattr(box, 'inventory') else 0
                return {
                    'code': box.code,
                    'name': box.name,
                    'dimensions': f"{box.length}x{box.width}x{box.height} cm",
                    'max_weight': f"{box.max_weight} kg",
                    'cost': f"{box.currency} {box.cost:.2f}",
                    'is_active': box.is_active,
                    'quantity_available': avail,
                    'quantity_on_hand': box.inventory.quantity_on_hand if hasattr(box, 'inventory') else 0,
                    'quantity_reserved': box.inventory.quantity_reserved if hasattr(box, 'inventory') else 0,
                }
            except BoxType.DoesNotExist:
                return {'error': f"Box '{box_code}' not found.", 'type': 'BoxNotFoundError'}

        elif tool_name == 'search_orders':
            query = arguments.get('query', '')
            status = arguments.get('status', '').upper()
            qs = Order.objects.prefetch_related('items__product', 'assigned_box').all()
            if status:
                qs = qs.filter(status=status)
            if query:
                qs = qs.filter(Q(order_number__icontains=query) | Q(customer_name__icontains=query))
            orders = qs[:20]
            return {
                'count': len(orders),
                'orders': [
                    {
                        'order_number': o.order_number,
                        'customer_name': o.customer_name,
                        'status': o.status,
                        'items_count': o.total_items_quantity,
                        'total_weight': float(o.total_weight),
                        'assigned_box': o.assigned_box.code if o.assigned_box else None,
                    }
                    for o in orders
                ]
            }

        elif tool_name == 'list_all_boxes':
            boxes = BoxType.objects.select_related('inventory').filter(is_active=True)
            return {
                'count': boxes.count(),
                'boxes': [
                    {
                        'code': b.code,
                        'name': b.name,
                        'dimensions': f"{b.length}x{b.width}x{b.height} cm",
                        'max_weight': f"{b.max_weight} kg",
                        'cost': f"{b.currency} {b.cost:.2f}",
                        'quantity_available': b.inventory.quantity_available if hasattr(b, 'inventory') else 0,
                    }
                    for b in boxes
                ]
            }

        elif tool_name == 'search_products':
            query = arguments.get('query', '')
            qs = Product.objects.filter(is_active=True)
            if query:
                qs = qs.filter(Q(sku__icontains=query) | Q(name__icontains=query))
            products = qs[:20]
            return {
                'count': len(products),
                'products': [
                    {
                        'sku': p.sku,
                        'name': p.name,
                        'dimensions': f"{p.length}x{p.width}x{p.height} cm",
                        'weight': f"{p.weight} kg",
                        'is_fragile': p.is_fragile,
                    }
                    for p in products
                ]
            }

        elif tool_name == 'get_recent_history':
            limit = int(arguments.get('limit', 10))
            runs = RecommendationRun.objects.select_related('order', 'best_box')[:limit]
            return {
                'count': len(runs),
                'runs': [
                    {
                        'id': r.id,
                        'order_number': r.order.order_number,
                        'is_successful': r.is_successful,
                        'best_box': r.best_box.code if r.best_box else None,
                        'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S'),
                        'summary': r.summary,
                    }
                    for r in runs
                ]
            }

        return {'error': f"Unrecognized tool: {tool_name}"}

    def _generate_explanation(
        self,
        tool_name: str,
        arguments: Dict[str, Any],
        result: Dict[str, Any],
    ) -> str:
        """
        Translates verified domain results into a concise, professional explanation for deterministic mode.
        """
        if 'error' in result:
            return f"Notice for {tool_name}: {result['error']}"

        if tool_name == 'get_box_recommendation':
            rec = result.get('recommendation', {})
            order_num = result.get('order_number', '')
            if rec.get('is_successful'):
                best = rec.get('best_box', {})
                alts = rec.get('alternatives', [])
                alt_text = ""
                if alts:
                    alt_codes = [f"{a['code']} ({a['currency']} {a['cost']:.2f})" for a in alts]
                    alt_text = f" Eligible alternative options: {', '.join(alt_codes)}."

                return (
                    f"For order {order_num}, the verified recommendation is **{best.get('code')}** "
                    f"({best.get('name')}) at {best.get('currency')} {best.get('cost', 0):.2f}. "
                    f"Estimated total packed weight is {best.get('total_packed_weight', 0):.3f} kg "
                    f"(capacity: {best.get('max_weight', 0):.3f} kg). "
                    f"Available stock: {best.get('quantity_available', 0)} units.{alt_text} "
                    f"Note: To reserve this box, please confirm using the 'Reserve Box' action."
                )
            else:
                rejected = rec.get('rejected_boxes', [])
                reasons = "; ".join(
                    {r for b in rejected for r in b.get('rejection_reasons', [])}
                )
                return (
                    f"For order {order_num}, no available box satisfies the fit, weight, and stock rules. "
                    f"Rejection reasons: {reasons or 'All candidate boxes out of stock or too small.'}"
                )

        elif tool_name == 'lookup_order_details':
            items = result.get('items', [])
            item_desc = ", ".join(f"{it['quantity']}x {it['name']} ({it['sku']})" for it in items)
            return (
                f"Order {result.get('order_number')} ({result.get('status')}): "
                f"Total {result.get('total_items_quantity')} item(s) weighing {result.get('total_weight'):.3f} kg. "
                f"Items: {item_desc}. Box assigned: {result.get('assigned_box') or 'None'}."
            )

        elif tool_name == 'check_box_inventory':
            return (
                f"Box {result.get('code')} ({result.get('name')}): "
                f"Dimensions {result.get('dimensions')}, Max weight {result.get('max_weight')}, "
                f"Cost {result.get('cost')}. "
                f"Stock status: {result.get('quantity_available')} available "
                f"({result.get('quantity_on_hand')} on hand, {result.get('quantity_reserved')} reserved)."
            )

        elif tool_name == 'list_all_boxes':
            boxes = result.get('boxes', [])
            if not boxes:
                return "No active shipping boxes found in the database."
            box_lines = [
                f"• **{b['code']}** ({b['name']}): {b['dimensions']}, Max {b['max_weight']}, {b['cost']} — Stock: {b['quantity_available']} available"
                for b in boxes
            ]
            return f"Found {result.get('count', len(boxes))} active shipping boxes:\n" + "\n".join(box_lines)

        elif tool_name == 'search_products':
            products = result.get('products', [])
            if not products:
                return "No matching products found in the catalog."
            prod_lines = [
                f"• **{p['sku']}** - {p['name']}: {p['dimensions']}, {p['weight']}{' [Fragile]' if p['is_fragile'] else ''}"
                for p in products
            ]
            return f"Found {result.get('count', len(products))} product(s):\n" + "\n".join(prod_lines)

        elif tool_name == 'search_orders':
            orders = result.get('orders', [])
            if not orders:
                return "No orders matched your search criteria."
            order_lines = [
                f"• **{o['order_number']}** ({o['customer_name']}): {o['status']} - {o['items_count']} item(s), {o['total_weight']} kg, Box: {o['assigned_box'] or 'None'}"
                for o in orders
            ]
            return f"Found {result.get('count', len(orders))} order(s):\n" + "\n".join(order_lines)

        elif tool_name == 'get_recent_history':
            runs = result.get('runs', [])
            if not runs:
                return "No recent packaging recommendation history found."
            run_lines = [
                f"• **{r['order_number']}** ({r['created_at']}): {'✓ ' + r['best_box'] if r['is_successful'] else '✗ No Fit'}"
                for r in runs
            ]
            return f"Recent {len(runs)} packaging recommendation run(s):\n" + "\n".join(run_lines)

        return str(result)
