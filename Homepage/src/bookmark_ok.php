<?php
require_once 'db.php';

header('Content-Type: application/json; charset=utf-8');

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

$type = trim($_POST['type'] ?? 'post');
$targetId = (int)($_POST['target_id'] ?? ($_POST['post_id'] ?? 0));
if ($targetId <= 0) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => '잘못된 파라미터입니다.']);
    exit;
}

if ($type === 'track') {
    // 트랙 북마크 (track_saves 테이블 사용)
    $pdo->exec("CREATE TABLE IF NOT EXISTS track_saves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        track_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, track_id)
    )");

    $stmt = $pdo->prepare('SELECT id FROM tracks WHERE id = ?');
    $stmt->execute([$targetId]);
    if (!$stmt->fetch()) {
        http_response_code(404);
        echo json_encode(['success' => false, 'message' => '트랙을 찾을 수 없습니다.']);
        exit;
    }

    $stmt = $pdo->prepare('SELECT id FROM track_saves WHERE user_id = ? AND track_id = ?');
    $stmt->execute([$currentUser['id'], $targetId]);
    $existing = $stmt->fetch();

    if ($existing) {
        $stmt = $pdo->prepare('DELETE FROM track_saves WHERE id = ?');
        $stmt->execute([$existing['id']]);
        $bookmarked = false;
    } else {
        $stmt = $pdo->prepare("INSERT INTO track_saves (user_id, track_id, created_at) VALUES (?, ?, datetime('now'))");
        $stmt->execute([$currentUser['id'], $targetId]);
        $bookmarked = true;
    }

    echo json_encode(['success' => true, 'bookmarked' => $bookmarked]);

} elseif ($type === 'prompt') {
    // 프롬프트 스크랩 (prompt_saves 테이블 사용)
    $stmt = $pdo->prepare('SELECT id FROM prompts WHERE id = ?');
    $stmt->execute([$targetId]);
    if (!$stmt->fetch()) {
        http_response_code(404);
        echo json_encode(['success' => false, 'message' => '프롬프트를 찾을 수 없습니다.']);
        exit;
    }

    $stmt = $pdo->prepare('SELECT id FROM prompt_saves WHERE user_id = ? AND prompt_id = ?');
    $stmt->execute([$currentUser['id'], $targetId]);
    $existing = $stmt->fetch();

    if ($existing) {
        $stmt = $pdo->prepare('DELETE FROM prompt_saves WHERE id = ?');
        $stmt->execute([$existing['id']]);
        $pdo->prepare('UPDATE prompts SET save_count = MAX(0, save_count - 1) WHERE id = ?')->execute([$targetId]);
        $bookmarked = false;
    } else {
        $stmt = $pdo->prepare("INSERT INTO prompt_saves (user_id, prompt_id, created_at) VALUES (?, ?, datetime('now'))");
        $stmt->execute([$currentUser['id'], $targetId]);
        $pdo->prepare('UPDATE prompts SET save_count = save_count + 1 WHERE id = ?')->execute([$targetId]);
        $bookmarked = true;
    }

    $countStmt = $pdo->prepare('SELECT save_count FROM prompts WHERE id = ?');
    $countStmt->execute([$targetId]);
    $saveCount = (int)$countStmt->fetchColumn();

    echo json_encode(['success' => true, 'bookmarked' => $bookmarked, 'count' => $saveCount]);
} else {
    // 게시물 북마크 (bookmarks 테이블 사용)
    $stmt = $pdo->prepare('SELECT id FROM posts WHERE id = ?');
    $stmt->execute([$targetId]);
    if (!$stmt->fetch()) {
        http_response_code(404);
        echo json_encode(['success' => false, 'message' => '게시물을 찾을 수 없습니다.']);
        exit;
    }

    $stmt = $pdo->prepare('SELECT id FROM bookmarks WHERE user_id = ? AND post_id = ?');
    $stmt->execute([$currentUser['id'], $targetId]);
    $existing = $stmt->fetch();

    if ($existing) {
        $stmt = $pdo->prepare('DELETE FROM bookmarks WHERE id = ?');
        $stmt->execute([$existing['id']]);
        $bookmarked = false;
    } else {
        $stmt = $pdo->prepare("INSERT INTO bookmarks (user_id, post_id, created_at) VALUES (?, ?, datetime('now'))");
        $stmt->execute([$currentUser['id'], $targetId]);
        $bookmarked = true;
    }

    echo json_encode(['success' => true, 'bookmarked' => $bookmarked]);
}
