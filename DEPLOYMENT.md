# Free deployment guide

## 1. Create GitHub repository

Create a new GitHub repository and upload this project.

Do NOT upload:
- `.env`
- `store.db`
- `uploads/` contents containing private files

## 2. Create Supabase database

Create a free Supabase project and copy its PostgreSQL connection string.

Supabase Free currently includes a PostgreSQL database with a 500 MB database quota. Free projects can pause after inactivity.

Set this as Render's DATABASE_URL.

## 3. Create Render Web Service

Create a new Render Web Service and connect the GitHub repository.

Build command:

`pip install -r requirements.txt`

Start command:

`gunicorn app:app`

Plan: Free

Environment variables:
- SECRET_KEY = a long random secret
- DATABASE_URL = Supabase PostgreSQL connection string
- ADMIN_USERNAME = your admin username
- ADMIN_PASSWORD = a strong password
- CLOUDINARY_URL = your Cloudinary API URL (recommended for persistent uploads)

## 4. Deploy

Render builds the app and provides an `onrender.com` URL.

The free web service can sleep after 15 minutes of inactivity and take about a minute to wake.

## 5. Persistent product images

Do not rely on local uploads on a free Render service because its filesystem is ephemeral. This project supports Cloudinary automatically when `CLOUDINARY_URL` is configured.

Create a Cloudinary Free account, copy its `CLOUDINARY_URL`, and add it to Render environment variables. Product, banner and advertisement uploads will then be stored in Cloudinary and their HTTPS URLs will be saved in the database. Keep the Cloudinary URL secret and never put it in frontend JavaScript.

## 6. Custom domain

Render supports custom domains and managed TLS. Add your domain in the Render service settings and follow the DNS records Render provides.

## 7. Production security

Before launch:
- Change admin password
- Set a strong SECRET_KEY
- Use HTTPS
- Do not commit `.env`
- Use real object storage for uploads
- Back up the database
- Add rate limiting at the edge/application layer
- Add real payment gateway only after obtaining merchant credentials
