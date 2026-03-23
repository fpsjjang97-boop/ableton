<?php
require_once __DIR__ . '/header.php';

// 통계 데이터 가져오기
$stats = [];
$stats['users'] = $pdo->query("SELECT COUNT(*) FROM users")->fetchColumn();
$stats['tracks'] = $pdo->query("SELECT COUNT(*) FROM tracks")->fetchColumn();
$stats['prompts'] = $pdo->query("SELECT COUNT(*) FROM prompts")->fetchColumn();
$stats['posts'] = $pdo->query("SELECT COUNT(*) FROM posts")->fetchColumn();
$stats['messages'] = $pdo->query("SELECT COUNT(*) FROM messages")->fetchColumn();
$stats['comments'] = $pdo->query("SELECT COUNT(*) FROM post_comments")->fetchColumn()
                   + $pdo->query("SELECT COUNT(*) FROM track_comments")->fetchColumn()
                   + $pdo->query("SELECT COUNT(*) FROM prompt_comments")->fetchColumn();
$stats['reports_pending'] = $pdo->query("SELECT COUNT(*) FROM reports WHERE status = 'pending'")->fetchColumn();
$stats['total_plays'] = $pdo->query("SELECT COALESCE(SUM(play_count),0) FROM tracks")->fetchColumn();

// 최근 가입 회원
$recentUsers = $pdo->query("SELECT id, nickname, email, badge, created_at FROM users ORDER BY created_at DESC LIMIT 5")->fetchAll();

// 최근 트랙
$recentTracks = $pdo->query("SELECT t.id, t.title, u.nickname, t.play_count, t.like_count, t.created_at
    FROM tracks t JOIN users u ON t.user_id = u.id ORDER BY t.created_at DESC LIMIT 5")->fetchAll();

// 최근 게시글
$recentPosts = $pdo->query("SELECT p.id, p.title, u.nickname, b.board_name, p.view_count, p.created_at
    FROM posts p JOIN users u ON p.user_id = u.id JOIN boards b ON p.board_id = b.id ORDER BY p.created_at DESC LIMIT 5")->fetchAll();

$statCards = [
    ['회원', $stats['users'], 'bg-violet-600', '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4.354a4 4 0 110 5.292M15 21H3v-1a6 6 0 0112 0v1zm0 0h6v-1a6 6 0 00-9-5.197M13 7a4 4 0 11-8 0 4 4 0 018 0z"/>'],
    ['트랙', $stats['tracks'], 'bg-pink-600', '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 19V6l12-3v13M9 19c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zm12-3c0 1.105-1.343 2-3 2s-3-.895-3-2 1.343-2 3-2 3 .895 3 2zM9 10l12-3"/>'],
    ['프롬프트', $stats['prompts'], 'bg-cyan-600', '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M11 5H6a2 2 0 00-2 2v11a2 2 0 002 2h11a2 2 0 002-2v-5m-1.414-9.414a2 2 0 112.828 2.828L11.828 15H9v-2.828l8.586-8.586z"/>'],
    ['게시글', $stats['posts'], 'bg-amber-600', '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 20H5a2 2 0 01-2-2V6a2 2 0 012-2h10a2 2 0 012 2v1m2 13a2 2 0 01-2-2V7m2 13a2 2 0 002-2V9a2 2 0 00-2-2h-2m-4-3H9M7 16h6M7 8h6v4H7V8z"/>'],
    ['쪽지', $stats['messages'], 'bg-emerald-600', '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>'],
    ['댓글', $stats['comments'], 'bg-blue-600', '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 8h10M7 12h4m1 8l-4-4H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-3l-4 4z"/>'],
    ['총 재생수', number_format($stats['total_plays']), 'bg-indigo-600', '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>'],
    ['미처리 신고', $stats['reports_pending'], $stats['reports_pending'] > 0 ? 'bg-red-600' : 'bg-gray-600', '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z"/>'],
];
?>

<h1 class="text-2xl font-bold text-white mb-8">대시보드</h1>

<!-- 통계 카드 -->
<div class="grid grid-cols-2 md:grid-cols-4 gap-4 mb-8">
    <?php foreach ($statCards as $card): ?>
    <div class="bg-gray-800 rounded-xl p-5 border border-gray-700">
        <div class="flex items-center gap-3 mb-3">
            <div class="w-10 h-10 <?= $card[2] ?> rounded-lg flex items-center justify-center">
                <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24"><?= $card[3] ?></svg>
            </div>
            <span class="text-sm text-gray-400"><?= $card[0] ?></span>
        </div>
        <div class="text-2xl font-bold text-white"><?= $card[1] ?></div>
    </div>
    <?php endforeach; ?>
</div>

<div class="grid grid-cols-1 lg:grid-cols-2 gap-6">
    <!-- 최근 가입 회원 -->
    <div class="bg-gray-800 rounded-xl border border-gray-700">
        <div class="flex items-center justify-between p-5 border-b border-gray-700">
            <h2 class="font-semibold text-white">최근 가입 회원</h2>
            <a href="users.php" class="text-sm text-violet-400 hover:text-violet-300">전체 보기 &rarr;</a>
        </div>
        <div class="divide-y divide-gray-700">
            <?php foreach ($recentUsers as $user): ?>
            <div class="flex items-center justify-between px-5 py-3">
                <div>
                    <div class="text-sm font-medium text-white"><?= e($user['nickname']) ?></div>
                    <div class="text-xs text-gray-500"><?= e($user['email']) ?></div>
                </div>
                <div class="text-right">
                    <span class="inline-block px-2 py-0.5 text-xs rounded-full
                        <?php
                        $colors = ['Bronze'=>'bg-orange-500/20 text-orange-400','Silver'=>'bg-gray-500/20 text-gray-400','Gold'=>'bg-yellow-500/20 text-yellow-400','Diamond'=>'bg-cyan-500/20 text-cyan-400'];
                        echo $colors[$user['badge']] ?? 'bg-gray-500/20 text-gray-400';
                        ?>"><?= e($user['badge']) ?></span>
                    <div class="text-xs text-gray-500 mt-1"><?= formatDate($user['created_at']) ?></div>
                </div>
            </div>
            <?php endforeach; ?>
        </div>
    </div>

    <!-- 최근 트랙 -->
    <div class="bg-gray-800 rounded-xl border border-gray-700">
        <div class="flex items-center justify-between p-5 border-b border-gray-700">
            <h2 class="font-semibold text-white">최근 트랙</h2>
            <a href="tracks.php" class="text-sm text-violet-400 hover:text-violet-300">전체 보기 &rarr;</a>
        </div>
        <div class="divide-y divide-gray-700">
            <?php foreach ($recentTracks as $track): ?>
            <div class="flex items-center justify-between px-5 py-3">
                <div>
                    <div class="text-sm font-medium text-white"><?= e($track['title']) ?></div>
                    <div class="text-xs text-gray-500">by <?= e($track['nickname']) ?></div>
                </div>
                <div class="text-right text-xs text-gray-500">
                    <div>재생 <?= number_format($track['play_count']) ?> / 좋아요 <?= number_format($track['like_count']) ?></div>
                    <div class="mt-1"><?= formatDate($track['created_at']) ?></div>
                </div>
            </div>
            <?php endforeach; ?>
        </div>
    </div>

    <!-- 최근 게시글 -->
    <div class="bg-gray-800 rounded-xl border border-gray-700 lg:col-span-2">
        <div class="flex items-center justify-between p-5 border-b border-gray-700">
            <h2 class="font-semibold text-white">최근 게시글</h2>
            <a href="posts.php" class="text-sm text-violet-400 hover:text-violet-300">전체 보기 &rarr;</a>
        </div>
        <div class="divide-y divide-gray-700">
            <?php foreach ($recentPosts as $post): ?>
            <div class="flex items-center justify-between px-5 py-3">
                <div class="flex items-center gap-3">
                    <span class="px-2 py-0.5 text-xs rounded bg-gray-700 text-gray-400"><?= e($post['board_name']) ?></span>
                    <span class="text-sm text-white"><?= e($post['title']) ?></span>
                </div>
                <div class="text-right text-xs text-gray-500">
                    <span><?= e($post['nickname']) ?></span>
                    <span class="mx-2">|</span>
                    <span>조회 <?= number_format($post['view_count']) ?></span>
                    <span class="mx-2">|</span>
                    <span><?= formatDate($post['created_at']) ?></span>
                </div>
            </div>
            <?php endforeach; ?>
        </div>
    </div>
</div>

<?php require_once __DIR__ . '/footer.php'; ?>
