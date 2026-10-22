import os
import json
from decimal import Decimal
from django.shortcuts import render
from django.http import JsonResponse, HttpResponseBadRequest
from django.views.decorators.http import require_http_methods
from django.views.decorators.csrf import ensure_csrf_cookie, csrf_exempt
from django.db.models import Prefetch

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
    OrderWorkflowError,
)
from orders.services.ai_assistant import AIAssistantService


def index_view(request):
    """Renders the packing workstation as the default home view."""
    return render(request, 'workstation/workstation.html')


def workstation_page_view(request):
    """Renders the dedicated Packing Workstation page."""
    return render(request, 'workstation/workstation.html')


def orders_page_view(request):
    """Renders the dedicated Orders Catalog page."""
    return render(request, 'order/orders.html')


def boxes_page_view(request):
    """Renders the dedicated Boxes & Inventory page."""
    return render(request, 'boxes/boxes.html')


def history_page_view(request):
    """Renders the dedicated Audit History page."""
    return render(request, 'history/history.html')


def ai_page_view(request):
    """Renders the dedicated AI Packaging Assistant page."""
    from django.conf import settings
    gemini_key = getattr(settings, 'GEMINI_API_KEY', '') or os.getenv('GEMINI_API_KEY', '')
    is_gemini_active = bool(
        gemini_key and gemini_key.strip() and gemini_key.strip() not in ('your_gemini_api_key_here', 'dummy_key', 'test_key')
    )
    return render(request, 'ai/ai.html', {
        'gemini_active': is_gemini_active,
        'model_name': os.getenv('GEMINI_MODEL', 'gemini-2.5-flash'),
    })


@require_http_methods(["GET"])
def api_list_orders(request):
    """Returns all orders with summary metrics and line items for workstation lookup."""
    orders = Order.objects.prefetch_related('items__product', 'assigned_box').all()
    data = []
    for o in orders:
        items = [
            {
                'sku': item.product.sku,
                'name': item.product.name,
                'quantity': item.quantity,
                'dimensions': f"{item.product.length} × {item.product.width} × {item.product.height} cm",
                'weight': float(item.product.weight),
                'clearance': float(item.product.clearance),
                'is_fragile': item.product.is_fragile,
            }
            for item in o.items.all()
        ]
        data.append({
            'order_number': o.order_number,
            'customer_name': o.customer_name,
            'status': o.status,
            'status_display': o.get_status_display(),
            'is_assigned': o.is_assigned,
            'assigned_box': o.assigned_box.code if o.assigned_box else None,
            'assigned_at': o.assigned_at.isoformat() if o.assigned_at else None,
            'items_count': o.total_items_quantity,
            'total_weight': float(o.total_weight),
            'items': items,
        })
    return JsonResponse({'orders': data})


@require_http_methods(["GET"])
def api_recommend_box(request, order_number):
    """Calculates deterministic recommendation and returns structured candidate details."""
    service = OrderRecommendationService()
    requester = request.user.username if request.user.is_authenticated else 'warehouse_operator'

    try:
        order, run, result = service.get_recommendation_for_order(
            order_identifier=order_number,
            requester=requester,
        )
        return JsonResponse({
            'success': True,
            'order': {
                'order_number': order.order_number,
                'customer_name': order.customer_name,
                'status': order.status,
                'is_assigned': order.is_assigned,
                'assigned_box': order.assigned_box.code if order.assigned_box else None,
                'total_weight': float(order.total_weight),
                'total_items_count': order.total_items_quantity,
                'items': [
                    {
                        'sku': it.product.sku,
                        'name': it.product.name,
                        'quantity': it.quantity,
                        'length': float(it.product.length),
                        'width': float(it.product.width),
                        'height': float(it.product.height),
                        'weight': float(it.product.weight),
                        'clearance': float(it.product.clearance),
                        'is_fragile': it.product.is_fragile,
                    }
                    for it in order.items.all()
                ]
            },
            'run_id': run.id,
            'algorithm_version': run.algorithm_version,
            'recommendation': result.to_dict(),
        })
    except OrderNotFoundError as e:
        return JsonResponse({'success': False, 'error': str(e), 'code': 'NOT_FOUND'}, status=404)
    except EmptyOrderError as e:
        return JsonResponse({'success': False, 'error': str(e), 'code': 'EMPTY_ORDER'}, status=400)
    except OrderStatusError as e:
        return JsonResponse({'success': False, 'error': str(e), 'code': 'INVALID_STATUS'}, status=400)
    except InactiveProductInOrderError as e:
        return JsonResponse({'success': False, 'error': str(e), 'code': 'INACTIVE_PRODUCT'}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Server error: {str(e)}", 'code': 'INTERNAL_ERROR'}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_reserve_box(request):
    """
    Explicit, authorized reservation of a recommended box for an order.
    Atomically locks inventory row and increments reserved stock.
    """
    try:
        payload = json.loads(request.body)
    except Exception:
        return HttpResponseBadRequest("Invalid JSON payload.")

    order_number = payload.get('order_number')
    box_code = payload.get('box_code')

    if not order_number or not box_code:
        return JsonResponse({'success': False, 'error': 'Both order_number and box_code are required.'}, status=400)

    service = OrderRecommendationService()
    try:
        order, inventory = service.reserve_and_assign_box(
            order_identifier=order_number,
            box_code=box_code,
        )
        return JsonResponse({
            'success': True,
            'message': f"Box {box_code} successfully reserved and assigned to Order {order.order_number}.",
            'order': {
                'order_number': order.order_number,
                'status': order.status,
                'is_assigned': order.is_assigned,
                'assigned_box': order.assigned_box.code,
                'assigned_at': order.assigned_at.isoformat() if order.assigned_at else None,
            },
            'inventory': {
                'box_code': box_code,
                'quantity_on_hand': inventory.quantity_on_hand,
                'quantity_reserved': inventory.quantity_reserved,
                'quantity_available': inventory.quantity_available,
            }
        })
    except (OrderNotFoundError, InsufficientStockError, OrderWorkflowError) as e:
        return JsonResponse({'success': False, 'error': str(e)}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Internal error during reservation: {str(e)}"}, status=500)


@csrf_exempt
@require_http_methods(["POST"])
def api_chat(request):
    """
    AI natural-language assistant endpoint for packaging queries.
    Enforces allowlisted tool execution and verified response generation.
    """
    try:
        payload = json.loads(request.body)
    except Exception:
        return HttpResponseBadRequest("Invalid JSON payload.")

    message = payload.get('message', '')
    requester = request.user.username if request.user.is_authenticated else 'warehouse_operator'

    assistant = AIAssistantService()
    result = assistant.process_query(message=message, requester=requester)

    return JsonResponse(result)


@require_http_methods(["GET"])
def api_list_boxes(request):
    """Returns all active/inactive box specifications and live inventory."""
    boxes = BoxType.objects.select_related('inventory').all()
    data = []
    for b in boxes:
        avail = b.inventory.quantity_available if hasattr(b, 'inventory') else 0
        on_hand = b.inventory.quantity_on_hand if hasattr(b, 'inventory') else 0
        reserved = b.inventory.quantity_reserved if hasattr(b, 'inventory') else 0
        data.append({
            'code': b.code,
            'name': b.name,
            'length': float(b.length),
            'width': float(b.width),
            'height': float(b.height),
            'internal_volume': float(b.internal_volume),
            'max_weight': float(b.max_weight),
            'empty_weight': float(b.empty_weight),
            'cost': float(b.cost),
            'currency': b.currency,
            'is_active': b.is_active,
            'quantity_on_hand': on_hand,
            'quantity_reserved': reserved,
            'quantity_available': avail,
        })
    return JsonResponse({'boxes': data})


@require_http_methods(["GET"])
def api_list_history(request):
    """Returns audit log of recent recommendation runs."""
    runs = RecommendationRun.objects.select_related('order', 'best_box').prefetch_related('candidates__box_type')[:30]
    data = []
    for r in runs:
        data.append({
            'id': r.id,
            'order_number': r.order.order_number,
            'algorithm_version': r.algorithm_version,
            'requester': r.requester,
            'is_successful': r.is_successful,
            'best_box': r.best_box.code if r.best_box else None,
            'total_items_count': r.total_items_count,
            'total_products_weight': float(r.total_products_weight),
            'summary': r.summary,
            'created_at': r.created_at.strftime('%Y-%m-%d %H:%M:%S'),
            'candidates_count': r.candidates.count(),
        })
    return JsonResponse({'runs': data})


@require_http_methods(["GET"])
def api_list_products(request):
    """Returns active products catalog for order item selection."""
    products = Product.objects.filter(is_active=True).order_by('name')
    data = [
        {
            'id': p.id,
            'sku': p.sku,
            'name': p.name,
            'length': float(p.length),
            'width': float(p.width),
            'height': float(p.height),
            'weight': float(p.weight),
            'clearance': float(p.clearance),
            'is_fragile': p.is_fragile,
        }
        for p in products
    ]
    return JsonResponse({'products': data})


@require_http_methods(["POST"])
def api_create_box(request):
    """Creates a new BoxType and initializes its BoxInventory record."""
    try:
        payload = json.loads(request.body)
    except Exception:
        return HttpResponseBadRequest("Invalid JSON payload.")

    code = str(payload.get('code', '')).strip().upper()
    name = str(payload.get('name', '')).strip()

    if not code or not name:
        return JsonResponse({'success': False, 'error': 'Both Box Code and Box Name are required.'}, status=400)

    if BoxType.objects.filter(code=code).exists():
        return JsonResponse({'success': False, 'error': f"Box with code '{code}' already exists."}, status=400)

    try:
        length = Decimal(str(payload.get('length', '0.01')))
        width = Decimal(str(payload.get('width', '0.01')))
        height = Decimal(str(payload.get('height', '0.01')))
        max_weight = Decimal(str(payload.get('max_weight', '0.001')))
        empty_weight = Decimal(str(payload.get('empty_weight', '0.000')))
        cost = Decimal(str(payload.get('cost', '0.00')))
        currency = str(payload.get('currency', 'INR')).strip().upper() or 'INR'
        quantity_on_hand = int(payload.get('quantity_on_hand', 0))
        is_active = bool(payload.get('is_active', True))

        if length <= 0 or width <= 0 or height <= 0:
            return JsonResponse({'success': False, 'error': 'Dimensions must be strictly greater than 0.'}, status=400)
        if max_weight <= 0:
            return JsonResponse({'success': False, 'error': 'Max weight capacity must be greater than 0.'}, status=400)
        if empty_weight < 0 or cost < 0 or quantity_on_hand < 0:
            return JsonResponse({'success': False, 'error': 'Empty weight, cost, and stock quantity cannot be negative.'}, status=400)

        box = BoxType.objects.create(
            code=code,
            name=name,
            length=length,
            width=width,
            height=height,
            max_weight=max_weight,
            empty_weight=empty_weight,
            cost=cost,
            currency=currency,
            is_active=is_active,
        )
        BoxInventory.objects.create(
            box_type=box,
            quantity_on_hand=quantity_on_hand,
            quantity_reserved=0,
        )

        return JsonResponse({
            'success': True,
            'message': f"Box {box.code} successfully created with {quantity_on_hand} units in stock.",
            'box': {
                'code': box.code,
                'name': box.name,
                'cost': float(box.cost),
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Failed to create box: {str(e)}"}, status=400)


@require_http_methods(["POST"])
def api_update_box(request, code):
    """Updates attributes of an existing BoxType and its BoxInventory."""
    try:
        box = BoxType.objects.select_related('inventory').get(code=code)
    except BoxType.DoesNotExist:
        return JsonResponse({'success': False, 'error': f"Box '{code}' not found."}, status=404)

    try:
        payload = json.loads(request.body)
    except Exception:
        return HttpResponseBadRequest("Invalid JSON payload.")

    try:
        if 'name' in payload:
            box.name = str(payload['name']).strip()
        if 'length' in payload:
            box.length = Decimal(str(payload['length']))
        if 'width' in payload:
            box.width = Decimal(str(payload['width']))
        if 'height' in payload:
            box.height = Decimal(str(payload['height']))
        if 'max_weight' in payload:
            box.max_weight = Decimal(str(payload['max_weight']))
        if 'empty_weight' in payload:
            box.empty_weight = Decimal(str(payload['empty_weight']))
        if 'cost' in payload:
            box.cost = Decimal(str(payload['cost']))
        if 'currency' in payload:
            box.currency = str(payload['currency']).strip().upper()
        if 'is_active' in payload:
            box.is_active = bool(payload['is_active'])

        if box.length <= 0 or box.width <= 0 or box.height <= 0 or box.max_weight <= 0:
            return JsonResponse({'success': False, 'error': 'Dimensions and max weight must be positive.'}, status=400)

        box.save()

        # Update inventory if on_hand is specified
        if 'quantity_on_hand' in payload and hasattr(box, 'inventory'):
            new_on_hand = int(payload['quantity_on_hand'])
            if new_on_hand < box.inventory.quantity_reserved:
                return JsonResponse({
                    'success': False,
                    'error': f"Cannot set on-hand stock ({new_on_hand}) below reserved quantity ({box.inventory.quantity_reserved})."
                }, status=400)
            box.inventory.quantity_on_hand = new_on_hand
            box.inventory.save()

        return JsonResponse({
            'success': True,
            'message': f"Box {box.code} specifications and inventory updated successfully.",
            'box': {
                'code': box.code,
                'name': box.name,
                'cost': float(box.cost),
                'quantity_available': box.inventory.quantity_available if hasattr(box, 'inventory') else 0,
            }
        })
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Update failed: {str(e)}"}, status=400)


@require_http_methods(["POST"])
def api_create_order(request):
    """Creates a new Order and associates its line items."""
    try:
        payload = json.loads(request.body)
    except Exception:
        return HttpResponseBadRequest("Invalid JSON payload.")

    order_number = str(payload.get('order_number', '')).strip().upper()
    customer_name = str(payload.get('customer_name', '')).strip()
    status = str(payload.get('status', Order.STATUS_PENDING)).strip()
    items_data = payload.get('items', [])

    if not order_number:
        return JsonResponse({'success': False, 'error': 'Order Number is required.'}, status=400)

    if Order.objects.filter(order_number=order_number).exists():
        return JsonResponse({'success': False, 'error': f"Order '{order_number}' already exists."}, status=400)

    try:
        order = Order.objects.create(
            order_number=order_number,
            customer_name=customer_name,
            status=status,
        )

        for item_info in items_data:
            sku = item_info.get('sku')
            qty = int(item_info.get('quantity', 1))
            if qty <= 0:
                continue
            product = Product.objects.get(sku=sku)
            OrderItem.objects.create(order=order, product=product, quantity=qty)

        return JsonResponse({
            'success': True,
            'message': f"Order {order.order_number} created with {order.items.count()} item lines.",
            'order': {
                'order_number': order.order_number,
                'customer_name': order.customer_name,
                'status': order.status,
            }
        })
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': f"Product with SKU '{sku}' not found."}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Failed to create order: {str(e)}"}, status=400)


@require_http_methods(["POST"])
def api_update_order(request, order_number):
    """Updates Order details and line items."""
    try:
        order = Order.objects.get(order_number=order_number)
    except Order.DoesNotExist:
        return JsonResponse({'success': False, 'error': f"Order '{order_number}' not found."}, status=404)

    try:
        payload = json.loads(request.body)
    except Exception:
        return HttpResponseBadRequest("Invalid JSON payload.")

    try:
        if 'customer_name' in payload:
            order.customer_name = str(payload['customer_name']).strip()
        if 'status' in payload:
            order.status = str(payload['status']).strip()

        # If items provided, replace existing items
        if 'items' in payload:
            order.items.all().delete()
            for it in payload['items']:
                sku = it.get('sku')
                qty = int(it.get('quantity', 1))
                if qty > 0:
                    product = Product.objects.get(sku=sku)
                    OrderItem.objects.create(order=order, product=product, quantity=qty)

        order.save()

        return JsonResponse({
            'success': True,
            'message': f"Order {order.order_number} updated successfully.",
            'order': {
                'order_number': order.order_number,
                'customer_name': order.customer_name,
                'status': order.status,
                'items_count': order.total_items_quantity,
            }
        })
    except Product.DoesNotExist:
        return JsonResponse({'success': False, 'error': f"Product SKU not found."}, status=400)
    except Exception as e:
        return JsonResponse({'success': False, 'error': f"Failed to update order: {str(e)}"}, status=400)

