-- ===============================
-- SMART PARKING DATABASE
-- ===============================

CREATE DATABASE IF NOT EXISTS smartparking;
USE smartparking;

-- ================= ADMIN TABLE =================
CREATE TABLE IF NOT EXISTS admin (
    id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(50),
    password VARCHAR(50)
);

INSERT INTO admin (username, password) VALUES
('admin', 'admin123');


-- ================= PARKING LOTS TABLE =================
CREATE TABLE IF NOT EXISTS parking_lots (
    id INT AUTO_INCREMENT PRIMARY KEY,
    lot_name VARCHAR(50),
    total_slots INT
);

INSERT INTO parking_lots (lot_name, total_slots) VALUES
('A1', 20),
('A3', 25),
('B2', 30);


-- ================= PARKING DATA TABLE =================
CREATE TABLE IF NOT EXISTS parking_data_new (
    id INT AUTO_INCREMENT PRIMARY KEY,
    vehicle_number VARCHAR(50),
    parking_lot VARCHAR(50),
    entry_time DATETIME,
    exit_time DATETIME,
    parking_fee FLOAT DEFAULT 0,
    payment_mode VARCHAR(20),
    payment_status VARCHAR(20) DEFAULT 'Pending',
    transaction_id VARCHAR(100)
);


-- ================= SAMPLE DATA =================

-- Active Vehicles (Pending Payment)
INSERT INTO parking_data_new
(vehicle_number, parking_lot, entry_time, exit_time, parking_fee, payment_mode, payment_status, transaction_id)
VALUES
('MH12AB1234', 'A1', NOW(), NULL, 0, NULL, 'Pending', NULL),
('MH14CD5678', 'A1', NOW(), NULL, 0, NULL, 'Pending', NULL),
('MH20EF9012', 'B2', NOW(), NULL, 0, NULL, 'Pending', NULL);


-- Completed Paid Vehicles
INSERT INTO parking_data_new
(vehicle_number, parking_lot, entry_time, exit_time, parking_fee, payment_mode, payment_status, transaction_id)
VALUES
('MH11GH3456', 'A3', DATE_SUB(NOW(), INTERVAL 3 HOUR), NOW(), 60, 'UPI', 'Paid', 'TXN1001'),
('MH13IJ7890', 'B2', DATE_SUB(NOW(), INTERVAL 2 HOUR), NOW(), 40, 'Card', 'Paid', 'TXN1002'),
('MH15KL4321', 'A1', DATE_SUB(NOW(), INTERVAL 1 HOUR), NOW(), 20, 'Cash', 'Paid', 'TXN1003');