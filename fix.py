# -*- coding: utf-8 -*-
import os
import re

def fix():
    print("=" * 65)
    print(">>> [ВОЗВРАТ ОРИГИНАЛЬНОГО НЕОНА + УВЕДОМЛЕНИЕ ПРИ СОХРАНЕНИИ]")
    print("=" * 65)

    base_dir = os.path.dirname(os.path.abspath(__file__)) if '__file__' in globals() else os.getcwd()
    app_dir = os.path.join(base_dir, 'app')

    # =========================================================================
    # 1. ORDERS.PY: Добавляем flash('Черновик сохранён') при сохранении
    # =========================================================================
    orders_py_path = os.path.join(app_dir, 'blueprints', 'orders.py')
    if os.path.exists(orders_py_path):
        with open(orders_py_path, 'r', encoding='utf-8') as f:
            py_code = f.read()

        # Добавляем flash перед возвратом JSON при ручном сохранении с файлами
        old_return = "saved_id = database.save_draft(title, json.dumps(data, ensure_ascii=False), draft_id=draft_id)"
        new_return = """saved_id = database.save_draft(title, json.dumps(data, ensure_ascii=False), draft_id=draft_id)
        if request.content_type and 'multipart/form-data' in request.content_type:
            flash('Черновик сохранён', 'success')"""

        if "flash('Черновик сохранён', 'success')" not in py_code:
            py_code = py_code.replace(old_return, new_return)
            with open(orders_py_path, 'w', encoding='utf-8') as f:
                f.write(py_code)
            print("1. orders.py: Добавлено уведомление 'Черновик сохранён'.")

    # =========================================================================
    # 2. STYLE.CSS: Возвращаем точный темный неон из скриншота 8
    # =========================================================================
    style_path = os.path.join(app_dir, 'static', 'style.css')
    if os.path.exists(style_path):
        with open(style_path, 'r', encoding='utf-8') as f:
            css = f.read()

        # Чистим любые старые стили тостов
        css = re.sub(r'/\* =+ [^\n]*НЕОН[^\n]*[\s\S]*?\.toast-error\s*\{[^}]+\}', '', css)
        css = re.sub(r'/\* =+ [^\n]*TOAST[^\n]*[\s\S]*?\.toast-error\s*\{[^}]+\}', '', css)
        css = re.sub(r'\.toast-container\s*\{[\s\S]*?\.toast-error\s*\{[^}]+\}', '', css)

        # Оригинальный неон: полупрозрачный, текст слева, мягкая рамка, фиксирован сверху
        neon_css = """
/* =========================================================
   ФИКСИРОВАННЫЙ ОРИГИНАЛЬНЫЙ НЕОНОВЫЙ ALERT (СКРИНШОТ 8)
   ========================================================= */
.global-notification-bar {
    position: fixed !important;
    top: 12px !important;
    left: 50% !important;
    transform: translateX(-50%) !important;
    width: 100% !important;
    max-width: 1200px !important;
    padding: 0 15px !important;
    z-index: 9999999 !important;
    pointer-events: none !important;
    box-sizing: border-box !important;
}
.global-notification-bar .alert,
.dark-theme .global-notification-bar .alert {
    width: 100% !important;
    margin: 0 !important;
    padding: 10px 16px !important;
    border-radius: 8px !important;
    font-size: 13px !important;
    font-weight: 500 !important;
    text-align: left !important;
    justify-content: flex-start !important;
    box-sizing: border-box !important;
    pointer-events: auto !important;
    backdrop-filter: blur(10px) !important;
    -webkit-backdrop-filter: blur(10px) !important;
}
.dark-theme .alert-success,
.dark-theme .global-notification-bar .alert-success {
    background: rgba(16, 185, 129, 0.15) !important;
    color: #6ee7b7 !important;
    border: 1px solid rgba(16, 185, 129, 0.35) !important;
    box-shadow: 0 0 12px rgba(16, 185, 129, 0.15) !important;
}
.dark-theme .alert-error,
.dark-theme .global-notification-bar .alert-error {
    background: rgba(239, 68, 68, 0.15) !important;
    color: #fca5a5 !important;
    border: 1px solid rgba(239, 68, 68, 0.35) !important;
    box-shadow: 0 0 12px rgba(239, 68, 68, 0.15) !important;
}
"""
        css += "\n" + neon_css.strip() + "\n"
        with open(style_path, 'w', encoding='utf-8') as f:
            f.write(css)
        print("2. style.css: Восстановлен оригинальный полупрозрачный неон.")

    # =========================================================================
    # 3. BASE.HTML: Вывод оригинального неона и плавное скрытие
    # =========================================================================
    base_path = os.path.join(app_dir, 'templates', 'base.html')
    if os.path.exists(base_path):
        with open(base_path, 'r', encoding='utf-8') as f:
            base_html = f.read()

        # Панель уведомлений прямо в начале body
        notif_bar = """
    <div class="global-notification-bar" id="globalNotificationBar">
        {% with messages = get_flashed_messages(with_categories=true) %}
            {% if messages %}
                {% for category, message in messages %}
                    <div class="alert alert-{{ 'error' if category == 'error' else 'success' }}">{{ message }}</div>
                {% endfor %}
            {% endif %}
        {% endwith %}
    </div>
"""
        # Убираем старые вызовы flash
        base_html = re.sub(r'<div class="global-notification-bar"[\s\S]*?</div>\s*</div>', '', base_html)
        base_html = re.sub(r'{%\s*with messages = get_flashed_messages[\s\S]*?{%\s*endwith\s*%}', '', base_html)

        # Вставляем блок уведомлений сразу после <body>
        base_html = re.sub(r'(<body[^>]*>)', r'\1' + notif_bar, base_html)

        # JS логика плавного авто-скрытия через 3.5 секунды
        auto_hide_js = """
        // Плавное скрытие уведомления через 3.5 секунды
        document.addEventListener('DOMContentLoaded', function() {
            var alerts = document.querySelectorAll('.global-notification-bar .alert');
            if (alerts.length > 0) {
                setTimeout(function() {
                    alerts.forEach(function(el) {
                        el.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                        el.style.opacity = '0';
                        el.style.transform = 'translateY(-10px)';
                        setTimeout(function() { el.remove(); }, 400);
                    });
                }, 3500);
            }
        });

        // Функция показа уведомления из JS (если вызывается без перезагрузки)
        function showToast(msg, type='success') {
            var bar = document.getElementById('globalNotificationBar');
            if (!bar) return;
            bar.innerHTML = '';
            var el = document.createElement('div');
            el.className = 'alert alert-' + (type === 'error' ? 'error' : 'success');
            el.textContent = msg;
            bar.appendChild(el);
            setTimeout(function() {
                el.style.transition = 'opacity 0.4s ease, transform 0.4s ease';
                el.style.opacity = '0';
                el.style.transform = 'translateY(-10px)';
                setTimeout(function() { el.remove(); }, 400);
            }, 3500);
        }
"""
        # Заменяем старую showToast на чистую
        if 'function showToast(' in base_html:
            base_html = re.sub(r'function showToast\(msg, type=\'success\'\) \{[\s\S]*?\n        \}', auto_hide_js.strip(), base_html)
        else:
            base_html = base_html.replace('</body>', f"<script>{auto_hide_js}</script>\n</body>")

        with open(base_path, 'w', encoding='utf-8') as f:
            f.write(base_html)
        print("3. base.html: Уведомления подключены без белых галочек и ядовитых фонов.")

    print("=" * 65)
    print("[УСПЕХ] Готово! Неоновый дизайн полностью возвращен.")
    print("=" * 65)

if __name__ == '__main__':
    fix()