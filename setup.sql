CREATE DATABASE IF NOT EXISTS stock_management CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE stock_management;

CREATE TABLE IF NOT EXISTS products (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    sku VARCHAR(100) NOT NULL UNIQUE,
    category VARCHAR(100) DEFAULT 'General',
    quantity INT NOT NULL DEFAULT 0,
    min_stock INT NOT NULL DEFAULT 30,
    unit_price DECIMAL(10,2) NOT NULL DEFAULT 0.00,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

CREATE TABLE IF NOT EXISTS stock_movements (
    id INT AUTO_INCREMENT PRIMARY KEY,
    product_id INT NOT NULL,
    type ENUM('in', 'out') NOT NULL,
    quantity INT NOT NULL,
    notes VARCHAR(500) DEFAULT '',
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (product_id) REFERENCES products(id) ON DELETE CASCADE
);

-- FOTOMORI Inventory (seeded from March 2026 stock take — Week 4 quantities)
-- Note: Order if stock below 30 (except Ink: min = 2)

INSERT INTO products (name, sku, category, quantity, min_stock, unit_price) VALUES
-- Paper
('4R Paper - Glossy',       'PAP-4RG',    'Paper',       400,  30,  0.00),
('4R Paper - Matte',        'PAP-4RM',    'Paper',        35,  30,  0.00),
('Polaroid Paper',          'PAP-POL',    'Paper',        20,  30,  0.00),
('BP / A4',                 'PAP-BPA4',   'Paper',       450,  30,  0.00),
('Thermal Paper',           'PAP-THM',    'Paper',         2,  30,  0.00),

-- Batteries
('AAA Battery',             'BAT-AAA',    'Battery',      15,  30,  0.00),
('AA Battery',              'BAT-AA',     'Battery',       6,  30,  0.00),
('CR2025 3V Battery',       'BAT-CR2025', 'Battery',       6,  30,  0.00),

-- Frames
('4R Frame - Black',        'FRM-4RB',    'Frames',       18,  30,  0.00),
('4R Frame - Nude',         'FRM-4RN',    'Frames',       20,  30,  0.00),
('A4 Frame - Black',        'FRM-A4B',    'Frames',        6,  30,  0.00),
('A4 Frame - Nude',         'FRM-A4N',    'Frames',       14,  30,  0.00),

-- Ink (Epson 057 series — tracked in cartridge units; min = 2)
('LM-057 Epson Ink',        'INK-LM057',  'Ink',           1,   2,  0.00),
('Y-057 Epson Ink',         'INK-Y057',   'Ink',           1,   2,  0.00),
('C-057 Epson Ink',         'INK-C057',   'Ink',           1,   2,  0.00),
('M-057 Epson Ink',         'INK-M057',   'Ink',           1,   2,  0.00),
('BK-057 Epson Ink',        'INK-BK057',  'Ink',           1,   2,  0.00),
('LC-057 Epson Ink',        'INK-LC057',  'Ink',           0,   2,  0.00),

-- Accessories & Marketing
('Sampul',                  'ACC-SAM',    'Accessories',  17,  30,  0.00),
('Ziplock Passport',        'ACC-ZIP',    'Accessories',   1,   1,  0.00),
('Tissue',                  'ACC-TIS',    'Accessories',   4,  30,  0.00),
('Plastick',                'ACC-PLA',    'Accessories',   0,  30,  0.00),
('Gula-Gula',               'ACC-GUL',    'Accessories',   1,   1,  0.00),
('Flyers Small',            'MKT-FLS',    'Marketing',    38,  30,  0.00),
('Flyers Medium',           'MKT-FLM',    'Marketing',    47,  30,  0.00);

-- Seed initial stock movements (Week 4 opening stock)
INSERT INTO stock_movements (product_id, type, quantity, notes)
SELECT id, 'in', quantity, 'Opening stock — March 2026 Week 4'
FROM products WHERE quantity > 0;
