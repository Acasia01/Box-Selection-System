# Design — Smart Shipping Box Recommendation System

## 1. Design Goals

The system should make box selection understandable, reliable, and fast for warehouse staff.

Design priorities:

- Correctness before AI convenience
- Recommendations supported by stored data and explicit rules
- Clear explanation of why a box qualifies or is rejected
- Low-cost packaging without compromising fit, weight, handling, or stock constraints
- A simple workflow that can be expanded in phases
- Usable on desktop warehouse workstations and, later, tablets

## 2. Users and Permissions

### Warehouse staff

- Look up an order.
- Request a box recommendation.
- Compare the recommended box with eligible alternatives.
- Read fit, weight, stock, and cost details.
- Request an authorized box assignment or reservation if their role permits it.

### Catalog or inventory manager

- Create and update product measurements.
- Maintain box specifications and cost.
- Update box quantities and reservations.
- Activate or deactivate products and box types.

### Administrator

- Manage users and permissions.
- Review recommendation and reservation history.
- Configure system rules and operational settings.

Permissions should be enforced on the server, not only by hiding frontend controls.

## 3. Primary User Journey

1. Staff member opens the packing page.
2. Staff enters an order number or asks the assistant to find a box for that order.
3. The server validates access and loads the order.
4. The packaging engine checks candidate boxes.
5. The page shows the best eligible box, its cost, available quantity, fit measurements, and packed-weight calculation.
6. Staff can inspect eligible alternatives and rejection reasons.
7. Staff explicitly confirms a reservation or assignment if needed.
8. The server rechecks stock and records the action.

A recommendation alone must not reserve inventory.

## 4. Main Screens

### 4.1 Packing / order lookup

Purpose: start a recommendation.

Elements:
- Order number input
- “Find box” action
- Order status and line-item summary after lookup
- Loading state while the recommendation is calculated
- Clear validation and not-found errors

Example order summary:

| SKU | Product | Quantity | Unit dimensions | Unit weight |
|---|---|---:|---|---:|
| SPK-101 | Wireless Speaker | 2 | 20 × 15 × 10 cm | 1.200 kg |

This is illustrative sample data, not a real order.

### 4.2 Recommendation result

Show the best eligible option prominently without obscuring alternatives.

Recommended result details:
- Box code and name
- Cost and currency
- Internal dimensions
- Total packed weight versus maximum allowed weight
- Available stock
- Fit status and orientations considered
- Short explanation of why it is the best-ranked eligible option

Example:

**Recommended box: BX-102 — Medium Shipping Box**

- Internal dimensions: 30 × 25 × 20 cm
- Maximum packed weight: 5.000 kg
- Empty box weight: 0.300 kg
- Cost: ₹18.00
- Available quantity: 88

These values are illustrative and should be populated from database records in the application.

### 4.3 Alternative boxes

Show up to three alternatives, but only if they pass every mandatory rule. Each alternative should show:
- Box code and name
- Cost
- Internal dimensions
- Packed weight / capacity
- Available quantity
- Brief reason it is ranked below the best choice

Do not show an ineligible box as an alternative. If useful, place rejected candidates in a separate expandable “Why other boxes were rejected” section.

### 4.4 No eligible box

When nothing qualifies, show a clear message such as:

> No available box satisfies the current fit, weight, handling, and inventory rules for this order.

Where possible, include actionable reasons:
- All active boxes are out of stock.
- The product does not fit any box with the configured clearance.
- Packed weight exceeds available box capacity.
- A handling restriction excludes otherwise suitable boxes.

Never silently select a box that violates a mandatory rule.

### 4.5 Catalog and inventory management

Initially, Django admin can provide CRUD screens for products, box types, and inventory. A custom interface can be added after the core recommendation logic is reliable.

Forms should:
- Display units next to every dimension and weight field.
- Validate positive dimensions and weights.
- Prevent negative costs and quantities.
- Distinguish quantity on hand, quantity reserved, and quantity available.
- Ask for confirmation before deactivating a product or box type that is referenced by existing records.

## 5. Recommendation Logic and Explainability

### Mandatory eligibility checks

A box is eligible only if all applicable checks pass:

1. Box type is active.
2. Available quantity is greater than zero.
3. Product or order contents fit within internal dimensions under at least one permitted orientation or valid multi-item arrangement.
4. Configured clearance is respected.
5. Total packed weight is within the maximum capacity.
6. All applicable handling and compatibility rules pass.

Available quantity is:

`quantity_available = quantity_on_hand - quantity_reserved`

Total packed weight should include:
- All product weights multiplied by quantities
- Protective materials, where configured
- Empty box weight

### Ranking

Rank eligible boxes by this lexicographic order:

1. Lowest cost
2. Lowest unused internal volume
3. Highest available quantity

Unused volume can be calculated as internal box volume minus the volume occupied by the packed items, but it is a secondary efficiency indicator, not proof of fit. Multi-item physical arrangement must be checked separately.

### Explanation example

> BX-102 is recommended because it passes the fit and weight checks, has stock available, and is the lowest-cost eligible box. Its estimated packed weight is 2.700 kg against a 5.000 kg limit.

The explanation must be generated from actual engine output. The UI should not calculate or invent eligibility independently.

## 6. AI Chat Interaction (Later Phase)

Example staff prompt:

> Which box should I use for order ORD-1001?

Planned interaction:

1. AI interprets the request as a box recommendation for an order identifier.
2. Django validates the identifier and permissions.
3. Django fetches authoritative order, product, box, and inventory data.
4. The deterministic engine computes eligibility and ranking.
5. The AI turns the structured result into a concise explanation.
6. The UI renders the result using the same result component as a non-chat request.

AI constraints:
- It cannot guess missing product measurements.
- It cannot override a failed fit or weight check.
- It cannot run arbitrary SQL or Python.
- It cannot reserve stock without an explicit, authorized confirmation.
- If required data is missing, it should ask for correction or report that a reliable recommendation cannot be made.

## 7. Visual Direction

Use a clean, operational dashboard rather than a marketing-style ecommerce storefront.

### Layout

- Left navigation: Packing, Orders, Products, Boxes & Inventory, Recommendation History
- Main content: order lookup and recommendation results
- Compact top bar: page title, signed-in user, and notifications
- Responsive single-column layout on narrow screens

### Visual hierarchy

- Primary heading: current task, such as “Find a shipping box”
- Secondary text: order number and item summary
- Primary result: recommended box
- Secondary area: alternatives and rejection reasons
- Persistent, clear action button for “Reserve box” only when authorized and available

### Color and status

- Neutral background and readable text
- One consistent primary action color
- Green for eligible/success states
- Amber for warnings or missing optional information
- Red for blocking failures, validation errors, or unavailable stock

Never rely on color alone; pair status colors with text and/or icons.

### Accessibility

- Use semantic HTML and properly associated form labels.
- Ensure keyboard navigation and visible focus states.
- Provide sufficient color contrast.
- Use readable font sizes and clear error messages.
- Announce asynchronous result updates to assistive technologies.
- Avoid status information conveyed only through icons or color.

## 8. Error and Edge-Case States

Design explicit handling for:
- Empty or malformed order number
- Order not found or inaccessible
- Order with no line items
- Product with missing or invalid dimensions
- Inactive product in an order
- No active boxes
- No available inventory
- No box satisfying fit or weight rules
- Database or service error
- AI timeout or malformed AI response
- Inventory changing between recommendation and reservation
- Duplicate reservation request

Errors should explain what the user can do next without exposing stack traces or secrets.

## 9. Reservation Confirmation

Before reservation, show:
- Order number
- Selected box
- Quantity to reserve
- Current available stock
- Any applicable warnings

After the user confirms, the backend must recheck and update inventory in a database transaction. If another request has consumed the stock, do not create the reservation; show an understandable “availability changed” message and allow a fresh recommendation.

## 10. Acceptance Criteria

The initial user-facing flow is ready when:

- Staff can request a recommendation for a valid order.
- The system only recommends boxes that pass all mandatory checks.
- The best eligible box is ranked by the documented criteria.
- Up to three eligible alternatives can be inspected.
- The UI shows dimensions, weights, cost, and stock with units.
- A no-fit outcome includes useful reasons.
- Recommendations do not reserve stock automatically.
- Reservation is permission-checked and concurrency-safe.
- Tests cover normal, invalid, no-stock, overweight, orientation, and multi-item cases.
