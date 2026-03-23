<?php
/**
 * Summernote 이미지 업로드: ./uploads/board 에 저장 후 URL 반환
 */
require_once 'db.php';

header('Content-Type: application/json; charset=utf-8');

// 로그인 확인
if (!$currentUser) {
    http_response_code(401);
    echo json_encode(['success' => false, 'message' => '로그인이 필요합니다.']);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST' || !isset($_FILES['image']) || $_FILES['image']['error'] !== UPLOAD_ERR_OK) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => '이미지 파일이 없습니다.']);
    exit;
}

$file = $_FILES['image'];
$maxSize = 10 * 1024 * 1024; // 10MB
$allowedTypes = ['image/jpeg', 'image/png', 'image/gif', 'image/webp'];
$allowedExt = ['jpg', 'jpeg', 'png', 'gif', 'webp'];

if ($file['size'] > $maxSize) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => '이미지 크기는 10MB 이하만 가능합니다.']);
    exit;
}

$finfo = new finfo(FILEINFO_MIME_TYPE);
$mime = $finfo->file($file['tmp_name']);
if (!in_array($mime, $allowedTypes, true)) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => '허용 형식: JPG, PNG, GIF, WEBP']);
    exit;
}

$ext = strtolower(pathinfo($file['name'], PATHINFO_EXTENSION));
if (!in_array($ext, $allowedExt)) {
    $ext = ['image/jpeg' => 'jpg', 'image/png' => 'png', 'image/gif' => 'gif', 'image/webp' => 'webp'][$mime] ?? 'jpg';
}

$uploadDir = __DIR__ . '/uploads/board';
if (!is_dir($uploadDir)) {
    mkdir($uploadDir, 0755, true);
}

$fileName = 'board_' . date('Ymd_His') . '_' . substr(uniqid(), -6) . '.' . $ext;
$destPath = $uploadDir . '/' . $fileName;

if (!move_uploaded_file($file['tmp_name'], $destPath)) {
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => '파일 저장에 실패했습니다.']);
    exit;
}

// Summernote가 img src로 쓸 URL (프로젝트 루트 기준)
$url = 'uploads/board/' . $fileName;

echo json_encode(['success' => true, 'url' => $url]);
exit;
