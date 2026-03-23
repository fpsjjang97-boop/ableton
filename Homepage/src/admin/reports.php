<?php
require_once __DIR__ . '/header.php';

$statusFilter = $_GET['status'] ?? '';
$page = max(1, intval($_GET['page'] ?? 1));
$perPage = 20;
$offset = ($page - 1) * $perPage;

$where = '1=1';
$params = [];
if ($statusFilter) {
    $where .= " AND r.status = ?";
    $params[] = $statusFilter;
}

$totalStmt = $pdo->prepare("SELECT COUNT(*) FROM reports r WHERE $where");
$totalStmt->execute($params);
$total = $totalStmt->fetchColumn();
$totalPages = max(1, ceil($total / $perPage));

$stmt = $pdo->prepare("SELECT r.*, u.nickname as reporter_name, u.id as reporter_user_id
    FROM reports r JOIN users u ON r.reporter_id = u.id
    WHERE $where ORDER BY r.id DESC LIMIT $perPage OFFSET $offset");
$stmt->execute($params);
$reports = $stmt->fetchAll();

$statusCounts = $pdo->query("SELECT status, COUNT(*) as cnt FROM reports GROUP BY status")->fetchAll(PDO::FETCH_KEY_PAIR);

// 각 신고에 대해 대상 콘텐츠 정보와 피신고자 정보 조회
foreach ($reports as &$report) {
    $report['target_title'] = null;
    $report['target_content'] = null;
    $report['target_link'] = null;
    $report['target_owner_id'] = null;
    $report['target_owner_name'] = null;

    switch ($report['target_type']) {
        case 'track':
            $tStmt = $pdo->prepare('SELECT t.title, t.description, t.user_id, u.nickname as owner_name FROM tracks t JOIN users u ON t.user_id = u.id WHERE t.id = ?');
            $tStmt->execute([$report['target_id']]);
            $target = $tStmt->fetch();
            if ($target) {
                $report['target_title'] = $target['title'];
                $report['target_content'] = $target['description'];
                $report['target_link'] = '../music_detail.php?id=' . $report['target_id'];
                $report['target_owner_id'] = $target['user_id'];
                $report['target_owner_name'] = $target['owner_name'];
            }
            break;
        case 'prompt':
            $tStmt = $pdo->prepare('SELECT p.title, p.prompt_text, p.user_id, u.nickname as owner_name FROM prompts p JOIN users u ON p.user_id = u.id WHERE p.id = ?');
            $tStmt->execute([$report['target_id']]);
            $target = $tStmt->fetch();
            if ($target) {
                $report['target_title'] = $target['title'];
                $report['target_content'] = $target['prompt_text'];
                $report['target_link'] = '../prompt_detail.php?id=' . $report['target_id'];
                $report['target_owner_id'] = $target['user_id'];
                $report['target_owner_name'] = $target['owner_name'];
            }
            break;
        case 'post':
            $tStmt = $pdo->prepare('SELECT p.title, p.content, p.user_id, p.board_id, u.nickname as owner_name, b.board_key FROM posts p JOIN users u ON p.user_id = u.id JOIN boards b ON p.board_id = b.id WHERE p.id = ?');
            $tStmt->execute([$report['target_id']]);
            $target = $tStmt->fetch();
            if ($target) {
                $report['target_title'] = $target['title'];
                $report['target_content'] = strip_tags($target['content']);
                $report['target_link'] = '../board_detail.php?board=' . $target['board_key'] . '&id=' . $report['target_id'];
                $report['target_owner_id'] = $target['user_id'];
                $report['target_owner_name'] = $target['owner_name'];
            }
            break;
        case 'comment':
            $tStmt = $pdo->prepare('SELECT c.content, c.user_id, u.nickname as owner_name FROM post_comments c JOIN users u ON c.user_id = u.id WHERE c.id = ?');
            $tStmt->execute([$report['target_id']]);
            $target = $tStmt->fetch();
            if ($target) {
                $report['target_title'] = '댓글';
                $report['target_content'] = $target['content'];
                $report['target_owner_id'] = $target['user_id'];
                $report['target_owner_name'] = $target['owner_name'];
            }
            break;
        case 'user':
            $tStmt = $pdo->prepare('SELECT id, nickname, email FROM users WHERE id = ?');
            $tStmt->execute([$report['target_id']]);
            $target = $tStmt->fetch();
            if ($target) {
                $report['target_title'] = $target['nickname'];
                $report['target_content'] = $target['email'] ?? '';
                $report['target_link'] = 'users.php?search=' . urlencode($target['nickname']);
                $report['target_owner_id'] = $target['id'];
                $report['target_owner_name'] = $target['nickname'];
            }
            break;
        case 'message':
            $tStmt = $pdo->prepare('SELECT m.content, m.sender_id, u.nickname as owner_name FROM messages m JOIN users u ON m.sender_id = u.id WHERE m.id = ?');
            $tStmt->execute([$report['target_id']]);
            $target = $tStmt->fetch();
            if ($target) {
                $report['target_title'] = '쪽지';
                $report['target_content'] = $target['content'];
                $report['target_owner_id'] = $target['sender_id'];
                $report['target_owner_name'] = $target['owner_name'];
            }
            break;
    }
}
unset($report);

$statusLabels = ['pending' => '대기', 'reviewed' => '검토중', 'resolved' => '처리완료', 'dismissed' => '기각'];
$statusColors = ['pending' => 'bg-yellow-600', 'reviewed' => 'bg-blue-600', 'resolved' => 'bg-green-600', 'dismissed' => 'bg-gray-600'];
$typeLabels = ['track'=>'트랙','prompt'=>'프롬프트','post'=>'게시글','comment'=>'댓글','user'=>'회원','message'=>'쪽지'];
$typeIcons = ['track'=>'fa-music','prompt'=>'fa-wand-magic-sparkles','post'=>'fa-newspaper','comment'=>'fa-comment','user'=>'fa-user','message'=>'fa-envelope'];
$typeColors = ['track'=>'text-violet-400','prompt'=>'text-amber-400','post'=>'text-emerald-400','comment'=>'text-blue-400','user'=>'text-rose-400','message'=>'text-cyan-400'];
?>

<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">신고 관리</h1>
    <span class="text-sm text-gray-500">총 <?= number_format($total) ?>건</span>
</div>

<!-- 상태 필터 -->
<div class="flex gap-2 mb-6">
    <a href="reports.php" class="px-4 py-2 rounded-lg text-sm transition-colors <?= !$statusFilter ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700' ?>">
        전체 (<?= array_sum($statusCounts ?: []) ?>)
    </a>
    <?php foreach ($statusLabels as $sk => $sv): ?>
    <a href="?status=<?= $sk ?>" class="px-4 py-2 rounded-lg text-sm transition-colors <?= $statusFilter === $sk ? $statusColors[$sk] . ' text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700' ?>">
        <?= $sv ?> (<?= $statusCounts[$sk] ?? 0 ?>)
    </a>
    <?php endforeach; ?>
</div>

<?php if (empty($reports)): ?>
<div class="bg-gray-800 rounded-xl border border-gray-700 p-12 text-center text-gray-500">신고 내역이 없습니다.</div>
<?php endif; ?>

<!-- 신고 목록 (카드 형태) -->
<div class="space-y-4">
    <?php foreach ($reports as $report): ?>
    <?php
        $sc = ['pending'=>'border-l-yellow-500','reviewed'=>'border-l-blue-500','resolved'=>'border-l-green-500','dismissed'=>'border-l-gray-500'];
        $scBadge = ['pending'=>'bg-yellow-500/20 text-yellow-400','reviewed'=>'bg-blue-500/20 text-blue-400','resolved'=>'bg-green-500/20 text-green-400','dismissed'=>'bg-gray-500/20 text-gray-400'];
    ?>
    <div class="bg-gray-800 rounded-xl border border-gray-700 border-l-4 <?= $sc[$report['status']] ?? 'border-l-gray-500' ?> overflow-hidden">
        <!-- 상단: 메타 정보 -->
        <div class="flex items-center justify-between px-5 pt-4 pb-2">
            <div class="flex items-center gap-3">
                <span class="text-xs text-gray-500">#<?= $report['id'] ?></span>
                <span class="inline-flex items-center gap-1.5 px-2.5 py-0.5 text-xs rounded-full bg-gray-700/50 <?= $typeColors[$report['target_type']] ?? 'text-gray-400' ?>">
                    <i class="fa-solid <?= $typeIcons[$report['target_type']] ?? 'fa-circle' ?> text-[10px]"></i>
                    <?= $typeLabels[$report['target_type']] ?? $report['target_type'] ?>
                </span>
                <span class="px-2 py-0.5 text-xs rounded-full <?= $scBadge[$report['status']] ?? '' ?>">
                    <?= $statusLabels[$report['status']] ?? $report['status'] ?>
                </span>
                <span class="text-xs text-gray-500"><?= formatDate($report['created_at']) ?></span>
            </div>
            <form method="POST" action="report_update_ok.php" class="inline-flex gap-1">
                <input type="hidden" name="id" value="<?= $report['id'] ?>">
                <select name="status" class="px-2 py-1 text-xs bg-gray-700 border border-gray-600 rounded text-white">
                    <?php foreach ($statusLabels as $sk => $sv): ?>
                    <option value="<?= $sk ?>" <?= $report['status'] === $sk ? 'selected' : '' ?>><?= $sv ?></option>
                    <?php endforeach; ?>
                </select>
                <button type="submit" class="px-2 py-1 text-xs bg-violet-600/20 text-violet-400 hover:bg-violet-600/30 rounded transition-colors">변경</button>
            </form>
        </div>

        <div class="px-5 pb-4">
            <!-- 신고 사유 -->
            <div class="flex items-start gap-2 mb-3 bg-red-500/5 border border-red-500/10 rounded-lg px-3 py-2.5">
                <i class="fa-solid fa-triangle-exclamation text-red-400 text-xs mt-0.5"></i>
                <div>
                    <span class="text-[10px] text-red-400/60 font-semibold uppercase tracking-wider">신고 사유</span>
                    <p class="text-sm text-red-300/90 mt-0.5"><?= e($report['reason']) ?></p>
                </div>
            </div>

            <div class="grid grid-cols-1 md:grid-cols-2 gap-3">
                <!-- 신고 대상 콘텐츠 정보 -->
                <div class="bg-gray-900/50 rounded-lg px-4 py-3">
                    <div class="flex items-center justify-between mb-2">
                        <span class="text-[10px] text-gray-500 font-semibold uppercase tracking-wider">신고 대상 콘텐츠</span>
                        <?php if ($report['target_link']): ?>
                        <a href="<?= $report['target_link'] ?>" target="_blank" class="text-[10px] text-violet-400 hover:text-violet-300 transition-colors flex items-center gap-1">
                            <i class="fa-solid fa-arrow-up-right-from-square text-[9px]"></i>
                            바로가기
                        </a>
                        <?php endif; ?>
                    </div>
                    <?php if ($report['target_title']): ?>
                    <p class="text-sm font-semibold text-white mb-1"><?= e($report['target_title']) ?></p>
                    <?php if ($report['target_content']): ?>
                    <p class="text-xs text-gray-400 line-clamp-2 leading-relaxed"><?= e(mb_substr($report['target_content'], 0, 150)) ?><?= mb_strlen($report['target_content']) > 150 ? '...' : '' ?></p>
                    <?php endif; ?>
                    <?php else: ?>
                    <p class="text-xs text-gray-500 italic">삭제되었거나 찾을 수 없는 콘텐츠입니다.</p>
                    <?php endif; ?>
                </div>

                <!-- 인물 정보: 신고자 + 피신고자 -->
                <div class="bg-gray-900/50 rounded-lg px-4 py-3">
                    <span class="text-[10px] text-gray-500 font-semibold uppercase tracking-wider block mb-2">관련 사용자</span>
                    <div class="space-y-2">
                        <!-- 신고자 -->
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="text-[10px] bg-blue-500/10 text-blue-400 px-1.5 py-0.5 rounded font-medium">신고자</span>
                                <a href="users.php?search=<?= urlencode($report['reporter_name']) ?>" class="text-sm text-gray-300 hover:text-white transition-colors">
                                    <?= e($report['reporter_name']) ?>
                                </a>
                            </div>
                            <a href="../profile.php?id=<?= $report['reporter_user_id'] ?>" target="_blank" class="text-[10px] text-gray-500 hover:text-gray-400 transition-colors">
                                프로필 <i class="fa-solid fa-arrow-up-right-from-square text-[8px]"></i>
                            </a>
                        </div>
                        <!-- 피신고자 (콘텐츠 작성자) -->
                        <?php if ($report['target_owner_name']): ?>
                        <div class="flex items-center justify-between">
                            <div class="flex items-center gap-2">
                                <span class="text-[10px] bg-red-500/10 text-red-400 px-1.5 py-0.5 rounded font-medium">피신고자</span>
                                <a href="users.php?search=<?= urlencode($report['target_owner_name']) ?>" class="text-sm text-gray-300 hover:text-white transition-colors">
                                    <?= e($report['target_owner_name']) ?>
                                </a>
                            </div>
                            <a href="../profile.php?id=<?= $report['target_owner_id'] ?>" target="_blank" class="text-[10px] text-gray-500 hover:text-gray-400 transition-colors">
                                프로필 <i class="fa-solid fa-arrow-up-right-from-square text-[8px]"></i>
                            </a>
                        </div>
                        <?php else: ?>
                        <div class="flex items-center gap-2">
                            <span class="text-[10px] bg-red-500/10 text-red-400 px-1.5 py-0.5 rounded font-medium">피신고자</span>
                            <span class="text-xs text-gray-500 italic">알 수 없음</span>
                        </div>
                        <?php endif; ?>
                    </div>
                </div>
            </div>
        </div>
    </div>
    <?php endforeach; ?>
</div>

<?php if ($totalPages > 1): ?>
<div class="flex items-center justify-center gap-1 mt-6">
    <?php for ($i = 1; $i <= $totalPages; $i++): ?>
    <a href="?page=<?= $i ?>&status=<?= urlencode($statusFilter) ?>"
       class="px-3 py-1 rounded text-sm <?= $i === $page ? 'bg-violet-600 text-white' : 'bg-gray-800 text-gray-400 hover:bg-gray-700' ?> transition-colors"><?= $i ?></a>
    <?php endfor; ?>
</div>
<?php endif; ?>

<style>
.line-clamp-2 {
    display: -webkit-box;
    -webkit-line-clamp: 2;
    -webkit-box-orient: vertical;
    overflow: hidden;
}
</style>

<?php require_once __DIR__ . '/footer.php'; ?>
