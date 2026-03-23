<?php require_once 'db.php'; ?>
<?php $pageTitle = '인기 음원'; ?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<?php
// 기간 필터
$period = isset($_GET['period']) ? $_GET['period'] : 'weekly';
$periodLabel = ['weekly' => '주간', 'monthly' => '월간', 'all' => '전체'];
if (!isset($periodLabel[$period])) $period = 'weekly';

// 기간 조건
$dateCondition = '';
if ($period === 'weekly') {
    $dateCondition = 'WHERE t.created_at >= datetime("now", "-7 days")';
} elseif ($period === 'monthly') {
    $dateCondition = 'WHERE t.created_at >= datetime("now", "-30 days")';
}

// Pagination
$page = isset($_GET['page']) ? max(1, intval($_GET['page'])) : 1;
$perPage = 12;
$offset = ($page - 1) * $perPage;

// Total count
$countQuery = "SELECT COUNT(*) FROM tracks t {$dateCondition}";
$totalStmt = $pdo->query($countQuery);
$totalTracks = (int)$totalStmt->fetchColumn();

// 기간 내 트랙이 부족하면 전체로 fallback
if ($totalTracks < 1 && $period !== 'all') {
    $dateCondition = '';
    $totalStmt = $pdo->query("SELECT COUNT(*) FROM tracks t");
    $totalTracks = (int)$totalStmt->fetchColumn();
}

$totalPages = max(1, ceil($totalTracks / $perPage));
if ($page > $totalPages) $page = $totalPages;

// Fetch tracks (인기순: like_count * 3 + play_count)
$stmt = $pdo->prepare("
    SELECT t.*, u.nickname as artist
    FROM tracks t
    JOIN users u ON t.user_id = u.id
    {$dateCondition}
    ORDER BY (t.like_count * 3 + t.play_count) DESC, t.created_at DESC
    LIMIT :limit OFFSET :offset
");
$stmt->bindValue(':limit', $perPage, PDO::PARAM_INT);
$stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
$stmt->execute();
$tracks = $stmt->fetchAll();

// Add gradient + genre
foreach ($tracks as &$track) {
    $gStmt = $pdo->prepare('SELECT genre FROM track_genres WHERE track_id = ? LIMIT 1');
    $gStmt->execute([$track['id']]);
    $track['genre'] = $gStmt->fetchColumn() ?: '';
    $track['gradient'] = getGradient($track['id'], $track['genre']);
}
unset($track);
?>

<main class="pt-20 min-h-screen">

    <!-- Page Header -->
    <section class="py-10 border-b border-suno-border bg-suno-surface/30">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4">
                <div>
                    <div class="flex items-center gap-3 mb-2">
                        <div class="w-10 h-10 bg-orange-500/10 border border-orange-500/20 rounded-xl flex items-center justify-center">
                            <span class="text-lg">🔥</span>
                        </div>
                        <h1 class="text-2xl lg:text-3xl font-extrabold">인기 음원</h1>
                    </div>
                    <p class="text-suno-muted text-sm">좋아요와 재생수 기반 인기 음원 차트</p>
                </div>
                <a href="music_list.php" class="inline-flex items-center gap-2 border border-suno-border hover:border-suno-accent/40 bg-suno-card text-white font-medium px-5 py-2.5 rounded-xl transition-all text-sm shrink-0">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/>
                    </svg>
                    전체 음원
                </a>
            </div>
        </div>
    </section>

    <!-- Period Tabs -->
    <section class="border-b border-suno-border bg-suno-dark sticky top-[57px] z-30">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex items-center gap-1 py-0">
                <?php foreach ($periodLabel as $key => $label): ?>
                <a href="popular_tracks.php?period=<?php echo $key; ?>"
                   class="text-sm font-medium px-4 py-3.5 whitespace-nowrap transition-colors <?php echo $period === $key ? 'tab-active text-suno-accent font-semibold' : 'text-suno-muted hover:text-white'; ?>">
                    <?php echo $label; ?>
                </a>
                <?php endforeach; ?>
            </div>
        </div>
    </section>

    <!-- Track Count -->
    <section class="py-4">
        <div class="max-w-7xl mx-auto px-6">
            <p class="text-sm text-suno-muted"><?php echo $periodLabel[$period]; ?> 인기 음원 <span class="text-white font-semibold"><?php echo number_format($totalTracks); ?></span>개</p>
        </div>
    </section>

    <!-- Music Grid -->
    <section class="pb-16">
        <div class="max-w-7xl mx-auto px-6">
            <?php if (empty($tracks)): ?>
            <div class="py-20 text-center">
                <p class="text-suno-muted">등록된 음원이 없습니다.</p>
            </div>
            <?php else: ?>
            <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-4 xl:grid-cols-6 gap-5">
                <?php foreach ($tracks as $idx => $track): ?>
                <a href="music_detail.php?id=<?php echo $track['id']; ?>" class="music-card group block relative">
                    <!-- Rank Badge -->
                    <?php $rank = $offset + $idx + 1; ?>
                    <?php if ($rank <= 3): ?>
                    <div class="absolute top-2 left-2 z-10 w-7 h-7 rounded-full <?php echo $rank === 1 ? 'bg-yellow-500' : ($rank === 2 ? 'bg-gray-400' : 'bg-amber-700'); ?> flex items-center justify-center text-xs font-bold text-white shadow-lg">
                        <?php echo $rank; ?>
                    </div>
                    <?php elseif ($rank <= 10): ?>
                    <div class="absolute top-2 left-2 z-10 w-7 h-7 rounded-full bg-suno-surface/90 border border-suno-border flex items-center justify-center text-xs font-bold text-white">
                        <?php echo $rank; ?>
                    </div>
                    <?php endif; ?>

                    <!-- Album Art -->
                    <div class="relative aspect-square rounded-xl bg-gradient-to-br <?php echo $track['gradient']; ?> border border-suno-border overflow-hidden mb-3">
                        <?php if (!empty($track['cover_image_path'])): ?>
                        <img src="<?php echo htmlspecialchars($track['cover_image_path']); ?>" alt="" class="absolute inset-0 w-full h-full object-cover">
                        <?php else: ?>
                        <div class="absolute inset-0 flex items-center justify-center">
                            <svg class="w-10 h-10 text-white/15" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/>
                            </svg>
                        </div>
                        <?php endif; ?>
                        <?php if (!empty($track['duration'])): ?>
                        <div class="absolute bottom-2 right-2 bg-black/60 text-white text-[10px] font-medium px-1.5 py-0.5 rounded">
                            <?php echo htmlspecialchars($track['duration']); ?>
                        </div>
                        <?php endif; ?>
                        <?php if (!empty($track['genre'])): ?>
                        <div class="absolute top-2 right-2 bg-black/50 text-white/80 text-[10px] font-medium px-2 py-0.5 rounded-full">
                            <?php echo htmlspecialchars($track['genre']); ?>
                        </div>
                        <?php endif; ?>
                        <div class="play-overlay absolute inset-0 bg-black/40 flex items-center justify-center">
                            <div class="w-12 h-12 bg-suno-accent rounded-full flex items-center justify-center shadow-lg shadow-suno-accent/30 transform group-hover:scale-100 scale-90 transition-transform">
                                <svg class="w-5 h-5 text-white ml-0.5" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>
                                </svg>
                            </div>
                        </div>
                    </div>
                    <!-- Track Info -->
                    <h3 class="font-semibold text-sm truncate group-hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($track['title']); ?></h3>
                    <p class="text-suno-muted text-xs mt-0.5 truncate"><?php echo htmlspecialchars($track['artist']); ?></p>
                    <div class="flex items-center gap-3 mt-1.5 text-[11px] text-suno-muted/60">
                        <span class="flex items-center gap-1">
                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>
                            </svg>
                            <?php echo number_format($track['play_count']); ?>
                        </span>
                        <span class="flex items-center gap-1">
                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/>
                            </svg>
                            <?php echo number_format($track['like_count']); ?>
                        </span>
                    </div>
                </a>
                <?php endforeach; ?>
            </div>

            <!-- Pagination -->
            <?php if ($totalPages > 1): ?>
            <div class="flex items-center justify-center gap-1 mt-12">
                <?php if ($page > 1): ?>
                <a href="popular_tracks.php?period=<?php echo $period; ?>&page=<?php echo $page - 1; ?>" class="w-8 h-8 rounded-lg border border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/50 transition-all text-xs flex items-center justify-center">&#9664;</a>
                <?php endif; ?>

                <?php
                $startPage = max(1, $page - 4);
                $endPage = min($totalPages, $startPage + 9);
                if ($endPage - $startPage < 9) $startPage = max(1, $endPage - 9);
                for ($i = $startPage; $i <= $endPage; $i++):
                ?>
                <a href="popular_tracks.php?period=<?php echo $period; ?>&page=<?php echo $i; ?>"
                   class="w-8 h-8 rounded-lg <?php echo $i === $page ? 'bg-suno-accent text-white font-bold' : 'border border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/50 transition-all'; ?> text-xs flex items-center justify-center"><?php echo $i; ?></a>
                <?php endfor; ?>

                <?php if ($page < $totalPages): ?>
                <a href="popular_tracks.php?period=<?php echo $period; ?>&page=<?php echo $page + 1; ?>" class="w-8 h-8 rounded-lg border border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/50 transition-all text-xs flex items-center justify-center">&#9654;</a>
                <?php endif; ?>
            </div>
            <?php endif; ?>
            <?php endif; ?>
        </div>
    </section>
</main>

<?php include 'footer.php'; ?>
