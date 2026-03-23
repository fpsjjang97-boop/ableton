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
$boardKey = isset($_POST['board']) ? trim($_POST['board']) : 'free';

if ($postId <= 0) {
    header('Location: board_list.php?board=' . urlencode($boardKey));
    exit;
}

$stmt = $pdo->prepare('SELECT user_id FROM posts WHERE id = ?');
$stmt->execute([$postId]);
$post = $stmt->fetch();

if (!$post || $post['user_id'] != $currentUser['id']) {
    header('Location: board_list.php?board=' . urlencode($boardKey));
    exit;
}

$pdo->beginTransaction();
try {
    $pdo->prepare('DELETE FROM post_comment_likes WHERE comment_id IN (SELECT id FROM post_comments WHERE post_id = ?)')->execute([$postId]);
    $pdo->prepare('DELETE FROM post_comments WHERE post_id = ?')->execute([$postId]);
    $pdo->prepare('DELETE FROM post_likes WHERE post_id = ?')->execute([$postId]);
    $pdo->prepare('DELETE FROM bookmarks WHERE post_id = ?')->execute([$postId]);
    $pdo->prepare('DELETE FROM posts WHERE id = ? AND user_id = ?')->execute([$postId, $currentUser['id']]);
    $pdo->commit();
} catch (Exception $e) {
    $pdo->rollBack();
}

header('Location: board_list.php?board=' . urlencode($boardKey));
exit;
