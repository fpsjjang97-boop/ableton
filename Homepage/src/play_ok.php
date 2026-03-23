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

$stmt = $pdo->prepare('UPDATE tracks SET play_count = play_count + 1 WHERE id = ?');
$stmt->execute([$trackId]);

$stmt = $pdo->prepare('SELECT play_count FROM tracks WHERE id = ?');
$stmt->execute([$trackId]);
$result = $stmt->fetch();

echo json_encode([
    'success' => true,
    'play_count' => $result ? (int)$result['play_count'] : 0,
]);
