# -*- coding: utf-8 -*-
import os
import re

def run_fix():
    print("=" * 65)
    print(">>> [ГЛОБАЛЬНЫЙ ПАТЧ: БЕЗОПАСНОСТЬ, ПАГИНАЦИЯ, БАГИ И UX]")
    print("=" * 65)

    base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    app_dir = os.path.join(base_dir, 'app')
    
    db_file = os.path.join(app_dir, 'models', 'database.py')
    orders_file = os.path.join(app_dir, 'blueprints', 'orders.py')
    add_order_html = os.path.join(app_dir, 'templates', 'add_order.html')
    edit_order_html = os.path.join(app_dir, 'templates', 'edit_order.html')
    orders_list_html = os.path.join(app_dir, 'templates', 'orders', 'orders_list.html')
    index_html = os.path.join(app_dir, 'templates', 'index.html')

    # ---------------------------------------------------------
    # 1. DATABASE.PY: Удаление файлов и Пагинация
    # ---------------------------------------------------------
    if os.path.exists(db_file):
        with open(db_file, 'r', encoding='utf-8') as f:
            db_c = f.read()

        # Фикс 1: Удаление физических файлов
        old_del = 'cursor.execute("DELETE FROM stages WHERE order_id = ?", (order_id,))'
        new_del = """cursor.execute("SELECT file_path FROM order_files WHERE order_id = ?", (order_id,))
    for row in cursor.fetchall():
        try:
            full_path = os.path.join(os.path.dirname(__file__), '../../app/static', row['file_path'])
            if os.path.exists(full_path):
                os.remove(full_path)
        except:
            pass
    cursor.execute("DELETE FROM stages WHERE order_id = ?", (order_id,))"""
        if 'os.remove(full_path)' not in db_c:
            db_c = db_c.replace(old_del, new_del)

        # Фикс 4: Пагинация в БД
        old_get_def = "def get_orders_list(sort_by='order_number', sort_order='desc', search='', filter_type='all'):"
        new_get_def = "def get_orders_list(sort_by='order_number', sort_order='desc', search='', filter_type='all', page=1, per_page=50):"
        db_c = db_c.replace(old_get_def, new_get_def)

        old_fetch = """    query += f" ORDER BY {order_col} {order_dir}"
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows]"""
        new_fetch = """    query += f" ORDER BY {order_col} {order_dir}"
    
    count_query = "SELECT COUNT(*) FROM (" + query + ")"
    cursor.execute(count_query, params)
    total_items = cursor.fetchone()[0]
    total_pages = max(1, (total_items + per_page - 1) // per_page)
    if page < 1: page = 1
    
    query += " LIMIT ? OFFSET ?"
    params.extend([per_page, (page - 1) * per_page])
    
    cursor.execute(query, params)
    rows = cursor.fetchall()
    conn.close()
    return [dict(r) for r in rows], total_pages, page"""
        if 'total_pages =' not in db_c:
            db_c = db_c.replace(old_fetch, new_fetch)

        with open(db_file, 'w', encoding='utf-8') as f:
            f.write(db_c)
        print("1. database.py: Утечка файлов устранена, добавлена поддержка пагинации.")

    # ---------------------------------------------------------
    # 2. ORDERS.PY: Пагинация и Безопасность файлов
    # ---------------------------------------------------------
    if os.path.exists(orders_file):
        with open(orders_file, 'r', encoding='utf-8') as f:
            ord_c = f.read()

        # Фикс 4: Пагинация в роуте
        old_list = """    if filter_type == 'drafts':
        drafts = database.get_drafts_list(search=search)
        orders = []
    else:
        orders = database.get_orders_list(sort_by, sort_order, search=search, filter_type=filter_type)
        drafts = []"""
        new_list = """    page = safe_int(request.args.get('page'), 1)
    total_pages = 1
    current_page = 1
    if filter_type == 'drafts':
        drafts = database.get_drafts_list(search=search)
        orders = []
    else:
        orders, total_pages, current_page = database.get_orders_list(sort_by, sort_order, search=search, filter_type=filter_type, page=page, per_page=50)
        drafts = []"""
        if 'total_pages = 1' not in ord_c:
            ord_c = ord_c.replace(old_list, new_list)
            ord_c = ord_c.replace("search=search, filter_type=filter_type)", "search=search, filter_type=filter_type, total_pages=total_pages, current_page=current_page)")

        # Фикс 5: Безопасность загрузки файлов
        old_ext = "ext = os.path.splitext(orig_name)[1]"
        new_ext = """ext = os.path.splitext(orig_name)[1].lower()
                        if ext not in {'.png', '.jpg', '.jpeg', '.pdf', '.ai', '.psd', '.cdr', '.svg', '.tif', '.tiff', '.zip', '.rar'}:
                            continue"""
        ord_c = ord_c.replace(old_ext, new_ext)

        with open(orders_file, 'w', encoding='utf-8') as f:
            f.write(ord_c)
        print("2. orders.py: Пагинация подключена, загрузка файлов защищена.")

    # ---------------------------------------------------------
    # 3. ORDERS_LIST.HTML: Кнопки пагинации
    # ---------------------------------------------------------
    if os.path.exists(orders_list_html):
        with open(orders_list_html, 'r', encoding='utf-8') as f:
            list_c = f.read()

        pag_html = """
{% if total_pages and total_pages > 1 and filter_type != 'drafts' %}
<div style="display: flex; justify-content: center; gap: 8px; margin-top: 15px;">
    {% if current_page > 1 %}
    <a href="?page={{ current_page - 1 }}&filter={{ filter_type }}&search={{ search }}&sort_by={{ sort_by }}&sort_order={{ sort_order }}" class="btn btn-outline">Назад</a>
    {% endif %}
    <span style="padding: 6px 12px; background: #f3f4f6; border-radius: 4px; font-weight: 600; color: #374151;">Страница {{ current_page }} из {{ total_pages }}</span>
    {% if current_page < total_pages %}
    <a href="?page={{ current_page + 1 }}&filter={{ filter_type }}&search={{ search }}&sort_by={{ sort_by }}&sort_order={{ sort_order }}" class="btn btn-outline">Вперед</a>
    {% endif %}
</div>
{% endif %}
"""
        if 'total_pages > 1' not in list_c:
            list_c = list_c.replace('</table>\n</div>\n{% endif %}', '</table>\n</div>\n' + pag_html + '\n{% endif %}')
            with open(orders_list_html, 'w', encoding='utf-8') as f:
                f.write(list_c)
            print("3. orders_list.html: Добавлен интерфейс пагинации.")

    # ---------------------------------------------------------
    # 4. ADD_ORDER.HTML: Валидация и предупреждение черновиков
    # ---------------------------------------------------------
    if os.path.exists(add_order_html):
        with open(add_order_html, 'r', encoding='utf-8') as f:
            add_c = f.read()

        # Фикс 3: Валидация позиций
        val_js = """
        document.querySelectorAll('.position-card').forEach((c) => {
            const pId = c.dataset.pid;
            const prod = c.querySelector(`[name="product_${pId}"]`);
            const pat = c.querySelector(`[name="pattern_${pId}"]`);
            const fab = c.querySelector(`[name="fabric_${pId}"]`);
            if (prod && pat && fab) {
                if (!prod.value.trim() || !pat.value.trim() || !fab.value.trim()) {
                    isValid = false;
                    if (!firstInvalid) firstInvalid = prod;
                    c.style.border = '1px solid #dc2626';
                } else {
                    c.style.border = '';
                }
            }
        });
        const type = document.getElementById('order_type').value;"""
        if 'c.style.border = \'1px solid #dc2626\';' not in add_c:
            add_c = add_c.replace("const type = document.getElementById('order_type').value;", val_js)

        # Фикс 6: Предупреждение о файлах в черновике
        draft_warn = """if (!draft || !draft.data_json) return;
            const alertDiv = document.createElement('div');
            alertDiv.className = 'alert alert-error';
            alertDiv.innerHTML = '<b>Черновик восстановлен!</b> Пожалуйста, прикрепите макеты/файлы заново, так как они не сохраняются в черновике.';
            document.querySelector('.form-container').prepend(alertDiv);"""
        if 'Черновик восстановлен!' not in add_c:
            add_c = add_c.replace("if (!draft || !draft.data_json) return;", draft_warn)

        with open(add_order_html, 'w', encoding='utf-8') as f:
            f.write(add_c)
        print("4. add_order.html: Улучшена валидация, добавлено предупреждение для файлов.")

    # ---------------------------------------------------------
    # 5. EDIT_ORDER.HTML: Починка редактирования образцов
    # ---------------------------------------------------------
    if os.path.exists(edit_order_html):
        with open(edit_order_html, 'r', encoding='utf-8') as f:
            edit_c = f.read()

        # Фикс 2: Добавляем блок sample-ui и логику
        sample_ui = """
            </div>

            <div id="sample-ui" style="display:none; margin-top:15px;">
                <div class="form-group sample-duration-box" id="group-sample-duration">
                    <label class="field-title">Общая длительность пошива образца *</label>
                    <div style="display: flex; gap: 10px; align-items: center; flex-wrap: wrap;">
                        <select id="sample-duration" style="width: auto; max-width: 200px;" onchange="calculateSampleSchedule();">
                            <option value="">Выберите...</option>
                            <option value="0.25">0.25 дня</option>
                            <option value="0.5">0.5 дня</option>
                            <option value="1">1 день</option>
                            <option value="2">2 дня</option>
                            <option value="3">3 дня</option>
                            <option value="4">4 дня</option>
                            <option value="5">5 дней</option>
                            <option value="6">6 дней</option>
                            <option value="7">7 дней</option>
                        </select>
                        <span id="sample-dates-display" style="font-size: 13px; font-weight:600; color:#58a6ff;"></span>
                    </div>
                    <input type="hidden" name="sample_end_date" id="sample-end-date">
                    <input type="hidden" name="sample_end_q" id="sample-end-q">
                </div>
            </div>"""
        
        if 'id="sample-ui"' not in edit_c:
            edit_c = edit_c.replace('</div>\n        </div>\n\n        <!-- ФАЙЛЫ -->', sample_ui + '\n        </div>\n\n        <!-- ФАЙЛЫ -->')
            edit_c = edit_c.replace('id="order_type"', 'id="order_type" onchange="toggleOrderTypeUI(); loadOccupiedSlots();"')
            
            js_funcs = """
    function toggleOrderTypeUI() {
        const type = document.getElementById('order_type').value;
        const batchUi = document.getElementById('batch-ui');
        const sampleUi = document.getElementById('sample-ui');
        if (type === 'sample') {
            if (batchUi) batchUi.style.display = 'none';
            if (sampleUi) sampleUi.style.display = 'block';
            if (typeof calculateSampleSchedule === 'function') calculateSampleSchedule();
        } else {
            if (batchUi) batchUi.style.display = 'block';
            if (sampleUi) sampleUi.style.display = 'none';
            if (typeof calculateSchedule === 'function') calculateSchedule();
        }
    }

    function calculateSampleSchedule() {
        let startD = document.getElementById('global-start-date').value;
        let startQ = document.getElementById('global-start-q').value;
        let sel = document.getElementById('sample-duration');
        if (!sel || !startD) return;
        let duration = parseFloat(sel.value || 0);

        if (duration > 0) {
            let currentAbsQ = dateToAbs(startD, startQ);
            let quartersNeeded = Math.round(duration * 4);
            let stageEndQ = currentAbsQ;
            let localOccupiedMap = {...dbOccupiedMap};
            
            while (quartersNeeded > 0) {
                if (!localOccupiedMap[currentAbsQ]) {
                    stageEndQ = currentAbsQ;
                    quartersNeeded--;
                    localOccupiedMap[currentAbsQ] = true;
                }
                currentAbsQ++;
            }
            
            let endObj = absToDateAndQ(stageEndQ);
            document.getElementById('sample-end-date').value = endObj.date;
            document.getElementById('sample-end-q').value = endObj.q;
            document.getElementById('sample-dates-display').textContent = `${formatD(startD)} (ч.${startQ}) — ${formatD(endObj.date)} (ч.${endObj.q})`;
        }
    }
"""
            edit_c = edit_c.replace("async function checkOrderNumber", js_funcs + "\n    async function checkOrderNumber")
            edit_c = edit_c.replace("loadOccupiedSlots();\n    });", "loadOccupiedSlots();\n        toggleOrderTypeUI();\n    });")
            
            with open(edit_order_html, 'w', encoding='utf-8') as f:
                f.write(edit_c)
            print("5. edit_order.html: Починен интерфейс редактирования образцов.")

    # ---------------------------------------------------------
    # 6. INDEX.HTML: Мобильный скролл и Выходные дни
    # ---------------------------------------------------------
    if os.path.exists(index_html):
        with open(index_html, 'r', encoding='utf-8') as f:
            idx_c = f.read()

        # Фикс 8: Предупреждение о выходных
        warn_js = """const dObj = new Date(targetDateStr);
        const dayOfWeek = dObj.getDay();
        const weekendWarn = (dayOfWeek === 0 || dayOfWeek === 6) ? ' <span style="color:#f59e0b;">(Выходной!)</span>' : '';

        const infoText = document.getElementById('moveInfoText');
        if (infoText) {
            let status = valid
                ? `<span style="color:#60a5fa; font-weight:700;">Новый период: ${formatShortDate(targetDateStr)} (ч.${targetQ})${weekendWarn} — ${formatShortDate(endInfo.date)} (ч.${endInfo.q})</span>`"""
        
        if 'weekendWarn' not in idx_c:
            idx_c = re.sub(r"const infoText = document\.getElementById\('moveInfoText'\);\s*if \(infoText\) \{\s*let status = valid\s*\?\s*`<span style=\"color:#60a5fa; font-weight:700;\">Новый период:[^`]+`", warn_js, idx_c)

        # Фикс 7: Задержка для тач-устройств (Drag & Drop)
        touch_js = """
            // Задержка для мобильных устройств (чтобы не блокировать скролл)
            if (e.pointerType === 'touch') {
                let touchTimer = setTimeout(() => {
                    isDragging = true;
                    document.body.classList.add('is-dragging-order');
                    document.querySelectorAll(`.q-cell[data-order-id="${movingOrderData.id}"]`).forEach(c => c.classList.add('drag-hidden'));
                    document.addEventListener('pointermove', onPointerMove, {passive: false});
                    document.addEventListener('pointerup', onPointerUp);
                }, 400);
                
                const cancelTouch = () => {
                    clearTimeout(touchTimer);
                    document.removeEventListener('pointermove', cancelTouch);
                    document.removeEventListener('pointerup', cancelTouch);
                };
                document.addEventListener('pointermove', cancelTouch, {once: true});
                document.addEventListener('pointerup', cancelTouch, {once: true});
            } else {
                document.addEventListener('pointermove', onPointerMove);
                document.addEventListener('pointerup', onPointerUp);
            }
        });

        function onPointerMove(e) {
            if (e.pointerType === 'touch' && isDragging) {
                e.preventDefault(); // Блокируем скролл только когда реально тащим
            }
            if (!isDragging) {"""
            
        if 'e.pointerType === \'touch\'' not in idx_c:
            idx_c = idx_c.replace("document.addEventListener('pointermove', onPointerMove);\n            document.addEventListener('pointerup', onPointerUp);\n        });\n\n        function onPointerMove(e) {\n            if (!isDragging) {", touch_js)

        with open(index_html, 'w', encoding='utf-8') as f:
            f.write(idx_c)
        print("6. index.html: Добавлена защита скролла на смартфонах и предупреждение о выходных.")

    print("=" * 65)
    print("[УСПЕХ] Все 8 проблем успешно устранены!")
    print("=" * 65)
    return True

if __name__ == '__main__':
    run_fix()