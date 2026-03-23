<?php require_once 'db.php'; ?>
<?php $pageTitle = '음원 공유'; ?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<?php
// Pagination
$page = isset($_GET['page']) ? max(1, intval($_GET['page'])) : 1;
$perPage = 12;
$offset = ($page - 1) * $perPage;

// Filter params
$sort = $_GET['sort'] ?? 'latest';
$genreFilter = $_GET['genre'] ?? '';
$searchQuery = trim($_GET['q'] ?? '');

// Build WHERE / ORDER BY
$whereParts = [];
$params = [];

if (!empty($searchQuery)) {
    $searchLike = '%' . $searchQuery . '%';
    $whereParts[] = '(tracks.title LIKE ? OR tracks.description LIKE ? OR users.nickname LIKE ? OR tracks.id IN (SELECT track_id FROM track_genres WHERE genre LIKE ?))';
    $params[] = $searchLike;
    $params[] = $searchLike;
    $params[] = $searchLike;
    $params[] = $searchLike;
}

if (!empty($genreFilter) && $genreFilter !== '전체') {
    $whereParts[] = 'tracks.id IN (SELECT track_id FROM track_genres WHERE genre = ?)';
    $params[] = $genreFilter;
    if (empty($searchQuery)) $sort = 'genre';
}

$whereClause = !empty($whereParts) ? 'WHERE ' . implode(' AND ', $whereParts) : '';

$orderBy = 'tracks.created_at DESC';
if ($sort === 'popular') {
    $orderBy = '(tracks.like_count * 3 + tracks.play_count) DESC, tracks.created_at DESC';
} elseif ($sort === 'latest') {
    $orderBy = 'tracks.created_at DESC';
}

// Total count
$countSql = "SELECT COUNT(*) FROM tracks JOIN users ON tracks.user_id = users.id {$whereClause}";
$totalStmt = $pdo->prepare($countSql);
$totalStmt->execute($params);
$totalTracks = (int)$totalStmt->fetchColumn();
$totalPages = max(1, ceil($totalTracks / $perPage));
if ($page > $totalPages) $page = $totalPages;

// Fetch tracks
$sql = "SELECT tracks.*, users.nickname as artist FROM tracks JOIN users ON tracks.user_id = users.id {$whereClause} ORDER BY {$orderBy} LIMIT :limit OFFSET :offset";
$stmt = $pdo->prepare($sql);
foreach ($params as $i => $p) {
    $stmt->bindValue($i + 1, $p, PDO::PARAM_STR);
}
$stmt->bindValue(':limit', $perPage, PDO::PARAM_INT);
$stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
$stmt->execute();
$tracks = $stmt->fetchAll();

// Add gradient + genre to each track
foreach ($tracks as &$track) {
    $gStmt = $pdo->prepare('SELECT genre FROM track_genres WHERE track_id = ? LIMIT 1');
    $gStmt->execute([$track['id']]);
    $track['genre'] = $gStmt->fetchColumn() ?: '';
    $track['gradient'] = getGradient($track['id'], $track['genre']);
}
unset($track);

// Fetch genres: 관리자 태그 + 실제 사용된 태그 병합
$dbGenres = [];
try {
    $__tt = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name='tag_options'")->fetchColumn();
    if ($__tt) {
        $dbGenres = $pdo->query("SELECT tag_name FROM tag_options WHERE tag_type='track_genre' AND is_active=1 ORDER BY sort_order, id")->fetchAll(PDO::FETCH_COLUMN);
    }
} catch (Exception $e) {}
// 실제 사용된 장르 중 관리자 목록에 없는 것도 추가
$usedGenres = $pdo->query('SELECT DISTINCT genre FROM track_genres ORDER BY genre')->fetchAll(PDO::FETCH_COLUMN);
foreach ($usedGenres as $ug) {
    if (!in_array($ug, $dbGenres)) $dbGenres[] = $ug;
}
$genres = array_merge(['전체'], $dbGenres);

$filterTabs = [
    ['label' => '전체', 'sort' => 'latest', 'active' => ($sort === 'latest' && empty($genreFilter))],
    ['label' => '인기순', 'sort' => 'popular', 'active' => ($sort === 'popular' && empty($genreFilter))],
    ['label' => '장르별', 'sort' => 'genre', 'active' => ($sort === 'genre' || !empty($genreFilter))],
];

// 페이지네이션에 필터 파라미터 유지용
$filterQuery = '';
if (!empty($searchQuery)) {
    $filterQuery .= '&q=' . urlencode($searchQuery);
}
if ($sort === 'popular') {
    $filterQuery .= '&sort=popular';
} elseif (!empty($genreFilter)) {
    $filterQuery .= '&sort=genre&genre=' . urlencode($genreFilter);
}
?>

<!-- Page Content -->
<main class="pt-20 min-h-screen">

    <!-- Page Header -->
    <section class="border-b border-suno-border bg-suno-surface/30">
        <div class="max-w-7xl mx-auto px-6 py-8">
            <div class="flex flex-col sm:flex-row items-start sm:items-center justify-between gap-4 mb-5">
                <div>
                    <div class="flex items-center gap-3 mb-1">
                        <div class="w-9 h-9 bg-suno-accent/10 border border-suno-accent/20 rounded-xl flex items-center justify-center">
                            <svg class="w-4.5 h-4.5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/>
                            </svg>
                        </div>
                        <h1 class="text-2xl font-extrabold">음원 공유</h1>
                    </div>
                    <p class="text-suno-muted text-sm ml-12">Suno AI로 만든 음악을 공유하고 다른 크리에이터의 작품을 감상하세요</p>
                </div>
                <a href="music_upload.php" class="inline-flex items-center gap-2 bg-suno-accent hover:bg-suno-accent2 text-white font-semibold px-5 py-2.5 rounded-xl transition-all text-sm shrink-0">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
                    내 음악 공유하기
                </a>
            </div>
            <!-- 검색바 -->
            <form action="music_list.php" method="GET">
                <?php if ($sort === 'popular'): ?><input type="hidden" name="sort" value="popular"><?php endif; ?>
                <?php if (!empty($genreFilter)): ?><input type="hidden" name="sort" value="genre"><input type="hidden" name="genre" value="<?php echo htmlspecialchars($genreFilter); ?>"><?php endif; ?>
                <div class="relative">
                    <svg class="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-suno-muted/40 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
                    <input type="text" name="q" value="<?php echo htmlspecialchars($searchQuery); ?>" placeholder="곡 제목, 아티스트, 설명, 장르로 검색..."
                        class="w-full bg-suno-dark/80 border border-suno-border rounded-xl pl-11 pr-10 py-3 text-sm text-white placeholder-suno-muted/40 focus:outline-none focus:border-suno-accent/50 transition-colors">
                    <?php if (!empty($searchQuery)): ?>
                    <a href="music_list.php<?php echo !empty($genreFilter) ? '?sort=genre&genre=' . urlencode($genreFilter) : ($sort === 'popular' ? '?sort=popular' : ''); ?>" class="absolute right-3 top-1/2 -translate-y-1/2 text-suno-muted hover:text-white transition-colors">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                    </a>
                    <?php endif; ?>
                </div>
            </form>
        </div>
    </section>

    <?php if (!empty($searchQuery)): ?>
    <section class="border-b border-suno-border bg-suno-accent/5">
        <div class="max-w-7xl mx-auto px-6 py-2.5">
            <div class="flex items-center gap-2 text-sm">
                <svg class="w-3.5 h-3.5 text-suno-accent shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
                <span class="text-suno-muted text-xs">"<span class="text-white font-medium"><?php echo htmlspecialchars($searchQuery); ?></span>" 검색 결과 <span class="text-suno-muted/50"><?php echo number_format($totalTracks); ?>개</span></span>
                <a href="music_list.php<?php echo !empty($genreFilter) ? '?sort=genre&genre=' . urlencode($genreFilter) : ($sort === 'popular' ? '?sort=popular' : ''); ?>" class="ml-auto text-xs text-suno-muted hover:text-white transition-colors flex items-center gap-1">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                    초기화
                </a>
            </div>
        </div>
    </section>
    <?php endif; ?>

    <!-- Filter Tabs + Genre -->
    <?php $searchParam = !empty($searchQuery) ? '&q=' . urlencode($searchQuery) : ''; ?>
    <section class="border-b border-suno-border bg-suno-dark sticky top-[57px] z-30">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex items-center gap-1 py-0">
                <?php foreach ($filterTabs as $tab):
                    $tabHref = 'music_list.php';
                    if ($tab['sort'] === 'popular') $tabHref .= '?sort=popular' . $searchParam;
                    elseif ($tab['sort'] === 'genre') $tabHref .= '?sort=genre' . $searchParam;
                    else $tabHref .= !empty($searchQuery) ? '?q=' . urlencode($searchQuery) : '';
                ?>
                <a href="<?php echo $tabHref; ?>"
                   class="text-sm font-medium px-4 py-3.5 whitespace-nowrap transition-colors border-b-2 <?php echo $tab['active'] ? 'border-suno-accent text-suno-accent' : 'border-transparent text-suno-muted hover:text-white'; ?>">
                    <?php echo htmlspecialchars($tab['label']); ?>
                </a>
                <?php endforeach; ?>
            </div>
        </div>
    </section>

    <section class="border-b border-suno-border bg-suno-surface/20">
        <div class="max-w-7xl mx-auto px-6 py-3">
            <div class="flex items-center gap-3">
                <div id="genreTagsWrap" class="flex-1 min-w-0 overflow-hidden">
                    <div id="genreTagsInner" class="flex flex-wrap gap-2 overflow-hidden transition-all duration-300" style="max-height:32px;">
                        <?php foreach ($genres as $genre):
                            $isActiveGenre = (!empty($genreFilter) && $genreFilter === $genre) || (empty($genreFilter) && $genre === '전체');
                            $genreHref = ($genre === '전체')
                                ? 'music_list.php?' . ($sort === 'popular' ? 'sort=popular' : 'sort=latest') . $searchParam
                                : 'music_list.php?genre=' . urlencode($genre) . $searchParam;
                        ?>
                        <a href="<?php echo $genreHref; ?>"
                           class="genre-tag border px-3.5 py-1 rounded-full text-xs whitespace-nowrap transition-colors <?php echo $isActiveGenre ? 'bg-suno-accent/20 border-suno-accent/40 text-suno-accent2' : 'border-suno-border bg-suno-card text-suno-muted hover:text-white hover:border-suno-accent/20'; ?>">
                            <?php echo htmlspecialchars($genre); ?>
                        </a>
                        <?php endforeach; ?>
                    </div>
                </div>
                <div class="flex items-center gap-1.5 shrink-0 self-start">
                    <button id="genreExpandBtn" onclick="toggleGenreExpand()" style="width:30px;height:30px;" class="rounded-lg border border-suno-border bg-suno-card hover:border-suno-accent/30 hover:bg-suno-accent/5 text-suno-muted hover:text-white flex items-center justify-center transition-all" title="태그 더보기">
                        <svg id="genreExpandIcon" class="w-3.5 h-3.5 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
                    </button>
                    <!-- Tag Search with Autocomplete (prompt_list.php 스타일) -->
                    <div class="relative hidden sm:block" id="musicTagSearchWrap">
                        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-suno-muted pointer-events-none z-10" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
                        <input type="text" id="musicTagSearchInput" placeholder="태그 검색..." autocomplete="off"
                            class="w-44 bg-suno-surface border border-suno-border rounded-lg pl-9 pr-8 py-1.5 text-xs text-white placeholder-suno-muted/60 focus:outline-none focus:border-suno-accent/50 transition-colors">
                        <?php if(!empty($genreFilter) && $genreFilter !== '전체'): ?>
                        <a href="music_list.php<?php echo $searchParam ? '?q=' . urlencode($searchQuery) : ''; ?>" class="absolute right-2.5 top-1/2 -translate-y-1/2 text-suno-muted hover:text-white transition-colors">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                        </a>
                        <?php endif; ?>
                        <div id="musicTagDropdown" class="hidden absolute top-full right-0 mt-1.5 w-72 bg-suno-card border border-suno-border rounded-xl shadow-2xl shadow-black/40 overflow-hidden z-50" style="animation: genreModalIn 0.15s ease-out;">
                            <div id="musicTagDropdownContent" class="max-h-72 overflow-y-auto scrollbar-hide"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Track Count Info -->
    <section class="py-4">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex items-center justify-between">
                <p class="text-sm text-suno-muted">총 <span class="text-white font-semibold"><?php echo number_format($totalTracks); ?></span>개의 음원</p>
                <div class="flex items-center gap-2">
                    <button id="gridViewBtn" onclick="setLayout('grid')" class="p-2 rounded-lg bg-suno-accent/10 border border-suno-accent/20 text-suno-accent" title="그리드 보기">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2V6zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2V6zM4 16a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2H6a2 2 0 01-2-2v-2zm10 0a2 2 0 012-2h2a2 2 0 012 2v2a2 2 0 01-2 2h-2a2 2 0 01-2-2v-2z"/>
                        </svg>
                    </button>
                    <button id="listViewBtn" onclick="setLayout('list')" class="p-2 rounded-lg hover:bg-white/5 text-suno-muted" title="리스트 보기">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 12h16M4 18h16"/>
                        </svg>
                    </button>
                </div>
            </div>
        </div>
    </section>

    <!-- Music Grid -->
    <section class="pb-16">
        <div class="max-w-7xl mx-auto px-6">
            <div id="trackContainer" class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-4 xl:grid-cols-6 gap-5">
                <?php foreach ($tracks as $track): ?>
                <a href="music_detail.php?id=<?php echo $track['id']; ?>" class="music-card group block">
                    <!-- Album Art -->
                    <div class="track-art relative aspect-square rounded-xl bg-gradient-to-br <?php echo $track['gradient']; ?> border border-suno-border overflow-hidden mb-3">
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
                        <div class="absolute top-2 left-2 bg-black/50 text-white/80 text-[10px] font-medium px-2 py-0.5 rounded-full">
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
                    <div class="track-info">
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
                    </div>
                </a>
                <?php endforeach; ?>
            </div>

            <!-- Pagination -->
            <?php if ($totalPages > 1): ?>
            <div class="flex items-center justify-center gap-2 mt-12">
                <?php if ($page > 1): ?>
                <a href="?page=<?php echo $page - 1 . $filterQuery; ?>" class="w-9 h-9 rounded-lg border border-suno-border bg-suno-card text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors flex items-center justify-center text-sm">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
                    </svg>
                </a>
                <?php else: ?>
                <button class="w-9 h-9 rounded-lg border border-suno-border bg-suno-card text-suno-muted flex items-center justify-center text-sm" disabled>
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
                    </svg>
                </button>
                <?php endif; ?>

                <?php
                // Determine page range to show
                $startPage = max(1, $page - 2);
                $endPage = min($totalPages, $page + 2);

                if ($startPage > 1): ?>
                    <a href="?page=1<?php echo $filterQuery; ?>" class="w-9 h-9 rounded-lg border border-suno-border bg-suno-card text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors flex items-center justify-center text-sm">1</a>
                    <?php if ($startPage > 2): ?>
                        <span class="text-suno-muted/50 px-1">...</span>
                    <?php endif; ?>
                <?php endif; ?>

                <?php for ($i = $startPage; $i <= $endPage; $i++): ?>
                    <?php if ($i === $page): ?>
                        <button class="w-9 h-9 rounded-lg bg-suno-accent text-white font-semibold text-sm flex items-center justify-center"><?php echo $i; ?></button>
                    <?php else: ?>
                        <a href="?page=<?php echo $i . $filterQuery; ?>" class="w-9 h-9 rounded-lg border border-suno-border bg-suno-card text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors flex items-center justify-center text-sm"><?php echo $i; ?></a>
                    <?php endif; ?>
                <?php endfor; ?>

                <?php if ($endPage < $totalPages): ?>
                    <?php if ($endPage < $totalPages - 1): ?>
                        <span class="text-suno-muted/50 px-1">...</span>
                    <?php endif; ?>
                    <a href="?page=<?php echo $totalPages . $filterQuery; ?>" class="w-9 h-9 rounded-lg border border-suno-border bg-suno-card text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors flex items-center justify-center text-sm"><?php echo $totalPages; ?></a>
                <?php endif; ?>

                <?php if ($page < $totalPages): ?>
                <a href="?page=<?php echo $page + 1 . $filterQuery; ?>" class="w-9 h-9 rounded-lg border border-suno-border bg-suno-card text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors flex items-center justify-center text-sm">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                    </svg>
                </a>
                <?php else: ?>
                <button class="w-9 h-9 rounded-lg border border-suno-border bg-suno-card text-suno-muted flex items-center justify-center text-sm" disabled>
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                    </svg>
                </button>
                <?php endif; ?>
            </div>
            <?php endif; ?>
        </div>
    </section>

</main>

<style>
@keyframes genreModalIn {
    from { opacity: 0; transform: translate(-50%, -50%) scale(0.95); }
    to { opacity: 1; transform: translate(-50%, -50%) scale(1); }
}
/* 리스트 뷰 스타일 */
#trackContainer.list-view {
    display: flex !important;
    flex-direction: column;
    gap: 0.5rem;
}
#trackContainer.list-view .music-card {
    display: flex;
    align-items: center;
    gap: 1rem;
    padding: 0.75rem;
    border-radius: 0.75rem;
    border: 1px solid rgba(255,255,255,0.06);
    background: rgba(255,255,255,0.02);
    transition: background 0.15s;
}
#trackContainer.list-view .music-card:hover {
    background: rgba(255,255,255,0.05);
}
#trackContainer.list-view .track-art {
    width: 56px;
    height: 56px;
    min-width: 56px;
    aspect-ratio: 1;
    margin-bottom: 0;
    border-radius: 0.5rem;
}
#trackContainer.list-view .track-art .play-overlay {
    opacity: 0;
}
#trackContainer.list-view .music-card:hover .track-art .play-overlay {
    opacity: 1;
}
#trackContainer.list-view .track-art .play-overlay > div {
    width: 2rem;
    height: 2rem;
}
#trackContainer.list-view .track-art .play-overlay > div svg {
    width: 0.875rem;
    height: 0.875rem;
}
#trackContainer.list-view .track-info {
    flex: 1;
    min-width: 0;
}
</style>
<script>
function setLayout(mode) {
    const container = document.getElementById('trackContainer');
    const gridBtn = document.getElementById('gridViewBtn');
    const listBtn = document.getElementById('listViewBtn');

    if (mode === 'list') {
        container.className = 'list-view';
        gridBtn.className = 'p-2 rounded-lg hover:bg-white/5 text-suno-muted';
        listBtn.className = 'p-2 rounded-lg bg-suno-accent/10 border border-suno-accent/20 text-suno-accent';
    } else {
        container.className = 'grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 lg:grid-cols-4 xl:grid-cols-6 gap-5';
        gridBtn.className = 'p-2 rounded-lg bg-suno-accent/10 border border-suno-accent/20 text-suno-accent';
        listBtn.className = 'p-2 rounded-lg hover:bg-white/5 text-suno-muted';
    }
    localStorage.setItem('music_layout', mode);
}

// 저장된 레이아웃 복원
document.addEventListener('DOMContentLoaded', function() {
    const saved = localStorage.getItem('music_layout');
    if (saved === 'list') setLayout('list');
});

// ── 장르 태그 펼치기/접기 ──
let genreExpanded = false;
function toggleGenreExpand() {
    const inner = document.getElementById('genreTagsInner');
    const icon = document.getElementById('genreExpandIcon');
    if (!inner) return;
    genreExpanded = !genreExpanded;
    if (genreExpanded) {
        inner.style.maxHeight = inner.scrollHeight + 'px';
        icon.style.transform = 'rotate(180deg)';
    } else {
        inner.style.maxHeight = '32px';
        icon.style.transform = 'rotate(0deg)';
    }
}

// ── 장르 태그 검색 (autocomplete dropdown) ──
(function() {
    const input = document.getElementById('musicTagSearchInput');
    const dropdown = document.getElementById('musicTagDropdown');
    const content = document.getElementById('musicTagDropdownContent');
    const wrap = document.getElementById('musicTagSearchWrap');
    if (!input || !dropdown || !content) return;

    const allGenres = <?php echo json_encode(array_values($dbGenres)); ?>;
    const currentGenre = <?php echo json_encode($genreFilter); ?>;
    const searchParamStr = <?php echo json_encode($searchParam); ?>;

    let isOpen = false;
    function openDD() { dropdown.classList.remove('hidden'); isOpen = true; }
    function closeDD() { dropdown.classList.add('hidden'); isOpen = false; }

    function escHtml(str) {
        const d = document.createElement('div'); d.textContent = str; return d.innerHTML;
    }

    function buildGenreHref(genre) {
        if (genre === '전체') return 'music_list.php' + (searchParamStr ? '?' + searchParamStr.substring(1) : '');
        return 'music_list.php?genre=' + encodeURIComponent(genre) + searchParamStr;
    }

    function renderAll(query) {
        query = (query || '').toLowerCase();
        const filtered = query ? allGenres.filter(g => g.toLowerCase().includes(query)) : allGenres;

        if (filtered.length === 0 && query) {
            content.innerHTML = '<div class="p-4 text-xs text-suno-muted text-center">검색 결과가 없습니다</div>';
            openDD();
            return;
        }

        let html = '';
        if (!query) {
            html += '<div class="px-3 pt-3 pb-2 flex flex-wrap gap-1.5">';
            allGenres.forEach(g => {
                const isActive = g === currentGenre;
                html += '<a href="' + buildGenreHref(g) + '" class="inline-block px-2.5 py-1 rounded-md text-[11px] font-medium border transition-all cursor-pointer '
                    + (isActive ? 'bg-suno-accent/20 border-suno-accent/40 text-suno-accent2' : 'bg-suno-surface border-suno-border/60 text-suno-muted hover:bg-suno-accent/15 hover:text-suno-accent2 hover:border-suno-accent/30')
                    + '">' + escHtml(g) + '</a>';
            });
            html += '</div>';
        } else {
            html += '<div class="py-1">';
            filtered.forEach(g => {
                const isActive = g === currentGenre;
                const idx = g.toLowerCase().indexOf(query);
                let highlighted = escHtml(g);
                if (idx >= 0) {
                    highlighted = escHtml(g.substring(0, idx))
                        + '<span class="text-suno-accent font-semibold">' + escHtml(g.substring(idx, idx + query.length)) + '</span>'
                        + escHtml(g.substring(idx + query.length));
                }
                html += '<a href="' + buildGenreHref(g) + '" class="flex items-center gap-3 px-4 py-2 hover:bg-suno-surface/60 transition-colors cursor-pointer">'
                    + '<span class="text-xs text-white flex-1">' + highlighted + '</span>'
                    + (isActive ? '<svg class="w-3.5 h-3.5 text-suno-accent shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>' : '')
                    + '</a>';
            });
            html += '</div>';
        }
        content.innerHTML = html;
        openDD();
    }

    let debounceTimer = null;
    input.addEventListener('focus', function() { renderAll(input.value.trim()); });
    input.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(() => renderAll(input.value.trim()), 150);
    });
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            const val = input.value.trim();
            if (val) {
                const match = allGenres.find(g => g.toLowerCase() === val.toLowerCase());
                if (match) window.location.href = buildGenreHref(match);
            }
        }
        if (e.key === 'Escape') { closeDD(); input.blur(); }
    });
    document.addEventListener('click', function(e) {
        if (!wrap.contains(e.target)) closeDD();
    });
})();
</script>

<?php include 'footer.php'; ?>
