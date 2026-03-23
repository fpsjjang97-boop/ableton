<?php
require_once __DIR__ . '/header.php';

$msg = $_GET['msg'] ?? '';
$boards = $pdo->query("SELECT b.*,
    (SELECT COUNT(*) FROM posts WHERE board_id = b.id) as post_count,
    (SELECT COUNT(*) FROM board_categories WHERE board_id = b.id) as cat_count
    FROM boards b ORDER BY b.sort_order")->fetchAll();
?>

<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">게시판 관리</h1>
    <a href="board_edit.php" class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm rounded-lg transition-colors">
        + 게시판 추가
    </a>
</div>

<?php if ($msg === 'saved'): ?>
<div class="bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg mb-6 text-sm">저장되었습니다.</div>
<?php elseif ($msg === 'deleted'): ?>
<div class="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-6 text-sm">삭제되었습니다.</div>
<?php endif; ?>

<div class="space-y-4">
    <?php foreach ($boards as $board): ?>
    <div class="bg-gray-800 rounded-xl border border-gray-700 p-5">
        <div class="flex items-center justify-between">
            <div class="flex items-center gap-4">
                <div class="w-12 h-12 bg-gray-700 rounded-xl flex items-center justify-center">
                    <?php if (!empty($board['icon_svg']) && strpos($board['icon_svg'], 'fa-') !== false): ?>
                    <i class="<?= e($board['icon_svg']) ?> text-lg <?= e($board['color_class']) ?>"></i>
                    <?php else: ?>
                    <span class="text-lg <?= e($board['color_class']) ?>">#<?= $board['id'] ?></span>
                    <?php endif; ?>
                </div>
                <div>
                    <div class="flex items-center gap-2">
                        <h3 class="text-white font-semibold text-lg"><?= e($board['board_name']) ?></h3>
                        <span class="px-2 py-0.5 text-xs rounded bg-gray-700 text-gray-400"><?= e($board['board_key']) ?></span>
                        <span class="px-2 py-0.5 text-xs rounded bg-violet-500/20 text-violet-400"><?= e($board['board_type']) ?></span>
                        <?php if (!$board['is_active']): ?>
                        <span class="px-2 py-0.5 text-xs rounded bg-red-500/20 text-red-400">비활성</span>
                        <?php endif; ?>
                    </div>
                    <p class="text-sm text-gray-400 mt-1"><?= e($board['description']) ?></p>
                </div>
            </div>
            <div class="flex items-center gap-6">
                <div class="text-center">
                    <div class="text-xl font-bold text-white"><?= number_format($board['post_count']) ?></div>
                    <div class="text-xs text-gray-500">게시글</div>
                </div>
                <div class="text-center">
                    <div class="text-xl font-bold text-white"><?= $board['cat_count'] ?></div>
                    <div class="text-xs text-gray-500">카테고리</div>
                </div>
                <div class="flex gap-2">
                    <a href="board_edit.php?id=<?= $board['id'] ?>" class="px-3 py-1.5 text-sm bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded-lg transition-colors">수정</a>
                    <a href="board_delete_ok.php?id=<?= $board['id'] ?>" onclick="return confirmDelete('이 게시판을 삭제하시겠습니까? 모든 게시글도 삭제됩니다.')"
                       class="px-3 py-1.5 text-sm bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded-lg transition-colors">삭제</a>
                </div>
            </div>
        </div>

        <!-- 설정 정보 -->
        <div class="mt-4 flex flex-wrap gap-3 text-xs text-gray-500">
            <span>댓글: <?= $board['use_comment'] ? 'ON' : 'OFF' ?></span>
            <span>좋아요: <?= $board['use_like'] ? 'ON' : 'OFF' ?></span>
            <span>에디터: <?= $board['use_editor'] ? 'ON' : 'OFF' ?></span>
            <span>페이지당: <?= $board['posts_per_page'] ?>개</span>
            <span>인기탭: <?= $board['use_popular_tab'] ? 'ON' : 'OFF' ?></span>
            <span>작성 레벨: <?= $board['write_level'] ?></span>
            <span>댓글 레벨: <?= $board['comment_level'] ?></span>
            <span>열람 레벨: <?= $board['list_level'] ?></span>
        </div>
    </div>
    <?php endforeach; ?>
</div>

<?php require_once __DIR__ . '/footer.php'; ?>
