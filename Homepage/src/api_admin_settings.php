<?php
require_once 'db.php';

header('Content-Type: application/json; charset=utf-8');

if (!$currentUser || empty($currentUser['is_admin'])) {
    http_response_code(403);
    echo json_encode(['success' => false, 'message' => '관리자 권한이 필요합니다.'], JSON_UNESCAPED_UNICODE);
    exit;
}

$action = $_GET['action'] ?? $_POST['action'] ?? '';

if ($action === 'get') {
    $group = $_GET['group'] ?? '';
    $key = $_GET['key'] ?? '';
    if ($group && $key) {
        $value = getSiteSetting($pdo, $group, $key);
        echo json_encode(['success' => true, 'value' => $value], JSON_UNESCAPED_UNICODE);
    } else {
        $stmt = $pdo->query('SELECT setting_group, setting_key, setting_value FROM site_settings ORDER BY setting_group, setting_key');
        $all = $stmt->fetchAll();
        echo json_encode(['success' => true, 'settings' => $all], JSON_UNESCAPED_UNICODE);
    }
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'message' => 'POST 요청만 허용됩니다.'], JSON_UNESCAPED_UNICODE);
    exit;
}

if ($action === 'set') {
    $group = trim($_POST['group'] ?? '');
    $key = trim($_POST['key'] ?? '');
    $value = trim($_POST['value'] ?? '');

    if (empty($group) || empty($key)) {
        echo json_encode(['success' => false, 'message' => 'group, key는 필수입니다.'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $stmt = $pdo->prepare('SELECT id FROM site_settings WHERE setting_group = ? AND setting_key = ?');
    $stmt->execute([$group, $key]);
    if ($stmt->fetch()) {
        $upd = $pdo->prepare('UPDATE site_settings SET setting_value = ?, updated_at = datetime("now") WHERE setting_group = ? AND setting_key = ?');
        $upd->execute([$value, $group, $key]);
    } else {
        $ins = $pdo->prepare('INSERT INTO site_settings (setting_group, setting_key, setting_value) VALUES (?, ?, ?)');
        $ins->execute([$group, $key, $value]);
    }

    echo json_encode(['success' => true, 'group' => $group, 'key' => $key, 'value' => $value], JSON_UNESCAPED_UNICODE);
    exit;
}

if ($action === 'toggle') {
    $group = trim($_POST['group'] ?? '');
    $key = trim($_POST['key'] ?? '');

    if (empty($group) || empty($key)) {
        echo json_encode(['success' => false, 'message' => 'group, key는 필수입니다.'], JSON_UNESCAPED_UNICODE);
        exit;
    }

    $current = getSiteSetting($pdo, $group, $key, '0');
    $newValue = ($current === '1') ? '0' : '1';

    $stmt = $pdo->prepare('SELECT id FROM site_settings WHERE setting_group = ? AND setting_key = ?');
    $stmt->execute([$group, $key]);
    if ($stmt->fetch()) {
        $upd = $pdo->prepare('UPDATE site_settings SET setting_value = ?, updated_at = datetime("now") WHERE setting_group = ? AND setting_key = ?');
        $upd->execute([$newValue, $group, $key]);
    } else {
        $ins = $pdo->prepare('INSERT INTO site_settings (setting_group, setting_key, setting_value) VALUES (?, ?, ?)');
        $ins->execute([$group, $key, $newValue]);
    }

    echo json_encode([
        'success' => true,
        'group' => $group,
        'key' => $key,
        'previous' => $current,
        'value' => $newValue,
        'enabled' => $newValue === '1',
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

echo json_encode(['success' => false, 'message' => '유효하지 않은 action입니다. (get/set/toggle)'], JSON_UNESCAPED_UNICODE);
