const API = '/api';

let allProducts = [];
let searchTerm = '';
let filterCategory = '';
let sortCol = '';
let sortDir = 'asc';

async function request(action, method = 'GET', body = null, params = {}) {
    const url = new URL(API, window.location.href);
    url.searchParams.set('action', action);
    Object.entries(params).forEach(([k, v]) => url.searchParams.set(k, v));
    const opts = { method, headers: { 'Content-Type': 'application/json' } };
    if (body) opts.body = JSON.stringify(body);
    const res = await fetch(url, opts);
    return res.json();
}

async function loadProducts() {
    const params = {};
    if (searchTerm) params.search = searchTerm;
    if (filterCategory) params.category = filterCategory;

    const data = await request('get_products', 'GET', null, params);
    allProducts = data.products || [];
    renderStats(data.stats);
    renderTable(getSorted(allProducts));
}

function getSorted(products) {
    if (!sortCol) return products;
    return [...products].sort((a, b) => {
        let va = a[sortCol], vb = b[sortCol];
        if (typeof va === 'string') va = va.toLowerCase(), vb = vb.toLowerCase();
        if (va < vb) return sortDir === 'asc' ? -1 : 1;
        if (va > vb) return sortDir === 'asc' ? 1 : -1;
        return 0;
    });
}

function renderStats(s) {
    if (!s) return;
    document.getElementById('stat-total').textContent = s.total_products || 0;
    document.getElementById('stat-units').textContent = Number(s.total_units || 0).toLocaleString();
    document.getElementById('stat-value').textContent = 'RM ' + Number(s.total_value || 0).toFixed(2);
    const low = Number(s.low_stock_count || 0);
    document.getElementById('stat-low').textContent = low;
    document.getElementById('stat-low-card').classList.toggle('alert', low > 0);
}

function renderTable(products) {
    const tbody = document.getElementById('product-tbody');
    if (!products.length) {
        tbody.innerHTML = '<tr><td colspan="8" class="empty">No products found</td></tr>';
        return;
    }
    tbody.innerHTML = products.map(p => {
        const isLow = p.quantity <= p.min_stock;
        const stockClass = p.quantity === 0 ? 'badge out-of-stock' : isLow ? 'badge low-stock' : 'badge in-stock';
        const stockLabel = p.quantity === 0 ? 'Out of Stock' : isLow ? 'Low Stock' : 'In Stock';
        return `<tr class="${isLow ? 'row-low' : ''}">
            <td><span class="sku">${esc(p.sku)}</span></td>
            <td><strong>${esc(p.name)}</strong></td>
            <td>${esc(p.category)}</td>
            <td class="qty ${p.quantity === 0 ? 'zero' : ''}">${p.quantity}</td>
            <td class="min-qty">${p.min_stock}</td>
            <td>RM ${Number(p.unit_price).toFixed(2)}</td>
            <td><span class="${stockClass}">${stockLabel}</span></td>
            <td class="actions">
                <button class="btn-sm btn-in" onclick="openStockModal(${p.id},'in','${esc(p.name)}')">+ In</button>
                <button class="btn-sm btn-out" onclick="openStockModal(${p.id},'out','${esc(p.name)}')">- Out</button>
                <button class="btn-sm btn-del" onclick="deleteProduct(${p.id},'${esc(p.name)}')">Delete</button>
            </td>
        </tr>`;
    }).join('');
}

function esc(str) {
    return String(str).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

// --- Add Product Modal ---
function openAddModal() {
    document.getElementById('add-form').reset();
    document.getElementById('add-error').textContent = '';
    showModal('modal-add');
}

async function submitAddProduct(e) {
    e.preventDefault();
    const form = e.target;
    const errEl = document.getElementById('add-error');
    errEl.textContent = '';

    const data = {
        name: form.name.value.trim(),
        sku: form.sku.value.trim(),
        category: form.category.value.trim() || 'General',
        quantity: parseInt(form.quantity.value) || 0,
        min_stock: parseInt(form.min_stock.value) || 10,
        unit_price: parseFloat(form.unit_price.value) || 0
    };

    const res = await request('add_product', 'POST', data);
    if (res.error) { errEl.textContent = res.error; return; }
    closeModal('modal-add');
    showToast('Product added successfully!', 'success');
    loadProducts();
    loadCategories();
}

// --- Stock Modal ---
function openStockModal(id, type, name) {
    document.getElementById('stock-form').reset();
    document.getElementById('stock-error').textContent = '';
    document.getElementById('stock-product-id').value = id;
    document.getElementById('stock-type').value = type;
    document.getElementById('stock-modal-title').textContent = (type === 'in' ? 'Stock In' : 'Stock Out') + ' — ' + name;
    document.getElementById('stock-type-label').textContent = type === 'in' ? 'Quantity Received' : 'Quantity Dispatched';
    document.getElementById('stock-btn').textContent = type === 'in' ? 'Add Stock' : 'Remove Stock';
    document.getElementById('stock-btn').className = 'btn ' + (type === 'in' ? 'btn-success' : 'btn-danger');
    showModal('modal-stock');
}

async function submitStock(e) {
    e.preventDefault();
    const errEl = document.getElementById('stock-error');
    errEl.textContent = '';

    const data = {
        product_id: parseInt(document.getElementById('stock-product-id').value),
        type: document.getElementById('stock-type').value,
        quantity: parseInt(document.getElementById('stock-qty').value),
        notes: document.getElementById('stock-notes').value.trim()
    };

    const res = await request('update_stock', 'POST', data);
    if (res.error) { errEl.textContent = res.error; return; }
    closeModal('modal-stock');
    showToast('Stock updated!', 'success');
    loadProducts();
}

// --- Delete ---
async function deleteProduct(id, name) {
    if (!confirm(`Delete "${name}"? This will also remove all stock movement history.`)) return;
    const res = await request('delete_product', 'GET', null, { id });
    if (res.error) { showToast(res.error, 'error'); return; }
    showToast('Product deleted', 'info');
    loadProducts();
    loadCategories();
}

// --- Movements Modal ---
async function openMovementsModal() {
    showModal('modal-movements');
    const res = await request('get_movements', 'GET', null, { limit: 100 });
    const list = document.getElementById('movements-list');
    const movements = res.movements || [];
    if (!movements.length) {
        list.innerHTML = '<div class="empty">No movements yet</div>';
        return;
    }
    list.innerHTML = movements.map(m => `
        <div class="movement-row ${m.type}">
            <div class="mv-info">
                <span class="mv-badge ${m.type}">${m.type === 'in' ? '▲ IN' : '▼ OUT'}</span>
                <span class="mv-name">${esc(m.product_name)}</span>
                <span class="mv-sku">${esc(m.sku)}</span>
            </div>
            <div class="mv-meta">
                <span class="mv-qty">${m.type === 'in' ? '+' : '-'}${m.quantity} units</span>
                <span class="mv-notes">${m.notes ? esc(m.notes) : ''}</span>
                <span class="mv-date">${new Date(m.created_at).toLocaleString()}</span>
            </div>
        </div>`).join('');
}

// --- Categories ---
async function loadCategories() {
    const res = await request('get_categories');
    const sel = document.getElementById('filter-category');
    const current = sel.value;
    sel.innerHTML = '<option value="">All Categories</option>';
    (res.categories || []).forEach(c => {
        const opt = document.createElement('option');
        opt.value = c; opt.textContent = c;
        if (c === current) opt.selected = true;
        sel.appendChild(opt);
    });
}

// --- Modal helpers ---
function showModal(id) {
    document.getElementById(id).classList.add('active');
    document.body.style.overflow = 'hidden';
}
function closeModal(id) {
    document.getElementById(id).classList.remove('active');
    document.body.style.overflow = '';
}

// Close on backdrop click
document.querySelectorAll('.modal').forEach(m => {
    m.addEventListener('click', e => {
        if (e.target === m) closeModal(m.id);
    });
});

// --- Toast ---
function showToast(msg, type = 'info') {
    const t = document.createElement('div');
    t.className = `toast toast-${type}`;
    t.textContent = msg;
    document.getElementById('toast-container').appendChild(t);
    setTimeout(() => t.classList.add('show'), 10);
    setTimeout(() => { t.classList.remove('show'); setTimeout(() => t.remove(), 300); }, 3000);
}

// --- Search / Filter ---
document.getElementById('filter-category').addEventListener('change', e => {
    filterCategory = e.target.value;
    loadProducts();
});

// --- Sortable headers ---
document.querySelectorAll('th.sortable').forEach(th => {
    th.addEventListener('click', () => {
        const col = th.dataset.col;
        if (sortCol === col) {
            sortDir = sortDir === 'asc' ? 'desc' : 'asc';
        } else {
            sortCol = col;
            sortDir = 'asc';
        }
        document.querySelectorAll('th.sortable').forEach(h => h.classList.remove('asc', 'desc'));
        th.classList.add(sortDir);
        renderTable(getSorted(allProducts));
    });
});

// --- Init ---
document.getElementById('add-form').addEventListener('submit', submitAddProduct);
document.getElementById('stock-form').addEventListener('submit', submitStock);

loadProducts();
loadCategories();
