<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$id = intval($_GET['id'] ?? 0);
if ($id) {
    $stmt = $pdo->prepare("DELETE FROM prompts WHERE id = ?");
    $stmt->execute([$id]);
}
header('Location: prompts.php');
exit;
