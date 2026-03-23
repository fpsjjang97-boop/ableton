<?php
require_once 'db.php';

// ── 로그인 확인 ──
if (!$currentUser) {
    header('Location: login.php');
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: prompt_write.php');
    exit;
}

// ── 입력값 수집 ──
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

// ── 필수값 검증 ──
if (empty($title) || empty($prompt_text)) {
    header('Location: prompt_write.php?error=empty');
    exit;
}

// ── 길이 제한 ──
if (mb_strlen($title) > 100) {
    $title = mb_substr($title, 0, 100);
}
if (mb_strlen($prompt_text) > 2000) {
    $prompt_text = mb_substr($prompt_text, 0, 2000);
}
if (mb_strlen($exclude_styles) > 500) {
    $exclude_styles = mb_substr($exclude_styles, 0, 500);
}
if (mb_strlen($description) > 1000) {
    $description = mb_substr($description, 0, 1000);
}
if (mb_strlen($lyrics) > 5000) {
    $lyrics = mb_substr($lyrics, 0, 5000);
}
if (mb_strlen($sample_label) > 50) {
    $sample_label = mb_substr($sample_label, 0, 50);
}

// ── Suno 링크 검증 ──
if (!empty($suno_link) && !filter_var($suno_link, FILTER_VALIDATE_URL)) {
    $suno_link = '';
}

// ── linked_track_id 유효성 검증 (본인 소유 곡인지) ──
if ($linked_track_id) {
    $stmt = $pdo->prepare('SELECT id FROM tracks WHERE id = ? AND user_id = ?');
    $stmt->execute([$linked_track_id, $currentUser['id']]);
    if (!$stmt->fetch()) {
        $linked_track_id = null;
    }
}

// ── 샘플 파일 업로드 처리 (설정에 따라 on/off) ──
$sample_file_path = null;
if (!$useSampleSound) {
    $sample_label = '';
}

$sampleUploadDir = __DIR__ . '/uploads/samples';
if (!is_dir($sampleUploadDir)) {
    mkdir($sampleUploadDir, 0755, true);
}

if ($useSampleSound && isset($_FILES['sample_file']) && $_FILES['sample_file']['error'] === UPLOAD_ERR_OK) {
    $sampleFile = $_FILES['sample_file'];

    // 파일 크기 제한 (10MB)
    if ($sampleFile['size'] > 10 * 1024 * 1024) {
        header('Location: prompt_write.php?error=sample_size');
        exit;
    }

    // 확장자 검증
    $sampleExt = strtolower(pathinfo($sampleFile['name'], PATHINFO_EXTENSION));
    $allowedSample = ['mp3', 'wav', 'ogg'];
    if (!in_array($sampleExt, $allowedSample)) {
        header('Location: prompt_write.php?error=sample_type');
        exit;
    }

    // MIME 타입 검증
    $sampleMime = mime_content_type($sampleFile['tmp_name']);
    $allowedSampleMimes = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/ogg'];
    if (!in_array($sampleMime, $allowedSampleMimes)) {
        header('Location: prompt_write.php?error=sample_type');
        exit;
    }

    // 고유 파일명 생성
    $sampleFileName = uniqid('sample_', true) . '.' . $sampleExt;
    $sampleDestPath = $sampleUploadDir . '/' . $sampleFileName;

    if (move_uploaded_file($sampleFile['tmp_name'], $sampleDestPath)) {
        $sample_file_path = 'uploads/samples/' . $sampleFileName;
    }
}

// ── 장르/스타일 파싱 ──
$genres = array_filter(array_map('trim', explode(',', $genres_raw)));
$styles = array_filter(array_map('trim', explode(',', $styles_raw)));

// 최대 3개 제한
$genres = array_slice($genres, 0, 3);
$styles = array_slice($styles, 0, 3);

// ── 장르 최소 1개 필수 ──
if (empty($genres)) {
    header('Location: prompt_write.php?error=no_genre');
    exit;
}

// ── 트랜잭션으로 INSERT ──
try {
    $pdo->beginTransaction();

    // prompts 테이블 INSERT
    $stmt = $pdo->prepare('
        INSERT INTO prompts (
            user_id, title, prompt_text, exclude_styles, description, lyrics,
            weirdness, style_influence, audio_influence,
            suno_link, linked_track_id, sample_file_path, sample_label,
            created_at, updated_at
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime("now"), datetime("now"))
    ');
    $stmt->execute([
        $currentUser['id'],
        $title,
        $prompt_text,
        $exclude_styles ?: null,
        $description ?: null,
        $lyrics ?: null,
        $weirdness,
        $style_influence,
        $audio_influence,
        $suno_link ?: null,
        $linked_track_id,
        $sample_file_path,
        $sample_label ?: null
    ]);

    $promptId = $pdo->lastInsertId();

    // prompt_genres INSERT
    $stmtGenre = $pdo->prepare('INSERT OR IGNORE INTO prompt_genres (prompt_id, genre) VALUES (?, ?)');
    foreach ($genres as $genre) {
        if (mb_strlen($genre) <= 50) {
            $stmtGenre->execute([$promptId, $genre]);
        }
    }

    // prompt_styles INSERT
    if (!empty($styles)) {
        $stmtStyle = $pdo->prepare('INSERT OR IGNORE INTO prompt_styles (prompt_id, style) VALUES (?, ?)');
        foreach ($styles as $style) {
            if (mb_strlen($style) <= 50) {
                $stmtStyle->execute([$promptId, $style]);
            }
        }
    }

    $pdo->commit();
} catch (Exception $e) {
    $pdo->rollBack();
    // 업로드된 샘플 파일 정리
    if ($sample_file_path && file_exists(__DIR__ . '/' . $sample_file_path)) {
        unlink(__DIR__ . '/' . $sample_file_path);
    }
    header('Location: prompt_write.php?error=db');
    exit;
}

header('Location: prompt_list.php');
exit;
