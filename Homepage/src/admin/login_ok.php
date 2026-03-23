<?php
if (session_status() === PHP_SESSION_NONE) session_start();

define('ADMIN_ID', 'admin');
define('ADMIN_PW', '1234');

$username = $_POST['username'] ?? '';
$password = $_POST['password'] ?? '';

if ($username === ADMIN_ID && $password === ADMIN_PW) {
    $_SESSION['admin_logged_in'] = true;
    $_SESSION['admin_username'] = $username;
    header('Location: index.php');
} else {
    header('Location: login.php?error=invalid');
}
exit;
