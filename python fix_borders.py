# -*- coding: utf-8 -*-
import os
import re

css_path = 'app/static/style.css'
with open(css_path, 'r', encoding='utf-8') as f:
    css = f.read()

boosted_contrast_css = '''
/* =========================================================
   УСИЛЕННЫЙ КОНТРАСТНЫЙ ФОН ДНЕЙ ЗАКАЗОВ (+20%)
   ========================================================= */

/* Пустые слоты внутри дня аккуратно подсвечиваются цветом заказа */
.dark-theme .q-cell.empty {
    background-color: rgba(18, 18, 18, 0.5) !important;
    border: 1px solid rgba(255, 255, 255, 0.06) !important;
}

/* Усиленная подсветка дней (20% прозрачности) для четкого разделения */
.dark-theme .day-bg-none { background-color: #121212 !important; }
.dark-theme .day-bg-0 { background-color: rgba(59, 130, 246, 0.20) !important; }  /* Заказ 1: Синий */
.dark-theme .day-bg-1 { background-color: rgba(245, 158, 11, 0.20) !important; }  /* Заказ 2: Янтарный */
.dark-theme .day-bg-2 { background-color: rgba(16, 185, 129, 0.20) !important; }  /* Заказ 3: Зеленый */
.dark-theme .day-bg-3 { background-color: rgba(236, 72, 153, 0.20) !important; }  /* Заказ 4: Розовый */
.dark-theme .day-bg-4 { background-color: rgba(168, 85, 247, 0.20) !important; }  /* Заказ 5: Фиолетовый */
.dark-theme .day-bg-5 { background-color: rgba(249, 115, 22, 0.20) !important; }  /* Заказ 6: Оранжевый */
'''

# Очищаем предыдущий блок с day-bg
css = re.sub(r'/\* =========================================================\s*КОНТРАСТНЫЙ ФОН ДНЕЙ[\s\S]*?day-bg-5[^\}]*\}', '', css)

css = css.rstrip() + '\n' + boosted_contrast_css

with open(css_path, 'w', encoding='utf-8') as f:
    f.write(css)

print("Контрастность фонов дней увеличена на 20%.")