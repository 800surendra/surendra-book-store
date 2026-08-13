# SurendraBookStore — safe run and deployment

## Local run (PowerShell)

```powershell
cd "C:\Users\HARISH\Documents\Codex\2026-08-13\is\SurendraStore-ULTRA-PRESERVED\surendra-book-store"
$env:DJANGO_DEBUG="1"
$env:DJANGO_SECURE_SSL_REDIRECT="0"
$env:DJANGO_ALLOWED_HOSTS="127.0.0.1,localhost"
C:\Users\HARISH\Documents\Codex\2026-08-13\is\work\surendra-book-store-audit\.venv\Scripts\python.exe manage.py migrate
C:\Users\HARISH\Documents\Codex\2026-08-13\is\work\surendra-book-store-audit\.venv\Scripts\python.exe manage.py runserver
```

Open `http://127.0.0.1:8000/`.

## Production (PythonAnywhere)

1. Create server environment variables from `.env.example`; do **not** upload `.env`.
2. Set `DJANGO_DEBUG=0`, an entirely new `DJANGO_SECRET_KEY`, host/CSRF values for the live domain and the newly rotated SMTP app password.
3. Run `python manage.py migrate` and `python manage.py collectstatic --noinput` inside the PythonAnywhere virtualenv.
4. Configure static files to `staticfiles/` and protected media storage. Payment proofs and e-book source files must not be exposed as public static paths.
5. Delivery accepts every Rajasthan PIN verified by India Post at checkout time. The optional CSV importer can be used only if you later want a narrower, custom service area list.
6. Create a staff account with `python manage.py createsuperuser`, then add books, e-books and store data from `/admin/`.
7. Optional legal demo content: run `python manage.py seed_public_domain_ebooks` to add public-domain Project Gutenberg EPUBs. Paid e-books are added from admin and use the secure manual payment-verification flow.

## Business policy implemented server-side

- Delivery: every Rajasthan PIN code verified by India Post.
- Delivery charge: ₹49 below ₹2,000; free at ₹2,000 and above.
- GST: 0%; prices are GST inclusive.
- Customer payment choices: UPI / dynamic QR / bank transfer only.
- COD and net banking are not accepted by checkout.
- Payment-method selection appears only once, before the payment/QR details screen.
