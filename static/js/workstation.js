/**
 * BoxIQ — Modern Warehouse Workstation Client Controller
 * Handles 3D isometric box packing visualization, order recommendations,
 * atomic reservations, and AI chat assistant.
 */

// Application State
const state = {
  currentOrder: null,
  currentRecommendation: null,
  activeTab: 'tab-workstation',
  allOrders: [],
  allBoxes: [],
};

// Item Color Palette for 3D Projection
const PALETTE = [
  '#0EA5E9', '#F59E0B', '#10B981', '#8B5CF6', '#EC4899', '#06B6D4', '#F97316'
];

document.addEventListener('DOMContentLoaded', () => {
  initTabs();
  initCanvas();
  // Auto-load default initial order
  window.loadOrder('ORD-1001');
});

// Tab Navigation (only for in-page tabs without dedicated URLs)
function initTabs() {
  const navTabs = document.querySelectorAll('.nav-link[data-tab]:not([href])');
  navTabs.forEach(link => {
    link.addEventListener('click', (e) => {
      const tabId = link.getAttribute('data-tab');
      if (tabId && document.getElementById(tabId)) {
        e.preventDefault();
        switchTab(tabId);
      }
    });
  });
}

function switchTab(tabId) {
  state.activeTab = tabId;
  document.querySelectorAll('.nav-link').forEach(l => l.classList.remove('active'));
  document.querySelectorAll('.tab-content').forEach(c => c.classList.remove('active'));

  const activeLink = document.querySelector(`.nav-link[data-tab="${tabId}"]`);
  const activeContent = document.getElementById(tabId);
  if (activeLink) activeLink.classList.add('active');
  if (activeContent) activeContent.classList.add('active');

  // Trigger data fetches on tab activations
  if (tabId === 'tab-orders') window.fetchOrdersList();
  if (tabId === 'tab-boxes') window.fetchBoxesList();
  if (tabId === 'tab-history') window.fetchHistoryList();
}

// Order Search & Loading
window.handleOrderSearch = function() {
  const input = document.getElementById('orderInput');
  const val = input.value.trim();
  if (val) {
    window.loadOrder(val);
  }
};

window.loadOrder = async function(orderNumber) {
  // If not on workstation tab, switch to it
  if (state.activeTab !== 'tab-workstation') {
    switchTab('tab-workstation');
  }

  const orderInput = document.getElementById('orderInput');
  orderInput.value = orderNumber;

  const loading = document.getElementById('loadingIndicator');
  const workstationContent = document.getElementById('workstationContent');
  const noFitBanner = document.getElementById('noFitBanner');

  loading.style.display = 'block';
  workstationContent.style.opacity = '0.3';
  noFitBanner.style.display = 'none';

  try {
    const res = await fetch(`/api/recommendation/${encodeURIComponent(orderNumber)}/`);
    const data = await res.json();

    loading.style.display = 'none';
    workstationContent.style.opacity = '1';

    if (!res.ok || !data.success) {
      handleOrderError(data.error || 'Failed to load recommendation for this order.');
      return;
    }

    state.currentOrder = data.order;
    state.currentRecommendation = data.recommendation;

    renderWorkstation(data);
  } catch (err) {
    loading.style.display = 'none';
    workstationContent.style.opacity = '1';
    handleOrderError('Network error connecting to backend service.');
  }
};

function handleOrderError(errorMessage) {
  showToast(errorMessage, 'error');
  const noFitBanner = document.getElementById('noFitBanner');
  const noFitReasonsText = document.getElementById('noFitReasonsText');
  noFitBanner.style.display = 'block';
  noFitReasonsText.innerText = errorMessage;

  // Clear recommended box card
  document.getElementById('recommendedBoxCard').style.display = 'none';
  document.getElementById('alternativesCard').style.display = 'none';
}

// Render Order and Recommendation Data
function renderWorkstation(data) {
  const { order, recommendation } = data;

  // 1. Order Summary
  document.getElementById('currentOrderNumber').innerText = order.order_number;
  document.getElementById('orderCustomerName').innerText = order.customer_name || 'Warehouse Order';
  document.getElementById('orderTotalQty').innerText = `${order.total_items_count} units`;
  document.getElementById('orderNetWeight').innerText = `${order.total_weight.toFixed(3)} kg`;

  const statusBadge = document.getElementById('orderStatusBadge');
  if (order.is_assigned) {
    statusBadge.className = 'badge badge-assigned';
    statusBadge.innerText = `Assigned (${order.assigned_box})`;
  } else {
    statusBadge.className = 'badge badge-pending';
    statusBadge.innerText = order.status === 'PENDING' ? 'Pending Packing' : order.status;
  }

  // 2. Line Items Table
  const tbody = document.getElementById('lineItemsTableBody');
  tbody.innerHTML = '';
  order.items.forEach((item, idx) => {
    const tr = document.createElement('tr');
    const color = PALETTE[idx % PALETTE.length];
    tr.innerHTML = `
      <td>
        <div style="display: flex; align-items: center; gap: 8px;">
          <span style="width: 10px; height: 10px; border-radius: 50%; background: ${color};"></span>
          <div>
            <div style="font-weight: 600; color: #FFFFFF;">${item.name}</div>
            <div class="sku-text">${item.sku} ${item.is_fragile ? '<span class="badge badge-fragile" style="font-size: 0.65rem;">FRAGILE</span>' : ''}</div>
          </div>
        </div>
      </td>
      <td>${item.length} × ${item.width} × ${item.height}</td>
      <td>${item.weight.toFixed(3)} kg</td>
      <td>+${item.clearance.toFixed(2)} cm</td>
      <td><strong style="color: #FFFFFF;">${item.quantity}</strong></td>
    `;
    tbody.appendChild(tr);
  });

  // 3. Recommended Box (Hero)
  const heroCard = document.getElementById('recommendedBoxCard');
  const altCard = document.getElementById('alternativesCard');
  const noFitBanner = document.getElementById('noFitBanner');

  if (recommendation.is_successful && recommendation.best_box) {
    heroCard.style.display = 'block';
    noFitBanner.style.display = 'none';

    const b = recommendation.best_box;
    document.getElementById('recBoxCode').innerText = b.code;
    document.getElementById('recBoxName').innerText = b.name;
    document.getElementById('recBoxPrice').innerText = `${b.currency} ${b.cost.toFixed(2)}`;

    document.getElementById('recBoxDims').innerText = `${b.dimensions.length} × ${b.dimensions.width} × ${b.dimensions.height} cm`;
    document.getElementById('recBoxVol').innerText = `Volume: ${b.internal_volume.toLocaleString()} cm³`;

    document.getElementById('recBoxWeight').innerText = `${b.total_packed_weight.toFixed(3)} kg`;
    document.getElementById('recBoxMaxWeight').innerText = `Max Capacity: ${b.max_weight.toFixed(3)} kg`;

    const weightPercent = Math.min(100, (b.total_packed_weight / b.max_weight) * 100);
    document.getElementById('weightProgressFill').style.width = `${weightPercent.toFixed(1)}%`;

    const usedVol = b.internal_volume - b.unused_volume;
    const volPercent = Math.min(100, (usedVol / b.internal_volume) * 100);
    document.getElementById('recVolumePercent').innerText = `${volPercent.toFixed(1)}% Used`;
    document.getElementById('recUnusedVol').innerText = `Unused: ${b.unused_volume.toLocaleString()} cm³`;
    document.getElementById('volProgressFill').style.width = `${volPercent.toFixed(1)}%`;

    document.getElementById('recStockAvailable').innerText = `${b.quantity_available} Available`;
    document.getElementById('recStockBreakdown').innerText = `In stock and ready for immediate packing`;

    document.getElementById('recExplanationText').innerText = b.explanation;

    // Reserve Button state
    const resBtn = document.getElementById('reserveBoxActionBtn');
    if (order.is_assigned) {
      resBtn.disabled = true;
      resBtn.innerHTML = `<span>✓ Already Assigned to Box ${order.assigned_box}</span>`;
      resBtn.style.background = 'rgba(255, 255, 255, 0.1)';
    } else {
      resBtn.disabled = false;
      resBtn.innerHTML = `<span>🔒 Reserve Box ${b.code} & Assign to Order</span>`;
      resBtn.style.background = 'linear-gradient(135deg, #10B981, #059669)';
    }

    // 4. Render 3D Box Placement
    render3DPlacements(b);

    // 5. Alternatives
    const alts = recommendation.alternatives || [];
    const altList = document.getElementById('alternativesList');
    altList.innerHTML = '';
    document.getElementById('altCountBadge').innerText = `${alts.length} Options`;

    if (alts.length > 0) {
      altCard.style.display = 'block';
      alts.forEach(alt => {
        const itemDiv = document.createElement('div');
        itemDiv.className = 'alt-card';
        itemDiv.innerHTML = `
          <div>
            <div style="display: flex; align-items: center; gap: 8px;">
              <span class="alt-rank">Rank #${alt.rank}</span>
              <span class="alt-code">${alt.code}</span>
              <span style="color: var(--text-muted); font-size: 0.85rem;">— ${alt.name}</span>
            </div>
            <div class="alt-info" style="margin-top: 4px;">
              ${alt.dimensions.length}×${alt.dimensions.width}×${alt.dimensions.height} cm • Packed: ${alt.total_packed_weight.toFixed(3)} kg • Unused Vol: ${alt.unused_volume.toLocaleString()} cm³
            </div>
            <div style="font-size: 0.75rem; color: var(--text-muted); margin-top: 2px;">
              ${alt.explanation}
            </div>
          </div>
          <div style="text-align: right;">
            <div style="font-weight: 800; font-size: 1.15rem; color: #FFFFFF;">${alt.currency} ${alt.cost.toFixed(2)}</div>
            <div style="font-size: 0.75rem; color: var(--emerald);">${alt.quantity_available} in stock</div>
          </div>
        `;
        altList.appendChild(itemDiv);
      });
    } else {
      altCard.style.display = 'none';
    }
  } else {
    // No eligible box found
    heroCard.style.display = 'none';
    altCard.style.display = 'none';
    noFitBanner.style.display = 'block';
    const reasons = recommendation.rejected_boxes.flatMap(b => b.rejection_reasons);
    document.getElementById('noFitReasonsText').innerText = reasons.length > 0
      ? `Reasons: ${Array.from(new Set(reasons)).join('; ')}`
      : 'All candidate boxes out of stock or too small.';
    clearCanvas();
  }

  // 6. Rejected Boxes Breakdown
  const rejected = recommendation.rejected_boxes || [];
  document.getElementById('rejectedCountTag').innerText = rejected.length;
  const rejectedBody = document.getElementById('rejectedAccordionBody');
  rejectedBody.innerHTML = '';
  rejected.forEach(b => {
    const div = document.createElement('div');
    div.className = 'rejected-item';
    div.innerHTML = `
      <div class="rejected-box-title">${b.code} — ${b.name} (${b.dimensions.length}×${b.dimensions.width}×${b.dimensions.height} cm)</div>
      <div class="rejected-reason">✗ ${b.rejection_reasons.join(' • ')}</div>
    `;
    rejectedBody.appendChild(div);
  });
}

// 3D Canvas Isometric Wireframe Packing Renderer
let canvas, ctx;
function initCanvas() {
  canvas = document.getElementById('packingCanvas');
  if (canvas) {
    ctx = canvas.getContext('2d');
  }
}

function clearCanvas() {
  if (!ctx || !canvas) return;
  ctx.clearRect(0, 0, canvas.width, canvas.height);
}

function render3DPlacements(box) {
  if (!ctx || !canvas) return;
  clearCanvas();

  const w = canvas.width;
  const h = canvas.height;

  // Box dimensions
  const BL = box.dimensions.length;
  const BW = box.dimensions.width;
  const BH = box.dimensions.height;

  document.getElementById('boxInternalDimTag').innerText = `Box: ${BL} × ${BW} × ${BH} cm (Internal)`;

  // Scale factor to fit inside canvas with padding
  const maxDim = Math.max(BL, BW, BH);
  const scale = 140 / maxDim;

  // Isometric projection origin (center bottom)
  const originX = w / 2 - 20;
  const originY = h / 2 + 50;

  // Isometric projection transform
  // Iso angles: X axis at 30 deg, Y axis at -30 deg, Z axis straight up
  const cos30 = Math.cos(Math.PI / 6);
  const sin30 = Math.sin(Math.PI / 6);

  function project(x, y, z) {
    const px = originX + (x - y) * cos30 * scale;
    const py = originY - z * scale + (x + y) * sin30 * scale * 0.6;
    return { x: px, y: py };
  }

  // Draw Box Wireframe (transparent interior, dashed boundary)
  ctx.save();
  ctx.strokeStyle = 'rgba(14, 165, 233, 0.4)';
  ctx.lineWidth = 1.5;
  ctx.setLineDash([4, 4]);

  // 8 vertices of the box
  const p000 = project(0, 0, 0);
  const pL00 = project(BL, 0, 0);
  const p0W0 = project(0, BW, 0);
  const pLW0 = project(BL, BW, 0);
  const p00H = project(0, 0, BH);
  const pL0H = project(BL, 0, BH);
  const p0WH = project(0, BW, BH);
  const pLWH = project(BL, BW, BH);

  // Bottom face
  drawPoly([p000, pL00, pLW0, p0W0], 'rgba(14, 165, 233, 0.05)', true);
  // Back walls
  drawPoly([p000, p00H, p0WH, p0W0], 'rgba(14, 165, 233, 0.03)', true);
  drawPoly([p000, pL00, pL0H, p00H], 'rgba(14, 165, 233, 0.03)', true);

  // Draw Placed Items (Sorted from back to front for proper occlusion)
  const placements = box.placements || [];
  const sortedPlacements = [...placements].sort((a, b) => (a.x + a.y + a.z) - (b.x + b.y + b.z));

  const legendContainer = document.getElementById('canvasLegend');
  legendContainer.innerHTML = '';
  const seenSkus = new Set();

  sortedPlacements.forEach((item, idx) => {
    const color = PALETTE[idx % PALETTE.length];
    drawCuboid(item.x, item.y, item.z, item.dx, item.dy, item.dz, color, project);

    if (!seenSkus.has(item.sku)) {
      seenSkus.add(item.sku);
      const leg = document.createElement('div');
      leg.className = 'legend-item';
      leg.innerHTML = `
        <span class="legend-color" style="background: ${color};"></span>
        <span>${item.sku} (${item.dx}×${item.dy}×${item.dz} cm)</span>
      `;
      legendContainer.appendChild(leg);
    }
  });

  // Front Box Outer Edges (Solid Lines)
  ctx.strokeStyle = '#0EA5E9';
  ctx.setLineDash([]);
  ctx.lineWidth = 2;
  drawLine(pLW0, pLWH);
  drawLine(pL00, pLW0);
  drawLine(p0W0, pLW0);
  drawLine(pL0H, pLWH);
  drawLine(p0WH, pLWH);
  drawLine(p00H, pL0H);
  drawLine(p00H, p0WH);

  ctx.restore();
}

function drawPoly(points, fillStyle, stroke = false) {
  ctx.beginPath();
  ctx.moveTo(points[0].x, points[0].y);
  for (let i = 1; i < points.length; i++) {
    ctx.lineTo(points[i].x, points[i].y);
  }
  ctx.closePath();
  if (fillStyle) {
    ctx.fillStyle = fillStyle;
    ctx.fill();
  }
  if (stroke) {
    ctx.stroke();
  }
}

function drawLine(p1, p2) {
  ctx.beginPath();
  ctx.moveTo(p1.x, p1.y);
  ctx.lineTo(p2.x, p2.y);
  ctx.stroke();
}

function drawCuboid(x, y, z, dx, dy, dz, colorHex, project) {
  // Vertices of item
  const p0 = project(x, y, z);
  const px = project(x + dx, y, z);
  const py = project(x, y + dy, z);
  const pxy = project(x + dx, y + dy, z);
  const pz = project(x, y, z + dz);
  const pxz = project(x + dx, y, z + dz);
  const pyz = project(x, y + dy, z + dz);
  const pxyz = project(x + dx, y + dy, z + dz);

  ctx.save();
  ctx.strokeStyle = 'rgba(255, 255, 255, 0.6)';
  ctx.lineWidth = 1;

  // Top face
  drawPoly([pz, pxz, pxyz, pyz], hexToRgba(colorHex, 0.85), true);
  // Front-right face
  drawPoly([px, pxy, pxyz, pxz], hexToRgba(colorHex, 0.65), true);
  // Front-left face
  drawPoly([py, pxy, pxyz, pyz], hexToRgba(colorHex, 0.45), true);

  ctx.restore();
}

function hexToRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return `rgba(${r}, ${g}, ${b}, ${alpha})`;
}

// Collapsible Rejection Accordion
window.toggleRejectedAccordion = function() {
  const body = document.getElementById('rejectedAccordionBody');
  const btn = document.getElementById('rejectedAccordionBtn');
  const chevron = document.getElementById('rejectedAccordionChevron');
  const isOpen = body.style.display !== 'none';

  if (isOpen) {
    body.style.display = 'none';
    btn.setAttribute('aria-expanded', 'false');
    chevron.innerText = '▼';
  } else {
    body.style.display = 'flex';
    btn.setAttribute('aria-expanded', 'true');
    chevron.innerText = '▲';
  }
};

// Box Reservation
window.reserveSelectedBox = async function() {
  if (!state.currentOrder || !state.currentRecommendation || !state.currentRecommendation.best_box) {
    showToast('No eligible recommended box to reserve.', 'error');
    return;
  }

  const orderNum = state.currentOrder.order_number;
  const boxCode = state.currentRecommendation.best_box.code;

  const btn = document.getElementById('reserveBoxActionBtn');
  btn.disabled = true;
  btn.innerHTML = '<span>⏳ Processing Atomic Reservation...</span>';

  try {
    const res = await fetch('/api/reserve/', {
      method: 'POST',
      headers: {
        'Content-Type': 'application/json',
      },
      body: JSON.stringify({
        order_number: orderNum,
        box_code: boxCode,
      })
    });
    const result = await res.json();

    if (res.ok && result.success) {
      showToast(result.message, 'success');
      // Reload order state
      window.loadOrder(orderNum);
    } else {
      showToast(result.error || 'Failed to reserve box.', 'error');
      btn.disabled = false;
      btn.innerHTML = `<span>🔒 Reserve Box ${boxCode} & Assign to Order</span>`;
    }
  } catch (err) {
    showToast('Network error during reservation.', 'error');
    btn.disabled = false;
    btn.innerHTML = `<span>🔒 Reserve Box ${boxCode} & Assign to Order</span>`;
  }
};

// AI Assistant Client Logic
window.handleChatSubmit = function() {
  const input = document.getElementById('chatInput');
  const msg = input.value.trim();
  if (msg) {
    window.sendAIMessage(msg);
    input.value = '';
  }
};

window.sendAIMessage = async function(text) {
  const chatMessages = document.getElementById('chatMessages');

  // Append user bubble
  const userBubble = document.createElement('div');
  userBubble.className = 'chat-bubble user';
  userBubble.innerText = text;
  chatMessages.appendChild(userBubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  // Append loading assistant bubble
  const assistantBubble = document.createElement('div');
  assistantBubble.className = 'chat-bubble assistant';
  assistantBubble.innerHTML = '<em>Thinking and validating deterministic packaging rules...</em>';
  chatMessages.appendChild(assistantBubble);
  chatMessages.scrollTop = chatMessages.scrollHeight;

  try {
    const res = await fetch('/api/chat/', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ message: text })
    });
    const data = await res.json();

    let toolHtml = '';
    if (data.tool_calls && data.tool_calls.length > 0) {
      const tc = data.tool_calls[0];
      toolHtml = `<div class="tool-badge">⚙ Tool: ${tc.tool} (${tc.status})</div><br>`;
    }

    let actionBtnHtml = '';
    if (data.verified_result && data.verified_result.order_number) {
      const ord = data.verified_result.order_number;
      actionBtnHtml = `<div style="margin-top: 10px;"><button class="search-btn" style="padding: 6px 14px; font-size: 0.8rem;" onclick="window.loadOrder('${ord}')">View Order ${ord} in Workstation ➔</button></div>`;
    }

    assistantBubble.innerHTML = `${toolHtml}${data.reply.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')}${actionBtnHtml}`;
    chatMessages.scrollTop = chatMessages.scrollHeight;
  } catch (err) {
    assistantBubble.innerHTML = '<span style="color: var(--rose);">Error communicating with AI service.</span>';
  }
};

// Orders Catalog Tab
window.fetchOrdersList = async function() {
  try {
    const res = await fetch('/api/orders/');
    const data = await res.json();
    state.allOrders = data.orders || [];

    const tbody = document.getElementById('ordersCatalogBody');
    tbody.innerHTML = '';
    state.allOrders.forEach(o => {
      const tr = document.createElement('tr');
      const assignedBadge = o.is_assigned 
        ? `<span class="badge badge-assigned">${o.assigned_box}</span>`
        : `<span style="color: var(--text-muted);">None</span>`;

      tr.innerHTML = `
        <td><strong class="sku-text" style="font-size: 0.95rem;">${o.order_number}</strong></td>
        <td>${o.customer_name || 'Customer'}</td>
        <td><span class="badge ${o.is_assigned ? 'badge-assigned' : 'badge-pending'}">${o.status_display}</span></td>
        <td>${o.items_count} items</td>
        <td>${o.total_weight.toFixed(3)} kg</td>
        <td>${assignedBadge}</td>
        <td>
          <div style="display: flex; align-items: center; gap: 8px;">
            <a href="/orders/" class="btn-edit" style="text-decoration: none;">
              <span>✏️</span>
              <span>Edit</span>
            </a>
            <button class="search-btn" style="padding: 6px 12px; font-size: 0.8rem;" onclick="window.loadOrder('${o.order_number}')">
              Pack Order ➔
            </button>
          </div>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    showToast('Failed to load orders catalog.', 'error');
  }
};

// Box Specifications Tab
window.fetchBoxesList = async function() {
  try {
    const res = await fetch('/api/boxes/');
    const data = await res.json();
    state.allBoxes = data.boxes || [];

    const tbody = document.getElementById('boxesCatalogBody');
    tbody.innerHTML = '';
    state.allBoxes.forEach(b => {
      const tr = document.createElement('tr');
      const stockColor = b.quantity_available > 0 ? 'var(--emerald)' : 'var(--rose)';
      tr.innerHTML = `
        <td><strong class="sku-text" style="color: #FFFFFF;">${b.code}</strong></td>
        <td>${b.name}</td>
        <td>${b.length} × ${b.width} × ${b.height} cm</td>
        <td>${b.internal_volume.toLocaleString()} cm³</td>
        <td>${b.max_weight.toFixed(3)} kg</td>
        <td><strong style="color: #FFFFFF;">${b.currency} ${b.cost.toFixed(2)}</strong></td>
        <td style="color: ${stockColor}; font-weight: 700;">
          ${b.quantity_available} <span style="font-size: 0.75rem; color: var(--text-muted);">(${b.quantity_on_hand} on hand, ${b.quantity_reserved} rsv)</span>
        </td>
        <td>
          <span class="badge ${b.is_active ? 'badge-verified' : 'badge-fragile'}">
            ${b.is_active ? 'Active' : 'Discontinued'}
          </span>
        </td>
        <td>
          <a href="/boxes/" class="btn-edit" style="text-decoration: none;">
            <span>✏️</span>
            <span>Edit</span>
          </a>
        </td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    showToast('Failed to load boxes specifications.', 'error');
  }
};

// Recommendation History Tab
window.fetchHistoryList = async function() {
  try {
    const res = await fetch('/api/history/');
    const data = await res.json();
    const runs = data.runs || [];

    const tbody = document.getElementById('historyTableBody');
    tbody.innerHTML = '';
    runs.forEach(r => {
      const tr = document.createElement('tr');
      tr.innerHTML = `
        <td>#${r.id}</td>
        <td><strong class="sku-text">${r.order_number}</strong></td>
        <td>
          <span class="badge ${r.is_successful ? 'badge-assigned' : 'badge-fragile'}">
            ${r.is_successful ? 'Eligible Box Found' : 'No Fit'}
          </span>
        </td>
        <td><strong>${r.best_box || 'None'}</strong></td>
        <td><span style="font-family: var(--font-mono); font-size: 0.75rem;">${r.algorithm_version}</span></td>
        <td>${r.requester}</td>
        <td>${r.candidates_count} checked</td>
        <td style="color: var(--text-muted); font-size: 0.8rem;">${r.created_at}</td>
      `;
      tbody.appendChild(tr);
    });
  } catch (err) {
    showToast('Failed to load audit history.', 'error');
  }
};

// Toast Notifications
function showToast(message, type = 'info') {
  const container = document.getElementById('toastContainer');
  const toast = document.createElement('div');
  toast.className = `toast ${type}`;
  toast.innerHTML = `
    <span>${type === 'success' ? '✓' : type === 'error' ? '✗' : 'ℹ'}</span>
    <span>${message}</span>
  `;
  container.appendChild(toast);
  setTimeout(() => {
    toast.style.opacity = '0';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}
