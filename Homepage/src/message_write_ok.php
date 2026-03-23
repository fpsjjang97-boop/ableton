<?php
require_once 'db.php';

// ── 로그인 확인 ──
if (!$currentUser) {
    header('Location: login.php');
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: message_write.php');
    exit;
}

// ── 입력값 수집 ──
$to      = trim($_POST['to'] ?? '');
$title   = trim($_POST['title'] ?? '');
$content = trim($_POST['content'] ?? '');

// ── 필수값 검증 ──
if (empty($to) || empty($title) || empty($content)) {
    header('Location: message_write.php?to=' . urlencode($to) . '&error=empty');
    exit;
}

// ── 길이 제한 ──
if (mb_strlen($title) > 200) {
    $title = mb_substr($title, 0, 200);
}
if (mb_strlen($content) > 2000) {
    $content = mb_substr($content, 0, 2000);
}

// ── 수신자 닉네임으로 user_id 조회 ──
$stmt = $pdo->prepare('SELECT id FROM users WHERE nickname = ?');
$stmt->execute([$to]);
$receiver = $stmt->fetch();

if (!$receiver) {
    header('Location: message_write.php?to=' . urlencode($to) . '&error=user_not_found');
    exit;
}

$receiver_id = $receiver['id'];

// ── 자기 자신에게 보내기 방지 ──
if ($receiver_id == $currentUser['id']) {
    header('Location: message_write.php?to=' . urlencode($to) . '&error=self_message');
    exit;
}

// ── INSERT ──
$stmt = $pdo->prepare('
    INSERT INTO messages (sender_id, receiver_id, title, content, created_at)
    VALUES (?, ?, ?, ?, datetime("now"))
');
$stmt->execute([
    $currentUser['id'],
    $receiver_id,
    $title,
    $content
]);

// 리다이렉트: 대화방에서 보낸 경우 대화방으로 복귀
$redirect = isset($_POST['redirect']) ? $_POST['redirect'] : '';
if (!empty($redirect) && strpos($redirect, 'message_view.php') === 0) {
    header('Location: ' . $redirect);
} else {
    header('Location: message_view.php?user=' . $receiver_id);
}
exit;
