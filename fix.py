# -*- coding: utf-8 -*-
import os

# 1. Обновляем run.py (поддержка динамического порта хостинга $PORT)
run_code = '''import os
from app import create_app

app = create_app()

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
'''

with open('run.py', 'w', encoding='utf-8') as f:
    f.write(run_code)
print("1. run.py настроен под динамический порт хостинга.")


# 2. Обновляем Procfile для Gunicorn
procfile_code = '''web: gunicorn --bind 0.0.0.0:${PORT:-5000} --workers 2 run:app
'''

with open('Procfile', 'w', encoding='utf-8') as f:
    f.write(procfile_code)
print("2. Procfile настроен для корректной маршрутизации хостинга.")


# 3. Создаем конфигурационный файл gunicorn.conf.py (страховка для сервера)
gunicorn_conf = '''import os

port = os.environ.get('PORT', '5000')
bind = f"0.0.0.0:{port}"
workers = 2
timeout = 120
'''

with open('gunicorn.conf.py', 'w', encoding='utf-8') as f:
    f.write(gunicorn_conf)
print("3. gunicorn.conf.py создан.")

print("\nГотово к отправке на хостинг!")