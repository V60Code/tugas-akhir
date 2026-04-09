-- test.sql
CREATE TABLE users (
    id INT PRIMARY KEY,
    name VARCHAR(100)
);

-- Baris ini HARUS hilang setelah upload (Sanitization)
INSERT INTO users (id, name) VALUES (1, 'Alfarizi');
INSERT INTO users (id, name) VALUES (2, 'Budi');

CREATE TABLE orders (
    id INT PRIMARY KEY,
    user_id INT
);