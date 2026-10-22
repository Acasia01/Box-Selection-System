"""
Order Recommendation and Reservation Workflow Service.
Orchestrates retrieving authoritative database records, calling the PackagingEngine,
and persisting recommendation run audit history.
"""

from decimal import Decimal
from typing import Tuple, List, Optional
from django.db import transaction
from django.utils import timezone
from products.models import Product
from boxes.models import BoxType, BoxInventory
from boxes.services.packing_engine import (
    ItemToPack,
    PackagingEngine,
    PackagingResult,
)
from orders.models import (
    Order,
    OrderItem,
    RecommendationRun,
    RecommendationCandidate,
)


class OrderWorkflowError(Exception):
    """Base error for order recommendation workflows."""
    pass


class OrderNotFoundError(OrderWorkflowError):
    pass


class EmptyOrderError(OrderWorkflowError):
    pass


class OrderStatusError(OrderWorkflowError):
    pass


class InactiveProductInOrderError(OrderWorkflowError):
    pass


class InsufficientStockError(OrderWorkflowError):
    pass


class OrderRecommendationService:
    """
    Service responsible for validating orders, computing shipping box recommendations,
    recording run histories, and executing authorized stock reservations.
    """

    ALGORITHM_VERSION = 'v1.0.0-3D-EXTREME-POINTS'

    def __init__(self, engine: Optional[PackagingEngine] = None):
        self.engine = engine or PackagingEngine()

    def get_recommendation_for_order(
        self,
        order_identifier: str,
        requester: str = 'warehouse_operator',
    ) -> Tuple[Order, RecommendationRun, PackagingResult]:
        """
        Validates order, expands catalog items, evaluates candidate boxes,
        and saves complete recommendation run history.
        Does NOT reserve stock or mutate box inventory.
        """
        if not order_identifier or not str(order_identifier).strip():
            raise OrderNotFoundError("An order identifier must be provided.")

        clean_id = str(order_identifier).strip()

        # 1. Fetch Order
        try:
            order = Order.objects.prefetch_related('items__product').get(
                models_q_filter(clean_id)
            )
        except Order.DoesNotExist:
            raise OrderNotFoundError(f"Order '{clean_id}' was not found in the system.")

        # 2. Check Order Status
        if order.status == Order.STATUS_CANCELLED:
            raise OrderStatusError(f"Cannot recommend box: Order {order.order_number} is CANCELLED.")

        # 3. Check items count
        order_items = list(order.items.all())
        if not order_items:
            raise EmptyOrderError(f"Order {order.order_number} contains no line items to pack.")

        # 4. Check for inactive products
        inactive_products = [
            item.product.sku for item in order_items if not item.product.is_active
        ]
        if inactive_products:
            raise InactiveProductInOrderError(
                f"Order contains inactive catalog product(s): {', '.join(inactive_products)}. "
                "Catalog data must be active before packing."
            )

        # 5. Expand order line items into ItemToPack instances
        items_to_pack: List[ItemToPack] = []
        for line_item in order_items:
            prod = line_item.product
            for _ in range(line_item.quantity):
                items_to_pack.append(
                    ItemToPack(
                        sku=prod.sku,
                        name=prod.name,
                        length=prod.length,
                        width=prod.width,
                        height=prod.height,
                        weight=prod.weight,
                        clearance=prod.clearance,
                        is_fragile=prod.is_fragile,
                    )
                )

        # 6. Load candidate boxes with live inventory from database
        candidate_boxes = list(
            BoxType.objects.all().select_related('inventory')
        )

        # 7. Evaluate candidates with deterministic packaging engine
        packaging_result = self.engine.evaluate_candidates(
            items=items_to_pack,
            candidate_boxes=candidate_boxes,
        )

        # 8. Persist recommendation run & candidate evaluations for traceability
        run = self._persist_run_audit(
            order=order,
            result=packaging_result,
            requester=requester,
            items_count=len(items_to_pack),
        )

        return (order, run, packaging_result)

    def _persist_run_audit(
        self,
        order: Order,
        result: PackagingResult,
        requester: str,
        items_count: int,
    ) -> RecommendationRun:
        with transaction.atomic():
            best_box_model = None
            if result.best_candidate and result.best_candidate.box_id:
                try:
                    best_box_model = BoxType.objects.get(id=result.best_candidate.box_id)
                except BoxType.DoesNotExist:
                    best_box_model = None

            run = RecommendationRun.objects.create(
                order=order,
                algorithm_version=self.ALGORITHM_VERSION,
                requester=requester,
                is_successful=result.is_successful,
                best_box=best_box_model,
                total_items_count=items_count,
                total_products_weight=result.total_products_weight,
                protective_material_weight=result.protective_material_weight,
                summary=result.summary_message,
            )

            # Persist evaluation for each candidate
            for cand in result.all_candidates:
                if cand.box_id:
                    try:
                        box_ref = BoxType.objects.get(id=cand.box_id)
                    except BoxType.DoesNotExist:
                        continue
                else:
                    box_ref = BoxType.objects.filter(code=cand.code).first()
                    if not box_ref:
                        continue

                RecommendationCandidate.objects.create(
                    run=run,
                    box_type=box_ref,
                    is_eligible=cand.is_eligible,
                    rank=cand.rank,
                    total_packed_weight=cand.total_packed_weight,
                    cost=cand.cost,
                    unused_volume=cand.unused_volume,
                    rejection_reasons=cand.rejection_reasons,
                    placements_json=[p.to_dict() for p in cand.placements],
                    explanation=cand.explanation,
                )

        return run

    @transaction.atomic
    def reserve_and_assign_box(
        self,
        order_identifier: str,
        box_code: str,
    ) -> Tuple[Order, BoxInventory]:
        """
        Concurrency-safe, explicit assignment of a box to an order with atomic inventory reservation.
        Rechecks available stock with row-level locking (select_for_update).
        """
        clean_id = str(order_identifier).strip()
        try:
            order = Order.objects.select_for_update().get(models_q_filter(clean_id))
        except Order.DoesNotExist:
            raise OrderNotFoundError(f"Order '{clean_id}' does not exist.")

        if order.is_assigned and order.assigned_box:
            # If already assigned the same box, return idempotently
            if order.assigned_box.code == box_code:
                inv = BoxInventory.objects.get(box_type=order.assigned_box)
                return (order, inv)
            raise OrderWorkflowError(
                f"Order {order.order_number} is already assigned to box {order.assigned_box.code}."
            )

        try:
            box = BoxType.objects.get(code=box_code)
        except BoxType.DoesNotExist:
            raise OrderWorkflowError(f"Box with code '{box_code}' does not exist.")

        # Lock inventory row
        try:
            inventory = BoxInventory.objects.select_for_update().get(box_type=box)
        except BoxInventory.DoesNotExist:
            raise InsufficientStockError(f"Box {box.code} has no inventory record.")

        # Recheck live stock inside atomic transaction
        if inventory.quantity_available < 1:
            raise InsufficientStockError(
                f"Cannot reserve {box.code}: available stock is {inventory.quantity_available} units."
            )

        # Atomically increment quantity_reserved
        inventory.quantity_reserved += 1
        inventory.save()

        # Update Order
        order.assigned_box = box
        order.is_assigned = True
        order.assigned_at = timezone.now()
        order.save()

        return (order, inventory)


def models_q_filter(clean_id: str):
    from django.db.models import Q
    if clean_id.isdigit():
        return Q(order_number=clean_id) | Q(id=int(clean_id))
    return Q(order_number=clean_id)
