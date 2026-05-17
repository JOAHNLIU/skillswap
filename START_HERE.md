# SkillSwap — email verification before onboarding

Ця збірка змінює принцип підтвердження пошти:

1. Користувач реєструється.
2. Система одразу створює акаунт, але блокує доступ до профілю, навичок, пошуку та обмінів.
3. На пошту користувача надсилається лист із кнопкою **«Підтвердити email»**.
4. Користувач відкриває свою пошту і натискає кнопку у листі.
5. Після підтвердження email користувача повертає в SkillSwap.
6. Тільки після цього він переходить до налаштування профілю, а потім до додавання навичок.

Так ніхто не зможе повноцінно користуватися системою, якщо зареєстрував акаунт на чужу пошту.

---

## 1. Розпакування

Скачай ZIP і розпакуй, наприклад сюди:

```text
C:\Users\lubch\Desktop\SkillSwap
```

Відкрий саме цю папку в PyCharm.

---

## 2. Локальний запуск

У терміналі PyCharm:

```bat
cd C:\Users\lubch\Desktop\SkillSwap
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
python app.py
```

Відкрити:

```text
http://127.0.0.1:5000
```

---

## 3. Важливо про SMTP

Підтвердження email тепер працює через реальний лист на пошту.
Щоб листи реально приходили, у файлі `.env` треба вказати SMTP.

Для Gmail потрібно створити **Google App Password**, звичайний пароль Gmail не підходить.

У `.env` має бути:

```text
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=1
MAIL_USE_SSL=0
MAIL_USERNAME=твоя_пошта@gmail.com
MAIL_PASSWORD=16_символьний_google_app_password
MAIL_DEFAULT_SENDER=твоя_пошта@gmail.com
```

Якщо SMTP не налаштований, акаунт створиться, але лист не буде надіслано, і користувач залишиться на сторінці очікування підтвердження email.

---

## 4. Перевірка сценарію

1. Зареєструй нового користувача.
2. Після реєстрації має відкритися сторінка **«Підтвердіть вашу пошту»**.
3. Користувач не повинен мати доступу до `/dashboard`, `/skills`, `/exchanges`, `/users` до підтвердження email.
4. Відкрий пошту.
5. Натисни кнопку **«Підтвердити email»** у листі.
6. Після підтвердження користувача поверне у SkillSwap.
7. Далі він заповнює профіль.
8. Потім додає мінімум одну навичку, яку надає, і мінімум одну навичку, яку шукає.
9. Тільки після цього відкривається вся система.

---

## 5. GitHub

Якщо це нова розпакована папка без Git:

```bat
git init
git remote add origin https://github.com/JOAHNLIU/skillswap.git
git branch -M main
git add .
git commit -m "Require real email verification before onboarding"
git push -u origin main --force
```

Якщо це твоя стара Git-папка:

```bat
git status
git add .
git commit -m "Require real email verification before onboarding"
git push
```

---

## 6. Render

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
LIGHTWEIGHT_LANDING=0
ENABLE_REALTIME=0
DATABASE_URL=твій PostgreSQL URL
SECRET_KEY=твій секретний ключ
UPLOAD_FOLDER=skillswap/static/uploads/avatars
MAIL_SERVER=smtp.gmail.com
MAIL_PORT=587
MAIL_USE_TLS=1
MAIL_USE_SSL=0
MAIL_USERNAME=твоя_пошта@gmail.com
MAIL_PASSWORD=твій_Google_App_Password
MAIL_DEFAULT_SENDER=твоя_пошта@gmail.com
```

Після `git push`:

```text
Render → Deploys → Manual Deploy → Clear build cache & deploy
```

---

## 7. Як пояснити в дипломі

У системі реалізовано механізм підтвердження email-адреси користувача. Після реєстрації акаунт створюється, але доступ до основних модулів системи обмежується до моменту підтвердження пошти. На email користувача надсилається лист із унікальним токеном підтвердження. Після переходу за посиланням токен перевіряється сервером, email позначається як підтверджений, після чого користувач може продовжити налаштування профілю та навичок. Такий підхід зменшує ризик реєстрації на чужу поштову адресу та підвищує довіру до користувацьких акаунтів.
