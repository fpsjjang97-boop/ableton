<?php
require_once 'db.php';

header('Content-Type: application/json; charset=utf-8');

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false]);
    exit;
}

$trackId = (int)($_POST['track_id'] ?? 0);
if ($trackId <= 0) {
    http_response_code(400);
    echo json_encode(['success' => false]);
    exit;
}

$stmt = $pdo->prepare('UPDATE tracks SET share_count = share_count + 1 WHERE id = ?');
$stmt->execute([$trackId]);

echo json_encode(['success' => true]);
