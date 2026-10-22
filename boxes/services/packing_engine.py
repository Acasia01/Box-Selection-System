"""
Deterministic 3D Packaging Engine for Smart Shipping Box Recommendation System.
Performs rigorous physical 3D bin placement, orientation permutations, clearance buffering,
weight limit verification, stock check, and lexicographic ranking.
"""

from decimal import Decimal
from itertools import permutations
from typing import List, Dict, Any, Optional, Tuple


class ItemToPack:
    """
    Representation of an individual product instance to be packed.
    Dimensions are in centimetres (cm), weight in kilograms (kg).
    """
    def __init__(
        self,
        sku: str,
        name: str,
        length: Decimal,
        width: Decimal,
        height: Decimal,
        weight: Decimal,
        clearance: Decimal = Decimal('0.00'),
        is_fragile: bool = False,
        allow_any_orientation: bool = True,
    ):
        self.sku = str(sku)
        self.name = str(name)
        self.length = Decimal(str(length))
        self.width = Decimal(str(width))
        self.height = Decimal(str(height))
        self.weight = Decimal(str(weight))
        self.clearance = Decimal(str(clearance))
        self.is_fragile = bool(is_fragile)
        self.allow_any_orientation = allow_any_orientation

    @property
    def effective_dimensions(self) -> Tuple[Decimal, Decimal, Decimal]:
        """
        Dimensions after applying clearance on every side:
        axis_effective = axis + 2 * clearance
        """
        extra = self.clearance * Decimal('2')
        return (self.length + extra, self.width + extra, self.height + extra)

    @property
    def effective_volume(self) -> Decimal:
        el, ew, eh = self.effective_dimensions
        return el * ew * eh

    def get_rotations(self) -> List[Tuple[Decimal, Decimal, Decimal]]:
        """
        Returns all unique 3D orthogonal rotations (dx, dy, dz).
        For an unconstrained cuboid, up to 6 unique permutations.
        """
        el, ew, eh = self.effective_dimensions
        if self.allow_any_orientation:
            raw_perms = set(permutations([el, ew, eh]))
        else:
            # Upright constraint: height axis eh remains fixed along Z
            raw_perms = {(el, ew, eh), (ew, el, eh)}
        # Return sorted list for deterministic evaluation
        return sorted(list(raw_perms), reverse=True)


class PlacedItem:
    """
    Represents an item placed in 3D coordinate space inside a box.
    Coordinates (x, y, z) mark the bottom-front-left corner.
    """
    def __init__(
        self,
        item: ItemToPack,
        x: Decimal,
        y: Decimal,
        z: Decimal,
        dx: Decimal,
        dy: Decimal,
        dz: Decimal,
    ):
        self.item = item
        self.sku = item.sku
        self.name = item.name
        self.x = Decimal(str(x))
        self.y = Decimal(str(y))
        self.z = Decimal(str(z))
        self.dx = Decimal(str(dx))
        self.dy = Decimal(str(dy))
        self.dz = Decimal(str(dz))

    def overlaps_with(self, other: 'PlacedItem') -> bool:
        """Checks whether two placed 3D items intersect in volume."""
        no_overlap = (
            (self.x + self.dx <= other.x) or (other.x + other.dx <= self.x) or
            (self.y + self.dy <= other.y) or (other.y + other.dy <= self.y) or
            (self.z + self.dz <= other.z) or (other.z + other.dz <= self.z)
        )
        return not no_overlap

    def to_dict(self) -> Dict[str, Any]:
        return {
            'sku': self.sku,
            'name': self.name,
            'x': float(self.x),
            'y': float(self.y),
            'z': float(self.z),
            'dx': float(self.dx),
            'dy': float(self.dy),
            'dz': float(self.dz),
            'weight': float(self.item.weight),
        }


class CandidateResult:
    """
    Detailed evaluation outcome for a single candidate box type.
    """
    def __init__(
        self,
        box_id: Any,
        code: str,
        name: str,
        length: Decimal,
        width: Decimal,
        height: Decimal,
        max_weight: Decimal,
        empty_weight: Decimal,
        cost: Decimal,
        currency: str,
        quantity_available: int,
        is_active: bool,
    ):
        self.box_id = box_id
        self.code = code
        self.name = name
        self.length = Decimal(str(length))
        self.width = Decimal(str(width))
        self.height = Decimal(str(height))
        self.max_weight = Decimal(str(max_weight))
        self.empty_weight = Decimal(str(empty_weight))
        self.cost = Decimal(str(cost))
        self.currency = currency
        self.quantity_available = quantity_available
        self.is_active = is_active

        self.internal_volume = self.length * self.width * self.height
        self.is_eligible = False
        self.total_packed_weight = Decimal('0.000')
        self.unused_volume = Decimal('0.00')
        self.rejection_reasons: List[str] = []
        self.placements: List[PlacedItem] = []
        self.rank: Optional[int] = None
        self.explanation: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            'box_id': self.box_id,
            'code': self.code,
            'name': self.name,
            'dimensions': {
                'length': float(self.length),
                'width': float(self.width),
                'height': float(self.height),
            },
            'max_weight': float(self.max_weight),
            'empty_weight': float(self.empty_weight),
            'cost': float(self.cost),
            'currency': self.currency,
            'quantity_available': self.quantity_available,
            'is_eligible': self.is_eligible,
            'rank': self.rank,
            'total_packed_weight': float(self.total_packed_weight),
            'unused_volume': float(self.unused_volume),
            'internal_volume': float(self.internal_volume),
            'rejection_reasons': self.rejection_reasons,
            'placements': [p.to_dict() for p in self.placements],
            'explanation': self.explanation,
        }


class PackagingResult:
    """
    Final result of the packaging engine recommendation process.
    """
    def __init__(
        self,
        best_candidate: Optional[CandidateResult],
        alternatives: List[CandidateResult],
        rejected_candidates: List[CandidateResult],
        all_candidates: List[CandidateResult],
        total_items_count: int,
        total_products_weight: Decimal,
        protective_material_weight: Decimal,
    ):
        self.best_candidate = best_candidate
        self.alternatives = alternatives
        self.rejected_candidates = rejected_candidates
        self.all_candidates = all_candidates
        self.is_successful = best_candidate is not None
        self.total_items_count = total_items_count
        self.total_products_weight = total_products_weight
        self.protective_material_weight = protective_material_weight

    @property
    def summary_message(self) -> str:
        if self.is_successful:
            return (
                f"Recommended box: {self.best_candidate.code} ({self.best_candidate.name}) "
                f"at {self.best_candidate.currency} {self.best_candidate.cost:.2f}. "
                f"{len(self.alternatives)} alternative(s) available."
            )
        else:
            reasons = "; ".join(
                {r for cand in self.rejected_candidates for r in cand.rejection_reasons}
            )
            return f"No eligible box found. Reasons: {reasons if reasons else 'No active candidate boxes with stock.'}"

    def to_dict(self) -> Dict[str, Any]:
        return {
            'is_successful': self.is_successful,
            'summary': self.summary_message,
            'total_items_count': self.total_items_count,
            'total_products_weight': float(self.total_products_weight),
            'protective_material_weight': float(self.protective_material_weight),
            'best_box': self.best_candidate.to_dict() if self.best_candidate else None,
            'alternatives': [c.to_dict() for c in self.alternatives],
            'rejected_boxes': [c.to_dict() for c in self.rejected_candidates],
        }


class PackagingEngine:
    """
    Deterministic packaging engine service that validates physical 3D fit, weight,
    stock, and computes cost-based ranking.
    """

    # Configurable protective buffer in kg per fragile item
    DEFAULT_FRAGILE_BUFFER_KG = Decimal('0.050')

    def __init__(self, fragile_material_buffer_kg: Optional[Decimal] = None):
        self.fragile_buffer = (
            fragile_material_buffer_kg
            if fragile_material_buffer_kg is not None
            else self.DEFAULT_FRAGILE_BUFFER_KG
        )

    def evaluate_candidates(
        self,
        items: List[ItemToPack],
        candidate_boxes: List[Any],
    ) -> PackagingResult:
        """
        Evaluates a list of items against candidate boxes.
        candidate_boxes can be BoxType model instances or dicts matching box specifications.
        """
        if not items:
            return PackagingResult(
                best_candidate=None,
                alternatives=[],
                rejected_candidates=[],
                all_candidates=[],
                total_items_count=0,
                total_products_weight=Decimal('0.000'),
                protective_material_weight=Decimal('0.000'),
            )

        # 1. Calculate order aggregates
        total_products_weight = sum(item.weight for item in items)
        fragile_items_count = sum(1 for item in items if item.is_fragile)
        protective_material_weight = self.fragile_buffer * Decimal(str(fragile_items_count))
        total_effective_volume = sum(item.effective_volume for item in items)

        evaluated_candidates: List[CandidateResult] = []

        # 2. Evaluate each candidate box
        for box in candidate_boxes:
            cand = self._create_candidate_result(box)
            self._evaluate_single_box(
                candidate=cand,
                items=items,
                total_products_weight=total_products_weight,
                protective_material_weight=protective_material_weight,
                total_effective_volume=total_effective_volume,
            )
            evaluated_candidates.append(cand)

        # 3. Filter eligible vs rejected
        eligible_candidates = [c for c in evaluated_candidates if c.is_eligible]
        rejected_candidates = [c for c in evaluated_candidates if not c.is_eligible]

        # 4. Rank eligible boxes according to documented lexicographic criteria:
        #    1) Lowest cost
        #    2) Least unused internal volume
        #    3) Highest available stock
        eligible_candidates.sort(
            key=lambda c: (c.cost, c.unused_volume, -c.quantity_available)
        )

        for idx, cand in enumerate(eligible_candidates, start=1):
            cand.rank = idx
            if idx == 1:
                cand.explanation = (
                    f"{cand.code} is recommended because it passes physical fit and weight checks, "
                    f"has stock available ({cand.quantity_available} units), and is the lowest-cost eligible box "
                    f"({cand.currency} {cand.cost:.2f}). Total packed weight: {cand.total_packed_weight:.3f} kg "
                    f"against {cand.max_weight:.3f} kg capacity."
                )
            else:
                cand.explanation = (
                    f"{cand.code} is an eligible alternative (Rank #{idx}). "
                    f"Cost: {cand.currency} {cand.cost:.2f}, unused volume: {cand.unused_volume:.2f} cm³, "
                    f"available stock: {cand.quantity_available}."
                )

        best_box = eligible_candidates[0] if eligible_candidates else None
        alternatives = eligible_candidates[1:4] if len(eligible_candidates) > 1 else []

        return PackagingResult(
            best_candidate=best_box,
            alternatives=alternatives,
            rejected_candidates=rejected_candidates,
            all_candidates=evaluated_candidates,
            total_items_count=len(items),
            total_products_weight=total_products_weight,
            protective_material_weight=protective_material_weight,
        )

    def _create_candidate_result(self, box: Any) -> CandidateResult:
        """Extracts box attributes from either Django model instance or dictionary."""
        if hasattr(box, 'code'):
            # Django Model instance
            avail = (
                box.inventory.quantity_available
                if hasattr(box, 'inventory')
                else 0
            )
            return CandidateResult(
                box_id=box.id if hasattr(box, 'id') else None,
                code=box.code,
                name=box.name,
                length=Decimal(str(box.length)),
                width=Decimal(str(box.width)),
                height=Decimal(str(box.height)),
                max_weight=Decimal(str(box.max_weight)),
                empty_weight=Decimal(str(box.empty_weight)),
                cost=Decimal(str(box.cost)),
                currency=box.currency,
                quantity_available=avail,
                is_active=box.is_active,
            )
        else:
            # Dictionary / Mock object
            return CandidateResult(
                box_id=box.get('id'),
                code=box['code'],
                name=box['name'],
                length=Decimal(str(box['length'])),
                width=Decimal(str(box['width'])),
                height=Decimal(str(box['height'])),
                max_weight=Decimal(str(box['max_weight'])),
                empty_weight=Decimal(str(box.get('empty_weight', '0.000'))),
                cost=Decimal(str(box['cost'])),
                currency=box.get('currency', 'INR'),
                quantity_available=int(box.get('quantity_available', 0)),
                is_active=bool(box.get('is_active', True)),
            )

    def _evaluate_single_box(
        self,
        candidate: CandidateResult,
        items: List[ItemToPack],
        total_products_weight: Decimal,
        protective_material_weight: Decimal,
        total_effective_volume: Decimal,
    ) -> None:
        """
        Runs all mandatory eligibility checks against candidate box:
        1. Active flag
        2. Stock availability
        3. Weight capacity
        4. Volume bounds
        5. Exact 3D physical arrangement
        """
        rejection_reasons = []

        # 1. Active status check
        if not candidate.is_active:
            rejection_reasons.append("Box type is inactive or discontinued.")

        # 2. Inventory check
        if candidate.quantity_available <= 0:
            rejection_reasons.append(
                f"Out of stock ({candidate.quantity_available} available in inventory)."
            )

        # 3. Total packed weight calculation and validation
        candidate.total_packed_weight = (
            total_products_weight + protective_material_weight + candidate.empty_weight
        )
        if candidate.total_packed_weight > candidate.max_weight:
            rejection_reasons.append(
                f"Packed weight ({candidate.total_packed_weight:.3f} kg) exceeds box maximum "
                f"capacity ({candidate.max_weight:.3f} kg)."
            )

        # 4. Total volume pre-check
        if total_effective_volume > candidate.internal_volume:
            rejection_reasons.append(
                f"Total items effective volume ({total_effective_volume:.2f} cm³) exceeds "
                f"box internal volume ({candidate.internal_volume:.2f} cm³)."
            )

        # 5. Check if any single item's minimal dimension exceeds largest box dimension
        max_box_dim = max(candidate.length, candidate.width, candidate.height)
        for it in items:
            min_item_dim = min(it.effective_dimensions)
            if min_item_dim > max_box_dim:
                rejection_reasons.append(
                    f"Item {it.sku} smallest effective dimension ({min_item_dim:.2f} cm) exceeds "
                    f"box largest internal dimension ({max_box_dim:.2f} cm)."
                )
                break

        # If already rejected on status/stock/weight/volume, skip expensive 3D search
        if rejection_reasons:
            candidate.is_eligible = False
            candidate.rejection_reasons = rejection_reasons
            return

        # 6. Physical 3D Bin Placement Validation
        fits, placements = self._pack_items_3d(
            items=items,
            box_length=candidate.length,
            box_width=candidate.width,
            box_height=candidate.height,
        )

        if not fits:
            rejection_reasons.append(
                "Items cannot physically fit inside box internal dimensions under any permitted orientation."
            )
            candidate.is_eligible = False
            candidate.rejection_reasons = rejection_reasons
            return

        # All checks passed!
        candidate.is_eligible = True
        candidate.placements = placements
        candidate.unused_volume = candidate.internal_volume - total_effective_volume

    def _pack_items_3d(
        self,
        items: List[ItemToPack],
        box_length: Decimal,
        box_width: Decimal,
        box_height: Decimal,
    ) -> Tuple[bool, List[PlacedItem]]:
        """
        Executes an exact/heuristic 3D placement algorithm using Extreme Corner Points
        and rotation permutations with backtracking.
        Guarantees that a physical, non-overlapping 3D arrangement exists within internal bounds.
        """
        # Sort items: largest effective volume first, then longest dimension
        sorted_items = sorted(
            items,
            key=lambda it: (it.effective_volume, max(it.effective_dimensions)),
            reverse=True,
        )

        # Start recursive placement
        placements: List[PlacedItem] = []
        state_counter = [0]
        max_states = 10000  # Guardrail against infinite loops

        success = self._backtrack_place(
            item_index=0,
            items=sorted_items,
            box_l=box_length,
            box_w=box_width,
            box_h=box_height,
            placed=placements,
            state_counter=state_counter,
            max_states=max_states,
        )

        return (success, placements if success else [])

    def _backtrack_place(
        self,
        item_index: int,
        items: List[ItemToPack],
        box_l: Decimal,
        box_w: Decimal,
        box_h: Decimal,
        placed: List[PlacedItem],
        state_counter: List[int],
        max_states: int,
    ) -> bool:
        if item_index == len(items):
            return True

        state_counter[0] += 1
        if state_counter[0] > max_states:
            return False

        item = items[item_index]
        candidate_points = self._generate_candidate_points(placed, box_l, box_w, box_h)
        rotations = item.get_rotations()

        for pt in candidate_points:
            x, y, z = pt
            for dx, dy, dz in rotations:
                # Check bounds
                if x + dx > box_l or y + dy > box_w or z + dz > box_h:
                    continue

                test_placement = PlacedItem(item, x, y, z, dx, dy, dz)

                # Check overlaps with currently placed items
                overlap = False
                for p in placed:
                    if test_placement.overlaps_with(p):
                        overlap = True
                        break

                if not overlap:
                    placed.append(test_placement)
                    if self._backtrack_place(
                        item_index + 1,
                        items,
                        box_l,
                        box_w,
                        box_h,
                        placed,
                        state_counter,
                        max_states,
                    ):
                        return True
                    # Backtrack
                    placed.pop()

        return False

    def _generate_candidate_points(
        self,
        placed: List[PlacedItem],
        box_l: Decimal,
        box_w: Decimal,
        box_h: Decimal,
    ) -> List[Tuple[Decimal, Decimal, Decimal]]:
        """
        Generates extreme corner points for item placement.
        Always includes origin (0, 0, 0), and after each placement generates
        (x+dx, y, z), (x, y+dy, z), (x, y, z+dz).
        Points are prioritized by lowest z (gravity/bottom-first), then lowest y, then lowest x.
        """
        raw_points = {(Decimal('0.00'), Decimal('0.00'), Decimal('0.00'))}

        for p in placed:
            raw_points.add((p.x + p.dx, p.y, p.z))
            raw_points.add((p.x, p.y + p.dy, p.z))
            raw_points.add((p.x, p.y, p.z + p.dz))
            # Also projection points along other placed items
            for other in placed:
                if other != p:
                    raw_points.add((p.x + p.dx, other.y + other.dy, p.z))
                    raw_points.add((other.x + other.dx, p.y + p.dy, p.z))

        valid_points = []
        for x, y, z in raw_points:
            if x >= box_l or y >= box_w or z >= box_h:
                continue

            # Ensure point does not sit strictly inside an existing placed item
            inside = False
            for p in placed:
                if (p.x <= x < p.x + p.dx) and (p.y <= y < p.y + p.dy) and (p.z <= z < p.z + p.dz):
                    inside = True
                    break

            if not inside:
                valid_points.append((x, y, z))

        # Sort candidate points: lowest Z, lowest Y, lowest X (dense bottom packing)
        valid_points.sort(key=lambda pt: (pt[2], pt[1], pt[0]))
        return valid_points
