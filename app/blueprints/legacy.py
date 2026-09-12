import json
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, send_file
from datetime import datetime, date
import calendar
from app.models import database
from app.services import planner
import os

legacy_bp = Blueprint('legacy', __name__)

STAGE_LIST = [
    'Раскрой', 'Пошив', 'Упаковка', 'ВТО и упаковка', 'Отгрузка', 'Разгрузка',
    'DTF', 'Вышивка', 'Шелкография', 'Разработка лекал', 'Бирки'
]

@legacy_bp.app_template_filter('format_date')
def format_date_filter(date_str):
    if not date_str:
        return ''
    try:
        return datetime.strptime(str(date_str)[:10], '%Y-%m-%d').strftime('%d.%m.%Y')
    except:
        return str(date_str)

def safe_parse_date(d_val):
    if not d_val:
        return None
    try:
        clean_str = str(d_val).strip()[:10]
        return date.fromisoformat(clean_str)
    except:
        return None

def date_to_abs_q(d_str, q):
    d = safe_parse_date(d_str)
    if not d:
        return 0
    try:
        q_int = int(q or 1)
    except:
        q_int = 1
    return d.toordinal() * 4 + max(1, min(4, q_int)) - 1

def abs_to_date_and_q(abs_q):
    try:
        d = date.fromordinal(int(abs_q) // 4)
        return d.isoformat(), (int(abs_q) % 4) + 1
    except:
        return date.today().isoformat(), 1

def touches_month(order, year, month):
    start_d = safe_parse_date(order.get('start_date'))
    end_d = safe_parse_date(order.get('end_date'))
    if not start_d or not end_d:
        return False
    try:
        m_start = date(year, month, 1)
        _, last_day = calendar.monthrange(year, month)
        m_end = date(year, month, last_day)
        return not (end_d < m_start or start_d > m_end)
    except:
        return False

def calculate_order_pieces_for_month(quantity, start_date_str, start_q, end_date_str, end_q, target_year, target_month):
    if not quantity or quantity <= 0 or not start_date_str or not end_date_str:
        return 0
    
    s_abs = date_to_abs_q(start_date_str, start_q)
    e_abs = date_to_abs_q(end_date_str, end_q)
    total_q = e_abs - s_abs + 1
    if total_q <= 0:
        return 0

    s_date = date.fromordinal(s_abs // 4)
    e_date = date.fromordinal(e_abs // 4)

    months = []
    curr_y, curr_m = s_date.year, s_date.month
    end_y, end_m = e_date.year, e_date.month

    while (curr_y < end_y) or (curr_y == end_y and curr_m <= end_m):
        months.append((curr_y, curr_m))
        if curr_m == 12:
            curr_y += 1
            curr_m = 1
        else:
            curr_m += 1

    if len(months) == 1:
        return quantity if (target_year, target_month) == months[0] else 0

    month_durations = []
    for idx, (y, m) in enumerate(months):
        m_start_date = date(y, m, 1)
        _, last_day = calendar.monthrange(y, m)
        m_end_date = date(y, m, last_day)

        m_start_abs = m_start_date.toordinal() * 4
        m_end_abs = m_end_date.toordinal() * 4 + 3

        overlap_start = max(s_abs, m_start_abs)
        overlap_end = min(e_abs, m_end_abs)
        dur = max(0, overlap_end - overlap_start + 1)
        month_durations.append({'year': y, 'month': m, 'dur': dur, 'idx': idx})

    allocated = {}
    remainders = []
    base_sum = 0
    for item in month_durations:
        dur = item['dur']
        exact = (quantity * dur) / total_q
        base = int(exact)
        allocated[(item['year'], item['month'])] = base
        base_sum += base
        remainders.append((dur, item['idx'], item['year'], item['month']))

    leftover = quantity - base_sum
    remainders.sort(key=lambda x: (x[0], x[1]), reverse=True)

    for i in range(leftover):
        dur, idx, y, m = remainders[i]
        allocated[(y, m)] += 1

    return allocated.get((target_year, target_month), 0)

@legacy_bp.route('/')
def index():
    today = date.today()
    year = request.args.get('year', today.year, type=int)
    month = request.args.get('month', today.month, type=int)
    current_tab = request.args.get('tab', 'batch')

    if month < 1: month, year = 12, year - 1
    elif month > 12: month, year = 1, year + 1
    
    all_orders = database.get_orders_by_month(year, month)
    batch_orders = [o for o in all_orders if o.get('order_type') == 'batch']
    sample_orders = [o for o in all_orders if o.get('order_type') == 'sample']
    
    main_orders = batch_orders if current_tab == 'batch' else sample_orders
    other_orders = sample_orders if current_tab == 'batch' else []
    
    calendar_data = planner.get_month_calendar(year, month, main_orders, other_orders)
    
    month_orders = [o for o in all_orders if touches_month(o, year, month)]
    total_items = sum(calculate_order_pieces_for_month(
        o.get('quantity', 0), o['start_date'], o['start_q'], o['end_date'], o['end_q'], year, month
    ) for o in month_orders)

    active_batches = len(set(o['id'] for o in month_orders if o.get('order_type') == 'batch'))
    active_samples = len(set(o['id'] for o in month_orders if o.get('order_type') == 'sample'))
    
    month_days = [d for d in calendar_data if not d.get('is_other_month')]
    # Расчет независимой загруженности: для каждого цеха свои 4 слота в день
    month_days = [d for d in calendar_data if not d.get('is_other_month')]
    total_available_slots = len(month_days) * 4  # 4 слота цеха на рабочий день
    
    occupied_slots = 0
    for d in month_days:
        d_str = d['date_str']
        d_abs_start = date.fromisoformat(d_str).toordinal() * 4
        d_abs_end = d_abs_start + 3
        
        if current_tab == 'batch':
            for b in batch_orders:
                for st in b.get('stages', []):
                    s_abs = date_to_abs_q(st['start'], st['start_q'])
                    e_abs = date_to_abs_q(st['end'], st['end_q'])
                    if s_abs <= d_abs_end and e_abs >= d_abs_start:
                        q_start = max(d_abs_start, s_abs)
                        q_end = min(d_abs_end, e_abs)
                        occupied_slots += (q_end - q_start + 1)
        else:
            for s in sample_orders:
                s_abs = date_to_abs_q(s['start_date'], s['start_q'])
                e_abs = date_to_abs_q(s['end_date'], s['end_q'])
                if s_abs <= d_abs_end and e_abs >= d_abs_start:
                    q_start = max(d_abs_start, s_abs)
                    q_end = min(d_abs_end, e_abs)
                    occupied_slots += (q_end - q_start + 1)
                
    load_percent = int(round((occupied_slots / total_available_slots) * 100)) if total_available_slots > 0 else 0
    if load_percent > 100: load_percent = 100
    
        # Подготовка JSON данных заказов для мгновенного перетаскивания (без задержек сети)
    orders_json = []
    for o in main_orders:
        orders_json.append({
            'id': o['id'],
            'num': o.get('order_number') or o['id'],
            'name': o['name'],
            'qty': o.get('quantity') or 0,
            'type': o.get('order_type'),
            'start_date': o['start_date'],
            'start_q': o['start_q'],
            'end_date': o['end_date'],
            'end_q': o['end_q'],
            'stages': [{
                'type': st.get('type') or st.get('stage_type'),
                'start': st.get('start') or st.get('start_date'),
                'start_q': st.get('start_q', 1),
                'end': st.get('end') or st.get('end_date'),
                'end_q': st.get('end_q', 4)
            } for st in o.get('stages', [])]
        })
    main_orders_json = json.dumps(orders_json, ensure_ascii=False)

    return render_template('index.html', calendar_data=calendar_data, year=year, month=month, current_tab=current_tab,
                           month_name=planner.get_month_name(month), prev_month=month-1 if month>1 else 12, prev_year=year if month>1 else year-1,
                           next_month=month+1 if month<12 else 1, next_year=year if month<12 else year+1, 
                           now=today, load_percent=load_percent, total_items=total_items,
                           active_batches=active_batches, active_samples=active_samples, main_orders_json=main_orders_json)

@legacy_bp.route('/day/<date_str>')
def day_view(date_str):
    try: target_date = datetime.strptime(date_str, '%Y-%m-%d').date()
    except ValueError:
        flash('Некорректная дата', 'error')
        return redirect(url_for('legacy.index'))
    return render_template('day.html', target_date=target_date, groups=database.get_stages_by_date(date_str))

@legacy_bp.route('/api/move_order', methods=['POST'])
def api_move_order():
    data = request.get_json() or {}
    order_id = data.get('order_id')
    new_start_date = data.get('new_start_date')
    new_start_q = data.get('new_start_q')
    
    if not order_id or not new_start_date or not new_start_q:
        return jsonify({'success': False, 'error': 'Некорректные параметры'}), 400
        
    result = database.get_order(order_id)
    if not result:
        return jsonify({'success': False, 'error': 'Заказ не найден'}), 404
        
    order, stages = result
    old_start_abs = date_to_abs_q(order['start_date'], order['start_q'])
    new_start_abs = date_to_abs_q(new_start_date, int(new_start_q))
    delta = new_start_abs - old_start_abs
    
    occupied = database.get_all_occupied_slots(exclude_order_id=order_id, order_type=order['order_type'])
    occ_map = {}
    for slot in occupied:
        s_abs = date_to_abs_q(slot['start_date'], slot['start_q'])
        e_abs = date_to_abs_q(slot['end_date'], slot['end_q'])
        for q in range(s_abs, e_abs + 1):
            occ_map[q] = True
            
    if order['order_type'] == 'sample':
        old_end_abs = date_to_abs_q(order['end_date'], order['end_q'])
        new_end_abs = old_end_abs + delta
        for q in range(new_start_abs, new_end_abs + 1):
            if occ_map.get(q):
                return jsonify({'success': False, 'error': 'Пересечение с занятым временем'}), 409
        
        new_end_date, new_end_q = abs_to_date_and_q(new_end_abs)
        new_stages = []
        for s in stages:
            new_stages.append({
                'type': s['stage_type'],
                'start': new_start_date, 'start_q': int(new_start_q),
                'end': new_end_date, 'end_q': int(new_end_q)
            })
        if not new_stages:
            new_stages = [{'type': 'Образец (Этапы не указаны)', 'start': new_start_date, 'start_q': int(new_start_q), 'end': new_end_date, 'end_q': int(new_end_q)}]
            
        database.update_order(order_id, order['name'], order['client'], order['contact'], order['comment'],
                              order['order_type'], order['quantity'], new_start_date, int(new_start_q),
                              new_end_date, int(new_end_q), new_stages)
    else:
        new_stages = []
        max_end_abs = new_start_abs
        for s in stages:
            st_abs = date_to_abs_q(s['start_date'], s['start_q']) + delta
            en_abs = date_to_abs_q(s['end_date'], s['end_q']) + delta
            for q in range(st_abs, en_abs + 1):
                if occ_map.get(q):
                    return jsonify({'success': False, 'error': 'Пересечение с занятым временем'}), 409
            st_d, st_q = abs_to_date_and_q(st_abs)
            en_d, en_q = abs_to_date_and_q(en_abs)
            new_stages.append({'type': s['stage_type'], 'start': st_d, 'start_q': st_q, 'end': en_d, 'end_q': en_q})
            if en_abs > max_end_abs:
                max_end_abs = en_abs
                
        new_max_end_d, new_max_end_q = abs_to_date_and_q(max_end_abs)
        database.update_order(order_id, order['name'], order['client'], order['contact'], order['comment'],
                              order['order_type'], order['quantity'], new_start_date, int(new_start_q),
                              new_max_end_d, int(new_max_end_q), new_stages)
                              
    return jsonify({'success': True})

@legacy_bp.route('/order/<int:order_id>')
def order_view(order_id):
    try:
        result = database.get_order(order_id)
        if not result: return jsonify({'error': 'Заказ не найден'}), 404
        order, stages = result
        
        for s in stages:
            start_val = str(s.get('start', s.get('start_date')))[:10]
            end_val = str(s.get('end', s.get('end_date')))[:10]
            s['start_formatted'] = f"{datetime.strptime(start_val, '%Y-%m-%d').strftime('%d.%m.%Y')} (ч.{s['start_q']})"
            s['end_formatted'] = f"{datetime.strptime(end_val, '%Y-%m-%d').strftime('%d.%m.%Y')} (ч.{s['end_q']})"
            s_abs = date.fromisoformat(start_val).toordinal() * 4 + int(s['start_q']) - 1
            e_abs = date.fromisoformat(end_val).toordinal() * 4 + int(s['end_q']) - 1
            s['duration_days'] = (e_abs - s_abs + 1) / 4.0
            s['stage_type'] = s.get('stage_type', s.get('type'))
            
        order_s_abs = date.fromisoformat(str(order.get('start_date') or '2026-01-01')[:10]).toordinal() * 4 + int(order.get('start_q') or 1) - 1
        order_e_abs = date.fromisoformat(str(order.get('end_date') or '2026-01-01')[:10]).toordinal() * 4 + int(order.get('end_q') or 4) - 1
        total_duration = (order_e_abs - order_s_abs + 1) / 4.0
        
        return jsonify({
            'id': order['id'], 
            'order_number': order.get('order_number') or order['id'],
            'name': order['name'], 
            'client': order['client'] or '', 
            'contact': order['contact'] or '',
            'comment': order.get('comment') or '',
            'order_type': order['order_type'], 
            'quantity': order['quantity'] or 0,
            'start_date': order['start_date'], 
            'start_q': order['start_q'],
            'total_duration': total_duration, 
            'stages': stages
        })
    except Exception as e: return jsonify({'error': f'Внутренняя ошибка сервера: {str(e)}'}), 500

@legacy_bp.route('/delete_order/<int:order_id>', methods=['POST'])
def delete_order(order_id):
    database.delete_order(order_id)
    flash('Заказ удален', 'success')
    ref = request.referrer or ''
    if '/orders/' in ref or 'edit_order' in ref:
        return redirect(url_for('orders.orders_list'))
    if '/day/' in ref:
        return redirect(ref)
    if 'year=' in ref or 'month=' in ref or 'tab=' in ref or ref.endswith('/'):
        return redirect(ref if ('year=' in ref or 'month=' in ref) else url_for('legacy.index'))
    return redirect(url_for('orders.orders_list'))

@legacy_bp.route('/download_db')
def download_db():
    return send_file(database.DB_PATH, as_attachment=True, download_name=f"production_{date.today()}.db")

@legacy_bp.route('/upload_db', methods=['POST'])
def upload_db():
    if 'file' not in request.files: return redirect(request.referrer or url_for('legacy.index'))
    file = request.files['file']
    if file.filename.endswith('.db'):
        file.save(database.DB_PATH)
        flash('База данных успешно восстановлена', 'success')
    return redirect(request.referrer or url_for('legacy.index'))

@legacy_bp.route('/api/occupied')
def api_occupied():
    order_type = request.args.get('order_type', 'batch')
    exclude_id = request.args.get('exclude_id', type=int)
    slots = database.get_all_occupied_slots(exclude_order_id=exclude_id, order_type=order_type)
    return jsonify(slots)
