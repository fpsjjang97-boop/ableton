<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$id = intval($_GET['id'] ?? 0);
if ($id) {
    // 하위 메뉴도 함께 삭제 (CASCADE가 있지만 명시적으로도 처리)
    $pdo->prepare("DELETE FROM menus WHERE parent_id = ?")->execute([$id]);
    $pdo->prepare("DELETE FROM menus WHERE id = ?")->execute([$id]);
}
header('Location: menus.php?msg=deleted');
exit;
