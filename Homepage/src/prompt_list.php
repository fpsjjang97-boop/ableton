<?php require_once 'db.php'; ?>
<?php $pageTitle = '프롬프트 공유'; ?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<style>
    .prompt-card {
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .prompt-card:hover {
        transform: translateY(-4px);
        box-shadow: 0 12px 40px rgba(139,92,246,0.15);
        border-color: rgba(139,92,246,0.3);
    }
    .prompt-card:hover .card-title {
        color: #a78bfa;
    }
    .genre-chip {
        transition: all 0.2s ease;
    }
    .genre-chip:hover, .genre-chip.active {
        background: rgba(139,92,246,0.2);
        border-color: #8b5cf6;
        color: #a78bfa;
    }
    .page-btn {
        transition: all 0.2s ease;
    }
    .page-btn:hover {
        background: rgba(139,92,246,0.15);
        border-color: rgba(139,92,246,0.4);
        color: #a78bfa;
    }
    .page-btn.active {
        background: #8b5cf6;
        border-color: #8b5cf6;
        color: #fff;
    }
    .audio-play-btn {
        transition: all 0.2s;
    }
    .audio-play-btn:hover {
        background: #8b5cf6 !important;
        transform: scale(1.1);
    }
    /* Scrollbar hide */
    .scrollbar-hide::-webkit-scrollbar { display: none; }
    .scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
    /* Tag dropdown animation */
    #tagDropdown {
        animation: tagDropIn 0.15s ease-out;
    }
    @keyframes tagDropIn {
        from { opacity: 0; transform: translateY(-4px); }
        to { opacity: 1; transform: translateY(0); }
    }
</style>

<?php
// Pagination & filters
$perPage = 9;
$page = isset($_GET['page']) ? max(1, intval($_GET['page'])) : 1;
$activeGenre = isset($_GET['genre']) ? trim($_GET['genre']) : '전체';
$searchTag = isset($_GET['tag']) ? trim($_GET['tag']) : '';
$searchQuery = trim($_GET['q'] ?? '');
$sortMode = isset($_GET['sort']) ? trim($_GET['sort']) : 'latest';
if (!in_array($sortMode, ['latest', 'popular', 'copies'])) $sortMode = 'latest';
$offset = ($page - 1) * $perPage;

// Build WHERE conditions
$whereParts = [];
$params = [];
$paramIdx = 0;

if (!empty($searchQuery)) {
    $searchLike = '%' . $searchQuery . '%';
    $whereParts[] = '(prompts.title LIKE :sq1 OR prompts.prompt_text LIKE :sq2 OR prompts.description LIKE :sq3 OR users.nickname LIKE :sq4 OR prompts.id IN (SELECT prompt_id FROM prompt_genres WHERE genre LIKE :sq5))';
    $params[':sq1'] = $searchLike;
    $params[':sq2'] = $searchLike;
    $params[':sq3'] = $searchLike;
    $params[':sq4'] = $searchLike;
    $params[':sq5'] = $searchLike;
}

if ($activeGenre !== '' && $activeGenre !== '전체') {
    $whereParts[] = 'prompts.id IN (SELECT prompt_id FROM prompt_genres WHERE genre = :genre)';
    $params[':genre'] = $activeGenre;
} elseif ($searchTag !== '') {
    $whereParts[] = '(prompts.id IN (SELECT prompt_id FROM prompt_genres WHERE genre LIKE :tag) OR prompts.id IN (SELECT prompt_id FROM prompt_styles WHERE style LIKE :tag2))';
    $params[':tag'] = '%' . $searchTag . '%';
    $params[':tag2'] = '%' . $searchTag . '%';
}

$where = !empty($whereParts) ? ' WHERE ' . implode(' AND ', $whereParts) : '';

// Total count
$countSql = 'SELECT COUNT(*) FROM prompts JOIN users ON prompts.user_id = users.id' . $where;
$totalStmt = $pdo->prepare($countSql);
foreach ($params as $k => $v) { $totalStmt->bindValue($k, $v); }
$totalStmt->execute();
$totalCount = $totalStmt->fetchColumn();
$totalPages = max(1, ceil($totalCount / $perPage));
if ($page > $totalPages) $page = $totalPages;
$offset = ($page - 1) * $perPage;

// Fetch prompts with user info
$orderClause = 'prompts.created_at DESC';
if ($sortMode === 'popular') $orderClause = 'prompts.like_count DESC, prompts.created_at DESC';
elseif ($sortMode === 'copies') $orderClause = 'prompts.copy_count DESC, prompts.created_at DESC';

$sql = 'SELECT prompts.*, users.nickname as author, users.avatar_color
    FROM prompts
    JOIN users ON prompts.user_id = users.id'
    . $where .
    ' ORDER BY ' . $orderClause . '
    LIMIT :limit OFFSET :offset';
$stmt = $pdo->prepare($sql);
foreach ($params as $k => $v) { $stmt->bindValue($k, $v); }
$stmt->bindValue(':limit', $perPage, PDO::PARAM_INT);
$stmt->bindValue(':offset', $offset, PDO::PARAM_INT);
$stmt->execute();
$promptRows = $stmt->fetchAll();

// DB에서 읽은 장르/태그 문자열이 JSON 배열 형태면 풀어서 일반 문자열 배열로 만듦
function normalizeTagList(array $list) {
    $out = [];
    foreach ($list as $item) {
        $item = trim((string)$item);
        if ($item === '') continue;
        if (strpos($item, '[') === 0 && ($dec = json_decode($item)) && is_array($dec)) {
            foreach ($dec as $t) {
                $t = trim((string)$t);
                if ($t !== '') $out[] = $t;
            }
        } else {
            $out[] = $item;
        }
    }
    return $out;
}

// Build prompts array with genres and track info
$prompts = [];
foreach ($promptRows as $row) {
    // Get genres for this prompt
    $gStmt = $pdo->prepare('SELECT genre FROM prompt_genres WHERE prompt_id = ?');
    $gStmt->execute([$row['id']]);
    $genresArr = normalizeTagList($gStmt->fetchAll(PDO::FETCH_COLUMN));

    $has_track = !empty($row['linked_track_id']);
    $track_title = '';
    $track_duration = '';
    $track_has_audio = false;
    $track_audio_path = '';
    $track_has_suno = false;
    $track_suno_link = '';

    if ($has_track) {
        $tStmt = $pdo->prepare('SELECT title, duration, has_audio_file, audio_file_path, suno_link FROM tracks WHERE id = ?');
        $tStmt->execute([$row['linked_track_id']]);
        $track = $tStmt->fetch();
        if ($track) {
            $track_title = $track['title'];
            $track_duration = $track['duration'] ?: '';
            $track_has_audio = !empty($track['has_audio_file']);
            $track_audio_path = $track['audio_file_path'] ?: '';
            $track_has_suno = !empty($track['suno_link']);
            $track_suno_link = $track['suno_link'] ?: '';
        } else {
            $has_track = false;
        }
    }

    $has_sample = $useSampleSound && !empty($row['sample_file_path']);

    $prompts[] = [
        'id' => $row['id'],
        'title' => $row['title'],
        'genres' => $genresArr,
        'preview' => $row['prompt_text'],
        'author' => $row['author'],
        'avatar_color' => $row['avatar_color'] ?: 'from-violet-500 to-purple-600',
        'likes' => $row['like_count'],
        'copies' => $row['copy_count'],
        'time' => timeAgo($row['created_at']),
        'has_track' => $has_track,
        'track_title' => $track_title,
        'track_duration' => $track_duration,
        'track_has_audio' => $track_has_audio,
        'track_audio_path' => $track_audio_path,
        'track_has_suno' => $track_has_suno,
        'track_suno_link' => $track_suno_link,
        'has_sample' => $has_sample,
    ];
}

// Get genres: 관리자 태그 + 실제 사용된 태그 병합
$dbGenres = [];
try {
    $__tt = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name='tag_options'")->fetchColumn();
    if ($__tt) {
        $dbGenres = $pdo->query("SELECT tag_name FROM tag_options WHERE tag_type='prompt_genre' AND is_active=1 ORDER BY sort_order, id")->fetchAll(PDO::FETCH_COLUMN);
    }
} catch (Exception $e) {}
$usedGenres = $pdo->query('SELECT DISTINCT genre FROM prompt_genres ORDER BY genre')->fetchAll(PDO::FETCH_COLUMN);
foreach ($usedGenres as $ug) {
    if (!in_array($ug, $dbGenres)) $dbGenres[] = $ug;
}
$genres = array_merge(['전체'], $dbGenres);
?>

<!-- Main Content -->
<main class="pt-20">
    <?php
    // 검색/필터 파라미터 유지용
    $promptSearchParam = '';
    if (!empty($searchQuery)) $promptSearchParam .= '&q=' . urlencode($searchQuery);
    if ($sortMode !== 'latest') $promptSearchParam .= '&sort=' . urlencode($sortMode);
    ?>

    <!-- Page Header -->
    <section class="border-b border-suno-border bg-suno-surface/30">
        <div class="max-w-7xl mx-auto px-6 py-8">
            <div class="flex flex-col md:flex-row md:items-center md:justify-between gap-4 mb-5">
                <div>
                    <div class="flex items-center gap-2 mb-1">
                        <svg class="w-5 h-5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"/>
                        </svg>
                        <h1 class="text-2xl font-extrabold tracking-tight">프롬프트 공유</h1>
                    </div>
                    <p class="text-suno-muted text-sm ml-7">프롬프트와 사운드 샘플을 함께 공유하세요</p>
                </div>
                <a href="prompt_write.php" class="inline-flex items-center gap-2 bg-suno-accent hover:bg-suno-accent2 text-white font-semibold px-6 py-2.5 rounded-xl transition-all text-sm shrink-0">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
                    프롬프트 공유하기
                </a>
            </div>
            <!-- 프롬프트 검색바 -->
            <form action="prompt_list.php" method="GET">
                <?php if ($activeGenre !== '전체'): ?><input type="hidden" name="genre" value="<?php echo htmlspecialchars($activeGenre); ?>"><?php endif; ?>
                <?php if (!empty($searchTag)): ?><input type="hidden" name="tag" value="<?php echo htmlspecialchars($searchTag); ?>"><?php endif; ?>
                <div class="relative">
                    <svg class="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-suno-muted/40 pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
                    <input type="text" name="q" value="<?php echo htmlspecialchars($searchQuery); ?>" placeholder="프롬프트 제목, 내용, 작성자, 장르로 검색..."
                        class="w-full bg-suno-dark/80 border border-suno-border rounded-xl pl-11 pr-10 py-3 text-sm text-white placeholder-suno-muted/40 focus:outline-none focus:border-suno-accent/50 transition-colors">
                    <?php if (!empty($searchQuery)): ?>
                    <a href="prompt_list.php<?php echo ($activeGenre !== '전체') ? '?genre=' . urlencode($activeGenre) : (!empty($searchTag) ? '?tag=' . urlencode($searchTag) : ''); ?>" class="absolute right-3 top-1/2 -translate-y-1/2 text-suno-muted hover:text-white transition-colors">
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
                <span class="text-suno-muted text-xs">"<span class="text-white font-medium"><?php echo htmlspecialchars($searchQuery); ?></span>" 검색 결과 <span class="text-suno-muted/50"><?php echo number_format($totalCount); ?>개</span></span>
                <a href="prompt_list.php<?php echo ($activeGenre !== '전체') ? '?genre=' . urlencode($activeGenre) : (!empty($searchTag) ? '?tag=' . urlencode($searchTag) : ''); ?>" class="ml-auto text-xs text-suno-muted hover:text-white transition-colors flex items-center gap-1">
                    <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                    초기화
                </a>
            </div>
        </div>
    </section>
    <?php endif; ?>

    <!-- Tag Filter -->
    <section class="border-b border-suno-border bg-suno-surface/20">
        <div class="max-w-7xl mx-auto px-6 py-3">
            <div class="flex items-center gap-3">
                <div id="promptTagsWrap" class="flex-1 min-w-0 overflow-hidden">
                    <div id="promptTagsInner" class="flex flex-wrap gap-2 overflow-hidden transition-all duration-300" style="max-height:32px;">
                        <?php foreach($genres as $idx => $genre): ?>
                        <a href="?genre=<?php echo urlencode($genre); ?><?php echo $promptSearchParam; ?>"
                           class="genre-chip border px-3.5 py-1 rounded-full text-xs whitespace-nowrap transition-colors <?php echo ($genre === $activeGenre || ($activeGenre === '전체' && $idx === 0 && $searchTag === '')) ? 'bg-suno-accent/20 border-suno-accent/40 text-suno-accent2' : 'border-suno-border bg-suno-card text-suno-muted hover:text-white hover:border-suno-accent/20'; ?>">
                            <?php echo htmlspecialchars($genre); ?>
                        </a>
                        <?php endforeach; ?>
                    </div>
                </div>
                <div class="flex items-center gap-1.5 shrink-0 self-start">
                    <button id="promptTagExpandBtn" onclick="togglePromptTagExpand()" style="width:30px;height:30px;" class="rounded-lg border border-suno-border bg-suno-card hover:border-suno-accent/30 hover:bg-suno-accent/5 text-suno-muted hover:text-white flex items-center justify-center transition-all" title="태그 더보기">
                        <svg id="promptTagExpandIcon" class="w-3.5 h-3.5 transition-transform duration-200" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
                    </button>
                    <!-- Tag Search with Autocomplete -->
                    <div class="relative hidden sm:block" id="tagSearchWrap">
                        <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-suno-muted pointer-events-none z-10" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                        </svg>
                        <input type="text" id="tagSearchInput" placeholder="태그 검색..." autocomplete="off"
                               value="<?php echo htmlspecialchars($searchTag); ?>"
                               class="w-44 bg-suno-surface border border-suno-border rounded-lg pl-9 pr-8 py-1.5 text-xs text-white placeholder-suno-muted/60 focus:outline-none focus:border-suno-accent/50 transition-colors">
                        <?php if($searchTag !== ''): ?>
                        <a href="?genre=전체" class="absolute right-2.5 top-1/2 -translate-y-1/2 text-suno-muted hover:text-white transition-colors">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                        </a>
                        <?php endif; ?>
                        <!-- Autocomplete Dropdown -->
                        <div id="tagDropdown" class="hidden absolute top-full right-0 mt-1.5 w-80 bg-suno-card border border-suno-border rounded-xl shadow-2xl shadow-black/40 overflow-hidden z-50">
                            <div id="tagDropdownContent" class="max-h-80 overflow-y-auto scrollbar-hide"></div>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <?php if($searchTag !== ''): ?>
    <div class="max-w-7xl mx-auto px-6 pt-4">
        <div class="flex items-center gap-2 text-sm">
            <span class="text-suno-muted">태그 검색:</span>
            <span class="inline-flex items-center gap-1.5 bg-suno-accent/10 text-suno-accent2 border border-suno-accent/20 px-3 py-1 rounded-full text-xs font-medium">
                <?php echo htmlspecialchars($searchTag); ?>
                <a href="?genre=전체" class="hover:text-white transition-colors"><svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg></a>
            </span>
        </div>
    </div>
    <?php endif; ?>

    <!-- Prompt Cards Grid -->
    <section class="py-10">
        <div class="max-w-7xl mx-auto px-6">
            <?php
            // Build query string for pagination links
            $filterParams = [];
            if ($activeGenre !== '' && $activeGenre !== '전체') $filterParams['genre'] = $activeGenre;
            if ($searchTag !== '') $filterParams['tag'] = $searchTag;
            if (!empty($searchQuery)) $filterParams['q'] = $searchQuery;
            if ($sortMode !== 'latest') $filterParams['sort'] = $sortMode;
            function pageUrl($pg, $filterParams) {
                $p = array_merge($filterParams, ['page' => $pg]);
                return '?' . http_build_query($p);
            }
            ?>

            <!-- Results count + Sort -->
            <div class="flex items-center justify-between mb-6">
                <div class="flex items-center gap-4">
                    <p class="text-sm text-suno-muted">총 <span class="text-white font-semibold"><?php echo $totalCount; ?></span>개</p>
                </div>
                <select onchange="window.location.href=this.value" class="bg-suno-surface border border-suno-border rounded-lg px-3 py-[7px] text-xs text-white/70 focus:outline-none focus:border-suno-accent/40 appearance-none bg-[url('data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2210%22%20height%3D%226%22%20viewBox%3D%220%200%2010%206%22%3E%3Cpath%20d%3D%22M1%201l4%204%204-4%22%20stroke%3D%22%2371717a%22%20stroke-width%3D%221.5%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%2F%3E%3C%2Fsvg%3E')] bg-no-repeat bg-[right_8px_center] pr-6 cursor-pointer">
                    <?php
                    $sortBaseUrl = 'prompt_list.php?';
                    $sortUrlParams = [];
                    if ($activeGenre !== '전체') $sortUrlParams['genre'] = $activeGenre;
                    if ($searchTag !== '') $sortUrlParams['tag'] = $searchTag;
                    if (!empty($searchQuery)) $sortUrlParams['q'] = $searchQuery;
                    ?>
                    <option value="<?php echo $sortBaseUrl . http_build_query(array_merge($sortUrlParams, ['sort' => 'latest'])); ?>" <?php echo $sortMode === 'latest' ? 'selected' : ''; ?>>최신순</option>
                    <option value="<?php echo $sortBaseUrl . http_build_query(array_merge($sortUrlParams, ['sort' => 'popular'])); ?>" <?php echo $sortMode === 'popular' ? 'selected' : ''; ?>>인기순</option>
                    <option value="<?php echo $sortBaseUrl . http_build_query(array_merge($sortUrlParams, ['sort' => 'copies'])); ?>" <?php echo $sortMode === 'copies' ? 'selected' : ''; ?>>복사순</option>
                </select>
            </div>

            <!-- Grid -->
            <div class="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-6">
                <?php foreach($prompts as $prompt): ?>
                <a href="prompt_detail.php?id=<?php echo $prompt['id']; ?>" class="prompt-card bg-suno-card border border-suno-border rounded-2xl p-6 flex flex-col">
                    <!-- Genre Tags + Audio Badges -->
                    <div class="flex items-center gap-1.5 mb-3 flex-wrap">
                        <?php foreach($prompt['genres'] as $genre): ?>
                        <span class="text-xs px-2.5 py-0.5 rounded-full bg-suno-accent/10 text-suno-accent2 border border-suno-accent/20 font-medium"><?php echo $genre; ?></span>
                        <?php endforeach; ?>
                        <?php if($prompt['has_track']): ?>
                        <span class="text-[10px] px-1.5 py-0.5 rounded bg-suno-accent/10 text-suno-accent2 border border-suno-accent/20 font-medium flex items-center gap-0.5">
                            <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/></svg>
                            완성곡
                        </span>
                        <?php endif; ?>
                        <?php if($prompt['has_sample']): ?>
                        <span class="text-[10px] px-1.5 py-0.5 rounded bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium flex items-center gap-0.5">
                            <svg class="w-2.5 h-2.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z"/></svg>
                            샘플
                        </span>
                        <?php endif; ?>
                        <span class="text-xs text-suno-muted/50 ml-auto"><?php echo $prompt['time']; ?></span>
                    </div>

                    <!-- Title -->
                    <h3 class="card-title font-bold text-base leading-snug mb-3 transition-colors"><?php echo htmlspecialchars($prompt['title']); ?></h3>

                    <!-- Prompt Preview -->
                    <div class="bg-suno-dark/60 border border-suno-border/50 rounded-lg p-3 mb-3">
                        <p class="text-xs text-suno-muted leading-relaxed line-clamp-3 font-mono"><?php echo htmlspecialchars($prompt['preview']); ?></p>
                    </div>

                    <!-- Track Player (완성본 곡이 있는 경우) -->
                    <?php if($prompt['has_track']): ?>
                        <?php if($prompt['track_has_audio'] && !empty($prompt['track_audio_path'])): ?>
                        <div class="flex items-center gap-2.5 bg-suno-accent/5 border border-suno-accent/15 rounded-lg px-3 py-2 mb-3" onclick="event.preventDefault(); event.stopPropagation();">
                            <button class="audio-play-btn w-7 h-7 bg-suno-accent/70 rounded-full flex items-center justify-center flex-shrink-0" onclick="event.preventDefault(); event.stopPropagation(); toggleCardAudio(this, '<?php echo htmlspecialchars($prompt['track_audio_path'], ENT_QUOTES); ?>');">
                                <svg class="play-icon w-3 h-3 text-white ml-px" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>
                                </svg>
                            </button>
                            <div class="flex-1 min-w-0" onclick="event.preventDefault(); event.stopPropagation();">
                                <div class="flex items-center gap-2">
                                    <span class="card-audio-time text-[10px] text-suno-muted/50 font-mono tabular-nums">0:00</span>
                                    <div class="flex-1 h-1 rounded-full bg-suno-border/60 cursor-pointer card-audio-bar" onclick="seekCardAudio(event, this)">
                                        <div class="h-full rounded-full bg-suno-accent transition-all card-audio-progress" style="width:0%"></div>
                                    </div>
                                    <span class="text-[10px] text-suno-muted/50 font-mono tabular-nums"><?php echo $prompt['track_duration']; ?></span>
                                </div>
                            </div>
                        </div>
                        <?php elseif($prompt['track_has_suno']): ?>
                        <div class="flex items-center gap-2.5 bg-suno-accent/5 border border-suno-accent/15 rounded-lg px-3 py-2 mb-3" onclick="event.preventDefault(); event.stopPropagation();">
                            <svg class="w-3.5 h-3.5 text-suno-accent flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/>
                            </svg>
                            <span class="text-xs text-suno-muted truncate flex-1"><?php echo htmlspecialchars($prompt['track_title']); ?></span>
                            <span class="inline-flex items-center gap-1 text-[10px] font-semibold text-suno-accent hover:text-suno-accent2 transition-colors bg-suno-accent/10 hover:bg-suno-accent/20 border border-suno-accent/20 px-2.5 py-1 rounded-lg flex-shrink-0 cursor-pointer" onclick="event.preventDefault(); event.stopPropagation(); window.open('<?php echo htmlspecialchars($prompt['track_suno_link'], ENT_QUOTES); ?>', '_blank');">
                                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                                </svg>
                                Suno에서 듣기
                            </span>
                        </div>
                        <?php endif; ?>
                    <?php endif; ?>

                    <!-- Footer: Author + Stats -->
                    <div class="flex items-center justify-between pt-3 border-t border-suno-border mt-auto">
                        <div class="flex items-center gap-2">
                            <div class="w-7 h-7 rounded-full bg-gradient-to-r <?php echo $prompt['avatar_color']; ?> flex items-center justify-center text-[10px] font-bold text-white">
                                <?php echo mb_substr($prompt['author'], 0, 1); ?>
                            </div>
                            <span class="text-xs text-suno-muted font-medium"><?php echo htmlspecialchars($prompt['author']); ?></span>
                        </div>
                        <div class="flex items-center gap-3 text-xs text-suno-muted/60">
                            <span class="flex items-center gap-1">
                                <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/></svg>
                                <?php echo $prompt['likes']; ?>
                            </span>
                            <span class="flex items-center gap-1">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
                                <?php echo $prompt['copies']; ?>
                            </span>
                        </div>
                    </div>
                </a>
                <?php endforeach; ?>
            </div>

            <!-- Pagination -->
            <?php if($totalPages > 1): ?>
            <div class="flex items-center justify-center gap-2 mt-12">
                <?php if($page > 1): ?>
                <a href="<?php echo pageUrl($page - 1, $filterParams); ?>" class="page-btn w-9 h-9 rounded-lg border border-suno-border bg-suno-card flex items-center justify-center text-suno-muted text-sm">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                </a>
                <?php else: ?>
                <button class="page-btn w-9 h-9 rounded-lg border border-suno-border bg-suno-card flex items-center justify-center text-suno-muted/30 text-sm cursor-not-allowed" disabled>
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                </button>
                <?php endif; ?>

                <?php
                $startPage = max(1, $page - 2);
                $endPage = min($totalPages, $page + 2);
                if ($startPage > 1): ?>
                    <a href="<?php echo pageUrl(1, $filterParams); ?>" class="page-btn w-9 h-9 rounded-lg border border-suno-border bg-suno-card flex items-center justify-center text-suno-muted text-sm font-medium">1</a>
                    <?php if($startPage > 2): ?>
                    <span class="text-suno-muted text-sm px-1">...</span>
                    <?php endif; ?>
                <?php endif; ?>

                <?php for($i = $startPage; $i <= $endPage; $i++): ?>
                <a href="<?php echo pageUrl($i, $filterParams); ?>" class="page-btn <?php echo $i === $page ? 'active' : ''; ?> w-9 h-9 rounded-lg border border-suno-border bg-suno-card flex items-center justify-center text-sm font-medium <?php echo $i !== $page ? 'text-suno-muted' : ''; ?>">
                    <?php echo $i; ?>
                </a>
                <?php endfor; ?>

                <?php if($endPage < $totalPages): ?>
                    <?php if($endPage < $totalPages - 1): ?>
                    <span class="text-suno-muted text-sm px-1">...</span>
                    <?php endif; ?>
                    <a href="<?php echo pageUrl($totalPages, $filterParams); ?>" class="page-btn w-9 h-9 rounded-lg border border-suno-border bg-suno-card flex items-center justify-center text-suno-muted text-sm font-medium"><?php echo $totalPages; ?></a>
                <?php endif; ?>

                <?php if($page < $totalPages): ?>
                <a href="<?php echo pageUrl($page + 1, $filterParams); ?>" class="page-btn w-9 h-9 rounded-lg border border-suno-border bg-suno-card flex items-center justify-center text-suno-muted text-sm">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </a>
                <?php else: ?>
                <button class="page-btn w-9 h-9 rounded-lg border border-suno-border bg-suno-card flex items-center justify-center text-suno-muted/30 text-sm cursor-not-allowed" disabled>
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </button>
                <?php endif; ?>
            </div>
            <?php endif; ?>
        </div>
    </section>
</main>

<script>
document.addEventListener('DOMContentLoaded', function() {
    // Tag expand/collapse
    window.togglePromptTagExpand = function() {
        var inner = document.getElementById('promptTagsInner');
        var icon = document.getElementById('promptTagExpandIcon');
        if (!inner) return;
        var expanded = inner.dataset.expanded === '1';
        if (expanded) {
            inner.style.maxHeight = '32px';
            icon.style.transform = 'rotate(0deg)';
            inner.dataset.expanded = '0';
        } else {
            inner.style.maxHeight = inner.scrollHeight + 'px';
            icon.style.transform = 'rotate(180deg)';
            inner.dataset.expanded = '1';
        }
    };

});

// ── Card audio player ──
var currentCardAudio = null;
var currentCardBtn = null;
var cardAudioRAF = null;

function toggleCardAudio(btn, src) {
    if (currentCardAudio && currentCardBtn === btn) {
        if (currentCardAudio.paused) {
            currentCardAudio.play();
            btn.querySelector('.play-icon').innerHTML = '<rect x="5" y="3" width="4" height="14" rx="1"/><rect x="13" y="3" width="4" height="14" rx="1"/>';
        } else {
            currentCardAudio.pause();
            btn.querySelector('.play-icon').innerHTML = '<path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>';
        }
        return;
    }
    if (currentCardAudio) {
        currentCardAudio.pause();
        currentCardAudio.currentTime = 0;
        if (currentCardBtn) {
            currentCardBtn.querySelector('.play-icon').innerHTML = '<path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>';
            var oldCard = currentCardBtn.closest('.flex');
            if (oldCard) {
                var oldProgress = oldCard.querySelector('.card-audio-progress');
                var oldTime = oldCard.querySelector('.card-audio-time');
                if (oldProgress) oldProgress.style.width = '0%';
                if (oldTime) oldTime.textContent = '0:00';
            }
        }
        cancelAnimationFrame(cardAudioRAF);
    }
    currentCardAudio = new Audio(src);
    currentCardBtn = btn;
    var card = btn.closest('.flex');
    var progressBar = card.querySelector('.card-audio-progress');
    var timeEl = card.querySelector('.card-audio-time');

    currentCardAudio.play();
    btn.querySelector('.play-icon').innerHTML = '<rect x="5" y="3" width="4" height="14" rx="1"/><rect x="13" y="3" width="4" height="14" rx="1"/>';

    function updateProgress() {
        if (!currentCardAudio || currentCardAudio.paused) return;
        var pct = (currentCardAudio.currentTime / currentCardAudio.duration) * 100;
        if (progressBar) progressBar.style.width = pct + '%';
        if (timeEl) {
            var m = Math.floor(currentCardAudio.currentTime / 60);
            var s = Math.floor(currentCardAudio.currentTime % 60);
            timeEl.textContent = m + ':' + (s < 10 ? '0' : '') + s;
        }
        cardAudioRAF = requestAnimationFrame(updateProgress);
    }
    currentCardAudio.addEventListener('play', function() { cardAudioRAF = requestAnimationFrame(updateProgress); });
    currentCardAudio.addEventListener('ended', function() {
        btn.querySelector('.play-icon').innerHTML = '<path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>';
        if (progressBar) progressBar.style.width = '0%';
        if (timeEl) timeEl.textContent = '0:00';
        currentCardAudio = null;
        currentCardBtn = null;
    });
}

function seekCardAudio(e, bar) {
    if (!currentCardAudio || !currentCardAudio.duration) return;
    var rect = bar.getBoundingClientRect();
    var pct = (e.clientX - rect.left) / rect.width;
    currentCardAudio.currentTime = pct * currentCardAudio.duration;
}

// ── Tag search (local, like music_list.php) ──
(function() {
    var input = document.getElementById('tagSearchInput');
    var dropdown = document.getElementById('tagDropdown');
    var content = document.getElementById('tagDropdownContent');
    var wrap = document.getElementById('tagSearchWrap');
    if (!input || !dropdown || !content) return;

    var allTags = <?php echo json_encode(array_values($dbGenres)); ?>;
    var currentTag = <?php echo json_encode($searchTag); ?>;
    var currentGenre = <?php echo json_encode($activeGenre); ?>;

    function openDD() { dropdown.classList.remove('hidden'); }
    function closeDD() { dropdown.classList.add('hidden'); }

    function escHtml(str) {
        var d = document.createElement('div'); d.textContent = str; return d.innerHTML;
    }

    function buildHref(tag) {
        return '?tag=' + encodeURIComponent(tag);
    }

    function renderAll(query) {
        query = (query || '').toLowerCase();
        var filtered = query ? allTags.filter(function(g) { return g.toLowerCase().indexOf(query) >= 0; }) : allTags;

        if (filtered.length === 0 && query) {
            content.innerHTML = '<div class="p-4 text-xs text-suno-muted text-center">검색 결과가 없습니다</div>';
            openDD();
            return;
        }

        var html = '';
        if (!query) {
            html += '<div class="px-3 py-3 flex flex-wrap gap-1.5">';
            allTags.forEach(function(g) {
                var isActive = g === currentTag || g === currentGenre;
                html += '<a href="' + buildHref(g) + '" class="inline-block px-2.5 py-1 rounded-md text-[11px] font-medium border transition-all cursor-pointer '
                    + (isActive ? 'bg-suno-accent/20 border-suno-accent/40 text-suno-accent2' : 'bg-suno-surface border-suno-border/60 text-suno-muted hover:bg-suno-accent/15 hover:text-suno-accent2 hover:border-suno-accent/30')
                    + '">' + escHtml(g) + '</a>';
            });
            html += '</div>';
        } else {
            html += '<div class="py-1">';
            filtered.forEach(function(g) {
                var isActive = g === currentTag || g === currentGenre;
                var idx = g.toLowerCase().indexOf(query);
                var highlighted = escHtml(g);
                if (idx >= 0) {
                    highlighted = escHtml(g.substring(0, idx))
                        + '<span class="text-suno-accent font-semibold">' + escHtml(g.substring(idx, idx + query.length)) + '</span>'
                        + escHtml(g.substring(idx + query.length));
                }
                html += '<a href="' + buildHref(g) + '" class="flex items-center gap-3 px-4 py-2 hover:bg-suno-surface/60 transition-colors cursor-pointer">'
                    + '<span class="text-xs text-white flex-1">' + highlighted + '</span>'
                    + (isActive ? '<svg class="w-3.5 h-3.5 text-suno-accent shrink-0" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>' : '')
                    + '</a>';
            });
            html += '</div>';
        }
        content.innerHTML = html;
        openDD();
    }

    var debounceTimer = null;
    input.addEventListener('focus', function() { renderAll(input.value.trim()); });
    input.addEventListener('input', function() {
        clearTimeout(debounceTimer);
        debounceTimer = setTimeout(function() { renderAll(input.value.trim()); }, 150);
    });
    input.addEventListener('keydown', function(e) {
        if (e.key === 'Enter') {
            e.preventDefault();
            var val = input.value.trim();
            if (val) {
                var match = allTags.find(function(g) { return g.toLowerCase() === val.toLowerCase(); });
                if (match) window.location.href = buildHref(match);
                else window.location.href = '?tag=' + encodeURIComponent(val);
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
