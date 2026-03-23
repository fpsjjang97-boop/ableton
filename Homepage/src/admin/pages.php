<?php
require_once __DIR__ . '/header.php';

$msg = $_GET['msg'] ?? '';

// 테이블 없으면 자동 생성 + 시드
$tableExists = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name='site_pages'")->fetchColumn();
if (!$tableExists) {
    $pdo->exec("CREATE TABLE site_pages (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        slug TEXT NOT NULL UNIQUE,
        title TEXT NOT NULL,
        content TEXT,
        is_active INTEGER DEFAULT 1,
        updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
    )");
    $seed = $pdo->prepare('INSERT OR IGNORE INTO site_pages (slug, title, content) VALUES (?, ?, ?)');
    $seed->execute(['about', '사이트소개', '']);
    $seed->execute(['terms', '이용약관', '']);
    $seed->execute(['privacy', '개인정보처리방침', '']);
    $seed->execute(['legal', '책임한계 및 법적고지', '']);
}

$pages = $pdo->query("SELECT * FROM site_pages ORDER BY id")->fetchAll();
?>

<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">페이지 관리</h1>
</div>

<?php if ($msg === 'saved'): ?>
<div class="bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg mb-6 text-sm">저장되었습니다.</div>
<?php endif; ?>

<div class="grid grid-cols-1 md:grid-cols-2 gap-4">
    <?php foreach ($pages as $page): ?>
    <div class="bg-gray-800 rounded-xl border border-gray-700 p-6">
        <div class="flex items-start justify-between mb-3">
            <div>
                <h3 class="text-white font-semibold text-lg"><?= e($page['title']) ?></h3>
                <p class="text-gray-500 text-sm mt-1">slug: <code class="bg-gray-700 px-1.5 py-0.5 rounded text-xs text-gray-300"><?= e($page['slug']) ?></code></p>
            </div>
            <?php if ($page['is_active']): ?>
            <span class="px-2 py-1 bg-green-500/10 border border-green-500/30 text-green-400 text-xs rounded-full">활성</span>
            <?php else: ?>
            <span class="px-2 py-1 bg-gray-500/10 border border-gray-500/30 text-gray-400 text-xs rounded-full">비활성</span>
            <?php endif; ?>
        </div>
        <p class="text-gray-400 text-xs mb-4">
            수정일: <?= formatDate($page['updated_at']) ?>
            &middot;
            <?= $page['content'] ? mb_strlen(strip_tags($page['content'])) . '자' : '내용 없음' ?>
        </p>
        <div class="flex gap-2">
            <a href="page_edit.php?id=<?= $page['id'] ?>" class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium rounded-lg transition-colors">수정</a>
            <a href="../page.php?slug=<?= e($page['slug']) ?>" target="_blank" class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 text-sm font-medium rounded-lg transition-colors">미리보기</a>
        </div>
    </div>
    <?php endforeach; ?>
</div>

<?php require_once __DIR__ . '/footer.php'; ?>
