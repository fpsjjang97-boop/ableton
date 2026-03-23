<?php
require_once __DIR__ . '/header.php';

$msg = $_GET['msg'] ?? '';

// 푸터 설정 키 목록
$footerKeys = [
    'company_name' => '상호',
    'ceo_name' => '대표자',
    'business_number' => '사업자번호',
    'telecom_number' => '통신판매업신고번호',
    'address' => '소재지',
    'phone' => '전화번호',
    'email' => '이메일',
    'kakao_url' => '카카오톡 URL',
    'description' => '안내 문구',
    'copyright' => '카피라이트',
];

// footer 시드가 없으면 자동 생성
$footerCount = $pdo->query("SELECT COUNT(*) FROM site_settings WHERE setting_group = 'footer'")->fetchColumn();
if ($footerCount == 0) {
    $seedStmt = $pdo->prepare("INSERT OR IGNORE INTO site_settings (setting_group, setting_key, setting_value) VALUES ('footer', ?, ?)");
    $seedStmt->execute(['company_name', 'SUNO Community']);
    $seedStmt->execute(['ceo_name', '김수노']);
    $seedStmt->execute(['business_number', '485-12-01987']);
    $seedStmt->execute(['telecom_number', '2025-서울마포-03821']);
    $seedStmt->execute(['address', '서울특별시 마포구 양화로 127, 7층 701호']);
    $seedStmt->execute(['phone', '02-6247-7203']);
    $seedStmt->execute(['email', 'admin@sunocommunity.kr']);
    $seedStmt->execute(['kakao_url', '']);
    $seedStmt->execute(['description', '']);
    $seedStmt->execute(['copyright', '© 2026 SUNO Community. All rights reserved.']);
}

// 현재 값 로드
$stmt = $pdo->prepare("SELECT setting_key, setting_value FROM site_settings WHERE setting_group = 'footer'");
$stmt->execute();
$rows = $stmt->fetchAll();
$values = [];
foreach ($rows as $r) {
    $values[$r['setting_key']] = $r['setting_value'];
}
?>

<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">푸터 설정</h1>
</div>

<?php if ($msg === 'saved'): ?>
<div class="bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg mb-6 text-sm">저장되었습니다.</div>
<?php endif; ?>

<form action="footer_settings_ok.php" method="POST" class="max-w-3xl space-y-6">
    <!-- 사업자 정보 -->
    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-700">
            <h2 class="text-white font-semibold">사업자 정보</h2>
        </div>
        <div class="p-6 space-y-4">
            <?php foreach (['company_name', 'ceo_name', 'business_number', 'telecom_number', 'address'] as $key): ?>
            <div class="flex items-center gap-4">
                <div class="w-48 flex-shrink-0">
                    <label class="text-sm font-medium text-gray-300"><?= e($footerKeys[$key]) ?></label>
                </div>
                <input type="text" name="<?= $key ?>" value="<?= e($values[$key] ?? '') ?>"
                    class="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
            <?php endforeach; ?>
        </div>
    </div>

    <!-- 연락처 -->
    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-700">
            <h2 class="text-white font-semibold">연락처</h2>
        </div>
        <div class="p-6 space-y-4">
            <?php foreach (['phone', 'email', 'kakao_url'] as $key): ?>
            <div class="flex items-center gap-4">
                <div class="w-48 flex-shrink-0">
                    <label class="text-sm font-medium text-gray-300"><?= e($footerKeys[$key]) ?></label>
                </div>
                <input type="text" name="<?= $key ?>" value="<?= e($values[$key] ?? '') ?>"
                    class="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
            <?php endforeach; ?>
        </div>
    </div>

    <!-- 안내 문구 -->
    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-700">
            <h2 class="text-white font-semibold">안내 문구</h2>
        </div>
        <div class="p-6">
            <textarea name="description" rows="5"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm"><?= e($values['description'] ?? '') ?></textarea>
        </div>
    </div>

    <!-- 카피라이트 -->
    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-700">
            <h2 class="text-white font-semibold">카피라이트</h2>
        </div>
        <div class="p-6">
            <input type="text" name="copyright" value="<?= e($values['copyright'] ?? '') ?>"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
        </div>
    </div>

    <div class="flex gap-3">
        <button type="submit" class="px-6 py-2 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg transition-colors">저장</button>
    </div>
</form>

<?php require_once __DIR__ . '/footer.php'; ?>
