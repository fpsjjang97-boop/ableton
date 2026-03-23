<?php
require_once 'db.php';

// ── 로그인 확인 ──
if (!$currentUser) {
    header('Location: login.php');
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: music_upload.php');
    exit;
}

// ── 입력값 수집 ──
$title       = trim($_POST['title'] ?? '');
$description = trim($_POST['description'] ?? '');
$suno_link   = trim($_POST['suno_link'] ?? '');
$genres_raw  = trim($_POST['genres'] ?? '');
$moods_raw   = trim($_POST['moods'] ?? '');

// ── 에러 시 입력값 보존 헬퍼 ──
function redirectWithData($url) {
    global $title, $description, $suno_link, $genres_raw, $moods_raw;
    $_SESSION['music_upload_data'] = [
        'title' => $title,
        'description' => $description,
        'suno_link' => $suno_link,
        'genres' => $genres_raw,
        'moods' => $moods_raw,
    ];
    header('Location: ' . $url);
    exit;
}

// ── 필수값 검증 ──
if (empty($title)) {
    redirectWithData('music_upload.php?error=empty_title');
}

if (mb_strlen($title) > 200) {
    $title = mb_substr($title, 0, 200);
}
if (mb_strlen($description) > 500) {
    $description = mb_substr($description, 0, 500);
}

// ── Suno 링크 정규화 (선택) ──
if (!empty($suno_link)) {
    $suno_link = trim($suno_link);
    if (strpos($suno_link, 'http://') !== 0 && strpos($suno_link, 'https://') !== 0) {
        $suno_link = 'https://' . $suno_link;
    }
    if (!filter_var($suno_link, FILTER_VALIDATE_URL)) {
        $suno_link = '';
    }
}

// ── 업로드 디렉토리 준비 ──
$uploadDir = __DIR__ . '/uploads';
if (!is_dir($uploadDir)) {
    mkdir($uploadDir, 0755, true);
}
$audioUploadDir = $uploadDir . '/audio';
if (!is_dir($audioUploadDir)) {
    mkdir($audioUploadDir, 0755, true);
}
$imageUploadDir = $uploadDir . '/covers';
if (!is_dir($imageUploadDir)) {
    mkdir($imageUploadDir, 0755, true);
}

// ── 오디오 파일 업로드 처리 ──
$has_audio_file  = 0;
$audio_file_path = null;

if (isset($_FILES['audio_file']) && $_FILES['audio_file']['error'] === UPLOAD_ERR_OK) {
    $audioFile = $_FILES['audio_file'];

    // 파일 크기 제한 (50MB)
    if ($audioFile['size'] > 50 * 1024 * 1024) {
        redirectWithData('music_upload.php?error=audio_size');
    }

    // 확장자 검증
    $audioExt = strtolower(pathinfo($audioFile['name'], PATHINFO_EXTENSION));
    $allowedAudio = ['mp3', 'wav', 'ogg', 'flac'];
    if (!in_array($audioExt, $allowedAudio)) {
        redirectWithData('music_upload.php?error=audio_type');
    }

    // MIME 타입 검증
    $audioMime = mime_content_type($audioFile['tmp_name']);
    $allowedAudioMimes = ['audio/mpeg', 'audio/wav', 'audio/x-wav', 'audio/ogg', 'audio/flac'];
    if (!in_array($audioMime, $allowedAudioMimes)) {
        redirectWithData('music_upload.php?error=audio_type');
    }

    // 고유 파일명 생성
    $audioFileName = uniqid('audio_', true) . '.' . $audioExt;
    $audioDestPath = $audioUploadDir . '/' . $audioFileName;

    if (move_uploaded_file($audioFile['tmp_name'], $audioDestPath)) {
        $has_audio_file  = 1;
        $audio_file_path = 'uploads/audio/' . $audioFileName;
    }
}

// ── 커버 이미지 업로드 처리 ──
$cover_image_path = null;

if (isset($_FILES['cover_image']) && $_FILES['cover_image']['error'] === UPLOAD_ERR_OK) {
    $imageFile = $_FILES['cover_image'];

    // 파일 크기 제한 (5MB)
    if ($imageFile['size'] > 5 * 1024 * 1024) {
        redirectWithData('music_upload.php?error=image_size');
    }

    // 확장자 검증
    $imageExt = strtolower(pathinfo($imageFile['name'], PATHINFO_EXTENSION));
    $allowedImage = ['jpg', 'jpeg', 'png', 'webp', 'gif'];
    if (!in_array($imageExt, $allowedImage)) {
        redirectWithData('music_upload.php?error=image_type');
    }

    // 이미지 실제 타입 검증
    $imageInfo = getimagesize($imageFile['tmp_name']);
    if ($imageInfo === false) {
        redirectWithData('music_upload.php?error=image_type');
    }

    // 고유 파일명 생성
    $imageFileName = uniqid('cover_', true) . '.' . $imageExt;
    $imageDestPath = $imageUploadDir . '/' . $imageFileName;

    if (move_uploaded_file($imageFile['tmp_name'], $imageDestPath)) {
        $cover_image_path = 'uploads/covers/' . $imageFileName;
    }
}

// ── 최소 하나의 음원 소스 필요 (Suno 링크 또는 오디오 파일) ──
if (empty($suno_link) && !$has_audio_file) {
    // 업로드 시도했으나 실패한 경우 구체적 안내
    $uploadError = isset($_FILES['audio_file']['error']) ? (int)$_FILES['audio_file']['error'] : UPLOAD_ERR_NO_FILE;
    if ($uploadError === UPLOAD_ERR_INI_SIZE || $uploadError === UPLOAD_ERR_FORM_SIZE) {
        redirectWithData('music_upload.php?error=audio_size');
    }
    if ($uploadError === UPLOAD_ERR_NO_FILE && isset($_FILES['audio_file']) && $_FILES['audio_file']['size'] > 0) {
        redirectWithData('music_upload.php?error=audio_upload_failed');
    }
    redirectWithData('music_upload.php?error=no_source');
}

// ── 연결할 프롬프트 ID ──
$linkedPromptId = (int)($_POST['linked_prompt_id'] ?? 0);

// ── 장르/분위기 파싱 ──
$genres = array_filter(array_map('trim', explode(',', $genres_raw)));
$moods  = array_filter(array_map('trim', explode(',', $moods_raw)));

// 최대 3개 제한
$genres = array_slice($genres, 0, 3);
$moods  = array_slice($moods, 0, 3);

// ── 트랜잭션으로 INSERT ──
try {
    $pdo->beginTransaction();

    // tracks 테이블 INSERT
    $stmt = $pdo->prepare('
        INSERT INTO tracks (user_id, title, description, suno_link, has_audio_file, audio_file_path, cover_image_path, created_at, updated_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, datetime("now"), datetime("now"))
    ');
    $stmt->execute([
        $currentUser['id'],
        $title,
        $description ?: null,
        $suno_link ?: null,
        $has_audio_file,
        $audio_file_path,
        $cover_image_path
    ]);

    $trackId = $pdo->lastInsertId();

    // track_genres INSERT
    if (!empty($genres)) {
        $stmtGenre = $pdo->prepare('INSERT OR IGNORE INTO track_genres (track_id, genre) VALUES (?, ?)');
        foreach ($genres as $genre) {
            if (mb_strlen($genre) <= 50) {
                $stmtGenre->execute([$trackId, $genre]);
            }
        }
    }

    // track_moods INSERT
    if (!empty($moods)) {
        $stmtMood = $pdo->prepare('INSERT OR IGNORE INTO track_moods (track_id, mood) VALUES (?, ?)');
        foreach ($moods as $mood) {
            if (mb_strlen($mood) <= 50) {
                $stmtMood->execute([$trackId, $mood]);
            }
        }
    }

    // 프롬프트 연결 (prompts.linked_track_id 업데이트)
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
    // 업로드된 파일 정리
    if ($audio_file_path && file_exists(__DIR__ . '/' . $audio_file_path)) {
        unlink(__DIR__ . '/' . $audio_file_path);
    }
    if ($cover_image_path && file_exists(__DIR__ . '/' . $cover_image_path)) {
        unlink(__DIR__ . '/' . $cover_image_path);
    }
    redirectWithData('music_upload.php?error=db');
}

header('Location: music_list.php');
exit;
