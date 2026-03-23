<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

// 기존 설정 업데이트
$settings = $_POST['settings'] ?? [];
$updateStmt = $pdo->prepare("UPDATE site_settings SET setting_value = ?, updated_at = datetime('now') WHERE id = ?");
foreach ($settings as $id => $value) {
    $updateStmt->execute([$value, intval($id)]);
}

// 새 설정 추가
$newGroup = trim($_POST['new_group'] ?? '');
$newKey = trim($_POST['new_key'] ?? '');
$newValue = trim($_POST['new_value'] ?? '');

if ($newGroup && $newKey) {
    $insertStmt = $pdo->prepare("INSERT OR REPLACE INTO site_settings (setting_group, setting_key, setting_value, updated_at) VALUES (?, ?, ?, datetime('now'))");
    $insertStmt->execute([$newGroup, $newKey, $newValue]);
}

header('Location: settings.php?msg=saved');
exit;
