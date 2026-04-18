<?php
header('Content-Type: application/json');
header('Access-Control-Allow-Origin: *');
header('Access-Control-Allow-Methods: GET, POST, DELETE, OPTIONS');
header('Access-Control-Allow-Headers: Content-Type');

if ($_SERVER['REQUEST_METHOD'] === 'OPTIONS') {
    http_response_code(200);
    exit;
}

require_once 'db.php';

$action = $_GET['action'] ?? '';
$method = $_SERVER['REQUEST_METHOD'];

$body = [];
if ($method === 'POST') {
    $raw = file_get_contents('php://input');
    $body = json_decode($raw, true) ?? [];
}

switch ($action) {

    case 'get_products':
        $db = getDB();
        $search = isset($_GET['search']) ? '%' . $db->real_escape_string($_GET['search']) . '%' : '%';
        $category = isset($_GET['category']) ? $db->real_escape_string($_GET['category']) : '';

        $where = "WHERE name LIKE '$search' OR sku LIKE '$search'";
        if ($category) $where .= " AND category = '$category'";

        $result = $db->query("SELECT * FROM products $where ORDER BY name ASC");
        $products = [];
        while ($row = $result->fetch_assoc()) $products[] = $row;

        $stats = $db->query("SELECT
            COUNT(*) as total_products,
            SUM(quantity) as total_units,
            SUM(quantity * unit_price) as total_value,
            SUM(CASE WHEN quantity <= min_stock THEN 1 ELSE 0 END) as low_stock_count
            FROM products")->fetch_assoc();

        echo json_encode(['products' => $products, 'stats' => $stats]);
        break;

    case 'add_product':
        $db = getDB();
        $name     = $db->real_escape_string(trim($body['name'] ?? ''));
        $sku      = $db->real_escape_string(trim($body['sku'] ?? ''));
        $category = $db->real_escape_string(trim($body['category'] ?? 'General'));
        $quantity = (int)($body['quantity'] ?? 0);
        $min_stock = (int)($body['min_stock'] ?? 10);
        $unit_price = (float)($body['unit_price'] ?? 0);

        if (!$name || !$sku) {
            echo json_encode(['error' => 'Name and SKU are required']);
            break;
        }

        $check = $db->query("SELECT id FROM products WHERE sku = '$sku'");
        if ($check->num_rows > 0) {
            echo json_encode(['error' => 'SKU already exists']);
            break;
        }

        $db->query("INSERT INTO products (name, sku, category, quantity, min_stock, unit_price)
            VALUES ('$name', '$sku', '$category', $quantity, $min_stock, $unit_price)");

        if ($db->error) {
            echo json_encode(['error' => $db->error]);
        } else {
            $id = $db->insert_id;
            if ($quantity > 0) {
                $db->query("INSERT INTO stock_movements (product_id, type, quantity, notes)
                    VALUES ($id, 'in', $quantity, 'Initial stock')");
            }
            echo json_encode(['success' => true, 'id' => $id]);
        }
        break;

    case 'update_stock':
        $db = getDB();
        $product_id = (int)($body['product_id'] ?? 0);
        $type       = $body['type'] ?? '';
        $quantity   = (int)($body['quantity'] ?? 0);
        $notes      = $db->real_escape_string(trim($body['notes'] ?? ''));

        if (!$product_id || !in_array($type, ['in', 'out']) || $quantity <= 0) {
            echo json_encode(['error' => 'Invalid input']);
            break;
        }

        $product = $db->query("SELECT quantity FROM products WHERE id = $product_id")->fetch_assoc();
        if (!$product) {
            echo json_encode(['error' => 'Product not found']);
            break;
        }

        if ($type === 'out' && $product['quantity'] < $quantity) {
            echo json_encode(['error' => 'Insufficient stock. Available: ' . $product['quantity']]);
            break;
        }

        $op = $type === 'in' ? '+' : '-';
        $db->query("UPDATE products SET quantity = quantity $op $quantity WHERE id = $product_id");
        $db->query("INSERT INTO stock_movements (product_id, type, quantity, notes)
            VALUES ($product_id, '$type', $quantity, '$notes')");

        $updated = $db->query("SELECT * FROM products WHERE id = $product_id")->fetch_assoc();
        echo json_encode(['success' => true, 'product' => $updated]);
        break;

    case 'delete_product':
        $db = getDB();
        $id = (int)($_GET['id'] ?? 0);
        if (!$id) { echo json_encode(['error' => 'Invalid ID']); break; }

        $db->query("DELETE FROM products WHERE id = $id");
        echo json_encode(['success' => $db->affected_rows > 0]);
        break;

    case 'get_movements':
        $db = getDB();
        $product_id = (int)($_GET['product_id'] ?? 0);
        $limit = min((int)($_GET['limit'] ?? 50), 200);

        $where = $product_id ? "WHERE sm.product_id = $product_id" : '';
        $result = $db->query("SELECT sm.*, p.name as product_name, p.sku
            FROM stock_movements sm
            JOIN products p ON sm.product_id = p.id
            $where
            ORDER BY sm.created_at DESC
            LIMIT $limit");

        $movements = [];
        while ($row = $result->fetch_assoc()) $movements[] = $row;
        echo json_encode(['movements' => $movements]);
        break;

    case 'get_categories':
        $db = getDB();
        $result = $db->query("SELECT DISTINCT category FROM products ORDER BY category");
        $cats = [];
        while ($row = $result->fetch_assoc()) $cats[] = $row['category'];
        echo json_encode(['categories' => $cats]);
        break;

    default:
        http_response_code(400);
        echo json_encode(['error' => 'Unknown action']);
}
