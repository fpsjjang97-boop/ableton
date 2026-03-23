<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$id = intval($_POST['id'] ?? 0);
$status = $_POST['status'] ?? '';

$validStatuses = ['pending', 'reviewed', 'resolved', 'dismissed'];
if ($id && in_array($status, $validStatuses)) {
    $stmt = $pdo->prepare("UPDATE reports SET status = ? WHERE id = ?");
    $stmt->execute([$status, $id]);
}
header('Location: reports.php');
exit;
