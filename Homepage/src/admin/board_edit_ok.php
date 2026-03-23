<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$id = intval($_POST['id'] ?? 0);

$data = [
    'board_key' => $_POST['board_key'] ?? '',
    'board_name' => $_POST['board_name'] ?? '',
    'board_type' => $_POST['board_type'] ?? 'normal',
    'description' => $_POST['description'] ?? '',
    'icon_svg' => $_POST['icon_svg'] ?? '',
    'color_class' => $_POST['color_class'] ?? '',
    'bg_class' => $_POST['bg_class'] ?? '',
    'write_title' => $_POST['write_title'] ?? '글쓰기',
    'use_comment' => isset($_POST['use_comment']) ? 1 : 0,
    'use_like' => isset($_POST['use_like']) ? 1 : 0,
    'use_editor' => isset($_POST['use_editor']) ? 1 : 0,
    'use_popular_tab' => isset($_POST['use_popular_tab']) ? 1 : 0,
    'is_active' => isset($_POST['is_active']) ? 1 : 0,
    'write_level' => intval($_POST['write_level'] ?? 1),
    'comment_level' => intval($_POST['comment_level'] ?? 1),
    'list_level' => intval($_POST['list_level'] ?? 0),
    'posts_per_page' => intval($_POST['posts_per_page'] ?? 20),
    'sort_order' => intval($_POST['sort_order'] ?? 0),
    'updated_at' => date('Y-m-d H:i:s'),
];

if ($id) {
    $sets = [];
    $params = [];
    foreach ($data as $key => $val) {
        $sets[] = "$key = ?";
        $params[] = $val;
    }
    $params[] = $id;
    $stmt = $pdo->prepare("UPDATE boards SET " . implode(', ', $sets) . " WHERE id = ?");
    $stmt->execute($params);
} else {
    $keys = array_keys($data);
    $placeholders = array_fill(0, count($keys), '?');
    $stmt = $pdo->prepare("INSERT INTO boards (" . implode(', ', $keys) . ") VALUES (" . implode(', ', $placeholders) . ")");
    $stmt->execute(array_values($data));
}

header('Location: boards.php?msg=saved');
exit;
