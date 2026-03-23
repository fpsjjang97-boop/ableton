<?php
require_once 'db.php';

if (!$currentUser) {
    header('Location: login.php');
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: prompt_list.php');
    exit;
}

$promptId = intval($_POST['id'] ?? 0);
if (!$promptId) {
    header('Location: prompt_list.php');
    exit;
}

// 본인 게시물인지 확인
$checkStmt = $pdo->prepare('SELECT * FROM prompts WHERE id = ? AND user_id = ?');
$checkStmt->execute([$promptId, $currentUser['id']]);
$existing = $checkStmt->fetch();
if (!$existing) {
    header('Location: prompt_list.php');
    exit;
}

// 입력값 수집
$title           = trim($_POST['title'] ?? '');
$prompt_text     = trim($_POST['prompt_text'] ?? '');
$exclude_styles  = trim($_POST['exclude_styles'] ?? '');
$description     = trim($_POST['description'] ?? '');
$lyrics          = trim($_POST['lyrics'] ?? '');
$genres_raw      = trim($_POST['genres'] ?? '');
$styles_raw      = trim($_POST['styles'] ?? '');
$suno_link       = trim($_POST['suno_link'] ?? '');
$linked_track_id = !empty($_POST['linked_track_id']) ? (int)$_POST['linked_track_id'] : null;
$sample_label    = trim($_POST['sample_label'] ?? '');
$weirdness       = isset($_POST['weirdness']) ? max(0, min(100, (int)$_POST['weirdness'])) : 50;
$style_influence = isset($_POST['style_influence']) ? max(0, min(100, (int)$_POST['style_influence'])) : 50;
$audio_influence = isset($_POST['audio_influence']) ? max(0, min(100, (int)$_POST['audio_influence'])) : 25;
$remove_sample   = !empty($_POST['remove_sample']);

// 필수값 검증
if (empty($title) || empty($prompt_text)) {
    header('Location: prompt_edit.php?id=' . $promptId . '&error=empty');
    exit;
}

// 길이 제한
if (mb_strlen($title) > 100) $title = mb_substr($title, 0, 100);
if (mb_strlen($prompt_text) > 2000) $prompt_text = mb_substr($prompt_text, 0, 2000);
if (mb_strlen($exclude_styles) > 500) $exclude_styles = mb_substr($exclude_styles, 0, 500);
if (mb_strlen($description) > 1000) $description = mb_substr($description, 0, 1000);
if (mb_strlen($lyrics) > 5000) $lyrics = mb_substr($lyrics, 0, 5000);
if (mb_strlen($sample_label) > 50) $sample_label = mb_substr($sample_label, 0, 50);

// Suno 링크 검증
if (!empty($suno_link) && !filter_var($suno_link, FILTER_VALIDATE_URL)) {
    $suno_link = '';
}

// linked_track_id 유효성 검증
if ($linked_track_id) {
    $stmt = $pdo->prepare('SELECT id FROM tracks WHERE id = ? AND user_id = ?');
    $stmt->execute([$linked_track_id, $currentUser['id']]);
    if (!$stmt->fetch()) {
        $linked_track_id = null;
    }
}

// 샘플 파일 처리
$sample_file_path = $existing['sample_file_path'];

if (!$useSampleSound) {
    $sample_label = '';
}

if ($remove_sample && $sample_file_path) {
    $fullPath = __DIR__ . '/' . $sample_file_path;
    if (file_exists($fullPath)) unlink($fullPath);
    $sample_file_path = null;
}

$sampleUploadDir = __DIR__ . '/uploads/samples';
if (!is_dir($sampleUploadDir)) mkdir($sampleUploadDir, 0755, true);

if ($useSampleSound && isset($_FILES['sample_file']) && $_FILES['sample_file']['error'] === UPLOAD_ERR_OK) {
    $sampleFile = $_FILES['sample_file'];
    if ($sampleFile['size'] > 10 * 1024 * 1024) {
        header('Location: prompt_edit.php?id=' . $promptId . '&error=sample_size');
        exit;
    }
    $sampleExt = strtolower(pathinfo($sampleFile['name'], PATHINFO_EXTENSION));
    if (!in_array($sampleExt, ['mp3', 'wav', 'ogg'])) {
        header('Location: prompt_edit.php?id=' . $promptId . '&error=sample_type');
        exit;
    }
    $sampleMime = mime_content_type($sampleFile['tmp_name']);
    if (!in_array($sampleMime, ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/ogg'])) {
        header('Location: prompt_edit.php?id=' . $promptId . '&error=sample_type');
        exit;
    }
    // 기존 파일 삭제
    if ($sample_file_path && file_exists(__DIR__ . '/' . $sample_file_path)) {
        unlink(__DIR__ . '/' . $sample_file_path);
    }
    $sampleFileName = uniqid('sample_', true) . '.' . $sampleExt;
    $sampleDestPath = $sampleUploadDir . '/' . $sampleFileName;
    if (move_uploaded_file($sampleFile['tmp_name'], $sampleDestPath)) {
        $sample_file_path = 'uploads/samples/' . $sampleFileName;
    }
}

// 장르/스타일 파싱
$genres = array_filter(array_map('trim', explode(',', $genres_raw)));
$styles = array_filter(array_map('trim', explode(',', $styles_raw)));
$genres = array_slice($genres, 0, 3);
$styles = array_slice($styles, 0, 3);

if (empty($genres)) {
    header('Location: prompt_edit.php?id=' . $promptId . '&error=no_genre');
    exit;
}

// 트랜잭션으로 UPDATE
try {
    $pdo->beginTransaction();

    $stmt = $pdo->prepare('
        UPDATE prompts SET
            title = ?, prompt_text = ?, exclude_styles = ?, description = ?, lyrics = ?,
            weirdness = ?, style_influence = ?, audio_influence = ?,
            suno_link = ?, linked_track_id = ?, sample_file_path = ?, sample_label = ?,
            updated_at = datetime("now")
        WHERE id = ? AND user_id = ?
    ');
    $stmt->execute([
        $title, $prompt_text, $exclude_styles ?: null, $description ?: null, $lyrics ?: null,
        $weirdness, $style_influence, $audio_influence,
        $suno_link ?: null, $linked_track_id, $sample_file_path, $sample_label ?: null,
        $promptId, $currentUser['id']
    ]);

    // 장르 교체
    $pdo->prepare('DELETE FROM prompt_genres WHERE prompt_id = ?')->execute([$promptId]);
    $stmtGenre = $pdo->prepare('INSERT OR IGNORE INTO prompt_genres (prompt_id, genre) VALUES (?, ?)');
    foreach ($genres as $genre) {
        if (mb_strlen($genre) <= 50) $stmtGenre->execute([$promptId, $genre]);
    }

    // 스타일 교체
    $pdo->prepare('DELETE FROM prompt_styles WHERE prompt_id = ?')->execute([$promptId]);
    if (!empty($styles)) {
        $stmtStyle = $pdo->prepare('INSERT OR IGNORE INTO prompt_styles (prompt_id, style) VALUES (?, ?)');
        foreach ($styles as $style) {
            if (mb_strlen($style) <= 50) $stmtStyle->execute([$promptId, $style]);
        }
    }

    $pdo->commit();
} catch (Exception $e) {
    $pdo->rollBack();
    header('Location: prompt_edit.php?id=' . $promptId . '&error=db');
    exit;
}

header('Location: prompt_detail.php?id=' . $promptId);
exit;
