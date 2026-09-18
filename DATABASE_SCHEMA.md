# Database schema

Admin(id, username, password_hash, created_at)
Category(id, name, slug, description, created_at)
Product(id, product_id, name, slug, brand, price, discount_price, stock, short_description, description, specifications, tags, rating, review_count, featured, best_seller, new_arrival, sale_item, created_at, updated_at, category_id)
ProductImage(id, product_id, image_url, alt_text, sort_order)
Customer(id, name, phone, email, address, city, area, postal_code, created_at)
Order(id, order_number, customer_id, subtotal, delivery_charge, total, payment_method, status, notes, created_at)
OrderItem(id, order_id, product_id, product_name, unit_price, quantity)
Review(id, product_id, customer_name, rating, comment, approved, created_at)
Wishlist(id, visitor_key, product_id, created_at)
Advertisement(id, title, description, image_url, cta_text, cta_link, placement, enabled, created_at)
Banner(id, title, subtitle, image_url, button_text, button_link, enabled, sort_order, created_at)
SiteSetting(id, key, value)
