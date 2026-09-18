# NovaStore — Full-Stack Flask E-commerce

A production-oriented e-commerce starter built with Flask, SQLAlchemy, SQLite/PostgreSQL, Flask-Login, Flask-WTF, Jinja, HTML/CSS and vanilla JavaScript.

## Included

- Responsive storefront
- Search, category filter and sorting
- Product detail pages
- Cart and wishlist using guest sessions
- Guest Cash on Delivery checkout
- Orders and stock updates
- Admin authentication
- Product/category management
- Advertisement and banner management
- Store settings
- Order status management
- Reviews
- SEO routes: robots.txt and sitemap.xml
- SQLite locally; PostgreSQL supported through DATABASE_URL
- Secure password hashing
- CSRF protection
- Upload validation and 8 MB upload limit

## Local setup (Windows)

1. Open the project folder in VS Code.
2. Open Terminal.
3. Create a virtual environment:

   `python -m venv .venv`

4. Activate it:

   PowerShell:
   `.venv\Scripts\Activate.ps1`

   If PowerShell blocks scripts, use:
   `Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass`
   then activate again.

5. Install packages:

   `pip install -r requirements.txt`

6. Copy `.env.example` to `.env` and change the admin password. For a simple local run, the default SQLite DATABASE_URL is enough.

7. Start:

   `python app.py`

8. Open:

   http://127.0.0.1:5000

9. Admin:

   http://127.0.0.1:5000/admin/login

The first run creates the database, admin account, categories, demo products and settings.

## Important

For real deployment, set a strong random SECRET_KEY and a strong ADMIN_PASSWORD. Never commit `.env` or secrets to GitHub.

The current production upload handler uses the local filesystem. Free Render web services have ephemeral filesystems, so uploaded files can disappear after restarts/redeploys. For a real store, move uploaded images to persistent object storage such as Supabase Storage and store only their public URLs in ProductImage/Banner/Advertisement.

## PostgreSQL

Set:

DATABASE_URL=postgresql+psycopg://USER:PASSWORD@HOST:5432/DATABASE

The same SQLAlchemy models work with PostgreSQL.

## Deployment

Recommended free test deployment:

- GitHub for source control
- Render Free Web Service for Flask
- Supabase Free Postgres for persistent relational data

Render Free web services can sleep after 15 minutes of inactivity. Render's free Postgres is not recommended here because it expires after 30 days; use Supabase Free for the database.

See DEPLOYMENT.md for exact steps.

## Demo data

Demo products are created only when the database has no products. Delete them from Admin > Products after you understand the system, then add your own.

## Online payments

This project intentionally does NOT fake payment processing. Checkout is Cash on Delivery. A real payment gateway should be added only after obtaining a legitimate merchant account and credentials.

## Testing checklist

- Browse home/shop
- Search and sort
- Add/remove/update cart
- Wishlist toggle
- Checkout with COD
- Admin login
- Add/edit/delete product
- Add/delete category
- Add/delete banner
- Add/delete advertisement
- Change order status
- Change store settings
