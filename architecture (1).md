# Architecture — Smart Shipping Box Recommendation System

## 1. Purpose

The Smart Shipping Box Recommendation System helps warehouse staff select a suitable shipping box for an ecommerce order. It uses verified product dimensions and weights, box specifications, packaging rules, and live box inventory to return a ranked recommendation.

**Primary goal:** recommend the lowest-cost eligible box without violating fit, weight, handling, or stock constraints.

## 2. Technology Stack

- **Backend:** Python, Django
- **Database:** PostgreSQL
- **Frontend (planned):** HTML, CSS, JavaScript
- **AI integration (planned):** OpenAI API, used for natural-language intent parsing and explanations
- **Packaging logic:** deterministic Python service, independent of the AI model
- **Initial interface:** Django admin and development tools; custom warehouse UI comes later

## 3. High-Level Architecture

```text
Warehouse Staff
      |
      v
Web UI (HTML / CSS / JavaScript)  [later phase]
      |
      v
Django Views / API
      |
      +-------------------------------+
      |                               |
      v                               v
Order & Product Services        Recommendation Service
      |                               |
      v                               v
PostgreSQL <------------------ Packaging Engine (Python)
      |                               |
      +------ Product / Order data     +-- Dimensions & orientations
      +------ Box specifications      +-- Clearance rules
      +------ Box inventory           +-- Packed-weight validation
      +------ Recommendation history  +-- Stock eligibility
                                      +-- Cost-based ranking
      |
      v
Verified recommendation returned to UI
```

When AI chat is introduced, it will sit at the request-interpretation layer. It will not replace the packaging engine or directly query the database.

## 4. Main Components

### 4.1 Django application

Django is responsible for HTTP handling, authentication and authorization, input validation, orchestration, persistence, and presenting results. Views or API endpoints call domain services rather than implementing packing rules inline.

### 4.2 `products` app

Stores the catalog facts required for packing:

- Unique SKU and product name
- Length, width, and height in centimetres
- Product weight in kilograms
- Additional clearance required on each side
- Fragile and active flags
- Created and updated timestamps

Product measurements are entered or imported from trusted catalog data. The system must not infer authoritative dimensions from an image or ask the language model to guess them.

### 4.3 `boxes` app

Stores shipping-box specifications and inventory:

- Unique box code and name
- Internal length, width, and height
- Maximum permitted total packed weight
- Empty box weight
- Cost and currency
- Active/inactive state
- Quantity on hand and quantity reserved

For the initial single-warehouse release, each box type has one inventory record. A multi-warehouse deployment can change this to inventory per warehouse.

### 4.4 Orders

Orders are a planned domain component. An order contains an order number, status, line items, quantities, and references to catalog products. Order data should be validated and stored in SQL before recommendations are generated. The first development stage may use manually entered or seeded sample orders.

Suggested future Django app: `orders`.

### 4.5 Packaging engine

A deterministic Python service receives validated order lines, product measurements, eligible box types, inventory, and packaging rules. It returns structured results with eligibility decisions and reasons.

The engine must not depend on OpenAI to decide whether an item physically fits.

### 4.6 AI request interpreter (planned)

The AI layer may translate a natural-language request such as “Which box should we use for order ORD-1001?” into a constrained action request. Django then:

1. Authenticates and authorizes the requester.
2. Validates the order identifier.
3. Loads order, product, box, and inventory records from PostgreSQL.
4. Calls the packaging engine.
5. Gives the verified result to the AI layer for a plain-language explanation.

The AI may explain verified results but must not invent measurements, prices, inventory, or eligibility. It must not execute arbitrary SQL, arbitrary Python, or unrestricted tools.

### 4.7 Recommendation and audit history (planned)

Store the inputs or versioned references used for a recommendation, eligible and rejected candidates, selected result, reasons, rule/algorithm version, requester, timestamp, and any later assignment or reservation action. Avoid storing unnecessary sensitive data.

## 5. Core Data Relationships

```text
Product 1 -------- * OrderLine * -------- 1 Order

BoxType 1 -------- 1 BoxInventory

Order 1 ---------- * RecommendationRun
RecommendationRun 1 -------- * RecommendationCandidate
```

`Order`, `OrderLine`, `RecommendationRun`, and `RecommendationCandidate` are planned models, not part of the initial product/box foundation unless implemented separately.

## 6. Recommendation Workflow

1. Receive an order identifier or validated order data.
2. Load the order and active catalog products.
3. Expand order lines by quantity for packing calculations.
4. Load active box types and current inventory.
5. Reject boxes that are inactive, out of stock, too small, too heavy, or incompatible with handling rules.
6. Test all allowed orientations for each item.
7. For multi-item orders, validate an actual arrangement; total volume alone is not sufficient proof that items fit.
8. Rank only eligible boxes by:
   1. Lowest box cost
   2. Least unused internal volume, as a secondary criterion
   3. Higher available stock, as a tertiary criterion
9. Return the best candidate and up to three eligible alternatives.
10. Persist the recommendation and its reasons for traceability.
11. Reserve or assign a box only after an explicit authorized action, rechecking stock atomically.

If no box qualifies, return “no eligible box” with clear rejection reasons rather than forcing a recommendation.

## 7. Packing Rules and Units

- Product dimensions and box internal dimensions use **centimetres**.
- Product, packaging-material, and box weights use **kilograms**.
- Cost is stored as a decimal amount with an explicit currency code.
- Box capacity is checked against total packed weight, including the empty box and any configured protective materials.
- Clearance is applied to the product dimensions according to a documented rule. The initial rule is additional clearance on every side, meaning the required dimension along each axis increases by twice the clearance value.
- Box internal dimensions must be used, not external dimensions.
- Fragile, liquid, hazardous, temperature-controlled, or other special handling restrictions must be represented as explicit rules before such products are supported.

## 8. Data Integrity and Concurrency

- Use database constraints for positive dimensions and weights, non-negative costs and clearance, and valid reservation quantities.
- Use Django validation for useful error messages; database constraints remain the final integrity guard.
- Use `transaction.atomic()` and row-level locking (for example, `select_for_update()`) when reserving stock.
- Recheck available inventory inside the same transaction that creates a reservation.
- Prevent duplicate order processing or reservations with appropriate unique constraints and idempotency rules.
- Keep API credentials and `SECRET_KEY` in environment variables; never commit `.env`.

## 9. Security

- Require authentication for warehouse operations.
- Apply role-based permissions for viewing recommendations, editing catalog data, and reserving/assigning boxes.
- Validate all user and AI-interpreted inputs on the server.
- Treat AI output and user-provided identifiers as untrusted.
- Use Django ORM or parameterized queries; do not execute AI-generated SQL.
- Keep OpenAI API keys server-side.
- Set `DEBUG=False` and configure production `ALLOWED_HOSTS`, HTTPS, secure cookies, backups, and logging before deployment.
- Avoid exposing customer details to the AI when order IDs and product facts are sufficient.

## 10. Testing Strategy

- **Model tests:** constraints, uniqueness, string representations, and inventory availability.
- **Unit tests:** dimension fit, orientations, clearance, weight, cost ranking, stock checks, and rejection reasons.
- **Multi-item tests:** arrangements that fit despite orientation changes and cases where volume is sufficient but no physical arrangement exists.
- **Integration tests:** Django database records flowing through the recommendation service.
- **Concurrency tests:** two requests attempting to reserve the last available box.
- **AI tests (later):** tool allowlisting, invalid order IDs, prompt injection resistance, and factual consistency with engine output.

## 11. Delivery Phases

1. **Foundation:** Django project, PostgreSQL connection, product and box/inventory models, admin, migrations, and model tests.
2. **Core rules:** packaging service and deterministic unit tests.
3. **Orders:** order and order-line models plus sample data.
4. **Recommendation workflow:** service orchestration, result persistence, and integration tests.
5. **Warehouse UI:** order lookup, recommendation details, alternatives, and clear no-fit reasons.
6. **AI chat:** constrained intent interpretation and verified-result explanations.
7. **Reservation and deployment:** transactional stock reservation, security hardening, monitoring, and deployment.

Do not start the next phase until the current phase's tests pass.
