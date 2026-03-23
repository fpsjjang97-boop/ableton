<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$id = intval($_POST['id'] ?? 0);
$parentId = $_POST['parent_id'] !== '' ? intval($_POST['parent_id']) : null;

$data = [
    'parent_id' => $parentId,
    'menu_type' => $_POST['menu_type'] ?? 'link',
    'title' => $_POST['title'] ?? '',
    'subtitle' => $_POST['subtitle'] ?? '',
    'url' => $_POST['url'] ?? '',
    'icon_svg' => $_POST['icon_svg'] ?? '',
    'sort_order' => intval($_POST['sort_order'] ?? 0),
    'is_active' => isset($_POST['is_active']) ? 1 : 0,
    'open_new_tab' => isset($_POST['open_new_tab']) ? 1 : 0,
];

if ($id) {
    $sets = [];
    $params = [];
    foreach ($data as $key => $val) {
        $sets[] = "$key = ?";
        $params[] = $val;
    }
    $params[] = $id;
    $stmt = $pdo->prepare("UPDATE menus SET " . implode(', ', $sets) . " WHERE id = ?");
    $stmt->execute($params);
    header("Location: menu_edit.php?id=$id&msg=saved");
} else {
    $keys = array_keys($data);
    $placeholders = array_fill(0, count($keys), '?');
    $stmt = $pdo->prepare("INSERT INTO menus (" . implode(', ', $keys) . ") VALUES (" . implode(', ', $placeholders) . ")");
    $stmt->execute(array_values($data));
    header('Location: menus.php?msg=saved');
}
exit;
