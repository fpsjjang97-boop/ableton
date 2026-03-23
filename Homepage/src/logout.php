<?php
require_once 'db.php';

// 세션 변수 모두 삭제
$_SESSION = [];

// 세션 쿠키 삭제
if (ini_get('session.use_cookies')) {
    $params = session_get_cookie_params();
    setcookie(
        session_name(),
        '',
        time() - 42000,
        $params['path'],
        $params['domain'],
        $params['secure'],
        $params['httponly']
    );
}

// 세션 파괴
session_destroy();

header('Location: index.php');
exit;
