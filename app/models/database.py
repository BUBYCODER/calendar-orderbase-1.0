import sqlite3
import os
import calendar
import json

DB_PATH = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../production.db'))

def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn

def init_db():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DROP TABLE IF EXISTS order_items")
    cursor.execute("DROP TABLE IF EXISTS order_files")
    cursor.execute("DROP TABLE IF EXISTS stages")
    cursor.execute("DROP TABLE IF EXISTS orders")
    cursor.execute("DROP TABLE IF EXISTS clients")
    cursor.execute("DROP TABLE IF EXISTS products")
    cursor.execute("DROP TABLE IF EXISTS patterns")
    cursor.execute("DROP TABLE IF EXISTS fabrics")
    cursor.execute("DROP TABLE IF EXISTS fabric_densities")

    cursor.execute("""
        CREATE TABLE orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_number INTEGER UNIQUE,
            name TEXT NOT NULL,
            client TEXT,
            contact TEXT,
            contact_type TEXT DEFAULT 'Телефон',
            comment TEXT,
            order_type TEXT DEFAULT 'batch',
            quantity INTEGER DEFAULT 0,
            amount REAL DEFAULT 0.0,
            start_date TEXT,
            start_q INTEGER,
            end_date TEXT,
            end_q INTEGER,
            client_id INTEGER,
            product_id INTEGER,
            pattern_id INTEGER,
            fabric_id INTEGER,
            fabric_density_id INTEGER,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            position_index INTEGER DEFAULT 1,
            product_name TEXT,
            pattern_name TEXT,
            fabric_name TEXT,
            fabric_density TEXT,
            fabric_color TEXT,
            size_3xs INTEGER DEFAULT 0,
            size_2xs INTEGER DEFAULT 0,
            size_xs INTEGER DEFAULT 0,
            size_s INTEGER DEFAULT 0,
            size_m INTEGER DEFAULT 0,
            size_l INTEGER DEFAULT 0,
            size_xl INTEGER DEFAULT 0,
            size_2xl INTEGER DEFAULT 0,
            size_3xl INTEGER DEFAULT 0,
            size_onesize INTEGER DEFAULT 0,
            total_quantity INTEGER DEFAULT 0,
            embellishments TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE stages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            stage_type TEXT NOT NULL,
            start_date TEXT NOT NULL,
            start_q INTEGER NOT NULL,
            end_date TEXT NOT NULL,
            end_q INTEGER NOT NULL,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE order_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE clients (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL UNIQUE,
            phone TEXT,
            city TEXT,
            preferences TEXT
        )
    """)

    cursor.execute("CREATE TABLE products (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)")
    cursor.execute("CREATE TABLE patterns (id INTEGER PRIMARY KEY AUTOINCREMENT, product_id INTEGER, name TEXT NOT NULL)")
    cursor.execute("CREATE TABLE fabrics (id INTEGER PRIMARY KEY AUTOINCREMENT, name TEXT NOT NULL UNIQUE)")
    cursor.execute("CREATE TABLE fabric_densities (id INTEGER PRIMARY KEY AUTOINCREMENT, fabric_id INTEGER, density TEXT NOT NULL)")

    
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            data_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.commit()
    conn.close()

def upgrade_db():
    conn = get_connection()
    cursor = conn.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            position_index INTEGER DEFAULT 1,
            product_name TEXT,
            pattern_name TEXT,
            fabric_name TEXT,
            fabric_density TEXT,
            fabric_color TEXT,
            size_3xs INTEGER DEFAULT 0,
            size_2xs INTEGER DEFAULT 0,
            size_xs INTEGER DEFAULT 0,
            size_s INTEGER DEFAULT 0,
            size_m INTEGER DEFAULT 0,
            size_l INTEGER DEFAULT 0,
            size_xl INTEGER DEFAULT 0,
            size_2xl INTEGER DEFAULT 0,
            size_3xl INTEGER DEFAULT 0,
            size_onesize INTEGER DEFAULT 0,
            total_quantity INTEGER DEFAULT 0,
            embellishments TEXT,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS order_files (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            order_id INTEGER NOT NULL,
            file_name TEXT NOT NULL,
            file_path TEXT NOT NULL,
            uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
        )
    """)

    cols_to_add = [
        ('order_number', 'INTEGER'),
        ('amount', 'REAL DEFAULT 0.0'),
        ('contact_type', "TEXT DEFAULT 'Телефон'"),
        ('client_id', 'INTEGER'),
        ('product_id', 'INTEGER'),
        ('pattern_id', 'INTEGER'),
        ('fabric_id', 'INTEGER'),
        ('fabric_density_id', 'INTEGER'),
        ('comment', 'TEXT'),
        ('contact', 'TEXT'),
        ('order_type', "TEXT DEFAULT 'batch'"),
        ('quantity', 'INTEGER DEFAULT 0')
    ]
    for col, definition in cols_to_add:
        try:
            cursor.execute(f"ALTER TABLE orders ADD COLUMN {col} {definition}")
        except sqlite3.OperationalError:
            pass

    conn.commit()
    conn.close()

def cleanup_db():
    upgrade_db()
    conn = get_connection()
    cursor = conn.cursor()
    for tbl in ['stages', 'order_items', 'order_files']:
        try:
            cursor.execute(f"DELETE FROM {tbl} WHERE order_id NOT IN (SELECT id FROM orders)")
        except sqlite3.OperationalError:
            pass
    conn.commit()
    conn.close()

def add_order(name, client, contact, comment, order_type, quantity, order_start, order_start_q, order_end, order_end_q, stages,
              order_number=None, client_id=None, contact_type='Телефон', product_id=None, pattern_id=None,
              fabric_id=None, fabric_density_id=None, amount=0.0, created_at=None, positions=None):
    conn = get_connection()
    cursor = conn.cursor()

    if positions:
        pos_sum = sum(int(p.get('total_quantity', 0) or 0) for p in positions)
        if pos_sum > 0:
            quantity = pos_sum

    cursor.execute("""
        INSERT INTO orders (
            name, client, contact, comment, order_type, quantity, 
            start_date, start_q, end_date, end_q,
            order_number, client_id, contact_type, product_id, pattern_id,
            fabric_id, fabric_density_id, amount, created_at
        ) 
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
    """, (
        name, client, contact, comment, order_type, quantity, 
        order_start, order_start_q, order_end, order_end_q,
        order_number, client_id, contact_type, product_id, pattern_id,
        fabric_id, fabric_density_id, amount, created_at
    ))
    order_id = cursor.lastrowid

    for stage in stages:
        cursor.execute("""
            INSERT INTO stages (order_id, stage_type, start_date, start_q, end_date, end_q)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (order_id, stage['type'], stage['start'], stage['start_q'], stage['end'], stage['end_q']))

    if positions:
        for idx, pos in enumerate(positions, 1):
            emb_json = json.dumps(pos.get('embellishments', []), ensure_ascii=False)
            cursor.execute("""
                INSERT INTO order_items (
                    order_id, position_index, product_name, pattern_name, fabric_name, fabric_density, fabric_color,
                    size_3xs, size_2xs, size_xs, size_s, size_m, size_l, size_xl, size_2xl, size_3xl, size_onesize,
                    total_quantity, embellishments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id, idx,
                pos.get('product_name', ''),
                pos.get('pattern_name', ''),
                pos.get('fabric_name', ''),
                pos.get('fabric_density', ''),
                pos.get('fabric_color', ''),
                int(pos.get('size_3xs', 0) or 0),
                int(pos.get('size_2xs', 0) or 0),
                int(pos.get('size_xs', 0) or 0),
                int(pos.get('size_s', 0) or 0),
                int(pos.get('size_m', 0) or 0),
                int(pos.get('size_l', 0) or 0),
                int(pos.get('size_xl', 0) or 0),
                int(pos.get('size_2xl', 0) or 0),
                int(pos.get('size_3xl', 0) or 0),
                int(pos.get('size_onesize', 0) or 0),
                int(pos.get('total_quantity', 0) or 0),
                emb_json
            ))

    conn.commit()
    conn.close()
    return order_id

def update_order_full(order_id, name, client, contact, comment, order_type, quantity, order_start, order_start_q, order_end, order_end_q, stages,
                      order_number=None, client_id=None, contact_type='Телефон', product_id=None, pattern_id=None,
                      fabric_id=None, fabric_density_id=None, amount=0.0, created_at=None, positions=None):
    conn = get_connection()
    cursor = conn.cursor()

    if positions:
        pos_sum = sum(int(p.get('total_quantity', 0) or 0) for p in positions)
        if pos_sum > 0:
            quantity = pos_sum

    cursor.execute("""
        UPDATE orders SET 
            name = ?, client = ?, contact = ?, comment = ?, order_type = ?, quantity = ?, 
            start_date = ?, start_q = ?, end_date = ?, end_q = ?,
            order_number = ?, client_id = ?, contact_type = ?, product_id = ?, pattern_id = ?,
            fabric_id = ?, fabric_density_id = ?, amount = ?, created_at = COALESCE(?, created_at)
        WHERE id = ?
    """, (
        name, client, contact, comment, order_type, quantity, 
        order_start, order_start_q, order_end, order_end_q,
        order_number, client_id, contact_type, product_id, pattern_id,
        fabric_id, fabric_density_id, amount, created_at,
        order_id
    ))

    cursor.execute("DELETE FROM stages WHERE order_id = ?", (order_id,))
    for stage in stages:
        cursor.execute("""
            INSERT INTO stages (order_id, stage_type, start_date, start_q, end_date, end_q)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (order_id, stage['type'], stage['start'], stage['start_q'], stage['end'], stage['end_q']))

    if positions is not None:
        cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
        for idx, pos in enumerate(positions, 1):
            emb_json = json.dumps(pos.get('embellishments', []), ensure_ascii=False)
            cursor.execute("""
                INSERT INTO order_items (
                    order_id, position_index, product_name, pattern_name, fabric_name, fabric_density, fabric_color,
                    size_3xs, size_2xs, size_xs, size_s, size_m, size_l, size_xl, size_2xl, size_3xl, size_onesize,
                    total_quantity, embellishments
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (
                order_id, idx,
                pos.get('product_name', ''),
                pos.get('pattern_name', ''),
                pos.get('fabric_name', ''),
                pos.get('fabric_density', ''),
                pos.get('fabric_color', ''),
                int(pos.get('size_3xs', 0) or 0),
                int(pos.get('size_2xs', 0) or 0),
                int(pos.get('size_xs', 0) or 0),
                int(pos.get('size_s', 0) or 0),
                int(pos.get('size_m', 0) or 0),
                int(pos.get('size_l', 0) or 0),
                int(pos.get('size_xl', 0) or 0),
                int(pos.get('size_2xl', 0) or 0),
                int(pos.get('size_3xl', 0) or 0),
                int(pos.get('size_onesize', 0) or 0),
                int(pos.get('total_quantity', 0) or 0),
                emb_json
            ))

    conn.commit()
    conn.close()

def update_order(order_id, name, client, contact, comment, order_type, quantity, order_start, order_start_q, order_end, order_end_q, stages):
    update_order_full(order_id, name, client, contact, comment, order_type, quantity, order_start, order_start_q, order_end, order_end_q, stages)

def get_order(order_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    if not order:
        conn.close()
        return None
    cursor.execute("SELECT * FROM stages WHERE order_id = ? ORDER BY start_date, start_q", (order_id,))
    stages = cursor.fetchall()
    conn.close()
    
    mapped_stages = [{'id': row['id'], 'stage_type': row['stage_type'], 'type': row['stage_type'], 'start': row['start_date'], 'start_q': row['start_q'], 'end': row['end_date'], 'end_q': row['end_q'], 'start_date': row['start_date'], 'end_date': row['end_date']} for row in stages]
    return dict(order), mapped_stages

def get_orders_by_month(year, month):
    conn = get_connection()
    cursor = conn.cursor()
    cal = calendar.Calendar(firstweekday=0)
    month_dates = list(cal.itermonthdates(year, month))
    first_visible_date = month_dates[0].strftime('%Y-%m-%d')
    last_visible_date = month_dates[-1].strftime('%Y-%m-%d')

    cursor.execute("""
        SELECT stages.*, orders.name AS order_name, orders.order_number, orders.client, orders.contact, orders.comment, orders.order_type, orders.quantity,
               orders.start_date AS order_start_date, orders.start_q AS order_start_q,
               orders.end_date AS order_end_date, orders.end_q AS order_end_q
        FROM stages
        JOIN orders ON stages.order_id = orders.id
        WHERE stages.start_date <= ? AND stages.end_date >= ?
        ORDER BY orders.start_date, orders.start_q, orders.id, stages.start_date, stages.start_q
    """, (last_visible_date, first_visible_date))

    rows = cursor.fetchall()
    conn.close()

    orders_dict = {}
    for row in rows:
        order_id = row['order_id']
        if order_id not in orders_dict:
            orders_dict[order_id] = {
                'id': order_id, 
                'name': row['order_name'], 
                'order_number': row['order_number'] or order_id,
                'client': row['client'], 
                'contact': row['contact'], 
                'comment': row['comment'],
                'order_type': row['order_type'], 
                'quantity': row['quantity'],
                'start_date': row['order_start_date'], 
                'start_q': row['order_start_q'],
                'end_date': row['order_end_date'], 
                'end_q': row['order_end_q'], 
                'stages': []
            }
        orders_dict[order_id]['stages'].append({
            'id': row['id'], 'type': row['stage_type'], 'start': row['start_date'], 'start_q': row['start_q'], 'end': row['end_date'], 'end_q': row['end_q']
        })
    return list(orders_dict.values())

def get_stages_by_date(date_str):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT stages.*, orders.name AS order_name, orders.order_number, orders.client, orders.contact, orders.comment, orders.order_type, orders.quantity
        FROM stages
        JOIN orders ON stages.order_id = orders.id
        WHERE ? BETWEEN stages.start_date AND stages.end_date
        ORDER BY orders.id, stages.start_date, stages.start_q
    """, (date_str,))
    rows = cursor.fetchall()
    conn.close()
    result = {}
    for row in rows:
        order_id = row['order_id']
        if order_id not in result:
            result[order_id] = {'id': order_id, 'order_number': row['order_number'] or order_id, 'name': row['order_name'], 'client': row['client'], 'contact': row['contact'], 'comment': row['comment'], 'order_type': row['order_type'], 'quantity': row['quantity'], 'stages': []}
        result[order_id]['stages'].append({'id': row['id'], 'type': row['stage_type'], 'start': row['start_date'], 'start_q': row['start_q'], 'end': row['end_date'], 'end_q': row['end_q']})
    return list(result.values())

def delete_order(order_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("DELETE FROM stages WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM order_items WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM order_files WHERE order_id = ?", (order_id,))
    cursor.execute("DELETE FROM orders WHERE id = ?", (order_id,))
    conn.commit()
    conn.close()

def get_all_occupied_slots(exclude_order_id=None, order_type='batch'):
    conn = get_connection()
    cursor = conn.cursor()
    query = """
        SELECT DISTINCT s.order_id, s.start_date, s.start_q, s.end_date, s.end_q 
        FROM stages s
        JOIN orders o ON s.order_id = o.id
        WHERE o.order_type = ?
    """
    params = [order_type]
    if exclude_order_id:
        query += " AND s.order_id != ?"
        params.append(exclude_order_id)
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_orders_list(sort_by='order_number', sort_order='desc', search='', filter_type='all'):
    conn = get_connection()
    cursor = conn.cursor()
    
    valid_columns = {
        'order_number': 'orders.order_number',
        'created_at': 'orders.created_at',
        'order_type': 'orders.order_type',
        'amount': 'orders.amount'
    }
    order_col = valid_columns.get(sort_by, 'orders.order_number')
    order_dir = 'ASC' if sort_order == 'asc' else 'DESC'
    
    query = """
        SELECT orders.id, orders.order_number, orders.created_at, orders.name, 
               orders.order_type, orders.quantity, orders.amount,
               COALESCE(clients.name, orders.client) as client_name
        FROM orders
        LEFT JOIN clients ON orders.client_id = clients.id
        WHERE 1=1
    """
    params = []
    if filter_type in ['batch', 'sample']:
        query += " AND orders.order_type = ?"
        params.append(filter_type)
        
    if search:
        search_like = f"%{search.strip()}%"
        query += """ AND (
            CAST(orders.order_number AS TEXT) LIKE ? OR
            orders.name LIKE ? OR
            orders.client LIKE ? OR
            clients.name LIKE ? OR
            orders.comment LIKE ?
        )"""
        params.extend([search_like, search_like, search_like, search_like, search_like])
        
    query += f" ORDER BY {order_col} {order_dir}"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_next_available_order_number():
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT order_number FROM orders WHERE order_number IS NOT NULL AND order_number > 0")
    rows = cursor.fetchall()
    conn.close()
    taken = set(r['order_number'] for r in rows)
    candidate = 1
    while candidate in taken:
        candidate += 1
    return candidate

def check_order_number_taken(order_number, exclude_id=None):
    if not order_number:
        return False
    conn = get_connection()
    cursor = conn.cursor()
    if exclude_id:
        cursor.execute("SELECT 1 FROM orders WHERE order_number = ? AND id != ?", (order_number, exclude_id))
    else:
        cursor.execute("SELECT 1 FROM orders WHERE order_number = ?", (order_number,))
    exists = cursor.fetchone() is not None
    conn.close()
    return exists

def add_order_file(order_id, file_name, file_path):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("INSERT INTO order_files (order_id, file_name, file_path) VALUES (?, ?, ?)",
                   (order_id, file_name, file_path))
    conn.commit()
    conn.close()

def delete_order_file(file_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("SELECT file_path FROM order_files WHERE id = ?", (file_id,))
    row = cursor.fetchone()
    if row:
        cursor.execute("DELETE FROM order_files WHERE id = ?", (file_id,))
        conn.commit()
    conn.close()
    return row['file_path'] if row else None

def get_order_full_details(order_id):
    conn = get_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT orders.*, 
               COALESCE(clients.name, orders.client) as client_name,
               clients.phone as client_phone, clients.city as client_city, clients.preferences as client_preferences,
               products.name as product_name,
               patterns.name as pattern_name,
               fabrics.name as fabric_name,
               fabric_densities.density as fabric_density_name
        FROM orders
        LEFT JOIN clients ON orders.client_id = clients.id
        LEFT JOIN products ON orders.product_id = products.id
        LEFT JOIN patterns ON orders.pattern_id = patterns.id
        LEFT JOIN fabrics ON orders.fabric_id = fabrics.id
        LEFT JOIN fabric_densities ON orders.fabric_density_id = fabric_densities.id
        WHERE orders.id = ?
    """, (order_id,))
    order_row = cursor.fetchone()
    if not order_row:
        conn.close()
        return None
    order = dict(order_row)
    
    cursor.execute("SELECT * FROM stages WHERE order_id = ? ORDER BY start_date, start_q", (order_id,))
    stages = [dict(r) for r in cursor.fetchall()]
    
    cursor.execute("SELECT * FROM order_files WHERE order_id = ? ORDER BY uploaded_at DESC", (order_id,))
    files = [dict(r) for r in cursor.fetchall()]

    cursor.execute("SELECT * FROM order_items WHERE order_id = ? ORDER BY position_index, id", (order_id,))
    items_rows = cursor.fetchall()
    items = []
    for r in items_rows:
        item = dict(r)
        try:
            item['embellishments_list'] = json.loads(item['embellishments']) if item.get('embellishments') else []
        except:
            item['embellishments_list'] = []
        items.append(item)
    
    conn.close()
    return order, stages, files, items

def get_or_create_client(name, phone='', city='', preferences=''):
    clean = name.strip()
    if not clean: return None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM clients")
    for r in cur.fetchall():
        if r['name'].strip().lower() == clean.lower():
            conn.close()
            return r['id']
    cur.execute("INSERT INTO clients (name, phone, city, preferences) VALUES (?, ?, ?, ?)", (clean, phone, city, preferences))
    cid = cur.lastrowid
    conn.commit()
    conn.close()
    return cid

def get_or_create_product(name):
    clean = name.strip()
    if not clean: return None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM products")
    for r in cur.fetchall():
        if r['name'].strip().lower() == clean.lower():
            conn.close()
            return r['id']
    cur.execute("INSERT INTO products (name) VALUES (?)", (clean,))
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid

def get_or_create_pattern(product_id, name):
    clean = name.strip()
    if not clean or not product_id: return None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM patterns WHERE product_id = ?", (product_id,))
    for r in cur.fetchall():
        if r['name'].strip().lower() == clean.lower():
            conn.close()
            return r['id']
    cur.execute("INSERT INTO patterns (product_id, name) VALUES (?, ?)", (product_id, clean))
    pid = cur.lastrowid
    conn.commit()
    conn.close()
    return pid

def get_or_create_fabric(name):
    clean = name.strip()
    if not clean: return None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM fabrics")
    for r in cur.fetchall():
        if r['name'].strip().lower() == clean.lower():
            conn.close()
            return r['id']
    cur.execute("INSERT INTO fabrics (name) VALUES (?)", (clean,))
    fid = cur.lastrowid
    conn.commit()
    conn.close()
    return fid

def get_or_create_density(fabric_id, density):
    clean = density.strip()
    if not clean or not fabric_id: return None
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, density FROM fabric_densities WHERE fabric_id = ?", (fabric_id,))
    for r in cur.fetchall():
        if r['density'].strip().lower() == clean.lower():
            conn.close()
            return r['id']
    cur.execute("INSERT INTO fabric_densities (fabric_id, density) VALUES (?, ?)", (fabric_id, clean))
    did = cur.lastrowid
    conn.commit()
    conn.close()
    return did


def save_draft(title, data_json, draft_id=None):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            data_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    if draft_id:
        cur.execute("UPDATE drafts SET title = ?, data_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?", (title, data_json, draft_id))
        d_id = draft_id
    else:
        cur.execute("INSERT INTO drafts (title, data_json) VALUES (?, ?)", (title, data_json))
        d_id = cur.lastrowid
    conn.commit()
    conn.close()
    return d_id

def get_all_drafts():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("""
        CREATE TABLE IF NOT EXISTS drafts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            title TEXT NOT NULL,
            data_json TEXT NOT NULL,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cur.execute("SELECT id, title, updated_at FROM drafts ORDER BY updated_at DESC")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_draft(draft_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT * FROM drafts WHERE id = ?", (draft_id,))
    row = cur.fetchone()
    conn.close()
    return dict(row) if row else None

def delete_draft(draft_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("DELETE FROM drafts WHERE id = ?", (draft_id,))
    conn.commit()
    conn.close()
