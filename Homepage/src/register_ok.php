<?php
require_once 'db.php';

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: register.php');
    exit;
}

$nickname         = trim($_POST['nickname'] ?? '');
$email            = trim($_POST['email'] ?? '');
$password         = $_POST['password'] ?? '';
$password_confirm = $_POST['password_confirm'] ?? '';
$terms            = $_POST['terms'] ?? '';

// ── 필수 항목 검증 ──
if (empty($nickname) || empty($email) || empty($password) || empty($password_confirm)) {
    header('Location: register.php?error=empty');
    exit;
}

// ── 이메일 형식 검증 ──
if (!filter_var($email, FILTER_VALIDATE_EMAIL)) {
    header('Location: register.php?error=email_format');
    exit;
}

// ── 닉네임 길이 검증 (2~50자) ──
if (mb_strlen($nickname) < 2 || mb_strlen($nickname) > 50) {
    header('Location: register.php?error=nickname_length');
    exit;
}

// ── 비밀번호 일치 확인 ──
if ($password !== $password_confirm) {
    header('Location: register.php?error=password_mismatch');
    exit;
}

// ── 비밀번호 길이 검증 (8자 이상) ──
if (mb_strlen($password) < 8) {
    header('Location: register.php?error=password_short');
    exit;
}

// ── 이용약관 동의 확인 ──
if (empty($terms)) {
    header('Location: register.php?error=terms');
    exit;
}

// ── 이메일 중복 확인 ──
$stmt = $pdo->prepare('SELECT id FROM users WHERE email = ?');
$stmt->execute([$email]);
if ($stmt->fetch()) {
    header('Location: register.php?error=email_exists');
    exit;
}

// ── 닉네임 중복 확인 ──
$stmt = $pdo->prepare('SELECT id FROM users WHERE nickname = ?');
$stmt->execute([$nickname]);
if ($stmt->fetch()) {
    header('Location: register.php?error=nickname_exists');
    exit;
}

// ── 비밀번호 해싱 및 INSERT ──
$password_hash = password_hash($password, PASSWORD_DEFAULT);
$avatar_color  = getAvatarColor(crc32($nickname));

$stmt = $pdo->prepare('
    INSERT INTO users (nickname, email, password_hash, avatar_color, terms_agreed, created_at, updated_at)
    VALUES (?, ?, ?, ?, 1, datetime("now"), datetime("now"))
');
$stmt->execute([$nickname, $email, $password_hash, $avatar_color]);

$userId = $pdo->lastInsertId();

// ── 세션 설정 후 리다이렉트 ──
$_SESSION['user_id'] = $userId;
header('Location: index.php');
exit;
