<?php
require_once __DIR__ . '/header.php';

$id = intval($_GET['id'] ?? 0);
if (!$id) { header('Location: pages.php'); exit; }

$stmt = $pdo->prepare("SELECT * FROM site_pages WHERE id = ?");
$stmt->execute([$id]);
$page = $stmt->fetch();
if (!$page) { header('Location: pages.php'); exit; }
?>

<div class="flex items-center justify-between mb-6">
    <div class="flex items-center gap-3">
        <a href="pages.php" class="text-gray-400 hover:text-white transition-colors">
            <i class="fa-solid fa-arrow-left"></i>
        </a>
        <h1 class="text-2xl font-bold text-white">페이지 수정: <?= e($page['title']) ?></h1>
    </div>
</div>

<form action="page_edit_ok.php" method="POST" class="max-w-4xl space-y-6">
    <input type="hidden" name="id" value="<?= $page['id'] ?>">

    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-700">
            <h2 class="text-white font-semibold">페이지 정보</h2>
        </div>
        <div class="p-6 space-y-4">
            <div class="flex items-center gap-4">
                <div class="w-32 flex-shrink-0">
                    <label class="text-sm font-medium text-gray-300">Slug</label>
                </div>
                <code class="px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-gray-300 text-sm"><?= e($page['slug']) ?></code>
            </div>
            <div class="flex items-center gap-4">
                <div class="w-32 flex-shrink-0">
                    <label class="text-sm font-medium text-gray-300">제목</label>
                </div>
                <input type="text" name="title" value="<?= e($page['title']) ?>"
                    class="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
            <div class="flex items-center gap-4">
                <div class="w-32 flex-shrink-0">
                    <label class="text-sm font-medium text-gray-300">활성화</label>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" name="is_active" value="1" <?= $page['is_active'] ? 'checked' : '' ?> class="sr-only peer">
                    <div class="w-11 h-6 bg-gray-600 peer-focus:outline-none peer-focus:ring-2 peer-focus:ring-violet-500 rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-violet-600"></div>
                </label>
            </div>
        </div>
    </div>

    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-700">
            <h2 class="text-white font-semibold">내용 <span class="text-xs text-gray-500 font-normal">(HTML 사용 가능)</span></h2>
        </div>
        <div class="p-6">
            <textarea name="content" rows="20"
                class="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500 text-sm font-mono leading-relaxed"><?= e($page['content'] ?? '') ?></textarea>
        </div>
    </div>

    <div class="flex gap-3">
        <button type="submit" class="px-6 py-2 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg transition-colors">저장</button>
        <a href="pages.php" class="px-6 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 font-medium rounded-lg transition-colors">취소</a>
    </div>
</form>

<?php require_once __DIR__ . '/footer.php'; ?>
