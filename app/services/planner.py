import calendar
from datetime import date

def date_to_abs_q(d_str, q):
    return date.fromisoformat(d_str).toordinal() * 4 + int(q) - 1

def get_month_calendar(year, month, main_orders, other_orders):
    cal = calendar.Calendar(firstweekday=0)
    result = []

    for i, order in enumerate(main_orders):
        order['day_bg_class'] = f"day-bg-{i % 6}"

    for day_date in cal.itermonthdates(year, month):
        date_str = day_date.strftime('%Y-%m-%d')
        day_abs_q_start = day_date.toordinal() * 4
        
        day_quarters = [None] * 4
        cross_indicators = [False] * 4 
        
        start_order_name = None
        start_order_id = None
        start_order_badge_text = None

        for order in main_orders:
            if order.get('start_date') == date_str:
                num = order.get('order_number') or order['id']
                qty = order.get('quantity', 0) or 0
                start_order_name = order['name']
                start_order_id = order['id']
                start_order_badge_text = f"#{num} ({qty} шт.)"
                break

        for order in other_orders:
            if order.get('order_type') == 'sample':
                s_abs_q = date_to_abs_q(order['start_date'], order['start_q'])
                e_abs_q = date_to_abs_q(order['end_date'], order['end_q'])
                if s_abs_q <= day_abs_q_start + 3 and e_abs_q >= day_abs_q_start:
                    q_start = max(0, s_abs_q - day_abs_q_start)
                    q_end = min(3, e_abs_q - day_abs_q_start)
                    for idx in range(q_start, q_end + 1):
                        cross_indicators[idx] = True
            else:
                for stage in order.get('stages', []):
                    s_abs_q = date_to_abs_q(stage['start'], stage['start_q'])
                    e_abs_q = date_to_abs_q(stage['end'], stage['end_q'])
                    if s_abs_q <= day_abs_q_start + 3 and e_abs_q >= day_abs_q_start:
                        q_start = max(0, s_abs_q - day_abs_q_start)
                        q_end = min(3, e_abs_q - day_abs_q_start)
                        for idx in range(q_start, q_end + 1):
                            cross_indicators[idx] = True

        for order_idx, order in enumerate(main_orders):
            num = order.get('order_number') or order['id']
            qty = order.get('quantity', 0) or 0
            order_label = f"#{num} ({qty} шт.)"

            if order.get('order_type') == 'sample':
                s_abs_q = date_to_abs_q(order['start_date'], order['start_q'])
                e_abs_q = date_to_abs_q(order['end_date'], order['end_q'])
                
                if s_abs_q <= day_abs_q_start + 3 and e_abs_q >= day_abs_q_start:
                    q_start_idx = max(0, s_abs_q - day_abs_q_start)
                    q_end_idx = min(3, e_abs_q - day_abs_q_start)
                    
                    css_class = f"order-bg-{order_idx % 6} order-border-{order_idx % 6}"
                        
                    for idx in range(q_start_idx, q_end_idx + 1):
                        day_quarters[idx] = {
                            'order_id': order['id'], 
                            'order_name': order['name'],
                            'order_number': num,
                            'quantity': qty,
                            'stage_type': order_label,
                            'css_class': css_class, 
                            'day_bg_class': order['day_bg_class']
                        }
            
            else:
                for stage in order.get('stages', []):
                    s_abs_q = date_to_abs_q(stage['start'], stage['start_q'])
                    e_abs_q = date_to_abs_q(stage['end'], stage['end_q'])
                    
                    if s_abs_q <= day_abs_q_start + 3 and e_abs_q >= day_abs_q_start:
                        q_start_idx = max(0, s_abs_q - day_abs_q_start)
                        q_end_idx = min(3, e_abs_q - day_abs_q_start)
                        
                        slug = stage['type'].lower().replace(' ', '-').replace('(', '').replace(')', '')
                        css_class = f"stage-bg-{slug} order-border-{order_idx % 6}"
                        for idx in range(q_start_idx, q_end_idx + 1):
                            day_quarters[idx] = {
                                'order_id': order['id'], 
                                'order_name': order['name'],
                                'order_number': num,
                                'quantity': qty,
                                'stage_type': stage['type'], 
                                'cell_display': f"#{num} {stage['type']}",
                                'css_class': css_class, 
                                'day_bg_class': order['day_bg_class']
                            }

        processed_quarters = []
        day_bg_class = 'day-bg-none'
        
        order_counts = {}
        for q in day_quarters:
            if q: order_counts[q['order_id']] = order_counts.get(q['order_id'], 0) + 1
        
        if len(order_counts) == 1:
            dominant_order_id = list(order_counts.keys())[0]
            for q in day_quarters:
                if q and q['order_id'] == dominant_order_id:
                    day_bg_class = q['day_bg_class']
                    break
        else:
            day_bg_class = 'day-bg-none'

        for i in range(4):
            q = day_quarters[i]
            if q is None:
                processed_quarters.append({'is_empty': True})
            else:
                conn_r = conn_b = conn_l = conn_t = False
                if i == 0: 
                    if day_quarters[1] and day_quarters[1]['order_id'] == q['order_id'] and day_quarters[1]['stage_type'] == q['stage_type']: conn_r = True
                    if day_quarters[2] and day_quarters[2]['order_id'] == q['order_id'] and day_quarters[2]['stage_type'] == q['stage_type']: conn_b = True
                elif i == 1: 
                    if day_quarters[0] and day_quarters[0]['order_id'] == q['order_id'] and day_quarters[0]['stage_type'] == q['stage_type']: conn_l = True
                    if day_quarters[3] and day_quarters[3]['order_id'] == q['order_id'] and day_quarters[3]['stage_type'] == q['stage_type']: conn_b = True
                elif i == 2: 
                    if day_quarters[0] and day_quarters[0]['order_id'] == q['order_id'] and day_quarters[0]['stage_type'] == q['stage_type']: conn_t = True
                    if day_quarters[3] and day_quarters[3]['order_id'] == q['order_id'] and day_quarters[3]['stage_type'] == q['stage_type']: conn_r = True
                elif i == 3: 
                    if day_quarters[2] and day_quarters[2]['order_id'] == q['order_id'] and day_quarters[2]['stage_type'] == q['stage_type']: conn_l = True
                    if day_quarters[1] and day_quarters[1]['order_id'] == q['order_id'] and day_quarters[1]['stage_type'] == q['stage_type']: conn_t = True

                show_text = False
                if i == 0: show_text = True
                elif i == 1 and not conn_l: show_text = True
                elif i == 2 and not conn_t and not (day_quarters[1] and day_quarters[1]['order_id']==q['order_id'] and day_quarters[1]['stage_type']==q['stage_type']): show_text = True
                elif i == 3 and not conn_l and not conn_t and not (day_quarters[0] and day_quarters[0]['order_id']==q['order_id'] and day_quarters[0]['stage_type']==q['stage_type']): show_text = True

                processed_quarters.append({
                    'is_empty': False, 
                    'css_class': q['css_class'], 
                    'stage_type': q['stage_type'],
                    'cell_display': q.get('cell_display', q['stage_type']),
                    'order_name': q['order_name'], 
                    'order_id': q['order_id'],
                    'order_number': q.get('order_number'),
                    'quantity': q.get('quantity'),
                    'conn_r': conn_r, 'conn_b': conn_b, 'conn_l': conn_l, 'conn_t': conn_t, 'show_text': show_text
                })

        result.append({
            'date': day_date, 'date_str': date_str, 'day': day_date.day,
            'quarters': processed_quarters, 'cross_indicators': cross_indicators,
            'is_other_month': day_date.month != month, 'is_today': day_date == date.today(),
            'day_bg_class': day_bg_class, 
            'start_order_name': start_order_name,
            'start_order_id': start_order_id,
            'start_order_badge_text': start_order_badge_text
        })
    return result

def get_month_name(month):
    return ['', 'Январь', 'Февраль', 'Март', 'Апрель', 'Май', 'Июнь', 'Июль', 'Август', 'Сентябрь', 'Октябрь', 'Ноябрь', 'Декабрь'][month]
