# Development Phases — Smart Shipping Box Recommendation System

## Purpose

This document defines the implementation sequence for the Smart Shipping Box Recommendation System. Build and test one phase at a time. **Do not proceed to the next phase until the current phase's acceptance criteria pass.**

The complete system architecture is documented in [`architecture.md`](architecture.md), and user-facing behavior and interface guidance are documented in [`design.md`](design.md).

## Phase 1: Django Foundation

**Status:** Start here

### Goals
Establish the Django project, connect PostgreSQL, and create the core product and box/inventory data models.

### Tasks
- Set up the Python virtual environment and Django project.
- Configure environment variables and connect Django to PostgreSQL.
- Create the `products` and `boxes` apps.
- Implement product, box type, and box inventory models.
- Add database constraints and Django Admin registrations.
- Run migrations.
- Add representative sample data through Django Admin.
- Write and run model tests.

### Acceptance criteria
- `python manage.py check` passes.
- Migrations apply successfully against PostgreSQL.
- Product, box, and inventory records can be created and viewed in Django Admin.
- Inventory availability is calculated correctly.
- Model tests pass.

### Out of scope
Do not implement the packaging algorithm, order workflow, AI, or custom frontend in this phase.

---

## Phase 2: Packaging Engine

### Goals
Implement a deterministic, testable Python service that identifies eligible boxes and ranks them.

### Tasks
- Implement orientation checks across all permitted rotations.
- Apply the configured clearance rule to product dimensions.
- Validate total packed weight, including product weights, protective materials where configured, and empty box weight.
- Exclude inactive boxes and boxes with no available inventory.
- Validate handling and compatibility rules that are supported by the product data.
- For multi-item orders, validate a physically possible arrangement; do not rely on volume alone.
- Rank eligible boxes using this order:
  1. Lowest cost
  2. Least unused internal volume
  3. Highest available stock
- Return the best eligible box and up to three eligible alternatives.
- Return clear rejection reasons when no box qualifies.
- Write unit tests before proceeding.

### Acceptance criteria
- Tests cover orientation, clearance, weight limits, inactive boxes, stock availability, ranking, and no-fit cases.
- Multi-item tests prove that a valid physical arrangement exists rather than merely comparing total volume.
- The engine never recommends an ineligible box.
- All packaging-engine tests pass.

---

## Phase 3: Order Workflow

### Goals
Connect stored orders to the packaging engine and persist recommendation outcomes.

### Tasks
- Create order and order-item models.
- Link order items to catalog products and store quantities.
- Validate order identifiers and order status before recommendation.
- Retrieve authoritative order, product, box, and inventory data from PostgreSQL.
- Pass validated data to the packaging engine.
- Return the best recommendation, eligible alternatives, and rejection reasons.
- Record recommendation runs and candidate results for traceability.
- Record assignments separately from recommendations.

### Acceptance criteria
- A valid order produces a recommendation based on database records.
- Missing, invalid, inaccessible, or empty orders are handled clearly.
- Recommendation history records the relevant result and rule/algorithm version.
- A recommendation does not reserve inventory automatically.
- Workflow integration tests pass.

---

## Phase 4: AI API

### Goals
Add natural-language interaction without allowing AI output to replace deterministic packaging rules.

### Tasks
- Configure the chosen AI provider's API key in server-side environment variables.
- Define a small allowlist of approved tools, such as looking up an authorized order and requesting a box recommendation.
- Implement a Django chat endpoint with input validation and controlled tool orchestration.
- Authenticate and authorize the requester before accessing order data.
- Use the order workflow and packaging engine as the source of truth.
- Let the AI explain verified results in plain language.
- Handle provider timeouts, invalid responses, and tool errors safely.
- Test tool calls with mocked AI-provider responses.

### Safety constraints
- Never execute arbitrary AI-generated SQL or Python.
- Never trust model-generated dimensions, prices, inventory counts, or fit decisions.
- Never reserve or assign a box merely because the model suggested it.
- Require explicit authorization and confirmation for any consequential action.

### Acceptance criteria
- Mocked tests verify valid tool calls, invalid inputs, tool errors, and malformed provider responses.
- The AI can only invoke approved tools.
- Explanations remain consistent with the verified engine result.
- API credentials are not exposed to the browser or committed to version control.

---

## Phase 5: Frontend

### Goals
Build a clear warehouse interface for order lookup and box recommendations.

### Tasks
- Build the warehouse dashboard using HTML, CSS, and JavaScript.
- Add order lookup and an order-item summary.
- Add interactive chat for natural-language requests.
- Display the recommended box and its dimensions, cost, packed weight, capacity, and available stock.
- Display up to three eligible alternative boxes.
- Show clear no-fit results and useful rejection reasons.
- Add loading, empty, validation-error, and server-error states.
- Ensure the interface is responsive and accessible.
- Keep all authorization and business-rule enforcement on the server.

### Acceptance criteria
- Staff can look up an order and inspect the verified recommendation.
- Alternative cards contain only eligible boxes.
- Units and status labels are clear and consistent.
- Keyboard navigation, focus states, form labels, and readable error messages are provided.
- Frontend integration tests or documented manual checks pass.

---

## Phase 6: Production Readiness

### Goals
Harden the application for reliable multi-user use and deployment.

### Tasks
- Add authentication and role-based permissions.
- Enforce permissions for catalog changes, inventory changes, recommendations, and assignments.
- Implement concurrency-safe inventory reservations using database transactions and row-level locking where supported.
- Recheck available inventory inside the reservation transaction.
- Prevent duplicate reservations with suitable uniqueness and idempotency rules.
- Add structured logging, operational error handling, and useful API error responses.
- Add end-to-end tests for the principal warehouse workflow.
- Configure production settings, HTTPS, secure cookies, secrets, database backups, and monitoring.
- Review data minimization and AI-provider data handling before production use.

### Acceptance criteria
- Unauthorized users cannot access protected operations.
- Concurrent attempts to reserve the last available box cannot over-reserve inventory.
- Failures are logged without exposing secrets or sensitive data to users.
- End-to-end tests cover order lookup, recommendation, and authorized reservation.
- Production configuration is reviewed before deployment.

---

## Cross-Phase Rules

- Use PostgreSQL as the authoritative database.
- Use centimetres for dimensions, kilograms for weight, and explicit currency codes for costs.
- Keep packing decisions in deterministic Python code.
- Treat user input and AI output as untrusted until validated by the server.
- Do not show an ineligible box as a recommendation or alternative.
- Do not reserve inventory during recommendation generation.
- Keep tests close to the feature being implemented.
- Record important assumptions and update `architecture.md` and `design.md` if system decisions change.
- At the end of each phase, run its relevant tests and review failures before continuing.
