<?php
require_once 'db.php';

if (!$currentUser) {
    header('Location: login.php');
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: index.php');
    exit;
}

$postId = isset($_POST['id']) ? (int)$_POST['id'] : 0;
$board_key = trim($_POST['board'] ?? 'free');
$title = trim($_POST['title'] ?? '');
$content = $_POST['content'] ?? '';
$category_id = !empty($_POST['category_id']) ? (int)$_POST['category_id'] : null;

if (empty($title) || empty($content) || $postId <= 0) {
    header('Location: board_edit.php?board=' . urlencode($board_key) . '&id=' . $postId);
    exit;
}

if (mb_strlen($title) > 200) {
    $title = mb_substr($title, 0, 200);
}

$stmt = $pdo->prepare('SELECT * FROM posts WHERE id = ?');
$stmt->execute([$postId]);
$post = $stmt->fetch();

if (!$post || $post['user_id'] != $currentUser['id']) {
    header('Location: board_list.php?board=' . urlencode($board_key));
    exit;
}

$stmt = $pdo->prepare('SELECT id, board_type FROM boards WHERE board_key = ? AND is_active = 1');
$stmt->execute([$board_key]);
$board = $stmt->fetch();

if (!$board) {
    header('Location: index.php');
    exit;
}

if ($category_id) {
    $stmt = $pdo->prepare('SELECT id FROM board_categories WHERE id = ? AND board_id = ? AND is_active = 1');
    $stmt->execute([$category_id, $board['id']]);
    if (!$stmt->fetch()) $category_id = null;
}

$recruit_count = null;
$contact_type = null;
$contact_info = null;
if ($board['board_type'] === 'collab') {
    $recruit_count = isset($_POST['recruit_count']) ? max(1, min(20, (int)$_POST['recruit_count'])) : 1;
    $contact_type = trim($_POST['contact_type'] ?? 'other');
    if (!in_array($contact_type, ['openchat', 'instagram', 'phone', 'email', 'other'])) $contact_type = 'other';
    $contact_info = trim($_POST['contact_info'] ?? '');
    if (mb_strlen($contact_info) > 300) $contact_info = mb_substr($contact_info, 0, 300);
}

$allowed_tags = '<p><br><strong><b><em><i><u><s><strike><h1><h2><h3><h4><h5><h6>'
    . '<ul><ol><li><blockquote><pre><code><a><img><table><thead><tbody><tr><th><td>'
    . '<hr><div><span><sub><sup><font><video><iframe>';
$content = strip_tags($content, $allowed_tags);

$stmt = $pdo->prepare('
    UPDATE posts SET category_id = ?, title = ?, content = ?, recruit_count = ?, contact_type = ?, contact_info = ?, updated_at = datetime("now")
    WHERE id = ? AND user_id = ?
');
$stmt->execute([$category_id, $title, $content, $recruit_count, $contact_type, $contact_info, $postId, $currentUser['id']]);

header('Location: board_detail.php?board=' . urlencode($board_key) . '&id=' . $postId);
exit;
