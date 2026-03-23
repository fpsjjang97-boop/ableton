<?php
require_once 'db.php';

header('Content-Type: application/json; charset=utf-8');

if (!$currentUser) {
    echo json_encode(['success' => false, 'message' => '로그인이 필요합니다.']);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    echo json_encode(['success' => false, 'message' => '잘못된 요청입니다.']);
    exit;
}

$postId = (int)($_POST['post_id'] ?? 0);
if ($postId <= 0) {
    echo json_encode(['success' => false, 'message' => '잘못된 파라미터입니다.']);
    exit;
}

$stmt = $pdo->prepare('SELECT user_id, is_closed FROM posts WHERE id = ?');
$stmt->execute([$postId]);
$post = $stmt->fetch();

if (!$post || $post['user_id'] != $currentUser['id']) {
    echo json_encode(['success' => false, 'message' => '권한이 없습니다.']);
    exit;
}

$newStatus = $post['is_closed'] ? 0 : 1;
$pdo->prepare('UPDATE posts SET is_closed = ?, updated_at = datetime("now") WHERE id = ?')->execute([$newStatus, $postId]);

echo json_encode(['success' => true, 'is_closed' => (bool)$newStatus]);
