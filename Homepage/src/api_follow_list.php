<?php
require_once 'db.php';

header('Content-Type: application/json; charset=utf-8');

$userId = (int)($_GET['user_id'] ?? 0);
$type = $_GET['type'] ?? 'followers';

if ($userId <= 0) {
    echo json_encode(['users' => []]);
    exit;
}

if ($type === 'following') {
    $stmt = $pdo->prepare('
        SELECT users.id, users.nickname, users.avatar_color
        FROM follows
        JOIN users ON follows.following_id = users.id
        WHERE follows.follower_id = ?
        ORDER BY follows.created_at DESC
    ');
} else {
    $stmt = $pdo->prepare('
        SELECT users.id, users.nickname, users.avatar_color
        FROM follows
        JOIN users ON follows.follower_id = users.id
        WHERE follows.following_id = ?
        ORDER BY follows.created_at DESC
    ');
}

$stmt->execute([$userId]);
$rows = $stmt->fetchAll();

$users = [];
foreach ($rows as $r) {
    $users[] = [
        'id' => $r['id'],
        'nickname' => $r['nickname'],
        'avatar_color' => $r['avatar_color'] ?: 'from-violet-500 to-purple-600',
        'initial' => mb_substr($r['nickname'], 0, 1),
    ];
}

echo json_encode(['users' => $users]);
