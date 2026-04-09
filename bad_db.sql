CREATE TABLE user_logs (
    log_date VARCHAR(100), -- Salah tipe data (harusnya DATE/TIMESTAMP)
    user_name VARCHAR(100), -- Redundansi (harusnya user_id)
    action TEXT
);
-- Tidak ada Primary Key (AI harusnya marah)