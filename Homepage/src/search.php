<?php
require_once 'db.php';
$pageTitle = '검색';
$query = isset($_GET['q']) ? trim($_GET['q']) : '';
$activeTab = isset($_GET['tab']) ? $_GET['tab'] : 'all';
$page = max(1, (int)($_GET['page'] ?? 1));
$perPage = 20;
$offset = ($page - 1) * $perPage;

$musicResults = [];
$promptResults = [];
$boardResults = [];
$userResults = [];
$counts = ['all' => 0, 'music' => 0, 'prompt' => 0, 'board' => 0, 'user' => 0];

if ($query !== '') {
    // macOS에서 한글이 NFD(자모 분해형)로 DB에 저장되는 경우가 있어
    // NFC(완성형)와 NFD(분해형) 양쪽 모두 검색하도록 처리
    $queryNFC = class_exists('Normalizer') ? Normalizer::normalize($query, Normalizer::FORM_C) : $query;
    $queryNFD = class_exists('Normalizer') ? Normalizer::normalize($query, Normalizer::FORM_D) : $query;
    $searchNFC = '%' . $queryNFC . '%';
    $searchNFD = '%' . $queryNFD . '%';
    $searchTerm = $searchNFC; // HTML 출력용

    // 음원 검색
    try {
        $musicLimit = $activeTab === 'all' ? 4 : $perPage;
        $musicOffset = $activeTab === 'music' ? $offset : 0;
        $stmt = $pdo->prepare("
            SELECT tracks.id, tracks.user_id, tracks.title, tracks.description, tracks.play_count, tracks.like_count, tracks.cover_image_path, tracks.created_at,
                   users.nickname as artist,
                   (SELECT GROUP_CONCAT(genre) FROM track_genres WHERE track_genres.track_id = tracks.id) as genre
            FROM tracks
            JOIN users ON tracks.user_id = users.id
            WHERE (tracks.title LIKE ? OR tracks.title LIKE ?)
               OR (tracks.description LIKE ? OR tracks.description LIKE ?)
               OR (users.nickname LIKE ? OR users.nickname LIKE ?)
               OR EXISTS (SELECT 1 FROM track_genres tg WHERE tg.track_id = tracks.id AND (tg.genre LIKE ? OR tg.genre LIKE ?))
            ORDER BY tracks.created_at DESC
            LIMIT {$musicLimit} OFFSET {$musicOffset}
        ");
        $stmt->execute([$searchNFC, $searchNFD, $searchNFC, $searchNFD, $searchNFC, $searchNFD, $searchNFC, $searchNFD]);
        $musicResults = $stmt->fetchAll();
    } catch (PDOException $e) {
        try {
            $stmt = $pdo->prepare("
                SELECT tracks.id, tracks.user_id, tracks.title, tracks.description, tracks.play_count, tracks.like_count, tracks.cover_image_path, tracks.created_at,
                       users.nickname as artist, '' as genre
                FROM tracks
                JOIN users ON tracks.user_id = users.id
                WHERE (tracks.title LIKE ? OR tracks.title LIKE ?)
                   OR (tracks.description LIKE ? OR tracks.description LIKE ?)
                   OR (users.nickname LIKE ? OR users.nickname LIKE ?)
                ORDER BY tracks.created_at DESC
                LIMIT {$musicLimit} OFFSET {$musicOffset}
            ");
            $stmt->execute([$searchNFC, $searchNFD, $searchNFC, $searchNFD, $searchNFC, $searchNFD]);
            $musicResults = $stmt->fetchAll();
        } catch (PDOException $e2) {
            $musicResults = [];
        }
    }

    // 음원 전체 개수
    try {
        $stmt = $pdo->prepare("
            SELECT COUNT(*) FROM tracks
            JOIN users ON tracks.user_id = users.id
            WHERE (tracks.title LIKE ? OR tracks.title LIKE ?)
               OR (tracks.description LIKE ? OR tracks.description LIKE ?)
               OR (users.nickname LIKE ? OR users.nickname LIKE ?)
               OR EXISTS (SELECT 1 FROM track_genres tg WHERE tg.track_id = tracks.id AND (tg.genre LIKE ? OR tg.genre LIKE ?))
        ");
        $stmt->execute([$searchNFC, $searchNFD, $searchNFC, $searchNFD, $searchNFC, $searchNFD, $searchNFC, $searchNFD]);
        $counts['music'] = (int)$stmt->fetchColumn();
    } catch (PDOException $e) {
        try {
            $stmt = $pdo->prepare("SELECT COUNT(*) FROM tracks JOIN users ON tracks.user_id = users.id WHERE (tracks.title LIKE ? OR tracks.title LIKE ?) OR (tracks.description LIKE ? OR tracks.description LIKE ?) OR (users.nickname LIKE ? OR users.nickname LIKE ?)");
            $stmt->execute([$searchNFC, $searchNFD, $searchNFC, $searchNFD, $searchNFC, $searchNFD]);
            $counts['music'] = (int)$stmt->fetchColumn();
        } catch (PDOException $e2) {
            $counts['music'] = 0;
        }
    }

    // 프롬프트 검색
    try {
        $stmt = $pdo->prepare("
            SELECT prompts.*, users.nickname as author
            FROM prompts
            JOIN users ON prompts.user_id = users.id
            WHERE (prompts.title LIKE ? OR prompts.title LIKE ?)
               OR (prompts.description LIKE ? OR prompts.description LIKE ?)
               OR (prompts.prompt_text LIKE ? OR prompts.prompt_text LIKE ?)
            ORDER BY prompts.created_at DESC
            LIMIT " . ($activeTab === 'all' ? 3 : $perPage) . " OFFSET " . ($activeTab === 'prompt' ? $offset : 0)
        );
        $stmt->execute([$searchNFC, $searchNFD, $searchNFC, $searchNFD, $searchNFC, $searchNFD]);
        $promptResults = $stmt->fetchAll();
    } catch (PDOException $e) {
        $promptResults = [];
    }
    try {
        $stmt = $pdo->prepare("SELECT COUNT(*) FROM prompts JOIN users ON prompts.user_id = users.id WHERE (prompts.title LIKE ? OR prompts.title LIKE ?) OR (prompts.description LIKE ? OR prompts.description LIKE ?) OR (prompts.prompt_text LIKE ? OR prompts.prompt_text LIKE ?)");
        $stmt->execute([$searchNFC, $searchNFD, $searchNFC, $searchNFD, $searchNFC, $searchNFD]);
        $counts['prompt'] = (int)$stmt->fetchColumn();
    } catch (PDOException $e) { $counts['prompt'] = 0; }

    // 게시판 검색 (모든 게시판, 제목+본문+댓글)
    try {
        $stmt = $pdo->prepare("
            SELECT DISTINCT posts.id, posts.board_id, posts.user_id, posts.title, posts.content, posts.view_count, posts.like_count, posts.comment_count, posts.created_at,
                   users.nickname as author,
                   b.board_key, b.board_name
            FROM posts
            JOIN users ON posts.user_id = users.id
            JOIN boards b ON posts.board_id = b.id
            WHERE (posts.title LIKE ? OR posts.title LIKE ?)
               OR (posts.content LIKE ? OR posts.content LIKE ?)
               OR EXISTS (SELECT 1 FROM post_comments c WHERE c.post_id = posts.id AND (c.content LIKE ? OR c.content LIKE ?))
            ORDER BY posts.created_at DESC
            LIMIT " . ($activeTab === 'all' ? 5 : $perPage) . " OFFSET " . ($activeTab === 'board' ? $offset : 0)
        );
        $stmt->execute([$searchNFC, $searchNFD, $searchNFC, $searchNFD, $searchNFC, $searchNFD]);
        $boardResults = $stmt->fetchAll();
    } catch (PDOException $e) {
        $boardResults = [];
    }
    try {
        $stmt = $pdo->prepare("
            SELECT COUNT(DISTINCT posts.id) FROM posts
            WHERE (posts.title LIKE ? OR posts.title LIKE ?)
               OR (posts.content LIKE ? OR posts.content LIKE ?)
               OR EXISTS (SELECT 1 FROM post_comments c WHERE c.post_id = posts.id AND (c.content LIKE ? OR c.content LIKE ?))
        ");
        $stmt->execute([$searchNFC, $searchNFD, $searchNFC, $searchNFD, $searchNFC, $searchNFD]);
        $counts['board'] = (int)$stmt->fetchColumn();
    } catch (PDOException $e) { $counts['board'] = 0; }

    // 유저 검색
    try {
        $stmt = $pdo->prepare("
            SELECT * FROM users
            WHERE (nickname LIKE ? OR nickname LIKE ?) OR (bio LIKE ? OR bio LIKE ?)
            ORDER BY id
            LIMIT " . ($activeTab === 'all' ? 3 : $perPage) . " OFFSET " . ($activeTab === 'user' ? $offset : 0)
        );
        $stmt->execute([$searchNFC, $searchNFD, $searchNFC, $searchNFD]);
        $userResults = $stmt->fetchAll();
    } catch (PDOException $e) {
        $userResults = [];
    }
    try {
        $stmt = $pdo->prepare("SELECT COUNT(*) FROM users WHERE (nickname LIKE ? OR nickname LIKE ?) OR (bio LIKE ? OR bio LIKE ?)");
        $stmt->execute([$searchNFC, $searchNFD, $searchNFC, $searchNFD]);
        $counts['user'] = (int)$stmt->fetchColumn();
    } catch (PDOException $e) { $counts['user'] = 0; }

    $counts['all'] = $counts['music'] + $counts['prompt'] + $counts['board'] + $counts['user'];
}

$tabs = [
    'all' => '전체',
    'music' => '음원',
    'prompt' => '프롬프트',
    'board' => '게시판',
    'user' => '유저',
];
?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<style>
    .search-tab { position: relative; padding: 0.75rem 1rem; font-size: 0.875rem; font-weight: 500; color: #71717a; transition: all 0.2s; cursor: pointer; white-space: nowrap; }
    .search-tab:hover { color: white; }
    .search-tab.active { color: #8b5cf6; font-weight: 600; }
    .search-tab.active::after { content: ''; position: absolute; bottom: 0; left: 0; right: 0; height: 2px; background: #8b5cf6; border-radius: 1px; }
    .result-card { transition: all 0.2s ease; }
    .result-card:hover { background: rgba(255,255,255,0.03); }
    .result-user-card { transition: all 0.2s ease; }
    .result-user-card:hover { border-color: rgba(139,92,246,0.3); transform: translateY(-2px); }
</style>

<main class="pt-20 pb-16 min-h-screen">
    <div class="max-w-4xl mx-auto px-6">

        <!-- 검색 헤더 -->
        <div class="mb-6">
            <form action="search.php" method="GET" class="relative">
                <svg class="absolute left-4 top-1/2 -translate-y-1/2 w-5 h-5 text-suno-muted pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
                <input type="text" name="q" value="<?php echo htmlspecialchars($query); ?>" placeholder="음원, 프롬프트, 게시글, 유저 검색..."
                    class="w-full bg-suno-surface border border-suno-border rounded-xl pl-12 pr-4 py-3.5 text-sm text-white placeholder-suno-muted/60 focus:outline-none focus:border-suno-accent/50 transition-all"
                    autofocus>
                <?php if($query): ?>
                <a href="search.php" class="absolute right-4 top-1/2 -translate-y-1/2 text-suno-muted hover:text-white transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                    </svg>
                </a>
                <?php endif; ?>
            </form>
        </div>

        <?php if($query): ?>
        <!-- 검색 결과 있을 때 -->

        <!-- 탭 -->
        <div class="flex items-center gap-0 border-b border-suno-border mb-6 overflow-x-auto hide-scrollbar">
            <?php foreach($tabs as $key => $label): ?>
            <a href="search.php?q=<?php echo urlencode($query); ?>&tab=<?php echo $key; ?>"
               class="search-tab <?php echo $activeTab === $key ? 'active' : ''; ?>">
                <?php echo $label; ?>
                <span class="ml-1 text-xs <?php echo $activeTab === $key ? 'text-suno-accent' : 'text-suno-muted/50'; ?>"><?php echo $counts[$key]; ?></span>
            </a>
            <?php endforeach; ?>
        </div>

        <!-- 검색 결과 정보 -->
        <p class="text-xs text-suno-muted mb-5">"<span class="text-white font-medium"><?php echo htmlspecialchars($query); ?></span>" 검색 결과 총 <span class="text-white font-medium"><?php echo $counts[$activeTab]; ?></span>건</p>

        <!-- ========== 음원 결과 ========== -->
        <?php if($activeTab === 'all' || $activeTab === 'music'): ?>
        <?php if(count($musicResults) > 0): ?>
        <div class="mb-8">
            <?php if($activeTab === 'all'): ?>
            <div class="flex items-center justify-between mb-3">
                <h2 class="text-sm font-bold flex items-center gap-2">
                    <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/>
                    </svg>
                    음원
                    <span class="text-xs text-suno-muted font-normal"><?php echo count($musicResults); ?></span>
                </h2>
                <a href="search.php?q=<?php echo urlencode($query); ?>&tab=music" class="text-xs text-suno-accent hover:text-suno-accent2 transition-colors">더보기 &rarr;</a>
            </div>
            <?php endif; ?>
            <div class="space-y-1">
                <?php foreach($musicResults as $m): ?>
                <a href="music_detail.php?id=<?php echo $m['id']; ?>" class="result-card flex items-center gap-3 p-2.5 rounded-lg group">
                    <div class="w-12 h-12 rounded-lg bg-gradient-to-br <?php echo getGradient($m['id'], $m['genre'] ? explode(',', $m['genre'])[0] : null); ?> flex items-center justify-center flex-shrink-0 relative overflow-hidden">
                        <?php if (!empty($m['cover_image_path'])): ?>
                        <img src="<?php echo htmlspecialchars($m['cover_image_path']); ?>" alt="" class="absolute inset-0 w-full h-full object-cover">
                        <?php else: ?>
                        <svg class="w-5 h-5 text-white/30" fill="currentColor" viewBox="0 0 20 20"><path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/></svg>
                        <?php endif; ?>
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-sm text-zinc-200 group-hover:text-suno-accent2 transition-colors truncate font-medium"><?php echo htmlspecialchars($m['title']); ?></p>
                        <p class="text-xs text-suno-muted truncate mt-0.5"><?php echo htmlspecialchars($m['artist'] ?? ''); ?> · <?php echo htmlspecialchars($m['genre'] ?? ''); ?></p>
                    </div>
                    <div class="flex items-center gap-4 flex-shrink-0 text-xs text-suno-muted">
                        <span class="flex items-center gap-1">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M14.752 11.168l-3.197-2.132A1 1 0 0010 9.87v4.263a1 1 0 001.555.832l3.197-2.132a1 1 0 000-1.664z"/></svg>
                            <?php echo formatCount($m['play_count'] ?? 0); ?>
                        </span>
                        <span class="flex items-center gap-1">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>
                            <?php echo formatCount($m['like_count'] ?? 0); ?>
                        </span>
                    </div>
                </a>
                <?php endforeach; ?>
            </div>
        </div>
        <?php endif; ?>
        <?php endif; ?>

        <!-- ========== 프롬프트 결과 ========== -->
        <?php if($activeTab === 'all' || $activeTab === 'prompt'): ?>
        <?php if(count($promptResults) > 0): ?>
        <div class="mb-8">
            <?php if($activeTab === 'all'): ?>
            <div class="flex items-center justify-between mb-3">
                <h2 class="text-sm font-bold flex items-center gap-2">
                    <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/>
                    </svg>
                    프롬프트
                    <span class="text-xs text-suno-muted font-normal"><?php echo count($promptResults); ?></span>
                </h2>
                <a href="search.php?q=<?php echo urlencode($query); ?>&tab=prompt" class="text-xs text-suno-accent hover:text-suno-accent2 transition-colors">더보기 &rarr;</a>
            </div>
            <?php endif; ?>
            <div class="space-y-1">
                <?php foreach($promptResults as $p): ?>
                <a href="prompt_detail.php?id=<?php echo $p['id']; ?>" class="result-card flex items-center gap-3 p-2.5 rounded-lg group">
                    <div class="w-12 h-12 rounded-lg bg-suno-surface border border-suno-border flex items-center justify-center flex-shrink-0">
                        <svg class="w-5 h-5 text-suno-accent/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/>
                        </svg>
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-sm text-zinc-200 group-hover:text-suno-accent2 transition-colors truncate font-medium"><?php echo htmlspecialchars($p['title']); ?></p>
                        <p class="text-xs text-suno-muted truncate mt-0.5"><?php echo htmlspecialchars($p['author'] ?? ''); ?> · <?php echo htmlspecialchars($p['genre'] ?? ''); ?></p>
                    </div>
                    <div class="flex items-center gap-4 flex-shrink-0 text-xs text-suno-muted">
                        <span class="flex items-center gap-1">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/></svg>
                            <?php echo formatCount($p['like_count'] ?? 0); ?>
                        </span>
                        <span class="flex items-center gap-1">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                            <?php echo formatCount($p['comments_count'] ?? 0); ?>
                        </span>
                    </div>
                </a>
                <?php endforeach; ?>
            </div>
        </div>
        <?php endif; ?>
        <?php endif; ?>

        <!-- ========== 게시판 결과 ========== -->
        <?php if($activeTab === 'all' || $activeTab === 'board'): ?>
        <?php if(count($boardResults) > 0): ?>
        <div class="mb-8">
            <?php if($activeTab === 'all'): ?>
            <div class="flex items-center justify-between mb-3">
                <h2 class="text-sm font-bold flex items-center gap-2">
                    <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"/>
                    </svg>
                    게시판
                    <span class="text-xs text-suno-muted font-normal"><?php echo count($boardResults); ?></span>
                </h2>
                <a href="search.php?q=<?php echo urlencode($query); ?>&tab=board" class="text-xs text-suno-accent hover:text-suno-accent2 transition-colors">더보기 &rarr;</a>
            </div>
            <?php endif; ?>
            <div class="space-y-1">
                <?php foreach($boardResults as $b): ?>
                <a href="board_detail.php?board=<?php echo urlencode($b['board_key'] ?? 'free'); ?>&id=<?php echo $b['id']; ?>" class="result-card flex items-center gap-3 p-2.5 rounded-lg group">
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2 mb-0.5">
                            <span class="text-[10px] px-1.5 py-0.5 rounded bg-suno-surface border border-suno-border text-suno-muted"><?php echo htmlspecialchars($b['board_name'] ?? $b['board_key'] ?? ''); ?></span>
                            <span class="text-sm text-zinc-200 group-hover:text-suno-accent2 transition-colors truncate font-medium"><?php echo htmlspecialchars($b['title']); ?>
                                <?php if(($b['comment_count'] ?? 0) > 0): ?>
                                <span class="text-suno-accent font-bold ml-1">[<?php echo $b['comment_count']; ?>]</span>
                                <?php endif; ?>
                            </span>
                        </div>
                        <p class="text-xs text-suno-muted"><?php echo htmlspecialchars($b['author'] ?? ''); ?> · <?php echo timeAgo($b['created_at']); ?></p>
                    </div>
                </a>
                <?php endforeach; ?>
            </div>
        </div>
        <?php endif; ?>
        <?php endif; ?>

        <!-- ========== 유저 결과 ========== -->
        <?php if($activeTab === 'all' || $activeTab === 'user'): ?>
        <?php if(count($userResults) > 0): ?>
        <div class="mb-8">
            <?php if($activeTab === 'all'): ?>
            <div class="flex items-center justify-between mb-3">
                <h2 class="text-sm font-bold flex items-center gap-2">
                    <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15 19.128a9.38 9.38 0 002.625.372 9.337 9.337 0 004.121-.952 4.125 4.125 0 00-7.533-2.493M15 19.128v-.003c0-1.113-.285-2.16-.786-3.07M15 19.128v.106A12.318 12.318 0 018.624 21c-2.331 0-4.512-.645-6.374-1.766l-.001-.109a6.375 6.375 0 0111.964-3.07M12 6.375a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zm8.25 2.25a2.625 2.625 0 11-5.25 0 2.625 2.625 0 015.25 0z"/>
                    </svg>
                    유저
                    <span class="text-xs text-suno-muted font-normal"><?php echo count($userResults); ?></span>
                </h2>
                <a href="search.php?q=<?php echo urlencode($query); ?>&tab=user" class="text-xs text-suno-accent hover:text-suno-accent2 transition-colors">더보기 &rarr;</a>
            </div>
            <?php endif; ?>
            <div class="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-3">
                <?php foreach($userResults as $u): ?>
                <a href="profile.php?id=<?php echo $u['id']; ?>" class="result-user-card block p-4 bg-suno-surface/50 border border-suno-border rounded-xl">
                    <div class="flex items-center gap-3 mb-3">
                        <div class="w-10 h-10 rounded-full bg-gradient-to-br <?php echo $u['avatar_color'] ?: 'from-violet-500 to-purple-500'; ?> flex items-center justify-center text-white text-sm font-bold flex-shrink-0">
                            <?php echo mb_substr($u['nickname'], 0, 1); ?>
                        </div>
                        <div class="min-w-0">
                            <p class="text-sm font-semibold text-white truncate"><?php echo htmlspecialchars($u['nickname']); ?></p>
                            <p class="text-xs text-suno-muted truncate"><?php echo htmlspecialchars($u['bio'] ?? ''); ?></p>
                        </div>
                    </div>
                    <div class="flex items-center gap-4 text-xs text-suno-muted">
                        <span>트랙 <span class="text-white font-medium"><?php echo $u['track_count'] ?? 0; ?></span></span>
                        <span>팔로워 <span class="text-white font-medium"><?php echo number_format($u['follower_count'] ?? 0); ?></span></span>
                    </div>
                </a>
                <?php endforeach; ?>
            </div>
        </div>
        <?php endif; ?>
        <?php endif; ?>

        <!-- 페이지네이션 (탭별 결과에서) -->
        <?php
        $totalTab = isset($counts[$activeTab]) ? $counts[$activeTab] : 0;
        $totalPages = $perPage > 0 ? max(1, (int)ceil($totalTab / $perPage)) : 1;
        $baseUrl = 'search.php?q=' . urlencode($query) . '&tab=' . urlencode($activeTab);
        ?>
        <?php if($query && $activeTab !== 'all' && $totalPages > 1): ?>
        <div class="flex items-center justify-center gap-1 mt-8 flex-wrap">
            <a href="<?php echo $baseUrl . '&page=' . ($page > 1 ? $page - 1 : 1); ?>" class="w-8 h-8 rounded-lg border border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/50 transition-all text-xs flex items-center justify-center <?php echo $page <= 1 ? 'opacity-50 pointer-events-none' : ''; ?>">&#9664;</a>
            <?php for ($i = max(1, $page - 2); $i <= min($totalPages, $page + 2); $i++): ?>
            <a href="<?php echo $baseUrl . '&page=' . $i; ?>" class="w-8 h-8 rounded-lg <?php echo $i === $page ? 'bg-suno-accent text-white' : 'border border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/50'; ?> transition-all text-xs font-bold flex items-center justify-center"><?php echo $i; ?></a>
            <?php endfor; ?>
            <a href="<?php echo $baseUrl . '&page=' . min($totalPages, $page + 1); ?>" class="w-8 h-8 rounded-lg border border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/50 transition-all text-xs flex items-center justify-center <?php echo $page >= $totalPages ? 'opacity-50 pointer-events-none' : ''; ?>">&#9654;</a>
        </div>
        <p class="text-center text-xs text-suno-muted mt-2"><?php echo $page; ?> / <?php echo $totalPages; ?> · 총 <?php echo $totalTab; ?>건</p>
        <?php endif; ?>

        <?php else: ?>
        <!-- 검색어 없을 때 -->
        <div class="text-center py-20">
            <div class="w-16 h-16 mx-auto mb-5 rounded-2xl bg-suno-surface border border-suno-border flex items-center justify-center">
                <svg class="w-7 h-7 text-suno-muted/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
            </div>
            <h2 class="text-lg font-bold mb-2">검색어를 입력해주세요</h2>
            <p class="text-sm text-suno-muted mb-8">음원, 프롬프트, 게시글, 유저를 검색할 수 있습니다</p>

            <!-- 인기 검색어 -->
            <div class="max-w-md mx-auto">
                <p class="text-xs text-suno-muted/50 font-medium uppercase tracking-wider mb-3">인기 검색어</p>
                <div class="flex flex-wrap justify-center gap-2">
                    <a href="search.php?q=K-Pop" class="text-xs px-3.5 py-2 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">K-Pop</a>
                    <a href="search.php?q=Lo-fi" class="text-xs px-3.5 py-2 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">Lo-fi</a>
                    <a href="search.php?q=%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8+%ED%8C%81" class="text-xs px-3.5 py-2 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">프롬프트 팁</a>
                    <a href="search.php?q=Hip-Hop" class="text-xs px-3.5 py-2 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">Hip-Hop</a>
                    <a href="search.php?q=%EC%88%98%EC%9D%B5%ED%99%94" class="text-xs px-3.5 py-2 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">수익화</a>
                    <a href="search.php?q=Suno+v4" class="text-xs px-3.5 py-2 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">Suno v4</a>
                    <a href="search.php?q=Synthwave" class="text-xs px-3.5 py-2 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">Synthwave</a>
                    <a href="search.php?q=EDM" class="text-xs px-3.5 py-2 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">EDM</a>
                </div>
            </div>

            <!-- 최근 검색어 (더미) -->
            <div class="max-w-md mx-auto mt-8">
                <p class="text-xs text-suno-muted/50 font-medium uppercase tracking-wider mb-3">최근 검색</p>
                <div class="space-y-1">
                    <a href="search.php?q=%EC%8B%9C%ED%8B%B0%ED%8C%9D+%ED%94%84%EB%A1%AC%ED%94%84%ED%8A%B8" class="flex items-center justify-between px-4 py-2.5 rounded-lg hover:bg-white/5 transition-colors group">
                        <div class="flex items-center gap-2.5">
                            <svg class="w-3.5 h-3.5 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
                            </svg>
                            <span class="text-sm text-suno-muted group-hover:text-white transition-colors">시티팝 프롬프트</span>
                        </div>
                        <svg class="w-3 h-3 text-suno-muted/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                        </svg>
                    </a>
                    <a href="search.php?q=%EB%B3%B4%EC%BB%AC+%EB%B6%84%EB%A6%AC" class="flex items-center justify-between px-4 py-2.5 rounded-lg hover:bg-white/5 transition-colors group">
                        <div class="flex items-center gap-2.5">
                            <svg class="w-3.5 h-3.5 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
                            </svg>
                            <span class="text-sm text-suno-muted group-hover:text-white transition-colors">보컬 분리</span>
                        </div>
                        <svg class="w-3 h-3 text-suno-muted/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                        </svg>
                    </a>
                    <a href="search.php?q=%EC%A0%80%EC%9E%91%EA%B6%8C" class="flex items-center justify-between px-4 py-2.5 rounded-lg hover:bg-white/5 transition-colors group">
                        <div class="flex items-center gap-2.5">
                            <svg class="w-3.5 h-3.5 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 6v6h4.5m4.5 0a9 9 0 11-18 0 9 9 0 0118 0z"/>
                            </svg>
                            <span class="text-sm text-suno-muted group-hover:text-white transition-colors">저작권</span>
                        </div>
                        <svg class="w-3 h-3 text-suno-muted/30" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                        </svg>
                    </a>
                </div>
            </div>
        </div>
        <?php endif; ?>

    </div>
</main>

<?php include 'footer.php'; ?>
