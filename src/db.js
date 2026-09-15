import { DatabaseSync } from 'node:sqlite';
import path from 'node:path';
import fs from 'node:fs';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const DB_PATH = path.resolve(__dirname, '../production.db');

export function getDb() {
  const db = new DatabaseSync(DB_PATH);
  try {
    db.exec("PRAGMA journal_mode=WAL;");
    db.exec("PRAGMA busy_timeout=30000;");
  } catch (e) {
    // Ignore pragma errors
  }
  return db;
}

export function initDb() {
  const db = getDb();
  db.exec(`
    CREATE TABLE IF NOT EXISTS clients (
      id INTEGER PRIMARY KEY AUTOINCREMENT, 
      name TEXT NOT NULL, 
      phone TEXT, 
      email TEXT, 
      city TEXT, 
      preferences TEXT
    );
    CREATE TABLE IF NOT EXISTS products (
      id INTEGER PRIMARY KEY AUTOINCREMENT, 
      name TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS patterns (
      id INTEGER PRIMARY KEY AUTOINCREMENT, 
      product_id INTEGER, 
      name TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS fabrics (
      id INTEGER PRIMARY KEY AUTOINCREMENT, 
      name TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS fabric_densities (
      id INTEGER PRIMARY KEY AUTOINCREMENT, 
      fabric_id INTEGER, 
      density TEXT NOT NULL
    );
    CREATE TABLE IF NOT EXISTS orders (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      name TEXT NOT NULL,
      client TEXT,
      contact TEXT,
      comment TEXT,
      order_type TEXT DEFAULT 'batch',
      quantity INTEGER DEFAULT 0,
      start_date TEXT,
      start_q INTEGER,
      end_date TEXT,
      end_q INTEGER,
      created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      order_number INTEGER,
      client_id INTEGER,
      product_id INTEGER,
      pattern_id INTEGER,
      fabric_id INTEGER,
      fabric_density_id INTEGER,
      amount REAL DEFAULT 0.0,
      contact_type TEXT DEFAULT 'Телефон'
    );
    CREATE TABLE IF NOT EXISTS stages (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      order_id INTEGER NOT NULL,
      stage_type TEXT NOT NULL,
      start_date TEXT NOT NULL,
      start_q INTEGER NOT NULL,
      end_date TEXT NOT NULL,
      end_q INTEGER NOT NULL,
      FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );
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
      total_quantity INTEGER DEFAULT 0,
      embellishments TEXT,
      FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS order_files (
      id INTEGER PRIMARY KEY AUTOINCREMENT, 
      order_id INTEGER, 
      file_name TEXT NOT NULL, 
      file_path TEXT NOT NULL,
      uploaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
      position_index INTEGER DEFAULT 1,
      FOREIGN KEY (order_id) REFERENCES orders(id) ON DELETE CASCADE
    );
    CREATE TABLE IF NOT EXISTS drafts (
      id INTEGER PRIMARY KEY AUTOINCREMENT,
      title TEXT NOT NULL,
      data_json TEXT NOT NULL,
      updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
    );
    CREATE INDEX IF NOT EXISTS idx_stages_order_id ON stages(order_id);
    CREATE INDEX IF NOT EXISTS idx_order_items_order_id ON order_items(order_id);
    CREATE INDEX IF NOT EXISTS idx_order_files_order_id ON order_files(order_id);
    CREATE INDEX IF NOT EXISTS idx_stages_dates ON stages(start_date, end_date);
  `);

  // Seed default clients if empty
  const clientCount = db.prepare("SELECT COUNT(*) as c FROM clients").get();
  if (clientCount.c === 0) {
    const insertClient = db.prepare("INSERT INTO clients (name, phone, city) VALUES (?, ?, ?)");
    insertClient.run('ООО Бомонти', '+7 999 123 45 67', 'Москва');
    insertClient.run('Розничный покупатель', '', 'СПб');
  }

  // Seed default products if empty
  const prodCount = db.prepare("SELECT COUNT(*) as c FROM products").get();
  if (prodCount.c === 0) {
    const defaultProducts = [
      'Худи', 'Зип-худи', 'Свитшот', 'Полузамок', 'Олимпийка',
      'Бомбер', 'Брюки', 'Футболка', 'Лонгслив', 'Майка', 'Шорты'
    ];
    const insertProd = db.prepare("INSERT INTO products (name) VALUES (?)");
    const insertPat = db.prepare("INSERT INTO patterns (product_id, name) VALUES (?, ?)");
    for (const p of defaultProducts) {
      const res = insertProd.run(p);
      const pid = Number(res.lastInsertRowid);
      if (['Худи', 'Зип-худи', 'Свитшот', 'Полузамок', 'Олимпийка', 'Бомбер'].includes(p)) {
        for (const pat of ['Oversize', 'Boxy-fit', 'Regular']) {
          insertPat.run(pid, pat);
        }
      } else if (['Футболка', 'Лонгслив', 'Майка'].includes(p)) {
        for (const pat of ['Oversize', 'Boxy-fit', 'Regular', 'Slim']) {
          insertPat.run(pid, pat);
        }
      } else if (p === 'Брюки') {
        for (const pat of ['Джоггеры', 'Прямые', 'Oversize']) {
          insertPat.run(pid, pat);
        }
      } else if (p === 'Шорты') {
        insertPat.run(pid, 'Oversize');
      }
    }
  }

  // Seed fabrics
  const fabricCount = db.prepare("SELECT COUNT(*) as c FROM fabrics").get();
  if (fabricCount.c === 0) {
    const defaultFabrics = {
      '3-х нитка Петля': ['340г', '420г', '500г'],
      '3-х нитка Начес': ['340г'],
      '2х нитка Петля': ['240г'],
      'Кулирная гладь': ['190г', '220г', '240г', '300г']
    };
    const insertFab = db.prepare("INSERT INTO fabrics (name) VALUES (?)");
    const insertDen = db.prepare("INSERT INTO fabric_densities (fabric_id, density) VALUES (?, ?)");
    for (const [fName, densities] of Object.entries(defaultFabrics)) {
      const res = insertFab.run(fName);
      const fid = Number(res.lastInsertRowid);
      for (const d of densities) {
        insertDen.run(fid, d);
      }
    }
  }

  db.close();
}

export function getOrdersByMonth(year, month) {
  const db = getDb();
  // Calculate first visible and last visible date for month grid
  const firstDay = new Date(Date.UTC(year, month - 1, 1));
  const startDayOfWeek = (firstDay.getUTCDay() + 6) % 7;
  const startDate = new Date(Date.UTC(year, month - 1, 1 - startDayOfWeek));
  const lastDay = new Date(Date.UTC(year, month, 0));
  const endDayOfWeek = (lastDay.getUTCDay() + 6) % 7;
  const endDate = new Date(Date.UTC(year, month - 1, lastDay.getUTCDate() + (6 - endDayOfWeek)));

  const firstVisibleDate = startDate.toISOString().slice(0, 10);
  const lastVisibleDate = endDate.toISOString().slice(0, 10);

  const query = `
    SELECT stages.*, orders.name AS order_name, orders.order_number, orders.client, orders.contact, orders.comment, orders.order_type, orders.quantity,
           orders.start_date AS order_start_date, orders.start_q AS order_start_q,
           orders.end_date AS order_end_date, orders.end_q AS order_end_q
    FROM stages JOIN orders ON stages.order_id = orders.id
    WHERE stages.start_date <= ? AND stages.end_date >= ?
    ORDER BY orders.start_date, orders.start_q, orders.id, stages.start_date, stages.start_q
  `;

  const rows = db.prepare(query).all(lastVisibleDate, firstVisibleDate);
  db.close();

  const ordersDict = {};
  for (const row of rows) {
    const orderId = row.order_id;
    if (!ordersDict[orderId]) {
      ordersDict[orderId] = {
        id: orderId,
        name: row.order_name,
        order_number: row.order_number || orderId,
        client: row.client,
        contact: row.contact,
        comment: row.comment,
        order_type: row.order_type,
        quantity: row.quantity,
        start_date: row.order_start_date,
        start_q: row.order_start_q,
        end_date: row.order_end_date,
        end_q: row.order_end_q,
        stages: []
      };
    }
    ordersDict[orderId].stages.push({
      id: row.id,
      type: row.stage_type,
      start: row.start_date,
      start_q: row.start_q,
      end: row.end_date,
      end_q: row.end_q
    });
  }
  return Object.values(ordersDict);
}

export function getStagesByDate(dateStr) {
  const db = getDb();
  const query = `
    SELECT stages.*, orders.name AS order_name, orders.order_number, orders.client, orders.contact, orders.comment, orders.order_type, orders.quantity 
    FROM stages JOIN orders ON stages.order_id = orders.id 
    WHERE ? BETWEEN stages.start_date AND stages.end_date 
    ORDER BY orders.id, stages.start_date, stages.start_q
  `;
  const rows = db.prepare(query).all(dateStr);
  db.close();

  const result = {};
  for (const row of rows) {
    const orderId = row.order_id;
    if (!result[orderId]) {
      result[orderId] = {
        id: orderId,
        order_number: row.order_number || orderId,
        name: row.order_name,
        client: row.client,
        contact: row.contact,
        comment: row.comment,
        order_type: row.order_type,
        quantity: row.quantity,
        stages: []
      };
    }
    result[orderId].stages.push({
      id: row.id,
      type: row.stage_type,
      start: row.start_date,
      start_q: row.start_q,
      end: row.end_date,
      end_q: row.end_q
    });
  }
  return Object.values(result);
}

export function getAllOccupiedSlots(excludeOrderId = null, orderType = 'batch') {
  const db = getDb();
  let query = `
    SELECT DISTINCT s.order_id, s.start_date, s.start_q, s.end_date, s.end_q 
    FROM stages s JOIN orders o ON s.order_id = o.id 
    WHERE o.order_type = ?
  `;
  const params = [orderType];
  if (excludeOrderId) {
    query += " AND s.order_id != ?";
    params.push(excludeOrderId);
  }
  const rows = db.prepare(query).all(...params);
  db.close();
  return rows;
}

export function getOrder(orderId) {
  const db = getDb();
  const order = db.prepare("SELECT * FROM orders WHERE id = ?").get(orderId);
  if (!order) {
    db.close();
    return null;
  }
  const stages = db.prepare("SELECT * FROM stages WHERE order_id = ? ORDER BY start_date, start_q").all(orderId);
  db.close();
  return [order, stages];
}

export function getOrderFullDetails(orderId) {
  const db = getDb();
  const order = db.prepare("SELECT * FROM orders WHERE id = ?").get(orderId);
  if (!order) {
    db.close();
    return null;
  }
  order.client_name = order.client || '';

  const stages = db.prepare("SELECT * FROM stages WHERE order_id = ? ORDER BY start_date, start_q").all(orderId);
  const files = db.prepare("SELECT * FROM order_files WHERE order_id = ? ORDER BY uploaded_at DESC").all(orderId);
  const itemRows = db.prepare("SELECT * FROM order_items WHERE order_id = ? ORDER BY position_index, id").all(orderId);
  db.close();

  const items = [];
  for (const r of itemRows) {
    const item = { ...r };
    try {
      item.embellishments_list = item.embellishments ? JSON.parse(item.embellishments) : [];
    } catch {
      item.embellishments_list = [];
    }
    item.files = files.filter(f => f.position_index === item.position_index);
    items.push(item);
  }
  return [order, stages, files, items];
}

export function getOrdersCounts() {
  const db = getDb();
  const rows = db.prepare("SELECT order_type, COUNT(*) as cnt FROM orders GROUP BY order_type").all();
  const counts = { all: 0, batch: 0, sample: 0, drafts: 0 };
  for (const r of rows) {
    if (r.order_type === 'batch') counts.batch = Number(r.cnt);
    else if (r.order_type === 'sample') counts.sample = Number(r.cnt);
  }
  counts.all = counts.batch + counts.sample;
  try {
    const dRow = db.prepare("SELECT COUNT(*) as c FROM drafts").get();
    counts.drafts = Number(dRow?.c || 0);
  } catch {
    counts.drafts = 0;
  }
  db.close();
  return counts;
}

export function getOrdersList(sortBy = 'order_number', sortOrder = 'desc', search = '', filterType = 'all', page = 1, perPage = 50) {
  const db = getDb();
  const validCols = {
    order_number: 'orders.order_number',
    created_at: 'orders.created_at',
    order_type: 'orders.order_type',
    amount: 'orders.amount'
  };
  const orderCol = validCols[sortBy] || 'orders.order_number';
  const orderDir = sortOrder.toLowerCase() === 'asc' ? 'ASC' : 'DESC';

  let query = `
    SELECT orders.id, orders.order_number, orders.created_at, orders.name, orders.order_type, orders.quantity, orders.amount, 
           COALESCE(clients.name, orders.client) as client_name 
    FROM orders 
    LEFT JOIN clients ON orders.client_id = clients.id 
    WHERE 1=1
  `;
  const params = [];

  if (['batch', 'sample'].includes(filterType)) {
    query += " AND orders.order_type = ?";
    params.push(filterType);
  }

  if (search && search.trim()) {
    const searchLike = `%${search.trim()}%`;
    query += " AND (CAST(orders.order_number AS TEXT) LIKE ? OR orders.name LIKE ? OR orders.client LIKE ? OR clients.name LIKE ? OR orders.comment LIKE ?)";
    params.push(searchLike, searchLike, searchLike, searchLike, searchLike);
  }

  const countQuery = "SELECT COUNT(*) as c FROM (" + query + ")";
  const countRow = db.prepare(countQuery).get(...params);
  const totalItems = Number(countRow?.c || 0);
  const totalPages = Math.max(1, Math.ceil(totalItems / perPage));
  const currentPage = Math.max(1, Number(page) || 1);

  query += ` ORDER BY ${orderCol} ${orderDir} LIMIT ? OFFSET ?`;
  params.push(perPage, (currentPage - 1) * perPage);

  const rows = db.prepare(query).all(...params);
  db.close();
  return [rows, totalPages, currentPage];
}

export function addOrder(name, client, contact, comment, orderType, quantity, orderStart, orderStartQ, orderEnd, orderEndQ, stages,
                         { orderNumber = null, clientId = null, contactType = 'Телефон', productId = null, patternId = null,
                           fabricId = null, fabricDensityId = null, amount = 0.0, createdAt = null, positions = null } = {}) {
  const db = getDb();
  let finalQty = quantity;
  if (positions && positions.length > 0) {
    const posSum = positions.reduce((acc, p) => acc + (parseInt(p.total_quantity, 10) || 0), 0);
    if (posSum > 0) finalQty = posSum;
  }

  let orderId;
  db.exec('BEGIN IMMEDIATE');
  try {
    const insertOrder = db.prepare(`
    INSERT INTO orders (
      name, client, contact, comment, order_type, quantity, 
      start_date, start_q, end_date, end_q,
      order_number, client_id, contact_type, product_id, pattern_id,
      fabric_id, fabric_density_id, amount, created_at
    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, COALESCE(?, CURRENT_TIMESTAMP))
  `);

  const res = insertOrder.run(
    name, client, contact, comment, orderType, finalQty, orderStart, orderStartQ, orderEnd, orderEndQ,
    orderNumber, clientId, contactType, productId, patternId, fabricId, fabricDensityId, amount, createdAt
  );
  orderId = Number(res.lastInsertRowid);

  const insertStage = db.prepare(`
    INSERT INTO stages (order_id, stage_type, start_date, start_q, end_date, end_q)
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  for (const s of stages) {
    insertStage.run(orderId, s.type, s.start, s.start_q, s.end, s.end_q);
  }

  if (positions && positions.length > 0) {
    const insertItem = db.prepare(`
      INSERT INTO order_items (
        order_id, position_index, product_name, pattern_name, fabric_name, fabric_density, fabric_color,
        size_3xs, size_2xs, size_xs, size_s, size_m, size_l, size_xl, size_2xl, size_3xl, total_quantity, embellishments
      ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    `);
    for (let idx = 0; idx < positions.length; idx++) {
      const pos = positions[idx];
      const embJson = JSON.stringify(pos.embellishments || []);
      insertItem.run(
        orderId, idx + 1, pos.product_name || '', pos.pattern_name || '', pos.fabric_name || '',
        pos.fabric_density || '', pos.fabric_color || '',
        parseInt(pos.size_3xs, 10) || 0, parseInt(pos.size_2xs, 10) || 0, parseInt(pos.size_xs, 10) || 0,
        parseInt(pos.size_s, 10) || 0, parseInt(pos.size_m, 10) || 0, parseInt(pos.size_l, 10) || 0,
        parseInt(pos.size_xl, 10) || 0, parseInt(pos.size_2xl, 10) || 0, parseInt(pos.size_3xl, 10) || 0,
        parseInt(pos.total_quantity, 10) || 0, embJson
      );
    }
  }

    db.exec('COMMIT');
  } catch(e) {
    db.exec('ROLLBACK');
    throw e;
  } finally {
    db.close();
  }
  return orderId;
}

export function updateOrder(orderId, name, client, contact, comment, orderType, quantity,
                            orderStart, orderStartQ, orderEnd, orderEndQ, stages) {
  const db = getDb();
  db.exec('BEGIN IMMEDIATE');
  try {
    db.prepare(`
    UPDATE orders SET 
      name = ?, client = ?, contact = ?, comment = ?, order_type = ?, quantity = ?, 
      start_date = ?, start_q = ?, end_date = ?, end_q = ? 
    WHERE id = ?
  `).run(name, client, contact, comment, orderType, quantity, orderStart, orderStartQ, orderEnd, orderEndQ, orderId);

  db.prepare("DELETE FROM stages WHERE order_id = ?").run(orderId);
  const insertStage = db.prepare(`
    INSERT INTO stages (order_id, stage_type, start_date, start_q, end_date, end_q) 
    VALUES (?, ?, ?, ?, ?, ?)
  `);
  for (const stage of stages) {
    const stType = stage.stage_type || stage.type || '';
    const stStart = stage.start || stage.start_date;
    const stSq = stage.start_q || 1;
    const stEnd = stage.end || stage.end_date;
    const stEq = stage.end_q || 4;
    insertStage.run(orderId, stType, stStart, stSq, stEnd, stEq);
  }
    db.exec('COMMIT');
  } catch(e) {
    db.exec('ROLLBACK');
    throw e;
  } finally {
    db.close();
  }
}

export function updateOrderFull(orderId, name, client, contact, comment, orderType, quantity,
                                orderStart, orderStartQ, orderEnd, orderEndQ, stages,
                                { orderNumber = null, clientId = null, contactType = 'Телефон',
                                  amount = 0.0, createdAt = null, positions = null } = {}) {
  const db = getDb();
  let finalQty = quantity;
  if (positions && positions.length > 0) {
    const posSum = positions.reduce((acc, p) => acc + (parseInt(p.total_quantity, 10) || 0), 0);
    if (posSum > 0) finalQty = posSum;
  }
  db.exec('BEGIN IMMEDIATE');
  try {
    db.prepare(`
      UPDATE orders SET 
         name = ?, client = ?, contact = ?, comment = ?, order_type = ?, quantity = ?, 
         start_date = ?, start_q = ?, end_date = ?, end_q = ?,
        order_number = ?, client_id = ?, contact_type = ?, amount = ?, created_at = COALESCE(?, created_at)
      WHERE id = ?
    `).run(name, client, contact, comment, orderType, finalQty, orderStart, orderStartQ, orderEnd, orderEndQ,
           orderNumber, clientId, contactType, amount, createdAt, orderId);

    db.prepare("DELETE FROM stages WHERE order_id = ?").run(orderId);
    const insertStage = db.prepare(`
      INSERT INTO stages (order_id, stage_type, start_date, start_q, end_date, end_q) 
      VALUES (?, ?, ?, ?, ?, ?)
    `);
    for (const s of stages) {
      const stType = s.stage_type || s.type || '';
      const stStart = s.start || s.start_date;
      const stSq = s.start_q || 1;
      const stEnd = s.end || s.end_date;
      const stEq = s.end_q || 4;
      insertStage.run(orderId, stType, stStart, stSq, stEnd, stEq);
    }
    
    if (positions !== null && positions !== undefined) {
      db.prepare("DELETE FROM order_items WHERE order_id = ?").run(orderId);
      const insertItem = db.prepare(`
        INSERT INTO order_items (
          order_id, position_index, product_name, pattern_name, fabric_name, fabric_density, fabric_color,
          size_3xs, size_2xs, size_xs, size_s, size_m, size_l, size_xl, size_2xl, size_3xl, total_quantity, embellishments
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
      `);
      for (let idx = 0; idx < positions.length; idx++) {
        const pos = positions[idx];
        const embJson = JSON.stringify(pos.embellishments || []);
        insertItem.run(
          orderId, idx + 1, pos.product_name || '', pos.pattern_name || '', pos.fabric_name || '',
          pos.fabric_density || '', pos.fabric_color || '',
          parseInt(pos.size_3xs, 10) || 0, parseInt(pos.size_2xs, 10) || 0, parseInt(pos.size_xs, 10) || 0,
          parseInt(pos.size_s, 10) || 0, parseInt(pos.size_m, 10) || 0, parseInt(pos.size_l, 10) || 0,
          parseInt(pos.size_xl, 10) || 0, parseInt(pos.size_2xl, 10) || 0, parseInt(pos.size_3xl, 10) || 0,
          parseInt(pos.total_quantity, 10) || 0, embJson
        );
      }
    }
    db.exec('COMMIT');
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  } finally {
    db.close();
  }
}

export function deleteOrder(orderId) {
  const db = getDb();
  const files = db.prepare("SELECT file_path FROM order_files WHERE order_id = ?").all(orderId);
  for (const f of files) {
    try {
      const fullPath = path.resolve(__dirname, '../app/static', f.file_path);
      if (fs.existsSync(fullPath)) fs.unlinkSync(fullPath);
    } catch {
      // ignore
    }
  }
  
  db.exec('BEGIN IMMEDIATE');
  try {
    db.prepare("DELETE FROM stages WHERE order_id = ?").run(orderId);
    db.prepare("DELETE FROM order_items WHERE order_id = ?").run(orderId);
    db.prepare("DELETE FROM order_files WHERE order_id = ?").run(orderId);
    db.prepare("DELETE FROM orders WHERE id = ?").run(orderId);
    db.exec('COMMIT');
  } catch (err) {
    db.exec('ROLLBACK');
    throw err;
  } finally {
    db.close();
  }
}

export function getNextAvailableOrderNumber() {
  const db = getDb();
  const rows = db.prepare("SELECT order_number FROM orders WHERE order_number IS NOT NULL AND order_number > 0").all();
  db.close();
  const taken = new Set(rows.map(r => r.order_number));
  let candidate = 1;
  while (taken.has(candidate)) candidate++;
  return candidate;
}

export function checkOrderNumberTaken(orderNumber, excludeId = null) {
  if (!orderNumber) return false;
  const db = getDb();
  let row;
  if (excludeId) {
    row = db.prepare("SELECT 1 FROM orders WHERE order_number = ? AND id != ?").get(orderNumber, excludeId);
  } else {
    row = db.prepare("SELECT 1 FROM orders WHERE order_number = ?").get(orderNumber);
  }
  db.close();
  return Boolean(row);
}

export function addOrderFile(orderId, fileName, filePath, positionIndex = 1) {
  const db = getDb();
  db.prepare("INSERT INTO order_files (order_id, position_index, file_name, file_path) VALUES (?, ?, ?, ?)").run(orderId, positionIndex, fileName, filePath);
  db.close();
}

export function deleteOrderFile(fileId) {
  const db = getDb();
  const row = db.prepare("SELECT file_path FROM order_files WHERE id = ?").get(fileId);
  if (row) {
    db.prepare("DELETE FROM order_files WHERE id = ?").run(fileId);
  }
  db.close();
  return row ? row.file_path : null;
}

export function getDraftsList(search = '') {
  const db = getDb();
  let query = "SELECT id, title, data_json, updated_at FROM drafts";
  const params = [];
  if (search && search.trim()) {
    query += " WHERE title LIKE ?";
    params.push(`%${search.trim()}%`);
  }
  query += " ORDER BY updated_at DESC";
  const rows = db.prepare(query).all(...params);
  db.close();
  return rows;
}

export function getAllDrafts() {
  return getDraftsList();
}

export function getDraft(draftId) {
  const db = getDb();
  const row = db.prepare("SELECT * FROM drafts WHERE id = ?").get(draftId);
  db.close();
  return row || null;
}

export function saveDraft(title, dataJson, draftId = null) {
  const db = getDb();
  let dId;
  let targetId = draftId;

  if (!targetId) {
    try {
      const recent = db.prepare("SELECT id FROM drafts WHERE title = ? ORDER BY id DESC LIMIT 1").get(title);
      if (recent) {
        const row = db.prepare("SELECT id, (strftime('%s', 'now') - strftime('%s', updated_at)) as diff_sec FROM drafts WHERE id = ?").get(recent.id);
        if (row && (row.diff_sec === null || Math.abs(Number(row.diff_sec)) <= 10)) {
          targetId = recent.id;
        }
      }
    } catch (e) {
      // If datetime diff calculation fails, fallback to standard insert
    }
  }

  if (targetId) {
    db.prepare("UPDATE drafts SET title = ?, data_json = ?, updated_at = CURRENT_TIMESTAMP WHERE id = ?").run(title, dataJson, targetId);
    dId = targetId;
  } else {
    const res = db.prepare("INSERT INTO drafts (title, data_json) VALUES (?, ?)").run(title, dataJson);
    dId = Number(res.lastInsertRowid);
  }
  db.close();
  return dId;
}

export function deleteDraft(draftId) {
  const db = getDb();
  const draft = db.prepare("SELECT data_json FROM drafts WHERE id = ?").get(draftId);
  if (draft && draft.data_json) {
    try {
      const parsed = JSON.parse(draft.data_json);
      const draftFiles = parsed.draft_files || {};
      const staticBase = path.resolve(__dirname, '../app/static');
      for (const key of Object.keys(draftFiles)) {
        for (const fileObj of draftFiles[key]) {
          const filePath = fileObj.path || fileObj.file_path;
          if (filePath) {
            const fullPath = path.resolve(staticBase, filePath);
            if (fullPath.startsWith(staticBase) && fs.existsSync(fullPath)) {
              fs.unlinkSync(fullPath);
            }
          }
        }
      }
    } catch (e) {
      console.error("Error deleting draft files:", e);
    }
  }
  db.prepare("DELETE FROM drafts WHERE id = ?").run(draftId);
  db.close();
}

export function getOrCreateClient(name, phone = '', city = '', preferences = '') {
  const clean = (name || '').trim();
  if (!clean) return null;
  const db = getDb();
  const clients = db.prepare("SELECT id, name FROM clients").all();
  for (const c of clients) {
    if (c.name.trim().toLowerCase() === clean.toLowerCase()) {
      db.close();
      return c.id;
    }
  }
  const res = db.prepare("INSERT INTO clients (name, phone, city, preferences) VALUES (?, ?, ?, ?)").run(clean, phone, city, preferences);
  const cid = Number(res.lastInsertRowid);
  db.close();
  return cid;
}

export function getAllClients() {
  const db = getDb();
  const rows = db.prepare("SELECT id, name, phone, city FROM clients ORDER BY name").all();
  db.close();
  return rows;
}

export function getAllProducts() {
  const db = getDb();
  const rows = db.prepare("SELECT id, name FROM products ORDER BY name").all();
  db.close();
  return rows;
}

export function getPatternsByProduct(productId) {
  const db = getDb();
  const rows = db.prepare("SELECT id, name FROM patterns WHERE product_id = ? ORDER BY name").all(productId);
  db.close();
  return rows;
}

export function getAllFabrics() {
  const db = getDb();
  const rows = db.prepare("SELECT id, name FROM fabrics ORDER BY name").all();
  db.close();
  return rows;
}

export function getDensitiesByFabric(fabricId) {
  const db = getDb();
  const rows = db.prepare("SELECT id, density as name FROM fabric_densities WHERE fabric_id = ? ORDER BY density").all(fabricId);
  db.close();
  return rows;
}
