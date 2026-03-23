<?php
require_once 'db.php';

// ── 로그인 확인 ──
if (!$currentUser) {
    header('Location: login.php');
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: index.php');
    exit;
}

// ── 입력값 수집 ──
$board_key   = trim($_POST['board'] ?? ($_GET['board'] ?? 'free'));
$title       = trim($_POST['title'] ?? '');
$content     = $_POST['content'] ?? '';
$category_id = !empty($_POST['category_id']) ? (int)$_POST['category_id'] : null;

// ── 필수값 검증 ──
if (empty($title) || empty($content)) {
    header('Location: board_write.php?board=' . urlencode($board_key) . '&error=empty');
    exit;
}

// ── 제목 길이 제한 (200자) ──
if (mb_strlen($title) > 200) {
    $title = mb_substr($title, 0, 200);
}

// ── board_key로 board_id 조회 ──
$stmt = $pdo->prepare('SELECT id, board_type FROM boards WHERE board_key = ? AND is_active = 1');
$stmt->execute([$board_key]);
$board = $stmt->fetch();

if (!$board) {
    header('Location: index.php?error=invalid_board');
    exit;
}

$board_id   = $board['id'];
$board_type = $board['board_type'];

// ── 카테고리 유효성 확인 ──
if ($category_id) {
    $stmt = $pdo->prepare('SELECT id FROM board_categories WHERE id = ? AND board_id = ? AND is_active = 1');
    $stmt->execute([$category_id, $board_id]);
    if (!$stmt->fetch()) {
        $category_id = null;
    }
}

// ── 협업(collab) 게시판 전용 필드 ──
$recruit_count = null;
$contact_info  = null;

$contact_type = null;

if ($board_type === 'collab') {
    $recruit_count = isset($_POST['recruit_count']) ? max(1, min(20, (int)$_POST['recruit_count'])) : 1;
    $contact_type  = trim($_POST['contact_type'] ?? 'other');
    if (!in_array($contact_type, ['openchat', 'instagram', 'phone', 'email', 'other'])) $contact_type = 'other';
    $contact_info  = trim($_POST['contact_info'] ?? '');
    if (mb_strlen($contact_info) > 300) {
        $contact_info = mb_substr($contact_info, 0, 300);
    }
}

// ── XSS 방지: content는 Summernote HTML이므로 strip_tags 대신 허용 태그만 남김 ──
$allowed_tags = '<p><br><strong><b><em><i><u><s><strike><h1><h2><h3><h4><h5><h6>'
    . '<ul><ol><li><blockquote><pre><code><a><img><table><thead><tbody><tr><th><td>'
    . '<hr><div><span><sub><sup><font><video><iframe>';
$content = strip_tags($content, $allowed_tags);

// ── INSERT ──
$stmt = $pdo->prepare('
    INSERT INTO posts (board_id, user_id, category_id, title, content, recruit_count, contact_type, contact_info, created_at, updated_at)
    VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime("now"), datetime("now"))
');
$stmt->execute([
    $board_id,
    $currentUser['id'],
    $category_id,
    $title,
    $content,
    $recruit_count,
    $contact_type,
    $contact_info
]);

header('Location: board_list.php?board=' . urlencode($board_key));
exit;
