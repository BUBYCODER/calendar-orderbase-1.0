
// Global error logging to prevent silent server deaths
process.on('uncaughtException', (err) => {
  console.error('[CRITICAL UNCAUGHT EXCEPTION]:', err);
});
process.on('unhandledRejection', (reason, promise) => {
  console.error('[UNHANDLED REJECTION]:', reason);
});
import express from 'express';
import session from 'express-session';
import flash from 'connect-flash';
import multer from 'multer';
import nunjucks from 'nunjucks';
import path from 'node:path';
import fs from 'node:fs';
import crypto from 'node:crypto';
import { fileURLToPath } from 'node:url';

import * as db from './src/db.js';
import * as planner from './src/planner.js';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Polyfill python string methods for template compatibility
String.prototype.startswith = String.prototype.startsWith;
String.prototype.endswith = String.prototype.endsWith;
String.prototype.format = function(val) {
  if (this.toString() === '{:,.0f}') {
    const n = Math.round(Number(val) || 0);
    return n.toLocaleString('ru-RU').replace(/\u00A0/g, ' ');
  }
  return this.toString();
};

const app = express();
const PORT = 3000;

// Initialize DB schema
db.initDb();

// Ensure upload directories exist
const uploadDir = path.resolve(__dirname, 'app/static/uploads');
const draftsDir = path.resolve(__dirname, 'app/static/uploads/drafts');
const tempDir = path.resolve(__dirname, 'app/static/uploads/temp');
fs.mkdirSync(uploadDir, { recursive: true });
fs.mkdirSync(draftsDir, { recursive: true });
fs.mkdirSync(tempDir, { recursive: true });

export function decodeFilename(name) {
  if (!name || typeof name !== 'string') return '';
  try {
    const decoded = Buffer.from(name, 'latin1').toString('utf8');
    if (decoded && !decoded.includes('\ufffd')) {
      return decoded;
    }
    return name;
  } catch {
    return name;
  }
}

// Setup multer
const storage = multer.diskStorage({
  destination: (req, file, cb) => {
    file.originalname = decodeFilename(file.originalname);
    cb(null, tempDir);
  },
  filename: (req, file, cb) => {
    file.originalname = decodeFilename(file.originalname);
    const ext = path.extname(file.originalname).toLowerCase();
    cb(null, `${Date.now()}_${crypto.randomUUID().slice(0, 8)}${ext}`);
  }
});
const upload = multer({ storage });

// Body parser
app.use(express.json({ limit: '50mb' }));
app.use(express.urlencoded({ extended: true, limit: '50mb' }));

// Static files
app.use('/static', express.static(path.resolve(__dirname, 'app/static')));

// Session & Flash
app.use(session({
  secret: process.env.SECRET_KEY || 'production-calendar-secret-2024',
  resave: false,
  saveUninitialized: false,
  cookie: { maxAge: 24 * 60 * 60 * 1000 }
}));
app.use(flash());

// Request header sanity check
app.use((req, res, next) => {
  next();
});

// Nunjucks configuration
const nunjucksEnv = nunjucks.configure(path.resolve(__dirname, 'app/templates'), {
  autoescape: true,
  express: app,
  watch: false,
  noCache: true
});

nunjucksEnv.addFilter('format_date', (dateStr) => {
  if (!dateStr) return '';
  try {
    const s = String(dateStr).slice(0, 10);
    const [y, m, d] = s.split('-');
    if (y && m && d) return `${d}.${m}.${y}`;
    return s;
  } catch {
    return String(dateStr);
  }
});

// Template globals and locals middleware
app.use((req, res, next) => {
  res.locals.request = {
    path: req.path,
    args: req.query
  };
  res.locals.url_for = (endpoint, opts) => {
    if (endpoint === 'static') {
      return '/static/' + (opts?.filename || '');
    }
    return '/' + (opts?.filename || '');
  };
  res.locals.get_flashed_messages = (withCategories) => {
    const flashes = req.flash();
    if (!withCategories) {
      const msgs = [];
      for (const k of Object.keys(flashes)) {
        msgs.push(...flashes[k]);
      }
      return msgs;
    }
    const catMsgs = [];
    for (const cat of Object.keys(flashes)) {
      for (const msg of flashes[cat]) {
        catMsgs.push([cat, msg]);
      }
    }
    return catMsgs;
  };
  next();
});

const STAGE_LIST = [
  'Раскрой', 'Пошив', 'Упаковка', 'ВТО и упаковка', 'Отгрузка', 'Разгрузка',
  'DTF', 'Вышивка', 'Шелкография', 'Разработка лекал', 'Бирки'
];

function safeInt(val, fallback = 0) {
  if (val === null || val === undefined) return fallback;
  const clean = String(val).trim();
  const parsed = parseInt(clean, 10);
  return isNaN(parsed) ? fallback : parsed;
}

function safeFloat(val, fallback = 0.0) {
  if (val === null || val === undefined) return fallback;
  const clean = String(val).trim().replace(/\s+/g, '').replace(',', '.');
  const parsed = parseFloat(clean);
  return isNaN(parsed) ? fallback : parsed;
}

function getAsArray(val) {
  if (val === undefined || val === null) return [];
  return Array.isArray(val) ? val : [val];
}

function parsePositionsFromForm(body) {
  const posIndexes = getAsArray(body['pos_index[]'] || body['pos_index']);
  const positions = [];

  for (const pIdx of posIndexes) {
    const pProd = (body[`product_${pIdx}`] || '').trim();
    const pPattern = (body[`pattern_${pIdx}`] || '').trim();
    const pFabric = (body[`fabric_${pIdx}`] || '').trim();
    const pDensity = (body[`density_${pIdx}`] || '').trim();
    const pColor = (body[`color_${pIdx}`] || '').trim();

    const s3xs = safeInt(body[`size_3xs_${pIdx}`]);
    const s2xs = safeInt(body[`size_2xs_${pIdx}`]);
    const sxs = safeInt(body[`size_xs_${pIdx}`]);
    const ss = safeInt(body[`size_s_${pIdx}`]);
    const sm = safeInt(body[`size_m_${pIdx}`]);
    const sl = safeInt(body[`size_l_${pIdx}`]);
    const sxl = safeInt(body[`size_xl_${pIdx}`]);
    const s2xl = safeInt(body[`size_2xl_${pIdx}`]);
    const s3xl = safeInt(body[`size_3xl_${pIdx}`]);

    const posTotal = s3xs + s2xs + sxs + ss + sm + sl + sxl + s2xl + s3xl;

    const embTypes = getAsArray(body[`emb_type_${pIdx}[]`] || body[`emb_type_${pIdx}`]);
    const embFormats = getAsArray(body[`emb_format_${pIdx}[]`] || body[`emb_format_${pIdx}`]);
    const embQuantities = getAsArray(body[`emb_quantity_${pIdx}[]`] || body[`emb_quantity_${pIdx}`]);
    const embList = [];

    for (let eI = 0; eI < embTypes.length; eI++) {
      const t = (embTypes[eI] || '').trim();
      if (t) {
        const eq = safeInt(embQuantities[eI], posTotal);
        const ef = (embFormats[eI] || 'A4').trim();
        embList.push({ type: t, format: ef, quantity: eq });
      }
    }

    positions.push({
      pos_index: pIdx,
      product_name: pProd,
      pattern_name: pPattern,
      fabric_name: pFabric,
      fabric_density: pDensity,
      fabric_color: pColor,
      size_3xs: s3xs,
      size_2xs: s2xs,
      size_xs: sxs,
      size_s: ss,
      size_m: sm,
      size_l: sl,
      size_xl: sxl,
      size_2xl: s2xl,
      size_3xl: s3xl,
      total_quantity: posTotal,
      embellishments: embList
    });
  }
  return positions;
}

// -------------------------------------------------------------
// ROUTES
// -------------------------------------------------------------

// 1. Calendar View
app.get('/', (req, res) => {
  const today = new Date();
  let year = safeInt(req.query.year, today.getFullYear());
  let month = safeInt(req.query.month, today.getMonth() + 1);
  const currentTab = req.query.tab === 'sample' ? 'sample' : 'batch';

  if (month < 1) {
    month = 12;
    year -= 1;
  } else if (month > 12) {
    month = 1;
    year += 1;
  }

  const allOrders = db.getOrdersByMonth(year, month);
  const batchOrders = allOrders.filter(o => o.order_type === 'batch');
  const sampleOrders = allOrders.filter(o => o.order_type === 'sample');

  const mainOrders = currentTab === 'batch' ? batchOrders : sampleOrders;
  const otherOrders = currentTab === 'batch' ? sampleOrders : [];

  const calendarData = planner.getMonthCalendar(year, month, mainOrders, otherOrders);

  const monthOrders = allOrders.filter(o => planner.touchesMonth(o, year, month));
  let totalItems = 0;
  for (const o of monthOrders) {
    totalItems += planner.calculateOrderPiecesForMonth(
      o.quantity || 0, o.start_date, o.start_q, o.end_date, o.end_q, year, month
    );
  }

  const activeBatches = new Set(monthOrders.filter(o => o.order_type === 'batch').map(o => o.id)).size;
  const activeSamples = new Set(monthOrders.filter(o => o.order_type === 'sample').map(o => o.id)).size;

  const monthDays = calendarData.filter(d => !d.is_other_month);
  const totalAvailableSlots = monthDays.length * 4;

  let occupiedSlots = 0;
  for (const d of monthDays) {
    const dStr = d.date_str;
    const parts = dStr.split('-').map(Number);
    const dAbsStart = planner.toOrdinal(parts[0], parts[1], parts[2]) * 4;
    const dAbsEnd = dAbsStart + 3;

    if (currentTab === 'batch') {
      for (const b of batchOrders) {
        for (const st of (b.stages || [])) {
          const sAbs = planner.dateToAbsQ(st.start, st.start_q);
          const eAbs = planner.dateToAbsQ(st.end, st.end_q);
          if (sAbs <= dAbsEnd && eAbs >= dAbsStart) {
            const qStart = Math.max(dAbsStart, sAbs);
            const qEnd = Math.min(dAbsEnd, eAbs);
            occupiedSlots += (qEnd - qStart + 1);
          }
        }
      }
    } else {
      for (const s of sampleOrders) {
        const sAbs = planner.dateToAbsQ(s.start_date, s.start_q);
        const eAbs = planner.dateToAbsQ(s.end_date, s.end_q);
        if (sAbs <= dAbsEnd && eAbs >= dAbsStart) {
          const qStart = Math.max(dAbsStart, sAbs);
          const qEnd = Math.min(dAbsEnd, eAbs);
          occupiedSlots += (qEnd - qStart + 1);
        }
      }
    }
  }

  let loadPercent = totalAvailableSlots > 0 ? Math.round((occupiedSlots / totalAvailableSlots) * 100) : 0;
  if (loadPercent > 100) loadPercent = 100;

  const ordersJson = mainOrders.map(o => ({
    id: o.id,
    num: o.order_number || o.id,
    name: o.name,
    qty: o.quantity || 0,
    type: o.order_type,
    start_date: o.start_date,
    start_q: o.start_q,
    end_date: o.end_date,
    end_q: o.end_q,
    stages: (o.stages || []).map(st => ({
      type: st.type || st.stage_type,
      start: st.start || st.start_date,
      start_q: st.start_q || 1,
      end: st.end || st.end_date,
      end_q: st.end_q || 4
    }))
  }));

  const mainOrdersJson = JSON.stringify(ordersJson);

  res.render('index.html', {
    calendar_data: calendarData,
    year,
    month,
    current_tab: currentTab,
    month_name: planner.getMonthName(month),
    prev_month: month > 1 ? month - 1 : 12,
    prev_year: month > 1 ? year : year - 1,
    next_month: month < 12 ? month + 1 : 1,
    next_year: month < 12 ? year : year + 1,
    now: { year: today.getFullYear(), month: today.getMonth() + 1 },
    load_percent: loadPercent,
    total_items: totalItems,
    active_batches: activeBatches,
    active_samples: activeSamples,
    main_orders_json: mainOrdersJson
  });
});

// 2. Day View
app.get('/day/:date_str', (req, res) => {
  const dateStr = req.params.date_str;
  const parsed = planner.safeParseDate(dateStr);
  if (!parsed) {
    req.flash('error', 'Некорректная дата');
    return res.redirect('/');
  }

  const targetDate = new Date(Date.UTC(parsed.year, parsed.month - 1, parsed.day));
  targetDate.strftime = (fmt) => {
    const d = String(parsed.day).padStart(2, '0');
    const m = String(parsed.month).padStart(2, '0');
    return `${d}.${m}.${parsed.year}`;
  };

  const groups = db.getStagesByDate(dateStr);
  res.render('day.html', { target_date: targetDate, groups });
});

// 3. Move Order API
app.post('/api/move_order', (req, res) => {
  const data = req.body || {};
  const orderId = safeInt(data.order_id);
  const newStartDate = data.new_start_date;
  const newStartQ = safeInt(data.new_start_q);

  if (!orderId || !newStartDate || !newStartQ) {
    return res.status(400).json({ success: false, error: 'Некорректные параметры' });
  }

  const result = db.getOrder(orderId);
  if (!result) {
    return res.status(404).json({ success: false, error: 'Заказ не найден' });
  }

  const [order, stages] = result;
  const oldStartAbs = planner.dateToAbsQ(order.start_date, order.start_q);
  const newStartAbs = planner.dateToAbsQ(newStartDate, newStartQ);
  const delta = newStartAbs - oldStartAbs;

  const occupied = db.getAllOccupiedSlots(orderId, order.order_type);
  const occMap = new Set();
  for (const slot of occupied) {
    const sAbs = planner.dateToAbsQ(slot.start_date, slot.start_q);
    const eAbs = planner.dateToAbsQ(slot.end_date, slot.end_q);
    for (let q = sAbs; q <= eAbs; q++) {
      occMap.add(q);
    }
  }

  if (order.order_type === 'sample') {
    const oldEndAbs = planner.dateToAbsQ(order.end_date, order.end_q);
    const newEndAbs = oldEndAbs + delta;
    for (let q = newStartAbs; q <= newEndAbs; q++) {
      if (occMap.has(q)) {
        return res.status(409).json({ success: false, error: 'Пересечение с занятым временем' });
      }
    }

    const [newEndDate, newEndQ] = planner.absToDateAndQ(newEndAbs);
    let newStages = stages.map(s => ({
      type: s.stage_type,
      start: newStartDate,
      start_q: newStartQ,
      end: newEndDate,
      end_q: newEndQ
    }));
    if (newStages.length === 0) {
      newStages = [{ type: 'Образец (Этапы не указаны)', start: newStartDate, start_q: newStartQ, end: newEndDate, end_q: newEndQ }];
    }

    db.updateOrder(orderId, order.name, order.client, order.contact, order.comment,
                   order.order_type, order.quantity, newStartDate, newStartQ,
                   newEndDate, newEndQ, newStages);
  } else {
    const newStages = [];
    let maxEndAbs = newStartAbs;
    for (const s of stages) {
      const stAbs = planner.dateToAbsQ(s.start_date, s.start_q) + delta;
      const enAbs = planner.dateToAbsQ(s.end_date, s.end_q) + delta;
      for (let q = stAbs; q <= enAbs; q++) {
        if (occMap.has(q)) {
          return res.status(409).json({ success: false, error: 'Пересечение с занятым временем' });
        }
      }
      const [stD, stQ] = planner.absToDateAndQ(stAbs);
      const [enD, enQ] = planner.absToDateAndQ(enAbs);
      newStages.push({ type: s.stage_type, start: stD, start_q: stQ, end: enD, end_q: enQ });
      if (enAbs > maxEndAbs) maxEndAbs = enAbs;
    }

    const [newMaxEndD, newMaxEndQ] = planner.absToDateAndQ(maxEndAbs);
    db.updateOrder(orderId, order.name, order.client, order.contact, order.comment,
                   order.order_type, order.quantity, newStartDate, newStartQ,
                   newMaxEndD, newMaxEndQ, newStages);
  }

  return res.json({ success: true });
});

// 4. Order Details Modal API
app.get(['/api/orders/:order_id', '/order/:order_id'], (req, res) => {
  try {
    const orderId = safeInt(req.params.order_id);
    const result = db.getOrder(orderId);
    if (!result) return res.status(404).json({ error: 'Заказ не найден' });
    const [order, stages] = result;

    for (const s of stages) {
      const startVal = String(s.start || s.start_date).slice(0, 10);
      const endVal = String(s.end || s.end_date).slice(0, 10);
      const [sy, sm, sd] = startVal.split('-');
      const [ey, em, ed] = endVal.split('-');
      s.start_formatted = `${sd}.${sm}.${sy} (ч.${s.start_q})`;
      s.end_formatted = `${ed}.${em}.${ey} (ч.${s.end_q})`;

      const sAbs = planner.dateToAbsQ(startVal, s.start_q);
      const eAbs = planner.dateToAbsQ(endVal, s.end_q);
      s.duration_days = (eAbs - sAbs + 1) / 4.0;
      s.stage_type = s.stage_type || s.type;
    }

    const orderStartVal = String(order.start_date || '2026-01-01').slice(0, 10);
    const orderEndVal = String(order.end_date || '2026-01-01').slice(0, 10);
    const orderSAbs = planner.dateToAbsQ(orderStartVal, order.start_q || 1);
    const orderEAbs = planner.dateToAbsQ(orderEndVal, order.end_q || 4);
    const totalDuration = (orderEAbs - orderSAbs + 1) / 4.0;

    return res.json({
      id: order.id,
      order_number: order.order_number || order.id,
      name: order.name,
      client: order.client || '',
      contact: order.contact || '',
      comment: order.comment || '',
      order_type: order.order_type,
      quantity: order.quantity || 0,
      start_date: order.start_date,
      start_q: order.start_q,
      total_duration: totalDuration,
      stages
    });
  } catch (e) {
    return res.status(500).json({ error: `Внутренняя ошибка сервера: ${e.message}` });
  }
});

// 5. Delete Order
app.post(['/api/orders/:order_id/delete', '/delete_order/:order_id'], (req, res) => {
  const orderId = safeInt(req.params.order_id);
  db.deleteOrder(orderId);
  req.flash('success', 'Заказ удален');

  const ref = req.get('Referrer') || '';
  if (ref.includes('/orders') || ref.includes('edit_order')) {
    return res.redirect('/orders');
  }
  if (ref.includes('/day/')) {
    return res.redirect(ref);
  }
  if (ref.includes('year=') || ref.includes('month=') || ref.includes('tab=') || ref.endsWith('/')) {
    return res.redirect(ref.includes('year=') || ref.includes('month=') ? ref : '/');
  }
  return res.redirect('/orders');
});

// 6. DB Backup & Restore
app.get('/download_db', (req, res) => {
  const dbFile = path.resolve(__dirname, 'production.db');
  const today = new Date().toISOString().slice(0, 10);
  res.download(dbFile, `production_${today}.db`);
});

app.post('/upload_db', upload.single('file'), (req, res) => {
  if (req.file) {
    const ext = path.extname(req.file.originalname).toLowerCase();
    if (ext === '.db') {
      const dest = path.resolve(__dirname, 'production.db');
      fs.copyFileSync(req.file.path, dest);
      try { fs.unlinkSync(req.file.path); } catch {}
      req.flash('success', 'База данных успешно восстановлена');
    }
  }
  return res.redirect(req.get('Referrer') || '/');
});

// 7. API Occupied Slots
app.get('/api/occupied', (req, res) => {
  const orderType = req.query.order_type || 'batch';
  const excludeId = safeInt(req.query.exclude_id, null);
  const slots = db.getAllOccupiedSlots(excludeId, orderType);
  return res.json(slots);
});

// 8. Orders List
app.get('/orders', (req, res) => {
  const sortBy = req.query.sort_by || 'order_number';
  const sortOrder = req.query.sort_order || 'desc';
  const search = (req.query.search || '').trim();
  const filterType = req.query.filter || 'all';
  const counts = db.getOrdersCounts();

  const page = safeInt(req.query.page, 1);
  let totalPages = 1;
  let currentPage = 1;
  let orders = [];
  let drafts = [];

  if (filterType === 'drafts') {
    const rawDrafts = db.getDraftsList(search);
    drafts = rawDrafts.map(d => {
      let fileCount = 0;
      let fileNames = [];
      try {
        if (d.data_json) {
          const parsed = JSON.parse(d.data_json);
          const dFiles = parsed.draft_files || {};
          for (const list of Object.values(dFiles)) {
            if (Array.isArray(list)) {
              for (const f of list) {
                const name = decodeFilename(typeof f === 'object' ? (f.name || f.file_name) : String(f));
                if (name && !fileNames.includes(name)) {
                  fileCount++;
                  fileNames.push(name);
                }
              }
            }
          }
        }
      } catch (e) {}
      return { ...d, file_count: fileCount, file_names: fileNames };
    });
  } else {
    const [fetchedOrders, tPages, cPage] = db.getOrdersList(sortBy, sortOrder, search, filterType, page, 50);
    orders = fetchedOrders;
    totalPages = tPages;
    currentPage = cPage;
  }

  const nextSortOrder = sortOrder === 'desc' ? 'asc' : 'desc';
  res.render('orders/orders_list.html', {
    orders,
    drafts,
    counts,
    sort_by: sortBy,
    sort_order: sortOrder,
    next_sort_order: nextSortOrder,
    search,
    filter_type: filterType,
    total_pages: totalPages,
    current_page: currentPage
  });
});

// 9. Order Detail
app.get('/orders/:order_id', (req, res) => {
  const orderId = safeInt(req.params.order_id);
  const data = db.getOrderFullDetails(orderId);
  if (!data) {
    req.flash('error', 'Заказ не найден');
    return res.redirect('/orders');
  }

  const [order, stages, files, items] = data;

  for (const s of stages) {
    const sStart = s.start_date || s.start;
    const sEnd = s.end_date || s.end;
    const sAbs = planner.dateToAbsQ(sStart, s.start_q || 1);
    const eAbs = planner.dateToAbsQ(sEnd, s.end_q || 1);
    s.duration_days = (sStart && sEnd) ? Math.max(0.25, (eAbs - sAbs + 1) / 4.0) : 0;
  }

  const sTotal = planner.dateToAbsQ(order.start_date, order.start_q || 1);
  const eTotal = planner.dateToAbsQ(order.end_date, order.end_q || 1);
  const totalDuration = (order.start_date && order.end_date) ? Math.max(0.25, (eTotal - sTotal + 1) / 4.0) : 0;

  const backUrl = req.query.from || 'orders';
  res.render('orders/order_detail.html', {
    order,
    stages,
    files,
    items,
    total_duration: totalDuration,
    back_url: backUrl
  });
});

// 10. Add Order
app.get('/add_order', (req, res) => {
  const nextNum = db.getNextAvailableOrderNumber();
  const todayStr = new Date().toISOString().slice(0, 10);
  const clients = db.getAllClients();
  res.render('add_order.html', {
    stage_list: STAGE_LIST,
    next_num: nextNum,
    today_str: todayStr,
    clients
  });
});

app.post('/add_order', upload.any(), (req, res) => {
  try {
    let orderNumber = safeInt(req.body.order_number, null);
    const creationDate = req.body.creation_date || new Date().toISOString().slice(0, 10);
    const orderType = req.body.order_type || 'batch';
    const name = (req.body.name || '').trim();

    if (!orderNumber) {
      orderNumber = db.getNextAvailableOrderNumber();
    } else if (db.checkOrderNumberTaken(orderNumber)) {
      req.flash('error', `Номер заказа ${orderNumber} уже занят! Выберите другой.`);
      return res.redirect('/add_order');
    }

    const clientName = (req.body.client_name || req.body.client_text || '').trim();
    const clientId = clientName ? db.getOrCreateClient(clientName) : null;

    const contactType = req.body.contact_type || 'Телефон';
    const contact = (req.body.contact || '').trim();
    const amount = safeFloat(req.body.amount);
    const comment = (req.body.comment || '').trim();
    const oStart = req.body.order_start_date || new Date().toISOString().slice(0, 10);
    const oStartQ = safeInt(req.body.order_start_q, 1);

    if (!name) {
      req.flash('error', 'Название заказа обязательно');
      return res.redirect('/add_order');
    }

    const positions = parsePositionsFromForm(req.body);
    let quantity = 0;
    if (positions.length > 0) {
      quantity = positions.reduce((acc, p) => acc + (p.total_quantity || 0), 0);
    } else {
      quantity = safeInt(req.body.quantity, 0);
    }

    const stages = [];
    let orderId;

    if (orderType === 'sample') {
      const sEnd = req.body.sample_end_date || oStart;
      const sEndQ = safeInt(req.body.sample_end_q, oStartQ);
      const sampleStages = getAsArray(req.body['sample_stages[]'] || req.body['sample_stages']);
      for (const st of sampleStages) {
        if ((st || '').trim()) {
          stages.push({ type: st.trim(), start: oStart, start_q: oStartQ, end: sEnd, end_q: sEndQ });
        }
      }
      if (stages.length === 0) {
        stages.push({ type: 'Образец', start: oStart, start_q: oStartQ, end: sEnd, end_q: sEndQ });
      }

      orderId = db.addOrder(
        name, clientName, contact, comment, orderType, quantity, oStart, oStartQ, sEnd, sEndQ, stages,
        { orderNumber, clientId, contactType, amount, createdAt: creationDate, positions }
      );
    } else {
      const types = getAsArray(req.body['stage_type[]'] || req.body['stage_type']);
      const starts = getAsArray(req.body['start_date[]'] || req.body['start_date']);
      const startQs = getAsArray(req.body['start_q[]'] || req.body['start_q']);
      const ends = getAsArray(req.body['end_date[]'] || req.body['end_date']);
      const endQs = getAsArray(req.body['end_q[]'] || req.body['end_q']);

      for (let i = 0; i < types.length; i++) {
        const t = (types[i] || '').trim();
        if (!t) continue;
        const st = (starts[i] && starts[i].trim()) ? starts[i].trim() : oStart;
        const stQ = safeInt(startQs[i], 1);
        const en = (ends[i] && ends[i].trim()) ? ends[i].trim() : st;
        const enQ = safeInt(endQs[i], 4);
        stages.push({ type: t, start: st, start_q: stQ, end: en, end_q: enQ });
      }

      if (stages.length === 0) {
        req.flash('error', 'Добавьте хотя бы один этап производства');
        return res.redirect('/add_order');
      }

      let maxStage = stages[0];
      let maxAbs = planner.dateToAbsQ(maxStage.end, maxStage.end_q);
      for (let i = 1; i < stages.length; i++) {
        const curAbs = planner.dateToAbsQ(stages[i].end, stages[i].end_q);
        if (curAbs > maxAbs) {
          maxAbs = curAbs;
          maxStage = stages[i];
        }
      }

      orderId = db.addOrder(
        name, clientName, contact, comment, orderType, quantity, oStart, oStartQ, maxStage.end, maxStage.end_q, stages,
        { orderNumber, clientId, contactType, amount, createdAt: creationDate, positions }
      );
    }

    // Save uploaded files & draft files
    try {
      const loadedDraftId = safeInt(req.body.loaded_draft_id, null);
      let draftFiles = {};
      if (loadedDraftId) {
        try {
          const draftObj = db.getDraft(loadedDraftId);
          if (draftObj && draftObj.data_json) {
            const draftData = JSON.parse(draftObj.data_json);
            draftFiles = draftData.draft_files || {};
          }
          db.deleteDraft(loadedDraftId);
        } catch {}
      }

      const filesList = req.files || [];
      const allowedExts = new Set(['.png', '.jpg', '.jpeg', '.pdf', '.ai', '.psd', '.cdr', '.svg', '.tif', '.tiff', '.zip', '.rar']);

      for (const p of positions) {
        const pIdx = p.pos_index || 1;
        const inputName = `pos_files_${pIdx}`;

        for (const file of filesList) {
          if (file.fieldname === inputName && file.originalname) {
            const decodedName = decodeFilename(file.originalname);
            const ext = path.extname(decodedName).toLowerCase();
            if (!allowedExts.has(ext)) continue;
            const diskName = `${orderId}_${crypto.randomUUID().slice(0, 8)}${ext}`;
            const destPath = path.join(uploadDir, diskName);
            fs.copyFileSync(file.path, destPath);
            try { fs.unlinkSync(file.path); } catch {}
            db.addOrderFile(orderId, decodedName, `uploads/${diskName}`, safeInt(pIdx, 1));
          }
        }

        if (draftFiles[inputName]) {
          for (const dFile of draftFiles[inputName]) {
            const origName = decodeFilename(typeof dFile === 'object' ? (dFile.name || dFile.file_name) : String(dFile));
            const origPath = typeof dFile === 'object' ? (dFile.path || dFile.file_path) : '';
            if (origName && origPath) {
              const fullSrc = path.resolve(__dirname, 'app/static', origPath);
              if (fs.existsSync(fullSrc)) {
                const ext = path.extname(origName).toLowerCase();
                const diskName = `${orderId}_${crypto.randomUUID().slice(0, 8)}${ext}`;
                const destPath = path.join(uploadDir, diskName);
                try {
                  fs.copyFileSync(fullSrc, destPath);
                  db.addOrderFile(orderId, origName, `uploads/${diskName}`, safeInt(pIdx, 1));
                } catch {
                  db.addOrderFile(orderId, origName, origPath, safeInt(pIdx, 1));
                }
              } else {
                db.addOrderFile(orderId, origName, origPath, safeInt(pIdx, 1));
              }
            }
          }
        }
      }

      // Order-level or unassigned files from draft
      for (const [dfKey, dfList] of Object.entries(draftFiles)) {
        if (dfKey.startsWith('pos_files_') && positions.some(p => `pos_files_${p.pos_index || 1}` === dfKey)) {
          continue; // Already processed above
        }
        if (Array.isArray(dfList)) {
          for (const dFile of dfList) {
            const origName = typeof dFile === 'object' ? (dFile.name || dFile.file_name) : String(dFile);
            const origPath = typeof dFile === 'object' ? (dFile.path || dFile.file_path) : '';
            if (origName && origPath) {
              const fullSrc = path.resolve(__dirname, 'app/static', origPath);
              if (fs.existsSync(fullSrc)) {
                const ext = path.extname(origName).toLowerCase();
                const diskName = `${orderId}_${crypto.randomUUID().slice(0, 8)}${ext}`;
                const destPath = path.join(uploadDir, diskName);
                try {
                  fs.copyFileSync(fullSrc, destPath);
                  db.addOrderFile(orderId, origName, `uploads/${diskName}`, 1);
                } catch {
                  db.addOrderFile(orderId, origName, origPath, 1);
                }
              } else {
                db.addOrderFile(orderId, origName, origPath, 1);
              }
            }
          }
        }
      }
    } catch (e) {
      console.error('File saving error:', e);
    }

    req.flash('success', `Заказ #${orderNumber} успешно создан`);
    return res.redirect(`/orders/${orderId}`);
  } catch (e) {
    req.flash('error', `Ошибка при создании заказа: ${e.message}`);
    return res.redirect('/add_order');
  }
});

// 11. Edit Order
app.get('/edit_order/:order_id', (req, res) => {
  const orderId = safeInt(req.params.order_id);
  const data = db.getOrderFullDetails(orderId);
  if (!data) {
    req.flash('error', 'Заказ не найден');
    return res.redirect('/orders');
  }
  const [order, stages, files, items] = data;

  for (const s of stages) {
    const sStart = s.start_date || s.start;
    const sEnd = s.end_date || s.end;
    const sAbs = planner.dateToAbsQ(sStart, s.start_q || 1);
    const eAbs = planner.dateToAbsQ(sEnd, s.end_q || 1);
    s.duration_days = (sStart && sEnd) ? Math.max(0.25, (eAbs - sAbs + 1) / 4.0) : 0;
  }

  const clients = db.getAllClients();
  res.render('edit_order.html', { stage_list: STAGE_LIST, order, stages, files, clients, items_json: JSON.stringify(items || []), stages_json: JSON.stringify(stages || []) });
});

app.post('/edit_order/:order_id', upload.any(), (req, res) => {
  const orderId = safeInt(req.params.order_id);
  const data = db.getOrderFullDetails(orderId);
  if (!data) {
    req.flash('error', 'Заказ не найден');
    return res.redirect('/orders');
  }
  const [order] = data;

  try {
    const orderNumber = safeInt(req.body.order_number, order.order_number || orderId);
    if (orderNumber && db.checkOrderNumberTaken(orderNumber, orderId)) {
      req.flash('error', `Номер заказа ${orderNumber} уже занят! Выберите другой.`);
      return res.redirect(`/edit_order/${orderId}`);
    }

    const name = (req.body.name || '').trim();
    if (!name) {
      req.flash('error', 'Название заказа обязательно');
      return res.redirect(`/edit_order/${orderId}`);
    }

    const clientName = (req.body.client_name || '').trim();
    const clientId = clientName ? db.getOrCreateClient(clientName) : null;

    const creationDate = req.body.creation_date || new Date().toISOString().slice(0, 10);
    const amount = safeFloat(req.body.amount);
    const orderType = req.body.order_type || order.order_type || 'batch';
    const contact = (req.body.contact || '').trim();
    const comment = (req.body.comment || '').trim();
    const oStart = req.body.order_start_date || order.start_date || new Date().toISOString().slice(0, 10);
    const oStartQ = safeInt(req.body.order_start_q, order.start_q || 1);

    const types = getAsArray(req.body['stage_type[]'] || req.body['stage_type']);
    const starts = getAsArray(req.body['start_date[]'] || req.body['start_date']);
    const startQs = getAsArray(req.body['start_q[]'] || req.body['start_q']);
    const ends = getAsArray(req.body['end_date[]'] || req.body['end_date']);
    const endQs = getAsArray(req.body['end_q[]'] || req.body['end_q']);

    const newStages = [];
    for (let i = 0; i < types.length; i++) {
      const t = (types[i] || '').trim();
      if (!t) continue;
      const st = (starts[i] && starts[i].trim()) ? starts[i].trim() : oStart;
      const stQ = safeInt(startQs[i], 1);
      const en = (ends[i] && ends[i].trim()) ? ends[i].trim() : st;
      const enQ = safeInt(endQs[i], 4);
      newStages.push({ type: t, start: st, start_q: stQ, end: en, end_q: enQ });
    }

    if (newStages.length === 0) {
      if (orderType === 'sample') {
        newStages.push({ type: 'Образец', start: oStart, start_q: oStartQ, end: oStart, end_q: oStartQ });
      } else {
        req.flash('error', 'Добавьте хотя бы один этап производства');
        return res.redirect(`/edit_order/${orderId}`);
      }
    }

    let maxStage = newStages[0];
    let maxAbs = planner.dateToAbsQ(maxStage.end, maxStage.end_q);
    for (let i = 1; i < newStages.length; i++) {
      const curAbs = planner.dateToAbsQ(newStages[i].end, newStages[i].end_q);
      if (curAbs > maxAbs) {
        maxAbs = curAbs;
        maxStage = newStages[i];
      }
    }

    const oEnd = maxStage.end;
    const oEndQ = safeInt(maxStage.end_q, 4);
    
    const positions = parsePositionsFromForm(req.body);
    let quantity = 0;
    for (const pos of positions) {
      quantity += safeInt(pos.total_quantity);
    }

    db.updateOrderFull(
      orderId, name, clientName, contact, comment, orderType, quantity,
      oStart, oStartQ, oEnd, oEndQ, newStages,
      {
        orderNumber,
        clientId,
        contactType: order.contact_type || 'Телефон',
        amount,
        createdAt: creationDate,
        positions: positions
      }

    );

    // Save new files
    try {
      const filesList = req.files || [];
      const allowedExts = new Set(['.png', '.jpg', '.jpeg', '.pdf', '.ai', '.psd', '.cdr', '.svg', '.tif', '.tiff', '.zip', '.rar']);
      for (const file of filesList) {
        if (file.fieldname === 'order_files' && file.originalname) {
          const decodedName = decodeFilename(file.originalname);
          const ext = path.extname(decodedName).toLowerCase();
          if (!allowedExts.has(ext)) continue;
          const diskName = `${orderId}_${crypto.randomUUID().slice(0, 8)}${ext}`;
          const destPath = path.join(uploadDir, diskName);
          fs.copyFileSync(file.path, destPath);
          try { fs.unlinkSync(file.path); } catch {}
          db.addOrderFile(orderId, decodedName, `uploads/${diskName}`, 1);
        }
      }
    } catch {}

    req.flash('success', `Заказ #${orderNumber} успешно обновлен`);
    return res.redirect(`/orders/${orderId}`);
  } catch (e) {
    req.flash('error', `Ошибка при обновлении заказа: ${e.message}`);
    return res.redirect(`/edit_order/${orderId}`);
  }
});

// 12. Delete File
app.post('/delete_file/:file_id', (req, res) => {
  const fileId = safeInt(req.params.file_id);
  const orderId = req.body.order_id;
  const filePath = db.deleteOrderFile(fileId);
  if (filePath) {
    try {
      const fullPath = path.resolve(__dirname, 'app/static', filePath);
      if (fs.existsSync(fullPath)) fs.unlinkSync(fullPath);
    } catch {}
  }
  req.flash('success', 'Файл удален');
  if (orderId) return res.redirect(`/edit_order/${orderId}`);
  return res.redirect(req.get('Referrer') || '/orders');
});

// 13. Delete Draft
app.post('/delete_draft/:draft_id', (req, res) => {
  const draftId = safeInt(req.params.draft_id);
  db.deleteDraft(draftId);
  req.flash('success', 'Черновик удален');
  return res.redirect('/orders?filter=drafts');
});

// 14. Check Order Number Taken API
app.get('/api/check_order_number', (req, res) => {
  const num = safeInt(req.query.number, null);
  const excludeId = safeInt(req.query.exclude_id, null);
  const taken = db.checkOrderNumberTaken(num, excludeId);
  return res.json({ taken });
});


// References API
app.get('/api/references', (req, res) => {
  const productsRows = db.getAllProducts();
  const productsList = productsRows.map(p => p.name);
  const patternsMap = {};
  for (const p of productsRows) {
    patternsMap[p.name] = db.getPatternsByProduct(p.id).map(x => x.name);
  }

  const fabricsRows = db.getAllFabrics();
  const fabricsList = fabricsRows.map(f => f.name);
  const densitiesMap = {};
  for (const f of fabricsRows) {
    densitiesMap[f.name] = db.getDensitiesByFabric(f.id).map(x => x.name);
  }

  res.json({
    products: productsList,
    patterns: patternsMap,
    fabrics: fabricsList,
    densities: densitiesMap
  });
});

// 15. Drafts API
app.get('/api/drafts', (req, res) => {
  const drafts = db.getAllDrafts();
  return res.json(drafts);
});

app.post('/api/drafts', upload.any(), (req, res) => {
  let data = {};
  const isMultipart = req.headers['content-type'] && req.headers['content-type'].includes('multipart/form-data');

  if (isMultipart) {
    const payloadStr = req.body.payload || '{}';
    try { data = JSON.parse(payloadStr); } catch { data = {}; }
    const draftFiles = data.draft_files || {};
    const filesList = req.files || [];
    const allowedExts = new Set(['.png', '.jpg', '.jpeg', '.pdf', '.ai', '.psd', '.cdr', '.svg', '.tif', '.tiff', '.zip', '.rar']);

    for (const file of filesList) {
      if (file.originalname) {
        const decodedName = decodeFilename(file.originalname);
        const ext = path.extname(decodedName).toLowerCase();
        if (!allowedExts.has(ext)) continue;

        const key = file.fieldname;
        if (!draftFiles[key]) draftFiles[key] = [];

        const existingNames = new Set(draftFiles[key].map(item => decodeFilename(typeof item === 'object' ? item.name : item)));
        if (existingNames.has(decodedName)) continue;

        const diskName = `draft_${crypto.randomUUID().slice(0, 8)}${ext}`;
        const relPath = `uploads/drafts/${diskName}`;
        const destPath = path.join(draftsDir, diskName);
        fs.copyFileSync(file.path, destPath);
        try { fs.unlinkSync(file.path); } catch {}

        draftFiles[key].push({ name: decodedName, path: relPath });
      }
    }

    data.draft_files = draftFiles;
  } else {
    data = req.body || {};
  }

  const title = (data.title || 'Черновик').trim() || 'Черновик';
  const draftId = safeInt(data.draft_id, null);
  const savedId = db.saveDraft(title, JSON.stringify(data), draftId);

  if (isMultipart) {
    req.flash('success', 'Черновик сохранён');
  }

  return res.json({ success: true, draft_id: savedId, draft_files: data.draft_files || {} });
});

app.get('/api/drafts/:draft_id', (req, res) => {
  const draftId = safeInt(req.params.draft_id);
  const draft = db.getDraft(draftId);
  if (!draft) return res.status(404).json({ error: 'Черновик не найден' });
  return res.json(draft);
});

app.delete('/api/drafts/:draft_id', (req, res) => {
  const draftId = safeInt(req.params.draft_id);
  db.deleteDraft(draftId);
  return res.json({ success: true });
});

// Start Server
app.listen(PORT, '0.0.0.0', () => {
  console.log(`Server running on http://0.0.0.0:${PORT}`);
});
