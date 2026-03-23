<?php
require_once __DIR__ . '/header.php';

$msg = $_GET['msg'] ?? '';

// 현재 설정 가져오기
$settings = $pdo->query("SELECT * FROM site_settings ORDER BY setting_group, setting_key")->fetchAll();

// 그룹별로 분류
$grouped = [];
foreach ($settings as $s) {
    $grouped[$s['setting_group']][] = $s;
}

$groupLabels = [
    'general' => '일반 설정',
    'prompt' => '프롬프트 설정',
    'footer' => '푸터 설정',
];
?>

<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">사이트 설정</h1>
</div>

<?php if ($msg === 'saved'): ?>
<div class="bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg mb-6 text-sm">저장되었습니다.</div>
<?php endif; ?>

<form action="settings_ok.php" method="POST" class="max-w-3xl space-y-6">
    <?php foreach ($grouped as $group => $items): ?>
    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-700">
            <h2 class="text-white font-semibold"><?= $groupLabels[$group] ?? ucfirst(e($group)) ?></h2>
        </div>
        <div class="p-6 space-y-4">
            <?php foreach ($items as $item): ?>
            <div class="flex items-center gap-4">
                <div class="w-48 flex-shrink-0">
                    <label class="text-sm font-medium text-gray-300"><?= e($item['setting_key']) ?></label>
                    <div class="text-xs text-gray-500"><?= e($item['setting_group']) ?>.<?= e($item['setting_key']) ?></div>
                </div>
                <input type="text" name="settings[<?= $item['id'] ?>]" value="<?= e($item['setting_value']) ?>"
                    class="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
            <?php endforeach; ?>
        </div>
    </div>
    <?php endforeach; ?>

    <!-- 새 설정 추가 -->
    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-700">
            <h2 class="text-white font-semibold">새 설정 추가</h2>
        </div>
        <div class="p-6">
            <div class="grid grid-cols-3 gap-4">
                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-1">그룹</label>
                    <input type="text" name="new_group" placeholder="general"
                        class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-1">키</label>
                    <input type="text" name="new_key" placeholder="setting_name"
                        class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-1">값</label>
                    <input type="text" name="new_value" placeholder="value"
                        class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                </div>
            </div>
        </div>
    </div>

    <div class="flex gap-3">
        <button type="submit" class="px-6 py-2 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg transition-colors">저장</button>
    </div>
</form>

<?php require_once __DIR__ . '/footer.php'; ?>
