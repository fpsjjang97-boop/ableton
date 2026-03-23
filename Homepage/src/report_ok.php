<?php
require_once 'db.php';

header('Content-Type: application/json');

// 로그인 필수
if (!$currentUser) {
    echo json_encode(['success' => false, 'message' => '로그인이 필요합니다.']);
    exit;
}

// POST 요청만 허용
if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    echo json_encode(['success' => false, 'message' => '잘못된 요청입니다.']);
    exit;
}

$targetType = $_POST['target_type'] ?? '';
$targetId = intval($_POST['target_id'] ?? 0);
$reason = trim($_POST['reason'] ?? '');

// 유효성 검사
$validTypes = ['track', 'prompt', 'post', 'comment', 'user', 'message'];
if (!in_array($targetType, $validTypes) || $targetId <= 0 || $reason === '') {
    echo json_encode(['success' => false, 'message' => '필수 항목을 입력해주세요.']);
    exit;
}

// 자기 자신 콘텐츠 신고 방지
$ownerId = null;
switch ($targetType) {
    case 'track':
        $ownerStmt = $pdo->prepare('SELECT user_id FROM tracks WHERE id = ?');
        $ownerStmt->execute([$targetId]);
        $ownerId = $ownerStmt->fetchColumn();
        break;
    case 'prompt':
        $ownerStmt = $pdo->prepare('SELECT user_id FROM prompts WHERE id = ?');
        $ownerStmt->execute([$targetId]);
        $ownerId = $ownerStmt->fetchColumn();
        break;
    case 'post':
        $ownerStmt = $pdo->prepare('SELECT user_id FROM posts WHERE id = ?');
        $ownerStmt->execute([$targetId]);
        $ownerId = $ownerStmt->fetchColumn();
        break;
    case 'comment':
        $ownerStmt = $pdo->prepare('SELECT user_id FROM post_comments WHERE id = ?');
        $ownerStmt->execute([$targetId]);
        $ownerId = $ownerStmt->fetchColumn();
        break;
    case 'user':
        $ownerId = $targetId;
        break;
}

if ($ownerId && (int)$ownerId === (int)$currentUser['id']) {
    echo json_encode(['success' => false, 'message' => '자신의 콘텐츠는 신고할 수 없습니다.']);
    exit;
}

// 중복 신고 방지
$dupStmt = $pdo->prepare('SELECT id FROM reports WHERE reporter_id = ? AND target_type = ? AND target_id = ?');
$dupStmt->execute([$currentUser['id'], $targetType, $targetId]);
if ($dupStmt->fetch()) {
    echo json_encode(['success' => false, 'message' => '이미 신고한 항목입니다.']);
    exit;
}

// 신고 등록
$insertStmt = $pdo->prepare('INSERT INTO reports (reporter_id, target_type, target_id, reason, status, created_at) VALUES (?, ?, ?, ?, ?, datetime("now"))');
$insertStmt->execute([$currentUser['id'], $targetType, $targetId, $reason, 'pending']);

echo json_encode(['success' => true, 'message' => '신고가 접수되었습니다.']);
