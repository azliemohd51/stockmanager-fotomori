"""
StockManager for Fotomori — Flask backend
- Local dev : SQLite  (auto, no config needed)
- Production: Supabase / PostgreSQL  (set DATABASE_URL env var)

Run locally : python3 server.py
"""
import os, json
from flask import Flask, request, jsonify, send_from_directory

app = Flask(__name__, static_folder='.', static_url_path='')

DATABASE_URL = os.environ.get('DATABASE_URL')          # set by Railway/Render
USE_POSTGRES  = bool(DATABASE_URL)

# ── DB adapter ──────────────────────────────────────────────────────────────
# Hides the SQLite vs PostgreSQL differences behind a uniform interface.

if USE_POSTGRES:
    import psycopg2
    import psycopg2.extras

    def get_db():
        conn = psycopg2.connect(DATABASE_URL, sslmode='require')
        return conn

    def query(conn, sql, params=()):
        """Run SELECT, return list of dicts."""
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql, params)
            return [dict(r) for r in cur.fetchall()]

    def execute(conn, sql, params=()):
        """Run INSERT/UPDATE/DELETE, return lastrowid."""
        with conn.cursor() as cur:
            cur.execute(sql, params)
            try:
                row = cur.fetchone()
                return row[0] if row else None
            except Exception:
                return None

    P = '%s'   # placeholder

else:
    import sqlite3
    DB_PATH = os.path.join(os.path.dirname(__file__), 'stock.db')

    def get_db():
        conn = sqlite3.connect(DB_PATH)
        conn.row_factory = sqlite3.Row
        conn.execute('PRAGMA foreign_keys = ON')
        return conn

    def query(conn, sql, params=()):
        return [dict(r) for r in conn.execute(sql, params).fetchall()]

    def execute(conn, sql, params=()):
        cur = conn.execute(sql, params)
        return cur.lastrowid

    P = '?'    # placeholder


def now_fn():
    return 'NOW()' if USE_POSTGRES else "datetime('now')"


# ── DB init + seed ───────────────────────────────────────────────────────────

def init_db():
    conn = get_db()
    if USE_POSTGRES:
        with conn.cursor() as cur:
            cur.execute(f"""
            CREATE TABLE IF NOT EXISTS products (
                id         SERIAL PRIMARY KEY,
                name       TEXT NOT NULL,
                sku        TEXT NOT NULL UNIQUE,
                category   TEXT NOT NULL DEFAULT 'General',
                quantity   INTEGER NOT NULL DEFAULT 0,
                min_stock  INTEGER NOT NULL DEFAULT 30,
                unit_price NUMERIC(10,2) NOT NULL DEFAULT 0.0,
                created_at TIMESTAMPTZ DEFAULT NOW(),
                updated_at TIMESTAMPTZ DEFAULT NOW()
            );
            CREATE TABLE IF NOT EXISTS stock_movements (
                id         SERIAL PRIMARY KEY,
                product_id INTEGER NOT NULL REFERENCES products(id) ON DELETE CASCADE,
                type       TEXT NOT NULL CHECK(type IN ('in','out')),
                quantity   INTEGER NOT NULL,
                notes      TEXT DEFAULT '',
                created_at TIMESTAMPTZ DEFAULT NOW()
            );
            """)
        conn.commit()
    else:
        conn.executescript("""
        CREATE TABLE IF NOT EXISTS products (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            name       TEXT NOT NULL,
            sku        TEXT NOT NULL UNIQUE,
            category   TEXT NOT NULL DEFAULT 'General',
            quantity   INTEGER NOT NULL DEFAULT 0,
            min_stock  INTEGER NOT NULL DEFAULT 30,
            unit_price REAL NOT NULL DEFAULT 0.0,
            created_at TEXT DEFAULT (datetime('now')),
            updated_at TEXT DEFAULT (datetime('now'))
        );
        CREATE TABLE IF NOT EXISTS stock_movements (
            id         INTEGER PRIMARY KEY AUTOINCREMENT,
            product_id INTEGER NOT NULL,
            type       TEXT NOT NULL CHECK(type IN ('in','out')),
            quantity   INTEGER NOT NULL,
            notes      TEXT DEFAULT '',
            created_at TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
        );
        """)

    # Seed Fotomori inventory if empty
    rows = query(conn, 'SELECT COUNT(*) AS c FROM products')
    if rows[0]['c'] == 0:
        seed = [
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
        ret = 'RETURNING id' if USE_POSTGRES else ''
        for p in seed:
            pid = execute(conn,
                f"INSERT INTO products (name,sku,category,quantity,min_stock) VALUES ({P},{P},{P},{P},{P}) {ret}",
                p)
            if not pid:
                rows2 = query(conn, f'SELECT id FROM products WHERE sku={P}', (p[1],))
                pid = rows2[0]['id']
            if p[3] > 0:
                execute(conn,
                    f"INSERT INTO stock_movements (product_id,type,quantity,notes) VALUES ({P},{P},{P},{P}) {ret}",
                    (pid, 'in', p[3], 'Opening stock — March 2026 Week 4'))
        conn.commit()

    conn.close()


# ── Routes ───────────────────────────────────────────────────────────────────

@app.route('/')
def index():
    return send_from_directory('.', 'index.html')

@app.route('/api', methods=['GET','POST','DELETE'])
def api():
    action = request.args.get('action', '')
    body   = request.get_json(silent=True) or {} if request.method == 'POST' else {}
    conn   = get_db()
    ret    = 'RETURNING id' if USE_POSTGRES else ''

    try:

        # ── get_products ──────────────────────────────────────────────
        if action == 'get_products':
            search   = request.args.get('search', '')
            category = request.args.get('category', '')
            like_op  = 'ILIKE' if USE_POSTGRES else 'LIKE'
            params   = [f'%{search}%', f'%{search}%']
            where    = f'WHERE (name {like_op} {P} OR sku {like_op} {P})'
            if category:
                where += f' AND category = {P}'
                params.append(category)

            products = query(conn, f'SELECT * FROM products {where} ORDER BY name', params)
            stats    = query(conn, """
                SELECT COUNT(*) AS total_products,
                       COALESCE(SUM(quantity),0) AS total_units,
                       COALESCE(SUM(quantity * unit_price),0) AS total_value,
                       SUM(CASE WHEN quantity <= min_stock THEN 1 ELSE 0 END) AS low_stock_count
                FROM products""")[0]
            return jsonify({'products': products, 'stats': stats})

        # ── add_product ───────────────────────────────────────────────
        elif action == 'add_product':
            name       = (body.get('name') or '').strip()
            sku        = (body.get('sku') or '').strip()
            category   = (body.get('category') or 'General').strip()
            quantity   = int(body.get('quantity') or 0)
            min_stock  = int(body.get('min_stock') or 10)
            unit_price = float(body.get('unit_price') or 0)

            if not name or not sku:
                return jsonify({'error': 'Name and SKU are required'}), 400
            if query(conn, f'SELECT id FROM products WHERE sku={P}', (sku,)):
                return jsonify({'error': 'SKU already exists'}), 400

            pid = execute(conn,
                f'INSERT INTO products (name,sku,category,quantity,min_stock,unit_price) VALUES ({P},{P},{P},{P},{P},{P}) {ret}',
                (name, sku, category, quantity, min_stock, unit_price))
            if not pid:
                pid = query(conn, f'SELECT id FROM products WHERE sku={P}', (sku,))[0]['id']
            if quantity > 0:
                execute(conn,
                    f"INSERT INTO stock_movements (product_id,type,quantity,notes) VALUES ({P},{P},{P},{P}) {ret}",
                    (pid, 'in', quantity, 'Initial stock'))
            conn.commit()
            return jsonify({'success': True, 'id': pid})

        # ── update_stock ──────────────────────────────────────────────
        elif action == 'update_stock':
            product_id = int(body.get('product_id') or 0)
            stype      = body.get('type', '')
            quantity   = int(body.get('quantity') or 0)
            notes      = (body.get('notes') or '').strip()

            if not product_id or stype not in ('in','out') or quantity <= 0:
                return jsonify({'error': 'Invalid input'}), 400

            rows = query(conn, f'SELECT * FROM products WHERE id={P}', (product_id,))
            if not rows:
                return jsonify({'error': 'Product not found'}), 404
            product = rows[0]

            if stype == 'out' and product['quantity'] < quantity:
                return jsonify({'error': f"Insufficient stock. Available: {product['quantity']}"}), 400

            op = '+' if stype == 'in' else '-'
            execute(conn,
                f'UPDATE products SET quantity = quantity {op} {P}, updated_at = {now_fn()} WHERE id={P}',
                (quantity, product_id))
            execute(conn,
                f"INSERT INTO stock_movements (product_id,type,quantity,notes) VALUES ({P},{P},{P},{P}) {ret}",
                (product_id, stype, quantity, notes))
            conn.commit()
            updated = query(conn, f'SELECT * FROM products WHERE id={P}', (product_id,))[0]
            return jsonify({'success': True, 'product': updated})

        # ── delete_product ────────────────────────────────────────────
        elif action == 'delete_product':
            pid = int(request.args.get('id') or 0)
            if not pid:
                return jsonify({'error': 'Invalid ID'}), 400
            execute(conn, f'DELETE FROM products WHERE id={P}', (pid,))
            conn.commit()
            return jsonify({'success': True})

        # ── get_movements ─────────────────────────────────────────────
        elif action == 'get_movements':
            product_id = int(request.args.get('product_id') or 0)
            limit      = min(int(request.args.get('limit') or 50), 200)
            where      = f'WHERE sm.product_id = {P}' if product_id else ''
            params     = [product_id] if product_id else []
            rows = query(conn, f"""
                SELECT sm.*, p.name AS product_name, p.sku
                FROM stock_movements sm
                JOIN products p ON sm.product_id = p.id
                {where}
                ORDER BY sm.created_at DESC
                LIMIT {P}
            """, params + [limit])
            return jsonify({'movements': rows})

        # ── get_categories ────────────────────────────────────────────
        elif action == 'get_categories':
            rows = query(conn, 'SELECT DISTINCT category FROM products ORDER BY category')
            return jsonify({'categories': [r['category'] for r in rows]})

        return jsonify({'error': 'Unknown action'}), 400

    finally:
        conn.close()


# Always init DB on startup (works for both direct run and Vercel serverless)
init_db()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 8080))
    mode = 'Supabase (PostgreSQL)' if USE_POSTGRES else 'SQLite (local)'
    print(f'\n  StockManager for Fotomori — {mode}')
    print(f'  Running at http://localhost:{port}\n')
    app.run(host='0.0.0.0', port=port, debug=False)
