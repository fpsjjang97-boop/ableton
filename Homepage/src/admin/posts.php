<?php
require_once __DIR__ . '/header.php';

$search = $_GET['search'] ?? '';
$boardFilter = $_GET['board'] ?? '';
$page = max(1, intval($_GET['page'] ?? 1));
$perPage = 20;
$offset = ($page - 1) * $perPage;

$where = '1=1';
$params = [];
if ($search) {
    $where .= " AND (p.title LIKE ? OR u.nickname LIKE ?)";
    $params[] = "%$search%";
    $params[] = "%$search%";
}
if ($boardFilter) {
    $where .= " AND p.board_id = ?";
    $params[] = intval($boardFilter);
}

$boards = $pdo->query("SELECT id, board_name FROM boards ORDER BY sort_order")->fetchAll();

$totalStmt = $pdo->prepare("SELECT COUNT(*) FROM posts p JOIN users u ON p.user_id = u.id WHERE $where");
$totalStmt->execute($params);
$total = $totalStmt->fetchColumn();
$totalPages = max(1, ceil($total / $perPage));

$stmt = $pdo->prepare("SELECT p.*, u.nickname, b.board_name, b.board_key
    FROM posts p JOIN users u ON p.user_id = u.id JOIN boards b ON p.board_id = b.id
    WHERE $where ORDER BY p.id DESC LIMIT $perPage OFFSET $offset");
$stmt->execute($params);
$posts = $stmt->fetchAll();
?>

<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">게시글 관리</h1>
    <span class="text-sm text-gray-500">총 <?= number_format($total) ?>개</span>
</div>

<form method="GET" class="mb-6">
    <div class="flex gap-2 flex-wrap">
        <input type="text" name="search" value="<?= e($search) ?>" placeholder="제목 또는 작성자 검색..."
            class="flex-1 max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500">
        <select name="board" class="px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            <option value="">전체 게시판</option>
            <?php foreach ($boards as $b): ?>
            <option value="<?= $b['id'] ?>" <?= $boardFilter == $b['id'] ? 'selected' : '' ?>><?= e($b['board_name']) ?></option>
            <?php endforeach; ?>
        </select>
        <button type="submit" class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors">검색</button>
        <?php if ($search || $boardFilter): ?>
        <a href="posts.php" class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors">초기화</a>
        <?php endif; ?>
    </div>
</form>

<div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
    <div class="overflow-x-auto">
        <table class="w-full text-sm">
            <thead>
                <tr class="border-b border-gray-700 text-gray-400">
                    <th class="px-4 py-3 text-left">ID</th>
                    <th class="px-4 py-3 text-left">게시판</th>
                    <th class="px-4 py-3 text-left">제목</th>
                    <th class="px-4 py-3 text-left">작성자</th>
                    <th class="px-4 py-3 text-right">조회</th>
                    <th class="px-4 py-3 text-right">좋아요</th>
                    <th class="px-4 py-3 text-right">댓글</th>
                    <th class="px-4 py-3 text-center">공지</th>
                    <th class="px-4 py-3 text-left">등록일</th>
                    <th class="px-4 py-3 text-center">관리</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-700">
                <?php foreach ($posts as $post): ?>
                <tr class="hover:bg-gray-750">
                    <td class="px-4 py-3 text-gray-500"><?= $post['id'] ?></td>
                    <td class="px-4 py-3">
                        <span class="px-2 py-0.5 text-xs rounded bg-gray-700 text-gray-400"><?= e($post['board_name']) ?></span>
                    </td>
                    <td class="px-4 py-3">
                        <a href="../board_detail.php?board=<?= urlencode($post['board_key']) ?>&id=<?= $post['id'] ?>" target="_blank" class="text-white font-medium max-w-sm truncate block hover:text-violet-400 transition-colors">
                            <?php if ($post['is_notice']): ?><span class="text-red-400">[공지]</span> <?php endif; ?>
                            <?= e($post['title']) ?>
                            <svg class="w-3 h-3 inline-block ml-1 opacity-50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                        </a>
                    </td>
                    <td class="px-4 py-3 text-gray-400"><?= e($post['nickname']) ?></td>
                    <td class="px-4 py-3 text-right text-gray-400"><?= number_format($post['view_count']) ?></td>
                    <td class="px-4 py-3 text-right text-gray-400"><?= number_format($post['like_count']) ?></td>
                    <td class="px-4 py-3 text-right text-gray-400"><?= number_format($post['comment_count']) ?></td>
                    <td class="px-4 py-3 text-center">
                        <?= $post['is_notice'] ? '<span class="text-red-400">Y</span>' : '<span class="text-gray-600">N</span>' ?>
                    </td>
                    <td class="px-4 py-3 text-gray-500 text-xs"><?= formatDate($post['created_at']) ?></td>
                    <td class="px-4 py-3 text-center">
                        <a href="post_delete_ok.php?id=<?= $post['id'] ?>" onclick="return confirmDelete('이 게시글을 삭제하시겠습니까?')"
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
    <a href="?page=<?= $i ?>&search=<?= urlencode($search) ?>&board=<?= urlencode($boardFilter) ?>"
       class="px-3 py-1 rounded text-sm <?= $i === $page ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700' ?> transition-colors"><?= $i ?></a>
    <?php endfor; ?>
</div>
<?php endif; ?>

<?php require_once __DIR__ . '/footer.php'; ?>
