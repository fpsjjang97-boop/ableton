<?php
require_once 'db.php';

if (!$currentUser) {
    header('Location: login.php');
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: music_list.php');
    exit;
}

$trackId = intval($_POST['id'] ?? 0);
if (!$trackId) {
    header('Location: music_list.php');
    exit;
}

// 본인 게시물인지 확인
$checkStmt = $pdo->prepare('SELECT * FROM tracks WHERE id = ? AND user_id = ?');
$checkStmt->execute([$trackId, $currentUser['id']]);
$existing = $checkStmt->fetch();
if (!$existing) {
    header('Location: music_list.php');
    exit;
}

// 입력값 수집
$title       = trim($_POST['title'] ?? '');
$description = trim($_POST['description'] ?? '');
$suno_link   = trim($_POST['suno_link'] ?? '');
$genres_raw  = trim($_POST['genres'] ?? '');
$moods_raw   = trim($_POST['moods'] ?? '');
$remove_cover = !empty($_POST['remove_cover']);

// 필수값 검증
if (empty($title)) {
    header('Location: music_edit.php?id=' . $trackId . '&error=empty_title');
    exit;
}

if (mb_strlen($title) > 200) $title = mb_substr($title, 0, 200);
if (mb_strlen($description) > 500) $description = mb_substr($description, 0, 500);

// Suno 링크 정규화
if (!empty($suno_link)) {
    if (strpos($suno_link, 'http://') !== 0 && strpos($suno_link, 'https://') !== 0) {
        $suno_link = 'https://' . $suno_link;
    }
    if (!filter_var($suno_link, FILTER_VALIDATE_URL)) $suno_link = '';
}

// 업로드 디렉토리
$uploadDir = __DIR__ . '/uploads';
$audioUploadDir = $uploadDir . '/audio';
$imageUploadDir = $uploadDir . '/covers';
foreach ([$uploadDir, $audioUploadDir, $imageUploadDir] as $dir) {
    if (!is_dir($dir)) mkdir($dir, 0755, true);
}

// 오디오 파일 업로드 처리
$has_audio_file  = (int)$existing['has_audio_file'];
$audio_file_path = $existing['audio_file_path'];

if (isset($_FILES['audio_file']) && $_FILES['audio_file']['error'] === UPLOAD_ERR_OK) {
    $audioFile = $_FILES['audio_file'];

    if ($audioFile['size'] > 50 * 1024 * 1024) {
        header('Location: music_edit.php?id=' . $trackId . '&error=audio_size');
        exit;
    }

    $audioExt = strtolower(pathinfo($audioFile['name'], PATHINFO_EXTENSION));
    if (!in_array($audioExt, ['mp3', 'wav', 'ogg', 'flac'])) {
        header('Location: music_edit.php?id=' . $trackId . '&error=audio_type');
        exit;
    }

    $audioMime = mime_content_type($audioFile['tmp_name']);
    if (!in_array($audioMime, ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/ogg', 'audio/flac'])) {
        header('Location: music_edit.php?id=' . $trackId . '&error=audio_type');
        exit;
    }

    // 기존 파일 삭제
    if ($audio_file_path && file_exists(__DIR__ . '/' . $audio_file_path)) {
        unlink(__DIR__ . '/' . $audio_file_path);
    }

    $audioFileName = uniqid('audio_', true) . '.' . $audioExt;
    $audioDestPath = $audioUploadDir . '/' . $audioFileName;

    if (move_uploaded_file($audioFile['tmp_name'], $audioDestPath)) {
        $has_audio_file  = 1;
        $audio_file_path = 'uploads/audio/' . $audioFileName;
    }
}

// 커버 이미지 처리
$cover_image_path = $existing['cover_image_path'];

if ($remove_cover && $cover_image_path) {
    if (file_exists(__DIR__ . '/' . $cover_image_path)) unlink(__DIR__ . '/' . $cover_image_path);
    $cover_image_path = null;
}

if (isset($_FILES['cover_image']) && $_FILES['cover_image']['error'] === UPLOAD_ERR_OK) {
    $imageFile = $_FILES['cover_image'];
    if ($imageFile['size'] > 5 * 1024 * 1024) {
        header('Location: music_edit.php?id=' . $trackId . '&error=image_size');
        exit;
    }
    $imageExt = strtolower(pathinfo($imageFile['name'], PATHINFO_EXTENSION));
    if (!in_array($imageExt, ['jpg', 'jpeg', 'png', 'webp', 'gif'])) {
        header('Location: music_edit.php?id=' . $trackId . '&error=image_type');
        exit;
    }
    $imageInfo = getimagesize($imageFile['tmp_name']);
    if ($imageInfo === false) {
        header('Location: music_edit.php?id=' . $trackId . '&error=image_type');
        exit;
    }
    // 기존 커버 삭제
    if ($cover_image_path && file_exists(__DIR__ . '/' . $cover_image_path)) {
        unlink(__DIR__ . '/' . $cover_image_path);
    }
    $imageFileName = uniqid('cover_', true) . '.' . $imageExt;
    $imageDestPath = $imageUploadDir . '/' . $imageFileName;
    if (move_uploaded_file($imageFile['tmp_name'], $imageDestPath)) {
        $cover_image_path = 'uploads/covers/' . $imageFileName;
    }
}

// 최소 하나의 음원 소스 필요
if (empty($suno_link) && !$has_audio_file) {
    header('Location: music_edit.php?id=' . $trackId . '&error=no_source');
    exit;
}

// 프롬프트 연결
$linkedPromptId = (int)($_POST['linked_prompt_id'] ?? 0);

// 장르/분위기 파싱
$genres = array_filter(array_map('trim', explode(',', $genres_raw)));
$moods  = array_filter(array_map('trim', explode(',', $moods_raw)));
$genres = array_slice($genres, 0, 3);
$moods  = array_slice($moods, 0, 3);

// 트랜잭션으로 UPDATE
try {
    $pdo->beginTransaction();

    $stmt = $pdo->prepare('
        UPDATE tracks SET
            title = ?, description = ?, suno_link = ?,
            has_audio_file = ?, audio_file_path = ?, cover_image_path = ?,
            updated_at = datetime("now")
        WHERE id = ? AND user_id = ?
    ');
    $stmt->execute([
        $title, $description ?: null, $suno_link ?: null,
        $has_audio_file, $audio_file_path, $cover_image_path,
        $trackId, $currentUser['id']
    ]);

    // 장르 교체
    $pdo->prepare('DELETE FROM track_genres WHERE track_id = ?')->execute([$trackId]);
    if (!empty($genres)) {
        $stmtGenre = $pdo->prepare('INSERT OR IGNORE INTO track_genres (track_id, genre) VALUES (?, ?)');
        foreach ($genres as $genre) {
            if (mb_strlen($genre) <= 50) $stmtGenre->execute([$trackId, $genre]);
        }
    }

    // 분위기 교체
    $pdo->prepare('DELETE FROM track_moods WHERE track_id = ?')->execute([$trackId]);
    if (!empty($moods)) {
        $stmtMood = $pdo->prepare('INSERT OR IGNORE INTO track_moods (track_id, mood) VALUES (?, ?)');
        foreach ($moods as $mood) {
            if (mb_strlen($mood) <= 50) $stmtMood->execute([$trackId, $mood]);
        }
    }

    // 기존 프롬프트 연결 해제
    $pdo->prepare('UPDATE prompts SET linked_track_id = NULL WHERE linked_track_id = ? AND user_id = ?')
        ->execute([$trackId, $currentUser['id']]);

    // 새 프롬프트 연결
    if ($linkedPromptId > 0) {
        $promptCheckStmt = $pdo->prepare('SELECT id FROM prompts WHERE id = ? AND user_id = ?');
        $promptCheckStmt->execute([$linkedPromptId, $currentUser['id']]);
        if ($promptCheckStmt->fetch()) {
            $pdo->prepare('UPDATE prompts SET linked_track_id = ? WHERE id = ?')
                ->execute([$trackId, $linkedPromptId]);
        }
    }

    $pdo->commit();
} catch (Exception $e) {
    $pdo->rollBack();
    header('Location: music_edit.php?id=' . $trackId . '&error=db');
    exit;
}

header('Location: music_detail.php?id=' . $trackId);
exit;
