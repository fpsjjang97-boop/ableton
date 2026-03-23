<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$id = intval($_GET['id'] ?? 0);
if ($id) {
    // 오디오/커버 파일 삭제
    $stmt = $pdo->prepare("SELECT audio_file_path, cover_image_path FROM tracks WHERE id = ?");
    $stmt->execute([$id]);
    $track = $stmt->fetch();
    if ($track) {
        $base = dirname(__DIR__);
        if ($track['audio_file_path'] && file_exists($base . '/' . $track['audio_file_path'])) {
            unlink($base . '/' . $track['audio_file_path']);
        }
        if ($track['cover_image_path'] && file_exists($base . '/' . $track['cover_image_path'])) {
            unlink($base . '/' . $track['cover_image_path']);
        }
    }
    $stmt = $pdo->prepare("DELETE FROM tracks WHERE id = ?");
    $stmt->execute([$id]);
}
header('Location: tracks.php');
exit;
