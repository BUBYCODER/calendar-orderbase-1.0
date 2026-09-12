import os
import uuid
import json
from datetime import date
from flask import Blueprint, render_template, request, redirect, url_for, flash, jsonify, current_app
from app.models import database, dict_model

orders_bp = Blueprint('orders', __name__)

STAGE_LIST = [
    'Раскрой', 'Пошив', 'Упаковка', 'ВТО и упаковка', 'Отгрузка', 'Разгрузка',
    'DTF', 'Вышивка', 'Шелкография', 'Разработка лекал', 'Бирки'
]

def safe_int(val, default=0):
    if val is None: return default
    try:
        clean = str(val).strip()
        return int(clean) if clean else default
    except: return default

def safe_float(val, default=0.0):
    if val is None: return default
    try:
        clean = str(val).strip().replace(' ', '').replace(',', '.')
        return float(clean) if clean else default
    except: return default

def safe_date_obj(d_val, fallback=None):
    if not d_val: return fallback or date.today()
    try:
        clean = str(d_val).strip()[:10]
        return date.fromisoformat(clean)
    except: return fallback or date.today()

def parse_positions_from_form(req_form):
    pos_indexes = req_form.getlist('pos_index[]')
    positions = []
    
    for p_idx in pos_indexes:
        p_prod = req_form.get(f'product_{p_idx}', '').strip()
        p_pattern = req_form.get(f'pattern_{p_idx}', '').strip()
        p_fabric = req_form.get(f'fabric_{p_idx}', '').strip()
        p_density = req_form.get(f'density_{p_idx}', '').strip()
        p_color = req_form.get(f'color_{p_idx}', '').strip()

        s_3xs = safe_int(req_form.get(f'size_3xs_{p_idx}'))
        s_2xs = safe_int(req_form.get(f'size_2xs_{p_idx}'))
        s_xs = safe_int(req_form.get(f'size_xs_{p_idx}'))
        s_s = safe_int(req_form.get(f'size_s_{p_idx}'))
        s_m = safe_int(req_form.get(f'size_m_{p_idx}'))
        s_l = safe_int(req_form.get(f'size_l_{p_idx}'))
        s_xl = safe_int(req_form.get(f'size_xl_{p_idx}'))
        s_2xl = safe_int(req_form.get(f'size_2xl_{p_idx}'))
        s_3xl = safe_int(req_form.get(f'size_3xl_{p_idx}'))

        pos_total = s_3xs + s_2xs + s_xs + s_s + s_m + s_l + s_xl + s_2xl + s_3xl

        emb_types = req_form.getlist(f'emb_type_{p_idx}[]')
        emb_formats = req_form.getlist(f'emb_format_{p_idx}[]')
        emb_quantities = req_form.getlist(f'emb_quantity_{p_idx}[]')
        emb_list = []
        for e_i in range(len(emb_types)):
            if emb_types[e_i].strip():
                eq = safe_int(emb_quantities[e_i] if e_i < len(emb_quantities) else None, default=pos_total)
                ef = emb_formats[e_i].strip() if e_i < len(emb_formats) else 'A4'
                emb_list.append({'type': emb_types[e_i].strip(), 'format': ef, 'quantity': eq})

        positions.append({
            'pos_index': p_idx, 'product_name': p_prod, 'pattern_name': p_pattern,
            'fabric_name': p_fabric, 'fabric_density': p_density, 'fabric_color': p_color,
            'size_3xs': s_3xs, 'size_2xs': s_2xs, 'size_xs': s_xs, 'size_s': s_s,
            'size_m': s_m, 'size_l': s_l, 'size_xl': s_xl, 'size_2xl': s_2xl, 'size_3xl': s_3xl,
            'total_quantity': pos_total, 'embellishments': emb_list
        })
    return positions

@orders_bp.route('/orders')
def orders_list():
    sort_by = request.args.get('sort_by', 'order_number')
    sort_order = request.args.get('sort_order', 'desc')
    search = request.args.get('search', '').strip()
    filter_type = request.args.get('filter', 'all')
    counts = database.get_orders_counts()
    
    if filter_type == 'drafts':
        drafts = database.get_drafts_list(search=search)
        orders = []
    else:
        orders = database.get_orders_list(sort_by, sort_order, search=search, filter_type=filter_type)
        drafts = []
        
    next_sort_order = 'asc' if sort_order == 'desc' else 'desc'
    return render_template('orders/orders_list.html', 
                           orders=orders, drafts=drafts, counts=counts,
                           sort_by=sort_by, sort_order=sort_order, next_sort_order=next_sort_order,
                           search=search, filter_type=filter_type)

@orders_bp.route('/orders/<int:order_id>')
def order_detail(order_id):
    try:
        data = database.get_order_full_details(order_id)
        if not data:
            flash('Заказ не найден', 'error')
            return redirect(url_for('orders.orders_list'))
        order, stages, files, items = data
    except Exception as e:
        flash('Ошибка чтения данных заказа', 'error')
        return redirect(url_for('orders.orders_list'))
    
    def safe_date_to_abs_q(d_str, q):
        if not d_str: return 0
        try: return date.fromisoformat(str(d_str)[:10]).toordinal() * 4 + safe_int(q, default=1) - 1
        except: return 0
            
    for s in stages:
        s_start = s.get('start_date') or s.get('start')
        s_end = s.get('end_date') or s.get('end')
        s_abs = safe_date_to_abs_q(s_start, s.get('start_q', 1))
        e_abs = safe_date_to_abs_q(s_end, s.get('end_q', 1))
        s['duration_days'] = max(0.25, (e_abs - s_abs + 1) / 4.0) if (s_start and s_end) else 0
        
    s_total = safe_date_to_abs_q(order.get('start_date'), order.get('start_q', 1))
    e_total = safe_date_to_abs_q(order.get('end_date'), order.get('end_q', 1))
    total_duration = max(0.25, (e_total - s_total + 1) / 4.0) if (order.get('start_date') and order.get('end_date')) else 0
    
    back_url = request.args.get('from', 'orders')
    return render_template('orders/order_detail.html', 
                           order=order, stages=stages, files=files, items=items,
                           total_duration=total_duration, back_url=back_url)

@orders_bp.route('/add_order', methods=['GET', 'POST'])
def add_order_view():
    if request.method == 'POST':
        try:
            order_number = safe_int(request.form.get('order_number'), default=None)
            creation_date = request.form.get('creation_date') or date.today().isoformat()
            order_type = request.form.get('order_type', 'batch')
            name = request.form.get('name', '').strip()
            
            if not order_number:
                order_number = database.get_next_available_order_number()
            elif database.check_order_number_taken(order_number):
                flash(f'Номер заказа {order_number} уже занят! Выберите другой.', 'error')
                return redirect(url_for('orders.add_order_view'))

            client_name = request.form.get('client_name', '').strip() or request.form.get('client_text', '').strip()
            client_id = database.get_or_create_client(client_name) if client_name else None

            contact_type = request.form.get('contact_type', 'Телефон')
            contact = request.form.get('contact', '').strip()
            amount = safe_float(request.form.get('amount'))
            comment = request.form.get('comment', '').strip()
            o_start = request.form.get('order_start_date') or date.today().isoformat()
            o_start_q = safe_int(request.form.get('order_start_q'), default=1)

            if not name:
                flash('Название заказа обязательно', 'error')
                return redirect(url_for('orders.add_order_view'))

            positions = parse_positions_from_form(request.form)
            quantity = sum(p['total_quantity'] for p in positions) if positions else safe_int(request.form.get('quantity'), default=0)

            stages = []
            if order_type == 'sample':
                s_end = request.form.get('sample_end_date') or o_start
                s_end_q = safe_int(request.form.get('sample_end_q'), default=o_start_q)
                s_stages = request.form.getlist('sample_stages[]')
                for st in s_stages:
                    if st.strip():
                        stages.append({'type': st.strip(), 'start': o_start, 'start_q': o_start_q, 'end': s_end, 'end_q': s_end_q})
                if not stages:
                    stages = [{'type': 'Образец', 'start': o_start, 'start_q': o_start_q, 'end': s_end, 'end_q': s_end_q}]
                
                order_id = database.add_order(
                    name, client_name, contact, comment, order_type, quantity, o_start, o_start_q, s_end, s_end_q, stages,
                    order_number=order_number, client_id=client_id, contact_type=contact_type,
                    amount=amount, created_at=creation_date, positions=positions
                )
            else:
                types = request.form.getlist('stage_type[]')
                starts = request.form.getlist('start_date[]')
                start_qs = request.form.getlist('start_q[]')
                ends = request.form.getlist('end_date[]')
                end_qs = request.form.getlist('end_q[]')

                for i in range(len(types)):
                    t = types[i].strip()
                    if not t: continue
                    st = starts[i] if i < len(starts) and starts[i] else o_start
                    st_q = safe_int(start_qs[i] if i < len(start_qs) else 1, default=1)
                    en = ends[i] if i < len(ends) and ends[i] else st
                    en_q = safe_int(end_qs[i] if i < len(end_qs) else 4, default=4)
                    stages.append({'type': t, 'start': st, 'start_q': st_q, 'end': en, 'end_q': en_q})

                if not stages:
                    flash('Добавьте хотя бы один этап производства', 'error')
                    return redirect(url_for('orders.add_order_view'))
                
                def safe_calc_abs(d, q):
                    d_obj = safe_date_obj(d, fallback=date.today())
                    return d_obj.toordinal() * 4 + safe_int(q, default=1)

                max_stage = max(stages, key=lambda s: safe_calc_abs(s['end'], s['end_q']))
                order_id = database.add_order(
                    name, client_name, contact, comment, order_type, quantity, o_start, o_start_q, max_stage['end'], safe_int(max_stage['end_q'], default=4), stages,
                    order_number=order_number, client_id=client_id, contact_type=contact_type,
                    amount=amount, created_at=creation_date, positions=positions
                )

            # Сохранение файлов к позициям (Пункт 10 ТЗ)
            try:
                upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
                os.makedirs(upload_folder, exist_ok=True)
                for p in positions:
                    p_idx = p.get('pos_index', 1)
                    p_files = request.files.getlist(f'pos_files_{p_idx}')
                    for file in p_files:
                        if file and file.filename:
                            orig_name = file.filename
                            ext = os.path.splitext(orig_name)[1]
                            disk_name = f"{order_id}_{uuid.uuid4().hex[:8]}{ext}"
                            file.save(os.path.join(upload_folder, disk_name))
                            database.add_order_file(order_id, orig_name, f"uploads/{disk_name}", position_index=int(p_idx))
            except: pass

            loaded_draft_id = safe_int(request.form.get('loaded_draft_id'), default=None)
            if loaded_draft_id:
                try: database.delete_draft(loaded_draft_id)
                except: pass

            flash(f'Заказ #{order_number} успешно создан', 'success')
            return redirect(url_for('orders.order_detail', order_id=order_id))

        except Exception as e:
            flash(f'Ошибка при создании заказа: {str(e)}', 'error')
            return redirect(url_for('orders.add_order_view'))

    next_num = database.get_next_available_order_number()
    today_str = date.today().isoformat()
    return render_template('add_order.html', 
                           stage_list=STAGE_LIST, 
                           next_num=next_num, 
                           today_str=today_str)

@orders_bp.route('/delete_draft/<int:draft_id>', methods=['POST'])
def delete_draft_view(draft_id):
    database.delete_draft(draft_id)
    flash('Черновик удален', 'success')
    return redirect(url_for('orders.orders_list', filter='drafts'))

@orders_bp.route('/api/check_order_number')
def check_order_number_api():
    num = safe_int(request.args.get('number'), default=None)
    exclude_id = safe_int(request.args.get('exclude_id'), default=None)
    taken = database.check_order_number_taken(num, exclude_id=exclude_id)
    return jsonify({'taken': taken})

@orders_bp.route('/api/drafts', methods=['GET', 'POST'])
def api_drafts():
    if request.method == 'POST':
        data = None
        try: data = request.get_json(silent=True)
        except: pass
        if not data and request.data:
            try: data = json.loads(request.data.decode('utf-8'))
            except: pass
        if not data and request.form:
            if 'payload' in request.form:
                try: data = json.loads(request.form['payload'])
                except: data = {}
            else: data = dict(request.form)

        data = data or {}
        title = data.get('title', 'Без названия').strip() or 'Без названия'
        draft_id = safe_int(data.get('draft_id'), default=None)
        saved_id = database.save_draft(title, json.dumps(data, ensure_ascii=False), draft_id=draft_id)
        return jsonify({'success': True, 'draft_id': saved_id})
    return jsonify(database.get_all_drafts())

@orders_bp.route('/api/drafts/<int:draft_id>', methods=['GET', 'DELETE'])
def api_draft_item(draft_id):
    if request.method == 'DELETE':
        database.delete_draft(draft_id)
        return jsonify({'success': True})
    draft = database.get_draft(draft_id)
    if not draft: return jsonify({'error': 'Черновик не найден'}), 404
    return jsonify(draft)
