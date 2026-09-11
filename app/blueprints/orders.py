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

def parse_positions_from_form(req_form):
    pos_indexes = req_form.getlist('pos_index[]')
    positions = []
    
    if not pos_indexes:
        product = req_form.get('product_name_single', '').strip()
        if product:
            sizes = {
                'size_3xs': req_form.get('size_3xs_single', 0, type=int),
                'size_2xs': req_form.get('size_2xs_single', 0, type=int),
                'size_xs': req_form.get('size_xs_single', 0, type=int),
                'size_s': req_form.get('size_s_single', 0, type=int),
                'size_m': req_form.get('size_m_single', 0, type=int),
                'size_l': req_form.get('size_l_single', 0, type=int),
                'size_xl': req_form.get('size_xl_single', 0, type=int),
                'size_2xl': req_form.get('size_2xl_single', 0, type=int),
                'size_3xl': req_form.get('size_3xl_single', 0, type=int),
                'size_onesize': req_form.get('size_onesize_single', 0, type=int),
            }
            total_qty = sum(sizes.values())
            positions.append({
                'product_name': product,
                'pattern_name': req_form.get('pattern_name_single', '').strip(),
                'fabric_name': req_form.get('fabric_name_single', '').strip(),
                'fabric_density': req_form.get('fabric_density_single', '').strip(),
                'fabric_color': req_form.get('fabric_color_single', '').strip(),
                **sizes,
                'total_quantity': total_qty,
                'embellishments': []
            })
        return positions

    for p_idx in pos_indexes:
        p_prod = req_form.get(f'product_{p_idx}', '').strip()
        p_pattern = req_form.get(f'pattern_{p_idx}', '').strip()
        p_fabric = req_form.get(f'fabric_{p_idx}', '').strip()
        p_density = req_form.get(f'density_{p_idx}', '').strip()
        p_color = req_form.get(f'color_{p_idx}', '').strip()

        s_3xs = req_form.get(f'size_3xs_{p_idx}', 0, type=int)
        s_2xs = req_form.get(f'size_2xs_{p_idx}', 0, type=int)
        s_xs = req_form.get(f'size_xs_{p_idx}', 0, type=int)
        s_s = req_form.get(f'size_s_{p_idx}', 0, type=int)
        s_m = req_form.get(f'size_m_{p_idx}', 0, type=int)
        s_l = req_form.get(f'size_l_{p_idx}', 0, type=int)
        s_xl = req_form.get(f'size_xl_{p_idx}', 0, type=int)
        s_2xl = req_form.get(f'size_2xl_{p_idx}', 0, type=int)
        s_3xl = req_form.get(f'size_3xl_{p_idx}', 0, type=int)
        s_onesize = req_form.get(f'size_onesize_{p_idx}', 0, type=int)

        pos_total = s_3xs + s_2xs + s_xs + s_s + s_m + s_l + s_xl + s_2xl + s_3xl + s_onesize

        emb_types = req_form.getlist(f'emb_type_{p_idx}[]')
        emb_formats = req_form.getlist(f'emb_format_{p_idx}[]')
        emb_quantities = req_form.getlist(f'emb_quantity_{p_idx}[]')
        emb_list = []
        for e_i in range(len(emb_types)):
            if emb_types[e_i].strip():
                try: eq = int(emb_quantities[e_i]) if e_i < len(emb_quantities) and emb_quantities[e_i] else pos_total
                except: eq = pos_total
                ef = emb_formats[e_i].strip() if e_i < len(emb_formats) else 'A4'
                emb_list.append({'type': emb_types[e_i].strip(), 'format': ef, 'quantity': eq})

        positions.append({
            'product_name': p_prod,
            'pattern_name': p_pattern,
            'fabric_name': p_fabric,
            'fabric_density': p_density,
            'fabric_color': p_color,
            'size_3xs': s_3xs,
            'size_2xs': s_2xs,
            'size_xs': s_xs,
            'size_s': s_s,
            'size_m': s_m,
            'size_l': s_l,
            'size_xl': s_xl,
            'size_2xl': s_2xl,
            'size_3xl': s_3xl,
            'size_onesize': s_onesize,
            'total_quantity': pos_total,
            'embellishments': emb_list
        })
    return positions

@orders_bp.route('/orders')
def orders_list():
    sort_by = request.args.get('sort_by', 'order_number')
    sort_order = request.args.get('sort_order', 'desc')
    search = request.args.get('search', '').strip()
    filter_type = request.args.get('filter', 'all')
    
    orders = database.get_orders_list(sort_by, sort_order, search=search, filter_type=filter_type)
    next_sort_order = 'asc' if sort_order == 'desc' else 'desc'
    
    return render_template('orders/orders_list.html', 
                           orders=orders, 
                           sort_by=sort_by, 
                           sort_order=sort_order,
                           next_sort_order=next_sort_order,
                           search=search,
                           filter_type=filter_type)

@orders_bp.route('/orders/<int:order_id>')
def order_detail(order_id):
    data = database.get_order_full_details(order_id)
    if not data:
        flash('Заказ не найден', 'error')
        return redirect(url_for('orders.orders_list'))
    order, stages, files, items = data
    
    def date_to_abs_q(d_str, q): return date.fromisoformat(d_str).toordinal() * 4 + int(q) - 1
    for s in stages:
        s_abs = date_to_abs_q(s['start_date'], s['start_q'])
        e_abs = date_to_abs_q(s['end_date'], s['end_q'])
        s['duration_days'] = (e_abs - s_abs + 1) / 4.0
        
    s_total = date_to_abs_q(order['start_date'], order['start_q'])
    e_total = date_to_abs_q(order['end_date'], order['end_q'])
    total_duration = (e_total - s_total + 1) / 4.0
    
    back_url = request.args.get('from', 'orders')
    return render_template('orders/order_detail.html', 
                           order=order, stages=stages, files=files, items=items,
                           total_duration=total_duration, back_url=back_url)

@orders_bp.route('/add_order', methods=['GET', 'POST'])
def add_order_view():
    if request.method == 'POST':
        order_number = request.form.get('order_number', type=int)
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
        amount = request.form.get('amount', 0.0, type=float)
        comment = request.form.get('comment', '').strip()

        o_start = request.form.get('order_start_date')
        o_start_q = request.form.get('order_start_q', type=int)

        if not name or not o_start or not o_start_q:
            flash('Название и дата начала производства обязательны', 'error')
            return redirect(url_for('orders.add_order_view'))

        positions = parse_positions_from_form(request.form)
        quantity = sum(p['total_quantity'] for p in positions) if positions else request.form.get('quantity', 0, type=int)

        stages = []
        if order_type == 'sample':
            s_end = request.form.get('sample_end_date')
            s_end_q = request.form.get('sample_end_q', type=int)
            s_stages = request.form.getlist('sample_stages[]')
            if not s_end or not s_end_q:
                flash('Выберите длительность образца', 'error')
                return redirect(url_for('orders.add_order_view'))
            for st in s_stages:
                st = st.strip()
                if st:
                    stages.append({'type': st, 'start': o_start, 'start_q': o_start_q, 'end': s_end, 'end_q': s_end_q})
            if not stages:
                stages = [{'type': 'Образец (Этапы не указаны)', 'start': o_start, 'start_q': o_start_q, 'end': s_end, 'end_q': s_end_q}]
            
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
            stages = [{'type': types[i].strip(), 'start': starts[i], 'start_q': int(start_qs[i]), 'end': ends[i], 'end_q': int(end_qs[i])} 
                      for i in range(len(types)) if i < len(starts) and starts[i] and types[i].strip()]
            if not stages:
                flash('Выберите хотя бы один этап производства', 'error')
                return redirect(url_for('orders.add_order_view'))
            
            def abs_q(d, q): return date.fromisoformat(d).toordinal() * 4 + int(q)
            max_stage = max(stages, key=lambda s: abs_q(s['end'], s['end_q']))
            order_id = database.add_order(
                name, client_name, contact, comment, order_type, quantity, o_start, o_start_q, max_stage['end'], int(max_stage['end_q']), stages,
                order_number=order_number, client_id=client_id, contact_type=contact_type,
                amount=amount, created_at=creation_date, positions=positions
            )

        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
        os.makedirs(upload_folder, exist_ok=True)
        files = request.files.getlist('order_files')
        for file in files:
            if file and file.filename:
                orig_name = file.filename
                ext = os.path.splitext(orig_name)[1]
                disk_name = f"{order_id}_{uuid.uuid4().hex[:8]}{ext}"
                file.save(os.path.join(upload_folder, disk_name))
                database.add_order_file(order_id, orig_name, f"uploads/{disk_name}")

                loaded_draft_id = request.form.get('loaded_draft_id', type=int)
        if loaded_draft_id:
            try: database.delete_draft(loaded_draft_id)
            except: pass

        flash(f'Заказ #{order_number} успешно создан', 'success')
        return redirect(url_for('orders.order_detail', order_id=order_id))

    clients = dict_model.get_all_clients()
    next_num = database.get_next_available_order_number()
    today_str = date.today().isoformat()
    return render_template('add_order.html', 
                           stage_list=STAGE_LIST, 
                           clients=clients, 
                           next_num=next_num, 
                           today_str=today_str)

@orders_bp.route('/edit_order/<int:order_id>', methods=['GET', 'POST'])
def edit_order_view(order_id):
    data = database.get_order_full_details(order_id)
    if not data:
        flash('Заказ не найден', 'error')
        return redirect(url_for('orders.orders_list'))
    order, stages, files, items = data

    if request.method == 'POST':
        order_number = request.form.get('order_number', type=int)
        creation_date = request.form.get('creation_date') or order['created_at']
        order_type = request.form.get('order_type', 'batch')
        name = request.form.get('name', '').strip()

        if order_number and database.check_order_number_taken(order_number, exclude_id=order_id):
            flash(f'Номер #{order_number} уже занят другим заказом!', 'error')
            return redirect(url_for('orders.edit_order_view', order_id=order_id))

        client_name = request.form.get('client_name', '').strip() or request.form.get('client_text', order['client']).strip()
        client_id = database.get_or_create_client(client_name) if client_name else order.get('client_id')

        contact_type = request.form.get('contact_type', 'Телефон')
        contact = request.form.get('contact', '').strip()
        amount = request.form.get('amount', 0.0, type=float)
        comment = request.form.get('comment', '').strip()
        o_start = request.form.get('order_start_date')
        o_start_q = request.form.get('order_start_q', type=int)

        positions = parse_positions_from_form(request.form)
        quantity = sum(p['total_quantity'] for p in positions) if positions else request.form.get('quantity', order['quantity'], type=int)

        new_stages = []
        if order_type == 'sample':
            s_end = request.form.get('sample_end_date')
            s_end_q = request.form.get('sample_end_q', type=int)
            s_stages = request.form.getlist('sample_stages[]')
            for st in s_stages:
                if st.strip():
                    new_stages.append({'type': st.strip(), 'start': o_start, 'start_q': o_start_q, 'end': s_end, 'end_q': s_end_q})
            if not new_stages:
                new_stages = [{'type': 'Образец (Этапы не указаны)', 'start': o_start, 'start_q': o_start_q, 'end': s_end, 'end_q': s_end_q}]
            
            database.update_order_full(
                order_id, name, client_name, contact, comment, order_type, quantity, o_start, o_start_q, s_end, s_end_q, new_stages,
                order_number=order_number, client_id=client_id, contact_type=contact_type,
                amount=amount, created_at=creation_date, positions=positions
            )
        else:
            types = request.form.getlist('stage_type[]')
            starts = request.form.getlist('start_date[]')
            start_qs = request.form.getlist('start_q[]')
            ends = request.form.getlist('end_date[]')
            end_qs = request.form.getlist('end_q[]')
            new_stages = [{'type': types[i].strip(), 'start': starts[i], 'start_q': int(start_qs[i]), 'end': ends[i], 'end_q': int(end_qs[i])} 
                          for i in range(len(types)) if i < len(starts) and starts[i] and types[i].strip()]
            def abs_q(d, q): return date.fromisoformat(d).toordinal() * 4 + int(q)
            max_stage = max(new_stages, key=lambda s: abs_q(s['end'], s['end_q']))
            database.update_order_full(
                order_id, name, client_name, contact, comment, order_type, quantity, o_start, o_start_q, max_stage['end'], int(max_stage['end_q']), new_stages,
                order_number=order_number, client_id=client_id, contact_type=contact_type,
                amount=amount, created_at=creation_date, positions=positions
            )

        upload_folder = current_app.config.get('UPLOAD_FOLDER', 'app/static/uploads')
        files_new = request.files.getlist('order_files')
        for file in files_new:
            if file and file.filename:
                orig_name = file.filename
                ext = os.path.splitext(orig_name)[1]
                disk_name = f"{order_id}_{uuid.uuid4().hex[:8]}{ext}"
                file.save(os.path.join(upload_folder, disk_name))
                database.add_order_file(order_id, orig_name, f"uploads/{disk_name}")

        flash('Заказ успешно сохранен', 'success')
        return redirect(url_for('orders.order_detail', order_id=order_id))

    def date_to_abs_q(d_str, q): return date.fromisoformat(d_str).toordinal() * 4 + int(q) - 1
    for s in stages:
        s_abs = date_to_abs_q(s['start_date'], s['start_q'])
        e_abs = date_to_abs_q(s['end_date'], s['end_q'])
        s['duration_days'] = (e_abs - s_abs + 1) / 4.0

    clients = dict_model.get_all_clients()

    return render_template('edit_order.html', 
                           order=order, stages=stages, files=files, items=items,
                           stage_list=STAGE_LIST, clients=clients)

@orders_bp.route('/delete_file/<int:file_id>', methods=['POST'])
def delete_file_view(file_id):
    order_id = request.form.get('order_id')
    rel_path = database.delete_order_file(file_id)
    if rel_path:
        full_path = os.path.join(current_app.root_path, 'static', rel_path)
        if os.path.exists(full_path):
            try: os.remove(full_path)
            except: pass
    flash('Файл удален', 'success')
    return redirect(url_for('orders.edit_order_view', order_id=order_id) if order_id else url_for('orders.orders_list'))

@orders_bp.route('/api/check_order_number')
def check_order_number_api():
    num = request.args.get('number', type=int)
    exclude_id = request.args.get('exclude_id', type=int)
    taken = database.check_order_number_taken(num, exclude_id=exclude_id)
    return jsonify({'taken': taken})


@orders_bp.route('/api/drafts', methods=['GET', 'POST'])
def api_drafts():
    if request.method == 'POST':
        data = None
        try:
            data = request.get_json(silent=True)
        except:
            pass
        if not data and request.data:
            try:
                data = json.loads(request.data.decode('utf-8'))
            except:
                pass
        if not data and request.form:
            if 'payload' in request.form:
                try: data = json.loads(request.form['payload'])
                except: data = {}
            else:
                data = dict(request.form)

        data = data or {}
        title = data.get('title', 'Без названия').strip() or 'Без названия'
        draft_id = data.get('draft_id')
        try:
            draft_id = int(draft_id) if draft_id else None
        except:
            draft_id = None

        saved_id = database.save_draft(title, json.dumps(data, ensure_ascii=False), draft_id=draft_id)
        return jsonify({'success': True, 'draft_id': saved_id})
    return jsonify(database.get_all_drafts())

@orders_bp.route('/api/drafts/<int:draft_id>', methods=['GET', 'DELETE'])
def api_draft_item(draft_id):
    if request.method == 'DELETE':
        database.delete_draft(draft_id)
        return jsonify({'success': True})
    draft = database.get_draft(draft_id)
    if not draft:
        return jsonify({'error': 'Черновик не найден'}), 404
    return jsonify(draft)
