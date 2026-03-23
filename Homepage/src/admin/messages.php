<?php
require_once __DIR__ . '/header.php';

$search = $_GET['search'] ?? '';
$page = max(1, intval($_GET['page'] ?? 1));
$perPage = 20;
$offset = ($page - 1) * $perPage;

$where = '';
$params = [];
if ($search) {
    $where = "WHERE m.title LIKE ? OR m.content LIKE ? OR s.nickname LIKE ? OR r.nickname LIKE ?";
    $params = ["%$search%", "%$search%", "%$search%", "%$search%"];
}

$totalStmt = $pdo->prepare("SELECT COUNT(*) FROM messages m
    JOIN users s ON m.sender_id = s.id JOIN users r ON m.receiver_id = r.id $where");
$totalStmt->execute($params);
$total = $totalStmt->fetchColumn();
$totalPages = max(1, ceil($total / $perPage));

$stmt = $pdo->prepare("SELECT m.*, s.nickname as sender_name, r.nickname as receiver_name
    FROM messages m JOIN users s ON m.sender_id = s.id JOIN users r ON m.receiver_id = r.id
    $where ORDER BY m.id DESC LIMIT $perPage OFFSET $offset");
$stmt->execute($params);
$messages = $stmt->fetchAll();
?>

<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">쪽지 관리</h1>
    <span class="text-sm text-gray-500">총 <?= number_format($total) ?>개</span>
</div>

<form method="GET" class="mb-6">
    <div class="flex gap-2">
        <input type="text" name="search" value="<?= e($search) ?>" placeholder="제목, 내용, 보낸이/받는이 검색..."
            class="flex-1 max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500">
        <button type="submit" class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors">검색</button>
        <?php if ($search): ?>
        <a href="messages.php" class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors">초기화</a>
        <?php endif; ?>
    </div>
</form>

<div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
    <div class="overflow-x-auto">
        <table class="w-full text-sm">
            <thead>
                <tr class="border-b border-gray-700 text-gray-400">
                    <th class="px-4 py-3 text-left">ID</th>
                    <th class="px-4 py-3 text-left">보낸이</th>
                    <th class="px-4 py-3 text-left">받는이</th>
                    <th class="px-4 py-3 text-left">제목</th>
                    <th class="px-4 py-3 text-center">읽음</th>
                    <th class="px-4 py-3 text-left">보낸 날짜</th>
                    <th class="px-4 py-3 text-center">관리</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-700">
                <?php foreach ($messages as $msg): ?>
                <tr class="hover:bg-gray-750">
                    <td class="px-4 py-3 text-gray-500"><?= $msg['id'] ?></td>
                    <td class="px-4 py-3 text-gray-300"><?= e($msg['sender_name']) ?></td>
                    <td class="px-4 py-3 text-gray-300"><?= e($msg['receiver_name']) ?></td>
                    <td class="px-4 py-3">
                        <div class="text-white max-w-sm truncate"><?= e($msg['title']) ?></div>
                        <div class="text-xs text-gray-500 max-w-sm truncate"><?= e(mb_substr($msg['content'], 0, 50)) ?></div>
                    </td>
                    <td class="px-4 py-3 text-center">
                        <?= $msg['is_read'] ? '<span class="text-green-400">Y</span>' : '<span class="text-gray-600">N</span>' ?>
                    </td>
                    <td class="px-4 py-3 text-gray-500 text-xs"><?= formatDate($msg['created_at']) ?></td>
                    <td class="px-4 py-3 text-center">
                        <a href="message_delete_ok.php?id=<?= $msg['id'] ?>" onclick="return confirmDelete('이 쪽지를 삭제하시겠습니까?')"
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
