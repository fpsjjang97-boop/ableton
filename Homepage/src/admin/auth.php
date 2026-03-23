<?php
// 관리자 인증 체크 - 모든 admin 페이지에서 include
if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

// 하드코딩된 관리자 계정
define('ADMIN_ID', 'admin');
define('ADMIN_PW', '1234');

// DB 연결
$db_path = dirname(__DIR__) . '/database.sqlite';
try {
    $pdo = new PDO('sqlite:' . $db_path);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $pdo->exec('PRAGMA journal_mode=WAL');
    $pdo->exec('PRAGMA foreign_keys=ON');
} catch (PDOException $e) {
    die('DB 연결 실패: ' . $e->getMessage());
}

function requireAdmin() {
    if (!isset($_SESSION['admin_logged_in']) || $_SESSION['admin_logged_in'] !== true) {
        header('Location: login.php');
        exit;
    }
}

function e($str) {
    return htmlspecialchars($str ?? '', ENT_QUOTES, 'UTF-8');
}

function formatDate($datetime) {
    if (!$datetime) return '-';
    return date('Y-m-d H:i', strtotime($datetime));
}
