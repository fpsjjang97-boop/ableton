<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$footerKeys = ['company_name', 'ceo_name', 'business_number', 'telecom_number', 'address', 'phone', 'email', 'kakao_url', 'description', 'copyright'];

$stmt = $pdo->prepare("INSERT INTO site_settings (setting_group, setting_key, setting_value, updated_at) VALUES ('footer', ?, ?, datetime('now'))
    ON CONFLICT(setting_group, setting_key) DO UPDATE SET setting_value = excluded.setting_value, updated_at = datetime('now')");

foreach ($footerKeys as $key) {
    $value = $_POST[$key] ?? '';
    $stmt->execute([$key, $value]);
}

header('Location: footer_settings.php?msg=saved');
exit;
