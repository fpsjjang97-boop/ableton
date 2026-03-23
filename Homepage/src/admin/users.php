<?php
require_once __DIR__ . '/header.php';

$search = $_GET['search'] ?? '';
$page = max(1, intval($_GET['page'] ?? 1));
$perPage = 20;
$offset = ($page - 1) * $perPage;

$where = '';
$params = [];
if ($search) {
    $where = "WHERE nickname LIKE ? OR email LIKE ?";
    $params = ["%$search%", "%$search%"];
}

$totalStmt = $pdo->prepare("SELECT COUNT(*) FROM users $where");
$totalStmt->execute($params);
$total = $totalStmt->fetchColumn();
$totalPages = max(1, ceil($total / $perPage));

$stmt = $pdo->prepare("SELECT * FROM users $where ORDER BY id DESC LIMIT $perPage OFFSET $offset");
$stmt->execute($params);
$users = $stmt->fetchAll();
?>

<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">회원 관리</h1>
    <span class="text-sm text-gray-500">총 <?= number_format($total) ?>명</span>
</div>

<!-- 검색 -->
<form method="GET" class="mb-6">
    <div class="flex gap-2">
        <input type="text" name="search" value="<?= e($search) ?>" placeholder="닉네임 또는 이메일 검색..."
            class="flex-1 max-w-md px-4 py-2 bg-gray-800 border border-gray-700 rounded-lg text-white placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500">
        <button type="submit" class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white rounded-lg transition-colors">검색</button>
        <?php if ($search): ?>
        <a href="users.php" class="px-4 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors">초기화</a>
        <?php endif; ?>
    </div>
</form>

<!-- 회원 목록 -->
<div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
    <div class="overflow-x-auto">
        <table class="w-full text-sm">
            <thead>
                <tr class="border-b border-gray-700 text-gray-400">
                    <th class="px-4 py-3 text-left">ID</th>
                    <th class="px-4 py-3 text-left">닉네임</th>
                    <th class="px-4 py-3 text-left">이메일</th>
                    <th class="px-4 py-3 text-center">등급</th>
                    <th class="px-4 py-3 text-center">관리자</th>
                    <th class="px-4 py-3 text-left">가입일</th>
                    <th class="px-4 py-3 text-center">관리</th>
                </tr>
            </thead>
            <tbody class="divide-y divide-gray-700">
                <?php foreach ($users as $user): ?>
                <tr class="hover:bg-gray-750">
                    <td class="px-4 py-3 text-gray-500"><?= $user['id'] ?></td>
                    <td class="px-4 py-3">
                        <div class="flex items-center gap-2">
                            <?php if ($user['avatar_url']): ?>
                            <img src="../<?= e($user['avatar_url']) ?>" class="w-8 h-8 rounded-full object-cover" alt="">
                            <?php else: ?>
                            <div class="w-8 h-8 bg-gradient-to-br <?= e($user['avatar_color'] ?? 'from-violet-500 to-purple-600') ?> rounded-full flex items-center justify-center text-white text-xs font-bold">
                                <?= mb_substr($user['nickname'], 0, 1) ?>
                            </div>
                            <?php endif; ?>
                            <span class="text-white font-medium"><?= e($user['nickname']) ?></span>
                        </div>
                    </td>
                    <td class="px-4 py-3 text-gray-400"><?= e($user['email']) ?></td>
                    <td class="px-4 py-3 text-center">
                        <span class="inline-block px-2 py-0.5 text-xs rounded-full
                            <?php
                            $colors = ['Bronze'=>'bg-orange-500/20 text-orange-400','Silver'=>'bg-gray-500/20 text-gray-400','Gold'=>'bg-yellow-500/20 text-yellow-400','Diamond'=>'bg-cyan-500/20 text-cyan-400'];
                            echo $colors[$user['badge']] ?? 'bg-gray-500/20 text-gray-400';
                            ?>"><?= e($user['badge']) ?></span>
                    </td>
                    <td class="px-4 py-3 text-center">
                        <?php if ($user['is_admin']): ?>
                        <span class="text-violet-400">Y</span>
                        <?php else: ?>
                        <span class="text-gray-600">N</span>
                        <?php endif; ?>
                    </td>
                    <td class="px-4 py-3 text-gray-500 text-xs"><?= formatDate($user['created_at']) ?></td>
                    <td class="px-4 py-3 text-center">
                        <div class="flex items-center justify-center gap-1">
                            <a href="user_edit.php?id=<?= $user['id'] ?>" class="px-2 py-1 text-xs bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded transition-colors">수정</a>
                            <a href="user_delete_ok.php?id=<?= $user['id'] ?>" onclick="return confirmDelete('이 회원을 삭제하시겠습니까? 관련 데이터도 모두 삭제됩니다.')"
                               class="px-2 py-1 text-xs bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded transition-colors">삭제</a>
                        </div>
                    </td>
                </tr>
                <?php endforeach; ?>
            </tbody>
        </table>
    </div>
</div>

<!-- 페이지네이션 -->
<?php if ($totalPages > 1): ?>
<div class="flex items-center justify-center gap-1 mt-6">
    <?php for ($i = 1; $i <= $totalPages; $i++): ?>
    <a href="?page=<?= $i ?>&search=<?= urlencode($search) ?>"
       class="px-3 py-1 rounded text-sm <?= $i === $page ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700' ?> transition-colors"><?= $i ?></a>
    <?php endfor; ?>
</div>
<?php endif; ?>

<?php require_once __DIR__ . '/footer.php'; ?>
