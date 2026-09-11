from app.models.database import get_connection

def get_all_clients():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name, phone, city FROM clients ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_products():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM products ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_patterns_by_product(product_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM patterns WHERE product_id = ? ORDER BY name", (product_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_all_fabrics():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, name FROM fabrics ORDER BY name")
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_densities_by_fabric(fabric_id):
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT id, density as name FROM fabric_densities WHERE fabric_id = ? ORDER BY density", (fabric_id,))
    rows = cur.fetchall()
    conn.close()
    return [dict(r) for r in rows]

def get_next_order_number():
    conn = get_connection()
    cur = conn.cursor()
    cur.execute("SELECT MAX(order_number) FROM orders")
    max_num = cur.fetchone()[0]
    conn.close()
    return (max_num or 0) + 1
