# SkillSwap — веб-система бартерного обміну навичками

Дипломний проєкт для спеціальності **126 Інформаційні системи та технології**.
Система реалізує платформу, де користувачі можуть пропонувати власні навички,
шукати навички інших користувачів, створювати запити на бартерний обмін,
планувати сесії, залишати відгуки та формувати рівень довіри.

## Що входить у систему

- реєстрація, авторизація, профілі користувачів;
- каталог навичок із категоріями, рівнями та пошуком;
- алгоритм підбору партнерів для бартерного обміну;
- заявки на обмін, сесії, повідомлення та відгуки;
- бейджі, рейтинги, скарги, диспути та підтримка;
- адміністративна панель і модерація;
- REST API та health-check `/health/status`;
- оптимізація під Render Free: легкі залежності, 1 worker, 2 threads.

## Локальний запуск у PyCharm / Windows

```bash
cd C:\Users\lubch\SkillSwap
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Відкрити у браузері:

```text
http://127.0.0.1:5000
```

## Запуск після розпакування цього архіву

1. Розпакуй архів у зручну папку, наприклад `C:\Users\lubch\SkillSwap_optimized`.
2. Відкрий цю папку в PyCharm через `File → Open`.
3. Відкрий Terminal у PyCharm.
4. Виконай команди:

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

## Render Free

### Build Command

```bash
pip install -r requirements.txt
```

### Start Command

```bash
gunicorn "app:create_app()" --workers 1 --worker-class gthread --threads 2 --timeout 120 --bind 0.0.0.0:$PORT
```

### Environment Variables

```text
WEB_CONCURRENCY=1
FLASK_ENV=production
FLASK_DEBUG=0
WTF_CSRF_ENABLED=True
AUTO_DB_INIT=1
LIGHTWEIGHT_LANDING=1
ENABLE_REALTIME=0
DATABASE_URL=<Render PostgreSQL External/Internal URL>
SECRET_KEY=<your-secret-key>
UPLOAD_FOLDER=skillswap/static/uploads/avatars
```

## Що було оптимізовано

- прибрано важкі залежності `numpy`, `scipy`, `scikit-learn`, `celery`, `redis`, `psutil`, `pytest` із production requirements;
- замінено `geventwebsocket` на `gthread`, що стабільніше для Render Free;
- головна сторінка не робить важкі запити до бази під час першого відкриття;
- Socket.IO не підключається для кожного гостя сайту, якщо `ENABLE_REALTIME=0`;
- додано сторінку `/system` для демонстрації ознак інформаційної системи на захисті;
- додано production-friendly `config.py`, `Procfile`, `runtime.txt`, `gunicorn.conf.py`.

## Корисні URL

```text
/                 — легка стартова сторінка
/system           — опис системи для захисту
/auth/register    — реєстрація
/auth/login       — вхід
/dashboard        — кабінет користувача
/skills           — каталог навичок
/exchanges        — обміни
/admin            — адмін-панель
/health/status    — перевірка стану сервера
```
