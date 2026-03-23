<?php
require_once __DIR__ . '/header.php';

$search = $_GET['search'] ?? '';
$page = max(1, intval($_GET['page'] ?? 1));
$perPage = 20;
$offset = ($page - 1) * $perPage;

$where = '';
$params = [];
if ($search) {
    $where = "WHERE p.title LIKE ? OR u.nickname LIKE ?";
    $params = ["%$search%", "%$search%"];
}

$totalStmt = $pdo->prepare("SELECT COUNT(*) FROM prompts p JOIN users u ON p.user_id = u.id $where");
$totalStmt->execute($params);
$total = $totalStmt->fetchColumn();
$totalPages = max(1, ceil($total / $perPage));

$stmt = $pdo->prepare("SELECT p.*, u.nickname,
    (SELECT GROUP_CONCAT(genre, ', ') FROM prompt_genres WHERE prompt_id = p.id) as genres
    FROM prompts p JOIN users u ON p.user_id = u.id $where ORDER BY p.id DESC LIMIT $perPage OFFSET $offset");
$stmt->execute($params);
$prompts = $stmt->fetchAll();
?>

<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">프롬프트 관리</h1>
    <span class="text-sm text-gray-500">총 <?= number_format($total) ?>개</span>
</div>

<form method="GET" class="mb-6">
    <div class="flex gap-2">
        <input type="text" name="search" value="<?= e($search) ?>" placeholder="프롬프트 제목 또는 작성자 검색..."
            class="flex-1 max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500">
        <button type="submit" class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors">검색</button>
        <?php if ($search): ?>
        <a href="prompts.php" class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors">초기화</a>
        <?php endif; ?>
    </div>
</form>

<div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
    <div class="overflow-x-auto">
        <table class="w-full text-sm">
            <thead>
                <tr class="border-b border-gray-700 text-gray-400">
                    <th class="px-4 py-3 text-left">ID</th>
                    <th class="px-4 py-3 text-left">제목</th>
                    <th class="px-4 py-3 text-left">작성자</th>
                    <th class="px-4 py-3 text-left">장르</th>
                    <th class="px-4 py-3 text-center">Weirdness</th>
                    <th class="px-4 py-3 text-right">좋아요</th>
                    <th class="px-4 py-3 text-right">복사</th>
                    <th class="px-4 py-3 text-left">등록일</th>
                    <th class="px-4 py-3 text-center">관리</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-700">
                <?php foreach ($prompts as $prompt): ?>
                <tr class="hover:bg-gray-750">
                    <td class="px-4 py-3 text-gray-500"><?= $prompt['id'] ?></td>
                    <td class="px-4 py-3">
                        <a href="../prompt_detail.php?id=<?= $prompt['id'] ?>" target="_blank" class="text-white font-medium max-w-xs truncate block hover:text-violet-400 transition-colors"><?= e($prompt['title']) ?>
                            <svg class="w-3 h-3 inline-block ml-1 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                        </a>
                        <div class="text-xs text-gray-500 max-w-xs truncate"><?= e(mb_substr($prompt['prompt_text'], 0, 60)) ?>...</div>
                    </td>
                    <td class="px-4 py-3 text-gray-400"><?= e($prompt['nickname']) ?></td>
                    <td class="px-4 py-3">
                        <?php if ($prompt['genres']): ?>
                        <div class="flex flex-wrap gap-1">
                            <?php foreach (explode(', ', $prompt['genres']) as $g): ?>
                            <span class="px-1.5 py-0.5 text-xs bg-cyan-500/20 text-cyan-400 rounded"><?= e($g) ?></span>
                            <?php endforeach; ?>
                        </div>
                        <?php else: ?>
                        <span class="text-gray-600">-</span>
                        <?php endif; ?>
                    </td>
                    <td class="px-4 py-3 text-center text-gray-400"><?= $prompt['weirdness'] ?>%</td>
                    <td class="px-4 py-3 text-right text-gray-400"><?= number_format($prompt['like_count']) ?></td>
                    <td class="px-4 py-3 text-right text-gray-400"><?= number_format($prompt['copy_count']) ?></td>
                    <td class="px-4 py-3 text-gray-500 text-xs"><?= formatDate($prompt['created_at']) ?></td>
                    <td class="px-4 py-3 text-center">
                        <a href="prompt_delete_ok.php?id=<?= $prompt['id'] ?>" onclick="return confirmDelete('이 프롬프트를 삭제하시겠습니까?')"
                           class="px-2 py-1 text-xs bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded transition-colors">삭제</a>
                    </td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</div>

<?php if ($totalPages > 1): ?>
<div class="flex items-center justify-center gap-1 mt-6">
    <?php for ($i = 1; $i <= $totalPages; $i++): ?>
    <a href="?page=<?= $i ?>&search=<?= urlencode($search) ?>"
       class="px-3 py-1 rounded text-sm <?= $i === $page ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700' ?> transition-colors"><?= $i ?></a>
    <?php endfor; ?>
</div>
<?php endif; ?>

<?php require_once __DIR__ . '/footer.php'; ?>
