<?php
require_once 'db.php';

if (!$currentUser) {
    header('Location: login.php');
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: profile_edit.php');
    exit;
}

$action = $_POST['action'] ?? '';
$uploadDir = __DIR__ . '/uploads/profiles/';

// ============================================================
// 이미지 업로드 처리
// ============================================================
if ($action === 'images') {
    $allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
    $maxSize = 5 * 1024 * 1024; // 5MB

    $avatarUrl = $currentUser['avatar_url'];
    $backgroundUrl = $currentUser['background_url'];

    // 업로드 에러 체크 헬퍼
    function checkUploadError($file) {
        if ($file['error'] === UPLOAD_ERR_INI_SIZE || $file['error'] === UPLOAD_ERR_FORM_SIZE) {
            header('Location: profile_edit.php?error=file_too_large');
            exit;
        }
        if ($file['error'] !== UPLOAD_ERR_OK && $file['error'] !== UPLOAD_ERR_NO_FILE) {
            header('Location: profile_edit.php?error=upload_fail');
            exit;
        }
    }

    // 에러 체크 (파일이 선택된 경우)
    if (isset($_FILES['avatar']) && $_FILES['avatar']['error'] !== UPLOAD_ERR_NO_FILE) {
        checkUploadError($_FILES['avatar']);
    }
    if (isset($_FILES['background']) && $_FILES['background']['error'] !== UPLOAD_ERR_NO_FILE) {
        checkUploadError($_FILES['background']);
    }

    // 프로필 사진 업로드
    if (!empty($_FILES['avatar']['tmp_name']) && $_FILES['avatar']['error'] === UPLOAD_ERR_OK) {
        $file = $_FILES['avatar'];

        if ($file['size'] > $maxSize) {
            header('Location: profile_edit.php?error=file_too_large');
            exit;
        }

        $finfo = new finfo(FILEINFO_MIME_TYPE);
        $mimeType = $finfo->file($file['tmp_name']);
        if (!in_array($mimeType, $allowedTypes)) {
            header('Location: profile_edit.php?error=invalid_type');
            exit;
        }

        $ext = match($mimeType) {
            'image/jpeg' => 'jpg',
            'image/png' => 'png',
            'image/gif' => 'gif',
            'image/webp' => 'webp',
            default => 'jpg',
        };

        $filename = 'avatar_' . $currentUser['id'] . '_' . time() . '.' . $ext;

        if (!is_dir($uploadDir)) {
            mkdir($uploadDir, 0755, true);
        }

        if (move_uploaded_file($file['tmp_name'], $uploadDir . $filename)) {
            // 이전 아바타 파일 삭제
            if (!empty($avatarUrl) && file_exists(__DIR__ . '/' . $avatarUrl)) {
                unlink(__DIR__ . '/' . $avatarUrl);
            }
            $avatarUrl = 'uploads/profiles/' . $filename;
        } else {
            header('Location: profile_edit.php?error=upload_fail');
            exit;
        }
    }

    // 배경 이미지 업로드
    if (!empty($_FILES['background']['tmp_name']) && $_FILES['background']['error'] === UPLOAD_ERR_OK) {
        $file = $_FILES['background'];

        if ($file['size'] > $maxSize) {
            header('Location: profile_edit.php?error=file_too_large');
            exit;
        }

        $finfo = new finfo(FILEINFO_MIME_TYPE);
        $mimeType = $finfo->file($file['tmp_name']);
        if (!in_array($mimeType, $allowedTypes)) {
            header('Location: profile_edit.php?error=invalid_type');
            exit;
        }

        $ext = match($mimeType) {
            'image/jpeg' => 'jpg',
            'image/png' => 'png',
            'image/gif' => 'gif',
            'image/webp' => 'webp',
            default => 'jpg',
        };

        $filename = 'bg_' . $currentUser['id'] . '_' . time() . '.' . $ext;

        if (!is_dir($uploadDir)) {
            mkdir($uploadDir, 0755, true);
        }

        if (move_uploaded_file($file['tmp_name'], $uploadDir . $filename)) {
            // 이전 배경 파일 삭제
            if (!empty($backgroundUrl) && file_exists(__DIR__ . '/' . $backgroundUrl)) {
                unlink(__DIR__ . '/' . $backgroundUrl);
            }
            $backgroundUrl = 'uploads/profiles/' . $filename;
        } else {
            header('Location: profile_edit.php?error=upload_fail');
            exit;
        }
    }

    // DB 업데이트
    $stmt = $pdo->prepare('UPDATE users SET avatar_url = ?, background_url = ?, updated_at = datetime("now") WHERE id = ?');
    $stmt->execute([$avatarUrl, $backgroundUrl, $currentUser['id']]);

    header('Location: profile_edit.php?success=profile');
    exit;
}

// ============================================================
// 프로필 정보 수정
// ============================================================
if ($action === 'profile') {
    $nickname         = trim($_POST['nickname'] ?? '');
    $email            = trim($_POST['email'] ?? '');
    $bio              = trim($_POST['bio'] ?? '');
    $youtube_url      = trim($_POST['youtube_url'] ?? '');
    $instagram_url    = trim($_POST['instagram_url'] ?? '');
    $suno_profile_url = trim($_POST['suno_profile_url'] ?? '');
    $social_links_raw = trim($_POST['social_links'] ?? '');
    $social_links     = null;
    if (!empty($social_links_raw)) {
        $decoded = json_decode($social_links_raw, true);
        if (is_array($decoded)) $social_links = json_encode($decoded, JSON_UNESCAPED_UNICODE);
    }

    if (empty($nickname) || empty($email)) {
        header('Location: profile_edit.php?error=empty');
        exit;
    }

    $stmt = $pdo->prepare('SELECT id FROM users WHERE nickname = ? AND id != ?');
    $stmt->execute([$nickname, $currentUser['id']]);
    if ($stmt->fetch()) {
        header('Location: profile_edit.php?error=nickname_exists');
        exit;
    }

    $stmt = $pdo->prepare('SELECT id FROM users WHERE email = ? AND id != ?');
    $stmt->execute([$email, $currentUser['id']]);
    if ($stmt->fetch()) {
        header('Location: profile_edit.php?error=email_exists');
        exit;
    }

    $stmt = $pdo->prepare('
        UPDATE users SET
            nickname = ?, email = ?, bio = ?,
            youtube_url = ?, instagram_url = ?, suno_profile_url = ?,
            social_links = ?,
            updated_at = datetime("now")
        WHERE id = ?
    ');
    $stmt->execute([
        $nickname, $email, $bio ?: null,
        $youtube_url ?: null, $instagram_url ?: null, $suno_profile_url ?: null,
        $social_links,
        $currentUser['id'],
    ]);

    header('Location: profile_edit.php?success=profile');
    exit;
}

// ============================================================
// 뱃지 선택
// ============================================================
if ($action === 'badge') {
    $selectedBadgeId = (int)($_POST['selected_badge_id'] ?? 0);

    // 0이면 뱃지 해제
    if ($selectedBadgeId === 0) {
        $stmt = $pdo->prepare('UPDATE users SET selected_badge_id = NULL, updated_at = datetime("now") WHERE id = ?');
        $stmt->execute([$currentUser['id']]);
    } else {
        // 해당 뱃지를 가지고 있는지 확인
        $stmt = $pdo->prepare('SELECT id FROM user_badges WHERE user_id = ? AND badge_id = ?');
        $stmt->execute([$currentUser['id'], $selectedBadgeId]);
        if ($stmt->fetch()) {
            $stmt = $pdo->prepare('UPDATE users SET selected_badge_id = ?, updated_at = datetime("now") WHERE id = ?');
            $stmt->execute([$selectedBadgeId, $currentUser['id']]);
        }
    }

    header('Location: profile_edit.php?success=profile');
    exit;
}

// ============================================================
// 비밀번호 변경
// ============================================================
if ($action === 'password') {
    $currentPassword    = $_POST['current_password'] ?? '';
    $newPassword        = $_POST['new_password'] ?? '';
    $newPasswordConfirm = $_POST['new_password_confirm'] ?? '';

    if (!password_verify($currentPassword, $currentUser['password_hash'])) {
        header('Location: profile_edit.php?error=password_wrong');
        exit;
    }

    if ($newPassword !== $newPasswordConfirm) {
        header('Location: profile_edit.php?error=password_mismatch');
        exit;
    }

    if (mb_strlen($newPassword) < 8) {
        header('Location: profile_edit.php?error=password_short');
        exit;
    }

    $newHash = password_hash($newPassword, PASSWORD_DEFAULT);
    $stmt = $pdo->prepare('UPDATE users SET password_hash = ?, updated_at = datetime("now") WHERE id = ?');
    $stmt->execute([$newHash, $currentUser['id']]);

    header('Location: profile_edit.php?success=password');
    exit;
}

header('Location: profile_edit.php');
exit;
