<?php
require_once 'db.php';
$pageTitle = '좋아요 랭킹';

$tab = isset($_GET['tab']) ? $_GET['tab'] : 'total';
if (!in_array($tab, ['total', 'board', 'prompt', 'music'])) $tab = 'total';

$period = isset($_GET['period']) ? $_GET['period'] : 'all';
if (!in_array($period, ['weekly', 'monthly', 'all'])) $period = 'all';

$perPage = 20;
$page = isset($_GET['page']) ? max(1, (int)$_GET['page']) : 1;
$offset = ($page - 1) * $perPage;

$orderColumn = 'total_likes';
if ($tab === 'board') $orderColumn = 'board_likes';
elseif ($tab === 'prompt') $orderColumn = 'prompt_likes';
elseif ($tab === 'music') $orderColumn = 'music_likes';

$periodMap = ['weekly' => 'weekly', 'monthly' => 'monthly', 'all' => 'all_time'];
$dbPeriod = $periodMap[$period];

$countStmt = $pdo->prepare('SELECT COUNT(*) FROM rankings WHERE period = ?');
$countStmt->execute([$dbPeriod]);
$totalUsers = (int)$countStmt->fetchColumn();
$totalPages = max(1, ceil($totalUsers / $perPage));
if ($page > $totalPages) $page = $totalPages;
$offset = ($page - 1) * $perPage;

$stmt = $pdo->prepare("
    SELECT rankings.*, users.nickname, users.avatar_color, users.badge
    FROM rankings
    JOIN users ON rankings.user_id = users.id
    WHERE period = ?
    ORDER BY $orderColumn DESC
    LIMIT ? OFFSET ?
");
$stmt->execute([$dbPeriod, $perPage, $offset]);
$users = $stmt->fetchAll();

// 순위 번호 재계산
foreach ($users as $i => &$u) {
    $u['rank_position'] = $offset + $i + 1;
}
unset($u);

$baseUrl = 'ranking.php?tab=' . $tab . '&period=' . $period;

$tabList = [
    'total' => '종합',
    'board' => '게시판',
    'prompt' => '프롬프트',
    'music' => '음원',
];
$periodList = [
    'weekly' => '주간',
    'monthly' => '월간',
    'all' => '전체',
];
?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<style>
    .rank-row { transition: all 0.15s ease; }
    .rank-row:hover { background: rgba(139,92,246,0.04); }
</style>

<main class="pt-20">
    <section class="py-10 border-b border-suno-border">
        <div class="max-w-5xl mx-auto px-6">
            <div class="flex items-center gap-3">
                <div class="w-10 h-10 bg-suno-accent/10 border border-suno-accent/20 rounded-xl flex items-center justify-center">
                    <svg class="w-5 h-5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16.5 18.75h-9m9 0a3 3 0 013 3h-15a3 3 0 013-3m9 0v-3.375c0-.621-.503-1.125-1.125-1.125h-.871M7.5 18.75v-3.375c0-.621.504-1.125 1.125-1.125h.872m5.007 0H9.497m5.007 0a7.454 7.454 0 01-.982-3.172M9.497 14.25a7.454 7.454 0 00.981-3.172M5.25 4.236c-.982.143-1.954.317-2.916.52A6.003 6.003 0 007.73 9.728M5.25 4.236V4.5c0 2.108.966 3.99 2.48 5.228M5.25 4.236V2.721C7.456 2.41 9.71 2.25 12 2.25c2.291 0 4.545.16 6.75.47v1.516M18.75 4.236c.982.143 1.954.317 2.916.52A6.003 6.003 0 0016.27 9.728M18.75 4.236V4.5c0 2.108-.966 3.99-2.48 5.228m0 0a6.003 6.003 0 01-2.54.923"/>
                    </svg>
                </div>
                <div>
                    <h1 class="text-xl font-bold">좋아요 랭킹</h1>
                    <p class="text-suno-muted text-xs mt-0.5">게시판 · 프롬프트 · 음원 전체 좋아요 기준</p>
                </div>
            </div>
        </div>
    </section>

    <section class="border-b border-suno-border">
        <div class="max-w-5xl mx-auto px-6">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-0">
                    <?php foreach ($tabList as $tKey => $tLabel): ?>
                    <a href="ranking.php?tab=<?php echo $tKey; ?>&period=<?php echo $period; ?>" class="px-4 py-3 text-sm font-medium transition-colors border-b-2 <?php echo $tab === $tKey ? 'font-semibold text-suno-accent border-suno-accent' : 'text-suno-muted hover:text-white border-transparent'; ?>"><?php echo $tLabel; ?></a>
                    <?php endforeach; ?>
                </div>
                <div class="flex gap-1 bg-suno-surface rounded-lg p-1">
                    <?php foreach ($periodList as $pKey => $pLabel): ?>
                    <a href="ranking.php?tab=<?php echo $tab; ?>&period=<?php echo $pKey; ?>" class="px-3 py-1 rounded-md text-xs font-medium transition-all <?php echo $period === $pKey ? 'bg-suno-card text-white shadow-sm' : 'text-suno-muted hover:text-white'; ?>"><?php echo $pLabel; ?></a>
                    <?php endforeach; ?>
                </div>
            </div>
        </div>
    </section>

    <?php if(count($users) >= 3 && $page === 1): ?>
    <section class="py-10 border-b border-suno-border">
        <div class="max-w-5xl mx-auto px-6">
            <div class="flex items-end justify-center gap-4 md:gap-8">
                <?php
                $topColors = [
                    1 => ['ring' => 'ring-amber-400/30', 'badge_bg' => 'bg-amber-400', 'badge_text' => 'text-amber-900', 'score_color' => 'text-amber-400', 'bar' => 'from-amber-400/15', 'size' => 100, 'bar_h' => 'h-28', 'text_size' => 'text-2xl md:text-3xl', 'name_size' => 'text-base'],
                    2 => ['ring' => 'ring-gray-400/20', 'badge_bg' => 'bg-gray-400', 'badge_text' => 'text-gray-900', 'score_color' => 'text-gray-300', 'bar' => 'from-gray-400/15', 'size' => 80, 'bar_h' => 'h-20', 'text_size' => 'text-xl md:text-2xl', 'name_size' => 'text-sm'],
                    3 => ['ring' => 'ring-amber-700/20', 'badge_bg' => 'bg-amber-700', 'badge_text' => 'text-amber-100', 'score_color' => 'text-amber-600', 'bar' => 'from-amber-700/15', 'size' => 80, 'bar_h' => 'h-14', 'text_size' => 'text-xl md:text-2xl', 'name_size' => 'text-sm'],
                ];
                $displayOrder = [1, 0, 2]; // 2nd, 1st, 3rd
                foreach ($displayOrder as $idx):
                    $u = $users[$idx];
                    $r = $idx + 1;
                    $c = $topColors[$r];
                    $likeVal = $tab === 'board' ? ($u['board_likes'] ?? 0) : ($tab === 'prompt' ? ($u['prompt_likes'] ?? 0) : ($tab === 'music' ? ($u['music_likes'] ?? 0) : ($u['total_likes'] ?? 0)));
                ?>
                <div class="text-center flex-1 <?php echo $r === 1 ? 'max-w-[200px]' : 'max-w-[180px]'; ?>">
                    <div class="relative inline-block mb-3">
                        <div class="rounded-full bg-gradient-to-r <?php echo $u['avatar_color'] ?: 'from-violet-500 to-purple-500'; ?> flex items-center justify-center <?php echo $c['text_size']; ?> font-bold mx-auto ring-4 <?php echo $c['ring']; ?>" style="width:<?php echo $c['size']; ?>px;height:<?php echo $c['size']; ?>px;">
                            <?php echo mb_substr($u['nickname'], 0, 1); ?>
                        </div>
                        <div class="absolute -bottom-1 -right-1 w-7 h-7 <?php echo $c['badge_bg']; ?> rounded-full flex items-center justify-center text-xs font-bold <?php echo $c['badge_text']; ?> shadow-lg">
                            <?php echo $r === 1 ? '<svg class="w-4 h-4" fill="currentColor" viewBox="0 0 24 24"><path d="M5 16L3 5l5.5 5L12 4l3.5 6L21 5l-2 11H5z"/></svg>' : $r; ?>
                        </div>
                    </div>
                    <a href="profile.php?id=<?php echo $u['user_id']; ?>" class="block font-bold <?php echo $c['name_size']; ?> hover:text-suno-accent2 transition-colors truncate"><?php echo htmlspecialchars($u['nickname']); ?></a>
                    <p class="text-sm font-bold <?php echo $c['score_color']; ?> mt-1">
                        <svg class="w-3.5 h-3.5 inline text-rose-400 mr-0.5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/></svg>
                        <?php echo number_format($likeVal); ?>
                    </p>
                    <div class="mt-3 <?php echo $c['bar_h']; ?> bg-gradient-to-t <?php echo $c['bar']; ?> to-transparent rounded-t-xl"></div>
                </div>
                <?php endforeach; ?>
            </div>
        </div>
    </section>
    <?php endif; ?>

    <section class="py-6">
        <div class="max-w-5xl mx-auto px-6">
            <div class="hidden md:flex items-center gap-4 px-4 py-2.5 text-[11px] font-medium text-suno-muted uppercase tracking-wider border-b border-suno-border">
                <div class="w-10 text-center">#</div>
                <div class="flex-1">크리에이터</div>
                <div class="w-24 text-right"><?php echo $tab === 'total' ? '총 좋아요' : $tabList[$tab] . ' 좋아요'; ?></div>
                <?php if ($tab === 'total'): ?>
                <div class="w-56">
                    <div class="flex items-center justify-end gap-4">
                        <span class="w-16 text-right">게시판</span>
                        <span class="w-16 text-right">프롬프트</span>
                        <span class="w-16 text-right">음원</span>
                    </div>
                </div>
                <?php endif; ?>
            </div>

            <?php if (empty($users)): ?>
            <div class="py-16 text-center text-suno-muted text-sm">아직 랭킹 데이터가 없습니다.</div>
            <?php else: ?>
            <div class="divide-y divide-suno-border/50">
                <?php
                $maxLikes = 1;
                foreach ($users as $u) {
                    $val = $tab === 'board' ? ($u['board_likes'] ?? 0) : ($tab === 'prompt' ? ($u['prompt_likes'] ?? 0) : ($tab === 'music' ? ($u['music_likes'] ?? 0) : ($u['total_likes'] ?? 0)));
                    if ($val > $maxLikes) $maxLikes = $val;
                }
                foreach($users as $user):
                    $rank = $user['rank_position'];
                    $totalLikes = $user['total_likes'] ?? 0;
                    $boardLikes = $user['board_likes'] ?? 0;
                    $promptLikes = $user['prompt_likes'] ?? 0;
                    $musicLikes = $user['music_likes'] ?? 0;
                    $displayLikes = $tab === 'board' ? $boardLikes : ($tab === 'prompt' ? $promptLikes : ($tab === 'music' ? $musicLikes : $totalLikes));
                    $boardPct = $totalLikes > 0 ? round(($boardLikes / $totalLikes) * 100) : 0;
                    $promptPct = $totalLikes > 0 ? round(($promptLikes / $totalLikes) * 100) : 0;
                    $musicPct = max(0, 100 - $boardPct - $promptPct);
                    $avatarColor = $user['avatar_color'] ?: 'from-violet-500 to-purple-500';
                    $badge = $user['badge'] ?? '';
                ?>
                <a href="profile.php?id=<?php echo $user['user_id']; ?>" class="rank-row flex items-center gap-4 px-4 py-3.5 rounded-lg group">
                    <div class="w-10 text-center shrink-0">
                        <?php if($rank <= 3): ?>
                        <span class="inline-flex items-center justify-center w-7 h-7 rounded-full text-xs font-bold <?php echo $rank === 1 ? 'bg-amber-400/20 text-amber-400' : ($rank === 2 ? 'bg-gray-300/20 text-gray-300' : 'bg-amber-700/20 text-amber-600'); ?>">
                            <?php echo $rank; ?>
                        </span>
                        <?php else: ?>
                        <span class="text-sm text-suno-muted font-medium"><?php echo $rank; ?></span>
                        <?php endif; ?>
                    </div>

                    <div class="flex items-center gap-3 flex-1 min-w-0">
                        <div class="w-9 h-9 rounded-full bg-gradient-to-r <?php echo $avatarColor; ?> flex items-center justify-center text-xs font-bold shrink-0">
                            <?php echo mb_substr($user['nickname'], 0, 1); ?>
                        </div>
                        <div class="min-w-0">
                            <div class="flex items-center gap-2">
                                <span class="font-semibold text-sm truncate group-hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($user['nickname']); ?></span>
                                <?php if($badge === 'diamond'): ?>
                                <span class="text-[9px] px-1.5 py-px rounded bg-violet-500/10 text-violet-400 border border-violet-500/20 font-semibold shrink-0">Diamond</span>
                                <?php elseif($badge === 'gold'): ?>
                                <span class="text-[9px] px-1.5 py-px rounded bg-amber-500/10 text-amber-400 border border-amber-500/20 font-semibold shrink-0">Gold</span>
                                <?php elseif($badge === 'silver'): ?>
                                <span class="text-[9px] px-1.5 py-px rounded bg-gray-400/10 text-gray-400 border border-gray-400/20 font-semibold shrink-0">Silver</span>
                                <?php elseif($badge === 'bronze'): ?>
                                <span class="text-[9px] px-1.5 py-px rounded bg-amber-700/10 text-amber-600 border border-amber-700/20 font-semibold shrink-0">Bronze</span>
                                <?php endif; ?>
                            </div>
                        </div>
                    </div>

                    <div class="w-24 text-right shrink-0">
                        <span class="text-sm font-bold text-rose-400 flex items-center justify-end gap-1">
                            <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/></svg>
                            <?php echo number_format($displayLikes); ?>
                        </span>
                    </div>

                    <?php if ($tab === 'total'): ?>
                    <div class="hidden md:block w-56 shrink-0">
                        <div class="flex items-center justify-end gap-4">
                            <span class="w-16 text-right text-xs text-emerald-400/70"><?php echo number_format($boardLikes); ?></span>
                            <span class="w-16 text-right text-xs text-violet-400/70"><?php echo number_format($promptLikes); ?></span>
                            <span class="w-16 text-right text-xs text-rose-400/70"><?php echo number_format($musicLikes); ?></span>
                        </div>
                        <div class="flex mt-1.5 bg-suno-surface rounded-full overflow-hidden h-1.5">
                            <div class="bg-emerald-400/50" style="width:<?php echo $boardPct; ?>%"></div>
                            <div class="bg-violet-400/50" style="width:<?php echo $promptPct; ?>%"></div>
                            <div class="bg-rose-400/50" style="width:<?php echo $musicPct; ?>%"></div>
                        </div>
                    </div>
                    <?php endif; ?>
                </a>
                <?php endforeach; ?>
            </div>
            <?php endif; ?>

            <?php if ($tab === 'total'): ?>
            <div class="flex items-center justify-center gap-6 mt-6 pt-4 border-t border-suno-border">
                <div class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-emerald-400/60"></span><span class="text-[11px] text-suno-muted">게시판</span></div>
                <div class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-violet-400/60"></span><span class="text-[11px] text-suno-muted">프롬프트</span></div>
                <div class="flex items-center gap-1.5"><span class="w-2.5 h-2.5 rounded-full bg-rose-400/60"></span><span class="text-[11px] text-suno-muted">음원</span></div>
            </div>
            <?php endif; ?>

            <?php if ($totalPages > 1): ?>
            <div class="flex items-center justify-center gap-1.5 mt-8 mb-6">
                <?php if ($page > 1): ?>
                <a href="<?php echo $baseUrl; ?>&page=<?php echo $page - 1; ?>" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                </a>
                <?php else: ?>
                <button disabled class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted/30">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                </button>
                <?php endif; ?>

                <?php
                $startPage = max(1, $page - 2);
                $endPage = min($totalPages, $page + 2);
                if ($startPage > 1): ?>
                <a href="<?php echo $baseUrl; ?>&page=1" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors text-sm">1</a>
                <?php if ($startPage > 2): ?><span class="w-9 h-9 flex items-center justify-center text-suno-muted text-sm">...</span><?php endif; ?>
                <?php endif; ?>

                <?php for ($i = $startPage; $i <= $endPage; $i++): ?>
                <?php if ($i === $page): ?>
                <button class="w-9 h-9 flex items-center justify-center rounded-lg bg-suno-accent text-white text-sm font-medium"><?php echo $i; ?></button>
                <?php else: ?>
                <a href="<?php echo $baseUrl; ?>&page=<?php echo $i; ?>" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors text-sm"><?php echo $i; ?></a>
                <?php endif; ?>
                <?php endfor; ?>

                <?php if ($endPage < $totalPages): ?>
                <?php if ($endPage < $totalPages - 1): ?><span class="w-9 h-9 flex items-center justify-center text-suno-muted text-sm">...</span><?php endif; ?>
                <a href="<?php echo $baseUrl; ?>&page=<?php echo $totalPages; ?>" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors text-sm"><?php echo $totalPages; ?></a>
                <?php endif; ?>

                <?php if ($page < $totalPages): ?>
                <a href="<?php echo $baseUrl; ?>&page=<?php echo $page + 1; ?>" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </a>
                <?php else: ?>
                <button disabled class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted/30">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </button>
                <?php endif; ?>
            </div>
            <?php endif; ?>
        </div>
    </section>
</main>

<?php include 'footer.php'; ?>
