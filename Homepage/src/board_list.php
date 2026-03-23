<?php
require_once 'db.php';

// 게시판 시각 설정 (아이콘 SVG, 색상 등 - DB에 없을 수 있으므로 PHP 상수로 유지)
$boardVisual = [
    'notice' => [
        'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 110-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511l-.657.38a.75.75 0 01-1.021-.27l-.112-.194a4.504 4.504 0 01-.585-1.422M10.34 15.84a24.1 24.1 0 005.292-1.692m-5.292 1.692l.214 1.026a2.25 2.25 0 002.195 1.784h.344a2.25 2.25 0 002.195-1.784l.214-1.026m-5.162 0a23.616 23.616 0 005.162 0m5.162 0a24.07 24.07 0 005.292 1.692M15.66 8.16a24.1 24.1 0 005.292 1.692m0 0l.214-1.026A2.25 2.25 0 0019.162 7h-.344a2.25 2.25 0 00-2.195 1.784l-.214 1.026"/>',
        'write_label' => '공지 작성',
        'color' => 'text-rose-400',
        'bg' => 'bg-rose-500/10 border-rose-500/20',
    ],
    'free' => [
        'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"/>',
        'write_label' => '글쓰기',
        'color' => 'text-emerald-400',
        'bg' => 'bg-emerald-500/10 border-emerald-500/20',
    ],
    'qna' => [
        'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z"/>',
        'write_label' => '질문하기',
        'color' => 'text-blue-400',
        'bg' => 'bg-blue-500/10 border-blue-500/20',
    ],
    'info' => [
        'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18"/>',
        'write_label' => '정보 공유',
        'color' => 'text-teal-400',
        'bg' => 'bg-teal-500/10 border-teal-500/20',
    ],
    'collab' => [
        'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z"/>',
        'write_label' => '협업 제안',
        'color' => 'text-amber-400',
        'bg' => 'bg-amber-500/10 border-amber-500/20',
    ],
];

// 카테고리명 -> 태그 색상 매핑
$tagColorMap = [
    // notice
    '공지' => 'text-rose-400',
    '업데이트' => 'text-cyan-400',
    '이벤트' => 'text-amber-400',
    '점검' => 'text-zinc-400',
    // free
    '잡담' => 'text-zinc-400',
    '후기' => 'text-amber-400',
    '토론' => 'text-rose-400',
    '작품 공유' => 'text-suno-accent2',
    '추천' => 'text-violet-400',
    // qna
    '프롬프트' => 'text-violet-400',
    '저작권' => 'text-rose-400',
    '기술' => 'text-cyan-400',
    '수익화' => 'text-amber-400',
    'Suno 기본' => 'text-blue-400',
    // info
    '가이드' => 'text-cyan-400',
    '뉴스' => 'text-blue-400',
    '팁' => 'text-amber-400',
    // collab
    '보컬 구함' => 'text-pink-400',
    '프로젝트' => 'text-emerald-400',
    '믹싱/마스터링' => 'text-cyan-400',
    '영상 제작' => 'text-amber-400',
    '작사' => 'text-violet-400',
    // fallback
    '기타' => 'text-zinc-400',
];

// DB에서 모든 게시판 정보 조회
$boardsFromDB = [];
$stmtBoards = $pdo->query('SELECT * FROM boards WHERE is_active = 1 ORDER BY sort_order ASC');
while ($row = $stmtBoards->fetch()) {
    $key = $row['board_key'];
    if (isset($boardVisual[$key])) {
        $visual = $boardVisual[$key];
        // DB에 FA 아이콘이 설정되어 있으면 우선 사용
        if (!empty($row['icon_svg']) && strpos($row['icon_svg'], 'fa-') !== false) {
            $visual['icon'] = $row['icon_svg'];
            $visual['icon_type'] = 'fa';
        } else {
            $visual['icon_type'] = 'svg';
        }
    } else {
        $iconSvg = $row['icon_svg'] ?? '';
        $isFa = !empty($iconSvg) && strpos($iconSvg, 'fa-') !== false;
        $visual = [
            'icon' => $iconSvg,
            'icon_type' => $isFa ? 'fa' : 'svg',
            'write_label' => $row['write_title'] ?: '글쓰기',
            'color' => $row['color_class'] ?: 'text-zinc-400',
            'bg' => $row['bg_class'] ?: 'bg-zinc-500/10 border-zinc-500/20',
        ];
    }
    $boardsFromDB[$key] = array_merge($row, $visual);
}

// 현재 게시판 결정 - DB에 존재하면 허용
$currentBoard = isset($_GET['board']) ? $_GET['board'] : 'free';
if (!array_key_exists($currentBoard, $boardsFromDB)) {
    // DB에서 한번 더 조회 (새로 추가된 게시판 커버)
    $stmtNewBoard = $pdo->prepare('SELECT * FROM boards WHERE board_key = ? AND is_active = 1');
    $stmtNewBoard->execute([$currentBoard]);
    $newBoardRow = $stmtNewBoard->fetch();
    if ($newBoardRow) {
        $iconSvg = $newBoardRow['icon_svg'] ?? '';
        $isFa = !empty($iconSvg) && strpos($iconSvg, 'fa-') !== false;
        $boardsFromDB[$currentBoard] = array_merge($newBoardRow, [
            'icon' => $iconSvg,
            'icon_type' => $isFa ? 'fa' : 'svg',
            'write_label' => $newBoardRow['write_title'] ?: '글쓰기',
            'color' => $newBoardRow['color_class'] ?: 'text-zinc-400',
            'bg' => $newBoardRow['bg_class'] ?: 'bg-zinc-500/10 border-zinc-500/20',
        ]);
    } else {
        $currentBoard = 'free';
    }
}
$board = $boardsFromDB[$currentBoard];

// 정렬 (notice 게시판은 항상 latest)
$sortMode = 'latest';
$showPopularTab = ($currentBoard !== 'notice' && !empty($board['use_popular_tab']));
if ($showPopularTab && isset($_GET['sort']) && $_GET['sort'] === 'popular') {
    $sortMode = 'popular';
}

// 검색 파라미터
$searchQuery = isset($_GET['q']) ? trim($_GET['q']) : '';
$searchType = isset($_GET['search_type']) ? $_GET['search_type'] : 'title';
if (!in_array($searchType, ['title', 'author', 'title_content'])) {
    $searchType = 'title';
}

// 카테고리 필터
$filterCat = isset($_GET['cat']) ? (int)$_GET['cat'] : 0;

// 게시판 카테고리 목록 조회
$stmtCats = $pdo->prepare('SELECT * FROM board_categories WHERE board_id = ? AND is_active = 1 ORDER BY sort_order ASC');
$stmtCats->execute([$board['id']]);
$boardCategories = $stmtCats->fetchAll();

// 페이지네이션
$perPage = (int)$board['posts_per_page'];
$page = isset($_GET['page']) ? max(1, (int)$_GET['page']) : 1;

// WHERE 조건 동적 구성
$whereConditions = ['posts.board_id = ?'];
$whereParams = [$board['id']];

if ($searchQuery !== '') {
    if ($searchType === 'title') {
        $whereConditions[] = 'posts.title LIKE ?';
        $whereParams[] = '%' . $searchQuery . '%';
    } elseif ($searchType === 'author') {
        $whereConditions[] = 'users.nickname LIKE ?';
        $whereParams[] = '%' . $searchQuery . '%';
    } else {
        $whereConditions[] = '(posts.title LIKE ? OR posts.content LIKE ?)';
        $whereParams[] = '%' . $searchQuery . '%';
        $whereParams[] = '%' . $searchQuery . '%';
    }
}

if ($filterCat > 0) {
    $whereConditions[] = 'posts.category_id = ?';
    $whereParams[] = $filterCat;
}

if ($sortMode === 'popular') {
    $whereConditions[] = "posts.created_at >= datetime('now', '-7 days')";
    $whereConditions[] = "posts.created_at <= datetime('now', '-1 hours')";
    $orderClause = '(posts.like_count * 3 + posts.view_count) DESC, posts.created_at DESC';
} elseif ($currentBoard === 'notice') {
    $orderClause = 'posts.created_at DESC';
} else {
    $orderClause = 'posts.is_notice DESC, posts.created_at DESC';
}

$whereClause = implode(' AND ', $whereConditions);

$stmtCount = $pdo->prepare("SELECT COUNT(*) FROM posts JOIN users ON posts.user_id = users.id WHERE $whereClause");
$stmtCount->execute($whereParams);
$totalPosts = (int)$stmtCount->fetchColumn();
$totalPages = max(1, ceil($totalPosts / $perPage));
if ($page > $totalPages) $page = $totalPages;
$offset = ($page - 1) * $perPage;

$stmtPosts = $pdo->prepare("
    SELECT posts.*, users.nickname as author, users.avatar_color,
           board_categories.category_name as tag
    FROM posts
    JOIN users ON posts.user_id = users.id
    LEFT JOIN board_categories ON posts.category_id = board_categories.id
    WHERE $whereClause
    ORDER BY $orderClause
    LIMIT $perPage OFFSET $offset
");
$stmtPosts->execute($whereParams);
$posts = $stmtPosts->fetchAll();

// 시간 표시 헬퍼: 오늘이면 H:i, 아니면 m-d
function formatPostTime($datetime) {
    $postDate = date('Y-m-d', strtotime($datetime));
    $today = date('Y-m-d');
    if ($postDate === $today) {
        return date('H:i', strtotime($datetime));
    }
    return date('m-d', strtotime($datetime));
}

$pageTitle = $board['board_name'];
$boardBaseUrl = 'board_list.php?board=' . $currentBoard;
if ($sortMode !== 'latest') $boardBaseUrl .= '&sort=' . urlencode($sortMode);
if ($searchQuery !== '') $boardBaseUrl .= '&q=' . urlencode($searchQuery) . '&search_type=' . urlencode($searchType);
if ($filterCat > 0) $boardBaseUrl .= '&cat=' . $filterCat;
?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<style>
    .board-tab {
        transition: all 0.2s ease;
    }
    .board-tab:hover {
        color: white;
        background: rgba(255,255,255,0.05);
    }
    .board-tab.active {
        color: white;
        background: rgba(139,92,246,0.15);
        border-color: rgba(139,92,246,0.4);
    }
    .board-tab.active .board-tab-icon {
        color: #8b5cf6;
    }
    .post-row {
        transition: all 0.15s ease;
    }
    .post-row:hover {
        background: rgba(139,92,246,0.03);
    }
    .sort-tab {
        transition: all 0.15s ease;
    }
    .sort-tab.active {
        color: #8b5cf6;
        border-bottom: 2px solid #8b5cf6;
    }
</style>

<!-- Page Content -->
<div class="pt-20">

    <!-- Board Header -->
    <section class="border-b border-suno-border">
        <div class="max-w-5xl mx-auto px-6 py-8">
            <div class="flex flex-col sm:flex-row sm:items-end sm:justify-between gap-4">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 <?php echo $board['bg']; ?> border rounded-xl flex items-center justify-center">
                        <?php if (isset($board['icon_type']) && $board['icon_type'] === 'fa' && !empty($board['icon'])): ?>
                        <i class="<?php echo htmlspecialchars($board['icon']); ?> text-lg <?php echo $board['color']; ?>"></i>
                        <?php elseif (!empty($board['icon'])): ?>
                        <svg class="w-5 h-5 <?php echo $board['color']; ?>" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <?php echo $board['icon']; ?>
                        </svg>
                        <?php else: ?>
                        <span class="text-lg <?php echo $board['color']; ?> font-bold">#</span>
                        <?php endif; ?>
                    </div>
                    <div>
                        <h1 class="text-xl font-bold"><?php echo htmlspecialchars($board['board_name']); ?></h1>
                        <p class="text-suno-muted text-xs mt-0.5"><?php echo htmlspecialchars($board['description']); ?></p>
                    </div>
                </div>
                <a href="<?php echo $currentUser ? 'board_write.php?board=' . $currentBoard : 'login.php'; ?>" class="inline-flex items-center gap-2 bg-suno-accent hover:bg-suno-accent2 text-white font-semibold px-5 py-2.5 rounded-xl transition-all text-sm shrink-0 self-start sm:self-auto">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                    </svg>
                    <?php echo htmlspecialchars($board['write_label']); ?>
                </a>
            </div>
        </div>
    </section>

    <!-- Sort Tabs + Search + List -->
    <section class="py-0">
        <div class="max-w-5xl mx-auto px-6">

            <!-- Category Tabs -->
            <?php if (!empty($boardCategories)): ?>
            <div class="flex items-center gap-1.5 overflow-x-auto py-3 border-b border-suno-border scrollbar-hide">
                <a href="board_list.php?board=<?php echo $currentBoard; ?>" class="flex-shrink-0 px-3 py-1.5 text-xs font-medium rounded-lg border transition-all <?php echo $filterCat === 0 ? 'bg-suno-accent/15 border-suno-accent/40 text-suno-accent2' : 'border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/30'; ?>">전체</a>
                <?php foreach($boardCategories as $cat): ?>
                <a href="board_list.php?board=<?php echo $currentBoard; ?>&cat=<?php echo $cat['id']; ?>" class="flex-shrink-0 px-3 py-1.5 text-xs font-medium rounded-lg border transition-all <?php echo $filterCat === (int)$cat['id'] ? 'bg-suno-accent/15 border-suno-accent/40 text-suno-accent2' : 'border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/30'; ?>"><?php echo htmlspecialchars($cat['category_name']); ?></a>
                <?php endforeach; ?>
            </div>
            <?php endif; ?>

            <!-- Sort Tabs + Search Row -->
            <div class="flex items-center justify-between py-0 border-b border-suno-border">
                <div class="flex items-center gap-0">
                    <?php
                    $latestUrl = 'board_list.php?board=' . $currentBoard;
                    if ($filterCat > 0) $latestUrl .= '&cat=' . $filterCat;
                    if ($searchQuery !== '') $latestUrl .= '&q=' . urlencode($searchQuery) . '&search_type=' . urlencode($searchType);
                    ?>
                    <a href="<?php echo $latestUrl; ?>" class="sort-tab <?php echo $sortMode === 'latest' ? 'active font-semibold' : 'text-suno-muted hover:text-white'; ?> px-4 py-3 text-sm font-medium transition-colors">최신</a>
                    <?php if ($showPopularTab): ?>
                    <?php
                    $popularUrl = 'board_list.php?board=' . $currentBoard . '&sort=popular';
                    if ($filterCat > 0) $popularUrl .= '&cat=' . $filterCat;
                    if ($searchQuery !== '') $popularUrl .= '&q=' . urlencode($searchQuery) . '&search_type=' . urlencode($searchType);
                    ?>
                    <a href="<?php echo $popularUrl; ?>" class="sort-tab <?php echo $sortMode === 'popular' ? 'active font-semibold' : 'text-suno-muted hover:text-white'; ?> px-4 py-3 text-sm font-medium transition-colors">주간 인기</a>
                    <?php endif; ?>
                </div>
                <div class="flex items-center">
                <form action="board_list.php" method="GET" class="flex items-center gap-0">
                    <input type="hidden" name="board" value="<?php echo $currentBoard; ?>">
                    <?php if ($filterCat > 0): ?><input type="hidden" name="cat" value="<?php echo $filterCat; ?>"><?php endif; ?>
                    <select name="search_type" class="bg-suno-surface border border-suno-border rounded-l-lg px-2.5 py-[7px] text-xs text-white/70 focus:outline-none focus:border-suno-accent/40 appearance-none bg-[url('data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2210%22%20height%3D%226%22%20viewBox%3D%220%200%2010%206%22%3E%3Cpath%20d%3D%22M1%201l4%204%204-4%22%20stroke%3D%22%2371717a%22%20stroke-width%3D%221.5%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%2F%3E%3C%2Fsvg%3E')] bg-no-repeat bg-[right_6px_center] pr-5 hidden sm:block">
                        <option value="title" <?php echo $searchType === 'title' ? 'selected' : ''; ?>>제목</option>
                        <option value="author" <?php echo $searchType === 'author' ? 'selected' : ''; ?>>작성자</option>
                        <option value="title_content" <?php echo $searchType === 'title_content' ? 'selected' : ''; ?>>제목+내용</option>
                    </select>
                    <div class="relative">
                        <input type="text" name="q" value="<?php echo htmlspecialchars($searchQuery); ?>" placeholder="검색어 입력" class="w-32 sm:w-44 bg-suno-surface border border-suno-border sm:border-l-0 sm:rounded-l-none rounded-lg sm:rounded-r-lg pl-3 pr-8 py-[7px] text-xs text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/40 transition-all">
                        <button type="submit" class="absolute right-2 top-1/2 -translate-y-1/2 text-suno-muted hover:text-suno-accent transition-colors">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
                        </button>
                    </div>
                </form>
                </div>
            </div>

            <!-- Post List -->
            <div class="divide-y divide-suno-border/60">
                <?php foreach($posts as $idx => $post): ?>
                <?php
                    $tagName = $post['tag'] ? $post['tag'] : '';
                    $tagColor = isset($tagColorMap[$tagName]) ? $tagColorMap[$tagName] : 'text-zinc-400';
                    $postTime = formatPostTime($post['created_at']);
                ?>
                <a href="board_detail.php?board=<?php echo $currentBoard; ?>&id=<?php echo $post['id']; ?>" class="post-row flex items-center gap-3 py-2.5 px-2 group rounded-sm">
                    <?php if($currentBoard === 'collab'): ?>
                    <?php if($post['is_closed']): ?>
                    <span class="inline-flex items-center gap-1 text-[10px] font-semibold bg-zinc-500/10 text-zinc-400 border border-zinc-500/20 px-2 py-0.5 rounded flex-shrink-0">모집완료</span>
                    <?php else: ?>
                    <span class="inline-flex items-center gap-1 text-[10px] font-semibold bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 px-2 py-0.5 rounded flex-shrink-0"><span class="w-1.5 h-1.5 rounded-full bg-emerald-400"></span>모집중</span>
                    <?php endif; ?>
                    <?php endif; ?>

                    <!-- Title + Comment Count -->
                    <div class="flex-1 min-w-0">
                        <span class="text-sm text-zinc-200 group-hover:text-suno-accent2 transition-colors truncate block">
                            <?php echo htmlspecialchars($post['title']); ?>
                            <?php if($post['comment_count'] > 0): ?>
                            <span class="text-suno-accent font-bold ml-1">[<?php echo $post['comment_count']; ?>]</span>
                            <?php endif; ?>
                        </span>
                    </div>

                    <!-- Author (아이콘 + 이름) - 분류 왼쪽 -->
                    <div class="flex items-center gap-2 flex-shrink-0 min-w-0 max-w-[120px] sm:max-w-[140px]">
                        <span class="w-6 h-6 rounded-full bg-gradient-to-br <?php echo !empty($post['avatar_color']) ? htmlspecialchars($post['avatar_color']) : 'from-suno-accent to-purple-600'; ?> flex items-center justify-center text-[10px] font-bold text-white/90 flex-shrink-0" title="<?php echo htmlspecialchars($post['author'] ?? ''); ?>">
                            <?php echo mb_substr($post['author'] ?? '?', 0, 1); ?>
                        </span>
                        <span class="text-xs text-white/70 truncate"><?php echo htmlspecialchars($post['author'] ?? ''); ?></span>
                    </div>

                    <!-- Category Tag -->
                    <span class="hidden sm:block text-xs <?php echo $tagColor; ?> w-28 text-right flex-shrink-0 truncate"><?php echo htmlspecialchars($tagName); ?></span>

                    <!-- Separator -->
                    <span class="hidden sm:block text-suno-border">|</span>

                    <!-- Time -->
                    <span class="text-xs text-suno-muted/60 w-12 text-right flex-shrink-0"><?php echo $postTime; ?></span>

                    <!-- View Count -->
                    <span class="hidden sm:flex items-center gap-1 text-[11px] text-suno-muted/40 w-14 justify-end flex-shrink-0">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M2.036 12.322a1.012 1.012 0 010-.639C3.423 7.51 7.36 4.5 12 4.5c4.638 0 8.573 3.007 9.963 7.178.07.207.07.431 0 .639C20.577 16.49 16.64 19.5 12 19.5c-4.638 0-8.573-3.007-9.963-7.178z"/><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/></svg>
                        <?php echo number_format($post['view_count']); ?>
                    </span>
                </a>
                <?php endforeach; ?>
                <?php if (empty($posts)): ?>
                <div class="py-12 text-center text-suno-muted text-sm">게시물이 없습니다.</div>
                <?php endif; ?>
            </div>

            <!-- Pagination -->
            <div class="flex items-center justify-center gap-1.5 mt-8 mb-10">
                <?php if ($page > 1): ?>
                <a href="<?php echo $boardBaseUrl; ?>&page=<?php echo $page - 1; ?>" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                </a>
                <?php else: ?>
                <button disabled class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted/30">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                </button>
                <?php endif; ?>

                <?php
                // 페이지 번호 계산
                $startPage = max(1, $page - 2);
                $endPage = min($totalPages, $page + 2);
                if ($startPage > 1): ?>
                <a href="<?php echo $boardBaseUrl; ?>&page=1" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors text-sm">1</a>
                <?php if ($startPage > 2): ?>
                <span class="w-9 h-9 flex items-center justify-center text-suno-muted text-sm">...</span>
                <?php endif; ?>
                <?php endif; ?>

                <?php for ($i = $startPage; $i <= $endPage; $i++): ?>
                    <?php if ($i === $page): ?>
                    <button class="w-9 h-9 flex items-center justify-center rounded-lg bg-suno-accent text-white text-sm font-medium"><?php echo $i; ?></button>
                    <?php else: ?>
                    <a href="<?php echo $boardBaseUrl; ?>&page=<?php echo $i; ?>" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors text-sm"><?php echo $i; ?></a>
                    <?php endif; ?>
                <?php endfor; ?>

                <?php if ($endPage < $totalPages): ?>
                <?php if ($endPage < $totalPages - 1): ?>
                <span class="w-9 h-9 flex items-center justify-center text-suno-muted text-sm">...</span>
                <?php endif; ?>
                <a href="<?php echo $boardBaseUrl; ?>&page=<?php echo $totalPages; ?>" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors text-sm"><?php echo $totalPages; ?></a>
                <?php endif; ?>

                <?php if ($page < $totalPages): ?>
                <a href="<?php echo $boardBaseUrl; ?>&page=<?php echo $page + 1; ?>" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </a>
                <?php else: ?>
                <button disabled class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted/30">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </button>
                <?php endif; ?>
            </div>
        </div>
    </section>
</div>


<?php include 'footer.php'; ?>
