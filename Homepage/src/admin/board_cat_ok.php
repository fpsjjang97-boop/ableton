<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$action = $_REQUEST['action'] ?? '';
$boardId = intval($_REQUEST['board_id'] ?? 0);

if (!$boardId) { header('Location: boards.php'); exit; }

switch ($action) {
    case 'add':
        $name = trim($_POST['category_name'] ?? '');
        $sortOrder = intval($_POST['sort_order'] ?? 0);
        if ($name) {
            $stmt = $pdo->prepare("INSERT OR IGNORE INTO board_categories (board_id, category_name, sort_order, is_active) VALUES (?, ?, ?, 1)");
            $stmt->execute([$boardId, $name, $sortOrder]);
        }
        break;

    case 'delete':
        $catId = intval($_GET['cat_id'] ?? 0);
        if ($catId) {
            // 해당 카테고리를 사용하는 게시글의 category_id를 NULL로
            $pdo->prepare("UPDATE posts SET category_id = NULL WHERE category_id = ?")->execute([$catId]);
            $pdo->prepare("DELETE FROM board_categories WHERE id = ? AND board_id = ?")->execute([$catId, $boardId]);
        }
        break;

    case 'deactivate':
        $catId = intval($_GET['cat_id'] ?? 0);
        if ($catId) {
            $pdo->prepare("UPDATE board_categories SET is_active = 0 WHERE id = ? AND board_id = ?")->execute([$catId, $boardId]);
        }
        break;

    case 'activate':
        $catId = intval($_GET['cat_id'] ?? 0);
        if ($catId) {
            $pdo->prepare("UPDATE board_categories SET is_active = 1 WHERE id = ? AND board_id = ?")->execute([$catId, $boardId]);
        }
        break;
}

// 게시판의 board_id로 board를 조회해서 board_edit로 복귀
$stmt = $pdo->prepare("SELECT id FROM boards WHERE id = ?");
$stmt->execute([$boardId]);
$board = $stmt->fetch();

header("Location: board_edit.php?id=$boardId");
exit;
