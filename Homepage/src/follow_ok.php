<?php
require_once 'db.php';

header('Content-Type: application/json; charset=utf-8');

// 로그인 확인
if (!$currentUser) {
    http_response_code(401);
    echo json_encode(['success' => false, 'message' => '로그인이 필요합니다.']);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'message' => '잘못된 요청입니다.']);
    exit;
}

$targetUserId = (int)($_POST['user_id'] ?? 0);

if ($targetUserId <= 0) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => '잘못된 파라미터입니다.']);
    exit;
}

// 자기 자신 팔로우 방지
if ($targetUserId === (int)$currentUser['id']) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => '자기 자신을 팔로우할 수 없습니다.']);
    exit;
}

// 대상 유저 존재 확인
$stmt = $pdo->prepare('SELECT id FROM users WHERE id = ?');
$stmt->execute([$targetUserId]);
if (!$stmt->fetch()) {
    http_response_code(404);
    echo json_encode(['success' => false, 'message' => '존재하지 않는 유저입니다.']);
    exit;
}

try {
    // 기존 팔로우 확인
    $stmt = $pdo->prepare('SELECT id FROM follows WHERE follower_id = ? AND following_id = ?');
    $stmt->execute([$currentUser['id'], $targetUserId]);
    $existing = $stmt->fetch();

    if ($existing) {
        // 언팔로우
        $stmt = $pdo->prepare('DELETE FROM follows WHERE id = ?');
        $stmt->execute([$existing['id']]);
        $followed = false;
    } else {
        // 팔로우
        $stmt = $pdo->prepare('INSERT INTO follows (follower_id, following_id, created_at) VALUES (?, ?, datetime("now"))');
        $stmt->execute([$currentUser['id'], $targetUserId]);
        $followed = true;
    }

    // 최신 팔로워 수 조회
    $stmt = $pdo->prepare('SELECT COUNT(*) FROM follows WHERE following_id = ?');
    $stmt->execute([$targetUserId]);
    $followerCount = (int)$stmt->fetchColumn();

    echo json_encode([
        'success'        => true,
        'followed'       => $followed,
        'follower_count' => $followerCount,
    ]);

} catch (Exception $e) {
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => '서버 오류가 발생했습니다.']);
}

exit;
