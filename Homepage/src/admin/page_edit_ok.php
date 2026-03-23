<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$id = intval($_POST['id'] ?? 0);
if (!$id) { header('Location: pages.php'); exit; }

$title = trim($_POST['title'] ?? '');
$content = $_POST['content'] ?? '';
$isActive = isset($_POST['is_active']) ? 1 : 0;

$stmt = $pdo->prepare("UPDATE site_pages SET title = ?, content = ?, is_active = ?, updated_at = datetime('now') WHERE id = ?");
$stmt->execute([$title, $content, $isActive, $id]);

header('Location: pages.php?msg=saved');
exit;
