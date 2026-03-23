<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$id = intval($_POST['id'] ?? 0);
if (!$id) { header('Location: users.php'); exit; }

$fields = [
    'nickname' => $_POST['nickname'] ?? '',
    'email' => $_POST['email'] ?? '',
    'bio' => $_POST['bio'] ?? '',
    'badge' => $_POST['badge'] ?? 'Bronze',
    'is_admin' => intval($_POST['is_admin'] ?? 0),
    'youtube_url' => $_POST['youtube_url'] ?? '',
    'instagram_url' => $_POST['instagram_url'] ?? '',
    'suno_profile_url' => $_POST['suno_profile_url'] ?? '',
    'updated_at' => date('Y-m-d H:i:s'),
];

$sets = [];
$params = [];
foreach ($fields as $key => $val) {
    $sets[] = "$key = ?";
    $params[] = $val;
}

// 비밀번호 변경
$newPw = $_POST['new_password'] ?? '';
if ($newPw !== '') {
    $sets[] = "password_hash = ?";
    $params[] = password_hash($newPw, PASSWORD_DEFAULT);
}

$params[] = $id;
$sql = "UPDATE users SET " . implode(', ', $sets) . " WHERE id = ?";
$stmt = $pdo->prepare($sql);
$stmt->execute($params);

header("Location: user_edit.php?id=$id&msg=saved");
exit;
