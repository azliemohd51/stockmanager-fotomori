"""
StockManager for Fotomori — Flask backend
- Local dev : SQLite  (no config needed)
- Production: Supabase via HTTP client (set SUPABASE_URL + SUPABASE_KEY)
"""
import os, sqlite3
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')

SUPABASE_URL = os.environ.get('SUPABASE_URL', '')
SUPABASE_KEY = os.environ.get('SUPABASE_KEY', '')
USE_SUPABASE = bool(SUPABASE_URL and SUPABASE_KEY)

# ── Supabase client setup ────────────────────────────────────────────────────
if USE_SUPABASE:
    from supabase import create_client
    sb = create_client(SUPABASE_URL, SUPABASE_KEY)

# ── SQLite setup (local dev) ─────────────────────────────────────────────────
DB_PATH = os.path.join(os.path.dirname(__file__), 'stock.db')

def get_sqlite():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute('PRAGMA foreign_keys = ON')
    return conn

SEED = [
    ('4R Paper - Glossy',  'PAP-4RG',    'Paper',       400, 30),
    ('4R Paper - Matte',   'PAP-4RM',    'Paper',        35, 30),
    ('Polaroid Paper',     'PAP-POL',    'Paper',        20, 30),
    ('BP / A4',            'PAP-BPA4',   'Paper',       450, 30),
    ('Thermal Paper',      'PAP-THM',    'Paper',         2, 30),
    ('AAA Battery',        'BAT-AAA',    'Battery',      15, 30),
    ('AA Battery',         'BAT-AA',     'Battery',       6, 30),
    ('CR2025 3V Battery',  'BAT-CR2025', 'Battery',       6, 30),
    ('4R Frame - Black',   'FRM-4RB',    'Frames',       18, 30),
    ('4R Frame - Nude',    'FRM-4RN',    'Frames',       20, 30),
    ('A4 Frame - Black',   'FRM-A4B',    'Frames',        6, 30),
    ('A4 Frame - Nude',    'FRM-A4N',    'Frames',       14, 30),
    ('LM-057 Epson Ink',   'INK-LM057',  'Ink',           1,  2),
    ('Y-057 Epson Ink',    'INK-Y057',   'Ink',           1,  2),
    ('C-057 Epson Ink',    'INK-C057',   'Ink',           1,  2),
    ('M-057 Epson Ink',    'INK-M057',   'Ink',           1,  2),
    ('BK-057 Epson Ink',   'INK-BK057',  'Ink',           1,  2),
    ('LC-057 Epson Ink',   'INK-LC057',  'Ink',           0,  2),
    ('Sampul',             'ACC-SAM',    'Accessories',  17, 30),
    ('Ziplock Passport',   'ACC-ZIP',    'Accessories',   1,  1),
    ('Tissue',             'ACC-TIS',    'Accessories',   4, 30),
    ('Plastick',           'ACC-PLA',    'Accessories',   0, 30),
    ('Gula-Gula',          'ACC-GUL',    'Accessories',   1,  1),
    ('Flyers Small',       'MKT-FLS',    'Marketing',    38, 30),
    ('Flyers Medium',      'MKT-FLM',    'Marketing',    47, 30),
]

def init_sqlite():
    with get_sqlite() as db:
        db.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL,
            sku TEXT NOT NULL UNIQUE, category TEXT NOT NULL DEFAULT 'General',
            quantity INTEGER NOT NULL DEFAULT 0, min_stock INTEGER NOT NULL DEFAULT 30,
            unit_price REAL NOT NULL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS stock_movements (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('in','out')),
            quantity INTEGER NOT NULL, notes TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );
        """)
        if db.execute('SELECT COUNT(*) FROM products').fetchone()[0] == 0:
            for p in SEED:
                db.execute('INSERT INTO products (name,sku,category,quantity,min_stock) VALUES (?,?,?,?,?)', p)
                if p[3] > 0:
                    pid = db.execute('SELECT id FROM products WHERE sku=?', (p[1],)).fetchone()[0]
                    db.execute('INSERT INTO stock_movements (product_id,type,quantity,notes) VALUES (?,?,?,?)',
                               (pid, 'in', p[3], 'Opening stock — March 2026 Week 4'))

def init_supabase():
    res = sb.table('products').select('id', count='exact').execute()
    if res.count == 0:
        rows = [{'name': p[0], 'sku': p[1], 'category': p[2],
                 'quantity': p[3], 'min_stock': p[4]} for p in SEED]
        inserted = sb.table('products').insert(rows).execute().data
        movements = [{'product_id': r['id'], 'type': 'in',
                      'quantity': r['quantity'],
                      'notes': 'Opening stock — March 2026 Week 4'}
                     for r in inserted if r['quantity'] > 0]
        if movements:
            sb.table('stock_movements').insert(movements).execute()

# Init on startup
if USE_SUPABASE:
    try:
        init_supabase()
    except Exception:
        pass  # tables already exist / already seeded
else:
    init_sqlite()

# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api', methods=['GET', 'POST', 'DELETE'])
def api():
    action = request.args.get('action', '')
    body   = request.get_json(silent=True) or {} if request.method == 'POST' else {}
    return sb_api(action, body) if USE_SUPABASE else sqlite_api(action, body)

# ── Supabase API ─────────────────────────────────────────────────────────────

def sb_api(action, body):

    if action == 'get_products':
        search   = request.args.get('search', '')
        category = request.args.get('category', '')
        q = sb.table('products').select('*')
        if search:
            q = q.or_(f'name.ilike.%{search}%,sku.ilike.%{search}%')
        if category:
            q = q.eq('category', category)
        products = q.order('name').execute().data

        total_units  = sum(p['quantity'] for p in products)
        total_value  = sum(p['quantity'] * float(p['unit_price']) for p in products)
        low_count    = sum(1 for p in products if p['quantity'] <= p['min_stock'])
        stats = {'total_products': len(products), 'total_units': total_units,
                 'total_value': total_value, 'low_stock_count': low_count}
        return jsonify({'products': products, 'stats': stats})

    elif action == 'add_product':
        name       = (body.get('name') or '').strip()
        sku        = (body.get('sku') or '').strip()
        if not name or not sku:
            return jsonify({'error': 'Name and SKU are required'}), 400
        exists = sb.table('products').select('id').eq('sku', sku).execute().data
        if exists:
            return jsonify({'error': 'SKU already exists'}), 400
        row = {'name': name, 'sku': sku,
               'category': (body.get('category') or 'General').strip(),
               'quantity': int(body.get('quantity') or 0),
               'min_stock': int(body.get('min_stock') or 10),
               'unit_price': float(body.get('unit_price') or 0)}
        result = sb.table('products').insert(row).execute().data[0]
        if row['quantity'] > 0:
            sb.table('stock_movements').insert({
                'product_id': result['id'], 'type': 'in',
                'quantity': row['quantity'], 'notes': 'Initial stock'
            }).execute()
        return jsonify({'success': True, 'id': result['id']})

    elif action == 'update_stock':
        product_id = int(body.get('product_id') or 0)
        stype      = body.get('type', '')
        quantity   = int(body.get('quantity') or 0)
        notes      = (body.get('notes') or '').strip()
        if not product_id or stype not in ('in', 'out') or quantity <= 0:
            return jsonify({'error': 'Invalid input'}), 400
        product = sb.table('products').select('*').eq('id', product_id).execute().data
        if not product:
            return jsonify({'error': 'Product not found'}), 404
        product = product[0]
        if stype == 'out' and product['quantity'] < quantity:
            return jsonify({'error': f"Insufficient stock. Available: {product['quantity']}"}), 400
        new_qty = product['quantity'] + quantity if stype == 'in' else product['quantity'] - quantity
        updated = sb.table('products').update({'quantity': new_qty}).eq('id', product_id).execute().data[0]
        sb.table('stock_movements').insert({
            'product_id': product_id, 'type': stype,
            'quantity': quantity, 'notes': notes
        }).execute()
        return jsonify({'success': True, 'product': updated})

    elif action == 'edit_product':
        pid        = int(body.get('id') or 0)
        name       = (body.get('name') or '').strip()
        sku        = (body.get('sku') or '').strip()
        if not pid or not name or not sku:
            return jsonify({'error': 'Invalid input'}), 400
        exists = sb.table('products').select('id').eq('sku', sku).neq('id', pid).execute().data
        if exists:
            return jsonify({'error': 'SKU already used by another product'}), 400
        updated = sb.table('products').update({
            'name': name, 'sku': sku,
            'category': (body.get('category') or 'General').strip(),
            'min_stock': int(body.get('min_stock') or 10),
            'unit_price': float(body.get('unit_price') or 0)
        }).eq('id', pid).execute().data
        return jsonify({'success': True, 'product': updated[0] if updated else {}})

    elif action == 'delete_product':
        pid = int(request.args.get('id') or 0)
        if not pid:
            return jsonify({'error': 'Invalid ID'}), 400
        sb.table('products').delete().eq('id', pid).execute()
        return jsonify({'success': True})

    elif action == 'get_movements':
        product_id = int(request.args.get('product_id') or 0)
        limit      = min(int(request.args.get('limit') or 50), 200)
        q = sb.table('stock_movements').select('*, products(name, sku)').order('created_at', desc=True).limit(limit)
        if product_id:
            q = q.eq('product_id', product_id)
        rows = q.execute().data
        movements = [{**r, 'product_name': r['products']['name'], 'sku': r['products']['sku']} for r in rows]
        return jsonify({'movements': movements})

    elif action == 'get_categories':
        rows = sb.table('products').select('category').execute().data
        cats = sorted(set(r['category'] for r in rows))
        return jsonify({'categories': cats})

    return jsonify({'error': 'Unknown action'}), 400

# ── SQLite API (local dev) ───────────────────────────────────────────────────

def sqlite_api(action, body):
    db = get_sqlite()
    try:
        if action == 'get_products':
            search   = request.args.get('search', '')
            category = request.args.get('category', '')
            params   = [f'%{search}%', f'%{search}%']
            where    = 'WHERE (name LIKE ? OR sku LIKE ?)'
            if category:
                where += ' AND category = ?'
                params.append(category)
            products = [dict(r) for r in db.execute(f'SELECT * FROM products {where} ORDER BY name', params).fetchall()]
            stats    = dict(db.execute("""SELECT COUNT(*) AS total_products,
                COALESCE(SUM(quantity),0) AS total_units,
                COALESCE(SUM(quantity*unit_price),0) AS total_value,
                SUM(CASE WHEN quantity<=min_stock THEN 1 ELSE 0 END) AS low_stock_count
                FROM products""").fetchone())
            return jsonify({'products': products, 'stats': stats})

        elif action == 'add_product':
            name = (body.get('name') or '').strip()
            sku  = (body.get('sku') or '').strip()
            if not name or not sku:
                return jsonify({'error': 'Name and SKU are required'}), 400
            if db.execute('SELECT id FROM products WHERE sku=?', (sku,)).fetchone():
                return jsonify({'error': 'SKU already exists'}), 400
            cur = db.execute('INSERT INTO products (name,sku,category,quantity,min_stock,unit_price) VALUES (?,?,?,?,?,?)',
                (name, sku, (body.get('category') or 'General').strip(),
                 int(body.get('quantity') or 0), int(body.get('min_stock') or 10),
                 float(body.get('unit_price') or 0)))
            pid = cur.lastrowid
            if int(body.get('quantity') or 0) > 0:
                db.execute('INSERT INTO stock_movements (product_id,type,quantity,notes) VALUES (?,?,?,?)',
                           (pid, 'in', int(body.get('quantity')), 'Initial stock'))
            db.commit()
            return jsonify({'success': True, 'id': pid})

        elif action == 'update_stock':
            product_id = int(body.get('product_id') or 0)
            stype      = body.get('type', '')
            quantity   = int(body.get('quantity') or 0)
            notes      = (body.get('notes') or '').strip()
            if not product_id or stype not in ('in','out') or quantity <= 0:
                return jsonify({'error': 'Invalid input'}), 400
            row = db.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone()
            if not row:
                return jsonify({'error': 'Product not found'}), 404
            if stype == 'out' and row['quantity'] < quantity:
                return jsonify({'error': f"Insufficient stock. Available: {row['quantity']}"}), 400
            op = '+' if stype == 'in' else '-'
            db.execute(f"UPDATE products SET quantity=quantity{op}?, updated_at=datetime('now') WHERE id=?", (quantity, product_id))
            db.execute('INSERT INTO stock_movements (product_id,type,quantity,notes) VALUES (?,?,?,?)', (product_id, stype, quantity, notes))
            db.commit()
            return jsonify({'success': True, 'product': dict(db.execute('SELECT * FROM products WHERE id=?', (product_id,)).fetchone())})

        elif action == 'edit_product':
            pid        = int(body.get('id') or 0)
            name       = (body.get('name') or '').strip()
            sku        = (body.get('sku') or '').strip()
            if not pid or not name or not sku:
                return jsonify({'error': 'Invalid input'}), 400
            if db.execute('SELECT id FROM products WHERE sku=? AND id!=?', (sku, pid)).fetchone():
                return jsonify({'error': 'SKU already used by another product'}), 400
            db.execute("""UPDATE products SET name=?, sku=?, category=?, min_stock=?,
                unit_price=?, updated_at=datetime('now') WHERE id=?""",
                (name, sku, (body.get('category') or 'General').strip(),
                 int(body.get('min_stock') or 10), float(body.get('unit_price') or 0), pid))
            db.commit()
            return jsonify({'success': True})

        elif action == 'delete_product':
            pid = int(request.args.get('id') or 0)
            if not pid: return jsonify({'error': 'Invalid ID'}), 400
            db.execute('DELETE FROM products WHERE id=?', (pid,))
            db.commit()
            return jsonify({'success': True})

        elif action == 'get_movements':
            product_id = int(request.args.get('product_id') or 0)
            limit      = min(int(request.args.get('limit') or 50), 200)
            where      = 'WHERE sm.product_id=?' if product_id else ''
            params     = [product_id] if product_id else []
            rows = db.execute(f"""SELECT sm.*, p.name AS product_name, p.sku
                FROM stock_movements sm JOIN products p ON sm.product_id=p.id
                {where} ORDER BY sm.created_at DESC LIMIT ?""", params + [limit]).fetchall()
            return jsonify({'movements': [dict(r) for r in rows]})

        elif action == 'get_categories':
            rows = db.execute('SELECT DISTINCT category FROM products ORDER BY category').fetchall()
            return jsonify({'categories': [r['category'] for r in rows]})

        return jsonify({'error': 'Unknown action'}), 400
    finally:
        db.close()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    mode = 'Supabase' if USE_SUPABASE else 'SQLite (local)'
    print(f'\n  StockManager for Fotomori — {mode}')
    print(f'  Running at http://localhost:{port}\n')
    app.run(host='0.0.0.0', port=port, debug=False)
