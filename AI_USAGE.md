# AI Usage & Development Trajectory: BoxIQ

This document details the end-to-end AI-assisted pair-programming journey used to design, architect, implement, test, and refine **BoxIQ** (Smart Shipping Box Recommendation System).

---

## Table of Contents
1. [Overview & Collaboration Model](#overview--collaboration-model)
2. [Prompt History & Step-by-Step Trajectory](#prompt-history--step-by-step-trajectory)
   - [Phase 1: Architecture, Core Engine & Production Workflow](#phase-1-architecture-core-engine--production-workflow)
   - [Phase 2: Modular Page & CSS Separation](#phase-2-modular-page--css-separation)
   - [Phase 3: Interactive CRUD Modals (+ Add Box, + Add Order, Edit Rows)](#phase-3-interactive-crud-modals--add-box--add-order-edit-rows)
   - [Phase 4: Navigation Diagnostics & Sidebar Redirection Fix](#phase-4-navigation-diagnostics--sidebar-redirection-fix)
   - [Phase 5: Google Gemini Integration & Database Search Grounding](#phase-5-google-gemini-integration--database-search-grounding)
3. [Key Engineering Decisions & Guardrails](#key-engineering-decisions--guardrails)
4. [Prompt Injection Defenses & Security Policies](#prompt-injection-defenses--security-policies)
5. [Verification & Test Trajectory](#verification--test-trajectory)

---

## Overview & Collaboration Model

The development of BoxIQ was conducted through an iterative pair-programming workflow between the **User** and **Antigravity (Advanced AI Agent)**. 

### Core AI Design Mandates
1. **Mathematical Determinism over Generative AI**: Box fit calculations are strictly ruled by deterministic algorithms (3D Extreme Points + Backtracking), never by LLM approximations.
2. **Zero Hallucination Guarantee**: The AI assistant answers queries exclusively by executing verified, allowlisted domain tools against the relational database and packing engine.
3. **Atomic Concurrency**: Simultaneous box reservations utilize database-level row locks (`select_for_update()`) to prevent overselling.
4. **Test-Driven Rigor**: Every phase was anchored with automated unit, concurrency, security, and end-to-end integration tests (43 test cases total).

---

## Prompt History & Step-by-Step Trajectory

##CHATGPT Coversation history

https://chatgpt.com/share/6ad9e872-9cb8-83e8-a504-352deac81023

### Phase 1: Architecture, Core Engine & Production Workflow

#### User Request
> *"i want you to read the architecture.md , design.md and phases.md and execute the phases in parts and make the box selection method accordingly"*

#### AI Agent Actions & Deliverables
1. **Specification Analysis**:
   - Examined `architecture.md`, `design.md`, and `phases.md` to map out the required domain models, constraints, and algorithmic stages.
2. **Phase 1 (Data Models & Validation)**:
   - Created `products/models.py` (`Product` with dimensional validation, positive weight checks, clearance margins, and fragility flags).
   - Created `boxes/models.py` (`BoxType` with dimensions, tare weight, capacity, cost, and `BoxInventory` tracking on-hand, reserved, and available stock).
   - Written unit tests in `products/tests.py` and `boxes/tests.py`.
3. **Phase 2 (Deterministic 3D Packaging Engine)**:
   - Built `boxes/services/packing_engine.py` using an **Extreme Points Algorithm** with backtracking.
   - Tested all 6 orthogonal rotations for every product: `(L, W, H)`, `(L, H, W)`, `(W, L, H)`, `(W, H, L)`, `(H, L, W)`, `(H, W, L)`.
   - Built non-overlapping Axis-Aligned Bounding Box (AABB) collision detection.
   - Added `clearance` padding (0.5 cm minimum) around item boundaries.
   - Enforced maximum weight limits: `total_products_weight <= box.max_weight`.
   - Verified 3D coordinates `(x, y, z)` for item arrangement rendering.
   - Tested edge cases in `boxes/tests_packaging_engine.py` (single items, multi-items, oversized items, overweight items, rotational necessity).
4. **Phase 3 (Order Workflow & Multi-Candidate Ranking)**:
   - Created `orders/models.py` (`Order`, `OrderItem`, `RecommendationRun`, `RecommendationCandidate`).
   - Implemented `OrderRecommendationService` with strict ranking hierarchy:
     1. Lowest unit cost
     2. Least unused volume (tightest fit)
     3. Highest available warehouse inventory
   - Maintained immutable audit logs for every packaging recommendation run without automatically mutating inventory.
5. **Phase 4 (AI Assistant with Security Guardrails)**:
   - Implemented `AIAssistantService` with an explicit tool allowlist: `get_box_recommendation`, `lookup_order_details`, `check_box_inventory`.
   - Implemented regex-based SQL injection and system command blocks.
   - Tested injection defenses and intent recognition in `orders/tests_ai_assistant.py`.
6. **Phase 5 (Interactive Frontend with 3D Isometric Canvas)**:
   - Built an interactive warehouse dashboard with 3D isometric packing visualization, candidate comparison, rejection reason accordions, and AI chat.
7. **Phase 6 (Production Readiness & Concurrency)**:
   - Implemented atomic box reservations using `select_for_update()` inside `transaction.atomic()`.
   - Created multi-threaded race condition tests in `orders/tests_concurrency.py` (simulating concurrent operators competing for limited box stock).
   - Created end-to-end workflow tests in `orders/tests_e2e.py`.

---

### Phase 2: Modular Page & CSS Separation

#### User Request
> *"seperate the pages in templates:- make the folder of page and include the html file and css file of it into that foder like:- inside order/ folder there should be orders.html and order.css"*

#### AI Agent Actions & Deliverables
1. **Restructured Template & Static Hierarchy**:
   Separated the single monolithic template into modular, co-located directories:
   - `templates/base/base.html` & `base.css` (Base shell, typography, sidebar, top bar, modals, toast system).
   - `templates/workstation/workstation.html` & `workstation.css` (3D canvas packing workstation).
   - `templates/order/orders.html` & `order.css` (Orders catalog table, status badges, metrics).
   - `templates/boxes/boxes.html` & `boxes.css` (Box inventory grid, dimensions, stock levels).
   - `templates/history/history.html` & `history.css` (Audit logs, run inspections).
   - `templates/ai/ai.html` & `ai.css` (Conversational AI assistant interface).
2. **Updated Django URL Routing & Static Settings**:
   - Updated `config/urls.py` and `orders/views.py` with dedicated views for `/workstation/`, `/orders/`, `/boxes/`, `/history/`, `/ai/`.
   - Configured `STATICFILES_DIRS` in `config/settings.py` to seamlessly serve co-located CSS files.

---

### Phase 3: Interactive CRUD Modals (+ Add Box, + Add Order, Edit Rows)

#### User Request
> *"i want you to add the (add box and add orders) button near refresh inventory and refresh order also add a edit button at the end of the row in each table so that we can edit the dimensions and weight and cost etc things for ex:- if i click on edit button it will open a pop up page for me to edit the attributes and by saving it it will save the changes."*

#### AI Agent Actions & Deliverables
1. **Built REST API Endpoints**:
   - `POST /api/boxes/create/`: Registers a new `BoxType` and its `BoxInventory`.
   - `POST /api/boxes/<str:code>/update/`: Updates dimensions, capacity, unit cost, active state, and on-hand stock.
   - `POST /api/orders/create/`: Creates new orders with customer name and line items.
   - `POST /api/orders/<str:order_number>/update/`: Updates customer name, order status, or item quantities.
   - `GET /api/products/`: Supplies active product catalog to populate order item selection dropdowns.
2. **Designed Glassmorphic Modal Dialogs**:
   - **`#addOrderModal` & `#editOrderModal`**: Includes dynamic line-item builders (Product SKU dropdown, quantity controls, remove buttons).
   - **`#addBoxModal` & `#editBoxModal`**: Dimension controls (length, width, height), weight capacity, tare weight, cost, and stock on hand.
3. **Frontend Integration**:
   - Added "+ Add Order" and "+ Add Box" buttons alongside "Refresh" in the top action bars.
   - Added "✏️ Edit" action buttons to every table row that fetch current data, pre-populate modal fields, and save via AJAX with instant table updates and toast notifications.

---

### Phase 4: Navigation Diagnostics & Sidebar Redirection Fix

#### User Request
> *"in the sidebar in homepage when i am clicking the order catalog and boxes & inventory links it is not clickable and not redirecting to the pages"*

#### AI Agent Actions & Root Cause Analysis
1. **Diagnosis**:
   - Investigated `templates/warehouse/index.html` lines 23–53: Anchor elements had `data-tab="tab-orders"` but were missing `href` attributes (i.e. `<a class="nav-link" id="navOrders">`). In HTML, anchor tags lacking `href` are non-navigable placeholders.
   - In `static/js/workstation.js`, `initTabs()` previously called `e.preventDefault()` indiscriminately across all `.nav-link` elements.
2. **Remediation**:
   - Updated `templates/warehouse/index.html` and `templates/base/base.html` to include clean, explicit hyperlinks: `href="/workstation/"`, `href="/orders/"`, `href="/boxes/"`, `href="/history/"`, `href="/ai/"`.
   - Updated `static/js/workstation.js` to target only `.nav-link[data-tab]:not([href])`, ensuring standard page links navigate natively without JavaScript interference.
   - Verified cross-page navigation via browser automation tests.

---

### Phase 5: Google Gemini Integration & Database Search Grounding

#### User Request
> *"i want to integrate google gemini key for the ai chatbot in the system .. create a .env file and integrate the key with the ai page which search the database and answer accordingly"*

#### AI Agent Actions & Deliverables
1. **Environment Configuration**:
   - Created `.env` and `.env.example` defining `GEMINI_API_KEY`.
   - Updated `config/settings.py` to automatically load environment variables using `python-dotenv`.
2. **Google Gemini Database Tools (`orders/services/ai_assistant.py`)**:
   - Integrated the `google-genai` SDK with model `gemini-2.5-flash`.
   - Built 7 allowlisted database tools exposed as function declarations to Gemini:
     1. `get_box_recommendation(order_number)` (Invokes 3D packing engine)
     2. `lookup_order_details(order_number)` (Order items, status, quantities)
     3. `check_box_inventory(box_code)` (Real-time stock and box dimensions)
     4. `search_orders(query, status)` (Order search in database)
     5. `list_all_boxes()` (Warehouse shipping box catalog)
     6. `search_products(query)` (Product catalog search)
     7. `get_recent_history(limit)` (Audit log of past recommendations)
3. **Resilient Automatic Fallback**:
   - If `GEMINI_API_KEY` is not provided or offline, the system automatically falls back to the internal deterministic rule engine.
   - All 43 test suites execute and pass without requiring external API access or credentials.
4. **Enhanced AI Assistant UI (`templates/ai/ai.html` & `ai.css`)**:
   - Added live **Connection Status Pill** (`Google Gemini Active` vs `Deterministic Mode Active`).
   - Added database query suggestion chips for one-click prompts.
   - Added engine badges (`✨ Google Gemini` vs `⚙ Deterministic Rule Engine`) on assistant messages.
   - Added direct workstation action links to open recommended orders into the 3D packing visualizer.

---

## Key Engineering Decisions & Guardrails

| Challenge | Decision | Rationale |
|---|---|---|
| **Box Fit Verification** | Extreme Corner Points + Backtracking (Deterministic) | Total product volume does not guarantee physical fit. 3D spatial packing simulation is mandatory to eliminate packaging failures. |
| **LLM Reliability** | Tool-Assisted Function Calling with Grounded DB Tools | Language models must never guess dimensions or calculate box packing. All facts originate from database queries and algorithm outputs. |
| **Inventory Overselling** | Pessimistic Locking (`select_for_update()`) | Multiple operators processing the same popular box type simultaneously will block and release atomically, preventing negative stock. |
| **API Key Optionality** | Dual-Engine Fallback Architecture | Development, local evaluation, and CI pipelines run 100% locally on the deterministic engine without external API dependencies. |
| **Template Structure** | Co-Located Modular Components | Grouping each HTML template with its dedicated CSS prevents CSS bloat and enhances project maintainability. |

---

## Prompt Injection Defenses & Security Policies

To ensure safe deployment in warehouse environments:
- **Strict Allowlist**: Only 7 approved functions can be called. Tools like `execute_sql`, `run_python`, or `shell_command` do not exist.
- **Pattern Blacklisting**: Queries containing `select * from`, `drop table`, `exec(`, `system(`, `__import__`, or `eval(` are intercepted before execution with security alerts.
- **CSRF & Mutation Protection**: AI queries are strictly read-only; recommendation requests never automatically mutate inventory or reserve boxes without explicit operator authorization.

---

## Verification & Test Trajectory

The codebase is protected by **43 automated tests**:

```
Creating test database for alias 'default'...
...........................................
----------------------------------------------------------------------
Ran 43 tests in 0.579s

OK
Destroying test database for alias 'default'...
Found 43 test(s).
System check identified no issues (0 silenced).
```

### Coverage Distribution:
- **Unit Testing**: Products, Box types, Inventory validation, and Order models.
- **Packaging Math**: 6-axis orthogonal rotation, dimensional overflow, clearance buffers, weight bounds.
- **Concurrency**: Threaded race conditions testing atomic reservations and stock exhaustion.
- **Security & AI**: Allowlisted tool validation, injection attempts, and API key fallback logic.
- **End-to-End**: Order creation -> 3D packaging recommendation -> atomic stock reservation -> packed status.

---

*Authored collaboratively by the User & Antigravity AI Assistant.*
