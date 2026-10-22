# BoxIQ — AI-Assisted Smart Shipping Box Recommendation System

[![Python](https://img.shields.io/badge/Python-3.10+-3776AB?style=flat&logo=python&logoColor=white)](https://www.python.org/)
[![Django](https://img.shields.io/badge/Django-6.1-092E20?style=flat&logo=django&logoColor=white)](https://www.djangoproject.com/)
[![Google Gemini](https://img.shields.io/badge/Google%20Gemini-2.5%20Flash-4285F4?style=flat&logo=google&logoColor=white)](https://aistudio.google.com/)
[![Tests](https://img.shields.io/badge/Tests-43%20Passing-brightgreen?style=flat&logo=checkmarx&logoColor=white)](#testing)
[![Architecture](https://img.shields.io/badge/Packing%20Engine-Deterministic%203D-blueviolet?style=flat)](#deterministic-3d-packaging-engine)

**BoxIQ** is an industrial-grade warehouse packaging intelligence system. It deterministically computes physically verified 3D shipping box recommendations for multi-item ecommerce orders, eliminates dimensional weight penalties, prevents product damage, and integrates a conversational **Google Gemini AI Assistant** grounded strictly in live database records.

---

## Table of Contents
1. [Core Features](#core-features)
2. [Deterministic 3D Packaging Engine](#deterministic-3d-packaging-engine)
3. [System Architecture](#system-architecture)
4. [Google Gemini AI Integration](#google-gemini-ai-integration)
5. [User Interface & Page Directory](#user-interface--page-directory)
6. [Installation & Setup](#installation--setup)
7. [Environment Variables](#environment-variables)
8. [API Reference](#api-reference)
9. [Testing](#testing)
10. [AI Usage Documentation](#ai-usage-documentation)

---

## Core Features

- **Authoritative 3D Bin Packing**: Proves physical fit for multi-item orders using extreme corner points, 6-axis orthogonal rotations, and 0.5 cm clearance safety margins. Total product volume is never accepted as proof of fit.
- **Cost-Optimal Box Selection**: Ranks eligible shipping boxes strictly by:
  1. **Lowest unit cost**
  2. **Least unused volume**
  3. **Highest available warehouse stock**
- **Concurrency-Safe Atomic Reservations**: Uses PostgreSQL/SQLite row-level locks (`select_for_update()`) inside `transaction.atomic()` to prevent inventory overselling during simultaneous operator checkouts.
- **Google Gemini 2.5 Flash Assistant**: Natural language warehouse queries powered by the `google-genai` SDK with real-time database tools. Answers questions strictly grounded on live database records.
- **Interactive 3D Packing Visualization**: Real-time HTML5 Canvas rendering of the packed box and color-coded items with spatial placement coordinates `(x, y, z)` and dimensions.
- **Independent Page Workspaces**: Dedicated template modules for Workstation, Orders Catalog, Boxes & Inventory, Audit History, and AI Assistant with embedded AJAX modals to add and edit entities.

---

## Deterministic 3D Packaging Engine

The packaging engine (`boxes/services/packing_engine.py`) enforces strict physics and safety guarantees:

```
Order Line Items
      │
      ▼
Sort Items by Volume (Largest First)
      │
      ▼
For Each Active Candidate Box in Warehouse:
      ├── 1. Max Weight Limit Check (Products Weight + Tare Weight <= Box Max Weight)
      ├── 2. Inventory Availability Check (quantity_available > 0)
      ├── 3. 3D Spatial Packing Simulation:
      │         ├── Backtracking Extreme Points (x, y, z)
      │         ├── 6 Orthogonal Rotations per item (L, W, H)
      │         ├── Non-Overlap Collision Check (AABB)
      │         ├── Clearance Margin Buffer (0.5 cm padding)
      │         └── Box Boundary Containment Check
      │
      ▼
Rank Valid Candidates: (Cost ASC, Unused Volume ASC, Available Stock DESC)
      │
      ▼
Optimal Recommended Box + 3D Coordinates + Rejection Reasons for Failures
```

### Constraints Enforced:
- **Rotational Degrees of Freedom**: Tests all 6 orientations `(L, W, H)`, `(L, H, W)`, `(W, L, H)`, `(W, H, L)`, `(H, L, W)`, `(H, W, L)`.
- **Clearance Buffering**: Each item boundary is padded with `clearance` (minimum 0.5 cm) to ensure real-world packaging material fit.
- **No Weight Exceedance**: Verifies `total_products_weight <= box.max_weight`.
- **Zero Hallucination**: Recommendation generation never mutates database inventory or reserves stock automatically.

---

## System Architecture

```
┌────────────────────────────────────────────────────────────────────────┐
│                        BoxIQ Web Application                           │
├───────────────────┬───────────────────┬────────────────────────────────┤
│ Packing Station   │ Orders Catalog    │ Boxes & Inventory              │
│ (/workstation/)   │ (/orders/)        │ (/boxes/)                      │
├───────────────────┴───────────────────┴────────────────────────────────┤
│                      AI Assistant (/ai/)                               │
│           Google Gemini 2.5 Flash + Database Tool Calling              │
└───────────────────────────────────┬────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                     Domain Services & Workflows                        │
├───────────────────────────────────┬────────────────────────────────────┤
│ OrderRecommendationService        │ PackagingEngine (Deterministic 3D) │
│ - Validation & State Transitions  │ - Extreme Points Algorithm         │
│ - Concurrency Atomic Reservations │ - 6-Rotation Collision Checking   │
│ - Multi-Candidate Ranking         │ - 3D Coordinates (X, Y, Z)         │
└───────────────────────────────────┴────────────────────────────────────┘
                                    │
                                    ▼
┌────────────────────────────────────────────────────────────────────────┐
│                        Relational Database                             │
│  - Product (SKU, dimensions, weight, clearance, is_fragile)            │
│  - BoxType (code, dimensions, volume, max_weight, empty_weight, cost)  │
│  - BoxInventory (quantity_on_hand, quantity_reserved, available)       │
│  - Order & OrderItem (order_number, items, quantities, assigned_box)   │
│  - RecommendationRun & RecommendationCandidate (audit logs)            │
└────────────────────────────────────────────────────────────────────────┘
```

---

## Google Gemini AI Integration

The system incorporates **Google Gemini** (`gemini-2.5-flash`) via the official `google-genai` SDK with real-time tool calling.

### Allowlisted Database Tools
To prevent SQL injection and AI hallucination, Gemini is restricted to an explicit allowlist of domain tools:

| Tool Name | Purpose | Data Source |
|---|---|---|
| `get_box_recommendation` | Computes optimal box via 3D packing engine | `OrderRecommendationService` + `PackagingEngine` |
| `lookup_order_details` | Retrieves order items, customer, weights, status | `Order` & `OrderItem` tables |
| `check_box_inventory` | Live inventory stock, dimensions, and limits | `BoxType` & `BoxInventory` tables |
| `search_orders` | Searches orders by number, customer, or status | `Order` table (Q filter) |
| `list_all_boxes` | Lists all active shipping boxes in catalog | `BoxType` table |
| `search_products` | Searches product catalog by SKU or name | `Product` table |
| `get_recent_history` | Audit log of past packaging runs | `RecommendationRun` table |

### Automatic Fallback Architecture
- If `GEMINI_API_KEY` is present in `.env`, the assistant leverages Gemini's conversational intelligence.
- If `GEMINI_API_KEY` is omitted, placeholder, or offline, the system **automatically falls back to its internal deterministic rule engine**. All 43 test suites and local environments run without requiring an external API key.

---

## User Interface & Page Directory

Templates are separated into independent, co-located modular directories:

```
templates/
├── base/
│   ├── base.html          # Shell layout, persistent navigation, modals, toasts
│   └── base.css           # Global design system, glassmorphism, dark palette
├── workstation/
│   ├── workstation.html   # 3D isometric packing canvas, candidate comparison
│   └── workstation.css    # Workstation layout, canvas styling
├── order/
│   ├── orders.html        # Orders table, metrics, + Add Order modal, Edit modal
│   └── order.css          # Orders catalog styles
├── boxes/
│   ├── boxes.html         # Box catalog table, + Add Box modal, Edit modal
│   └── boxes.css          # Boxes & inventory styles
├── history/
│   ├── history.html       # Packaging recommendation audit history
│   └── history.css        # Audit table & candidate inspection styles
└── ai/
    ├── ai.html            # AI chat interface, Gemini status indicator
    └── ai.css             # Chat bubbles, tool execution badges, pills
```

---

## Installation & Setup

### Prerequisites
- Python 3.10, 3.11, 3.12, 3.13, or 3.14
- Git

### 1. Clone & Enter Project
```bash
git clone <repository-url>
cd "AI-Assisted Box Selection System"
```

### 2. Create and Activate Virtual Environment
```bash
# Windows
python -m venv venv
.\venv\Scripts\activate

# Linux / macOS
python3 -m venv venv
source venv/bin/activate
```

### 3. Install Dependencies
```bash
pip install -r requirements.txt
```

### 4. Configure Environment Variables
Copy the sample environment file to `.env`:
```bash
# Windows PowerShell
Copy-Item .env.example .env

# Linux / macOS
cp .env.example .env
```

Edit `.env` and add your **Google Gemini API Key** (optional, for conversational AI):
```env
GEMINI_API_KEY=AIzaSy...your_actual_key_here
SECRET_KEY=django-insecure-your-secret-key
DEBUG=True
```

### 5. Apply Database Migrations
```bash
python manage.py migrate
```

### 6. Run the Development Server
```bash
python manage.py runserver
```

Open your browser at `http://127.0.0.1:8000/`.

---

## Environment Variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `GEMINI_API_KEY` | Optional | `""` | Google Gemini API key from [Google AI Studio](https://aistudio.google.com/) |
| `GEMINI_MODEL` | Optional | `gemini-2.5-flash` | Gemini model name |
| `SECRET_KEY` | Optional | Development key | Django secret key |
| `DEBUG` | Optional | `True` | Django debug mode |

---

## API Reference

### 1. Recommendations & Workflow
- `GET /api/recommendation/<order_number>/`  
  Computes verified 3D box recommendation, alternative options, coordinate mapping, and rejection reasons.
- `POST /api/reserve/`  
  Atomically reserves and assigns a box to an order.  
  **Payload**: `{"order_number": "ORD-1001", "box_code": "BX-102"}`

### 2. Orders Management
- `GET /api/orders/` — Lists all orders with summary metrics and line items.
- `POST /api/orders/create/` — Creates a new order with line items.
- `POST /api/orders/<order_number>/update/` — Modifies order customer name, status, or item quantities.

### 3. Boxes & Inventory Management
- `GET /api/boxes/` — Lists all box specifications and live stock counts.
- `POST /api/boxes/create/` — Registers a new shipping box type with inventory.
- `POST /api/boxes/<code>/update/` — Updates box dimensions, weight capacity, unit cost, or stock.

### 4. Products & Catalog
- `GET /api/products/` — Lists all products with dimensions, weights, and fragility flags.

### 5. AI Chatbot
- `POST /api/chat/`  
  Natural-language query endpoint invoking Google Gemini and safe database tools.  
  **Payload**: `{"message": "Which box should I use for order ORD-1001?"}`  
  **Response**:
  ```json
  {
    "reply": "For order ORD-1001, the verified recommendation is BX-102 at INR 18.00...",
    "tool_calls": [{"tool": "get_box_recommendation", "status": "success"}],
    "verified_result": { "order_number": "ORD-1001", "recommendation": { ... } },
    "is_gemini_powered": true,
    "model": "gemini-2.5-flash"
  }
  ```

### 6. Audit History
- `GET /api/history/` — Returns the latest 30 recommendation runs with candidate evaluation logs.

---

## Testing

BoxIQ features an automated test suite comprising **43 unit, concurrency, security, and end-to-end integration tests**:

```bash
python manage.py test
```

### Test Suite Breakdown:
- **`boxes/tests_packaging_engine.py`**: Validates 3D physical placement, 6-rotation checking, non-overlap collisions, clearance margins, and max weight rejection.
- **`orders/tests.py`**: Validates recommendation ranking (cost, volume, stock), order validation, and candidate logging.
- **`orders/tests_concurrency.py`**: Validates multi-threaded race conditions, row-level locks (`select_for_update()`), and stock exhaustion safety.
- **`orders/tests_ai_assistant.py`**: Validates tool allowlisting, natural language intent recognition, SQL injection defenses, and Gemini key initialization/fallback.
- **`orders/tests_e2e.py`**: Validates the end-to-end order packaging lifecycle: creation -> 3D recommendation -> atomic reservation -> packed state.
- **`products/tests.py`**: Validates dimensional integrity, positive weight enforcement, and SKU constraints.

---

## AI Usage Documentation

For complete, transparent documentation of the prompts, architectural decisions, and agent workflows used to build this system from specification to production, see [AI_USAGE.md](AI_USAGE.md).
