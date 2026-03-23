<?php require_once 'db.php'; ?>
<?php $pageTitle = '프롬프트 상세'; ?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<style>
    .prompt-code-block {
        background: #0d0d0d;
        border: 1px solid #1e1e1e;
        font-family: 'SF Mono', 'Fira Code', 'Fira Mono', 'Roboto Mono', monospace;
        position: relative;
    }
    .prompt-code-block:hover .copy-overlay {
        opacity: 1;
    }
    .copy-overlay {
        opacity: 0;
        transition: opacity 0.2s ease;
    }
    .action-btn {
        transition: all 0.2s ease;
    }
    .action-btn:hover {
        background: rgba(139,92,246,0.15);
        border-color: rgba(139,92,246,0.4);
        color: #a78bfa;
    }
    .action-btn.liked {
        background: rgba(239,68,68,0.1);
        border-color: rgba(239,68,68,0.3);
        color: #ef4444;
    }
    .audio-progress {
        background: linear-gradient(to right, #8b5cf6 0%, #8b5cf6 35%, #1e1e1e 35%, #1e1e1e 100%);
    }
    .comment-card {
        transition: all 0.2s ease;
    }
    .comment-card:hover {
        background: rgba(26,26,46,0.3);
    }
    .related-card {
        transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
    }
    .related-card:hover {
        transform: translateY(-2px);
        border-color: rgba(139,92,246,0.3);
        box-shadow: 0 8px 24px rgba(139,92,246,0.1);
    }
    .related-card:hover .related-title {
        color: #a78bfa;
    }
    .suno-external-btn {
        transition: all 0.3s ease;
        background: linear-gradient(135deg, #8b5cf6, #7c3aed);
    }
    .suno-external-btn:hover {
        background: linear-gradient(135deg, #a78bfa, #8b5cf6);
        box-shadow: 0 8px 30px rgba(139,92,246,0.3);
        transform: translateY(-1px);
    }
    .section-toggle {
        cursor: pointer;
        user-select: none;
    }
    .section-toggle .toggle-icon {
        transition: transform 0.2s ease;
    }
    .section-toggle.collapsed .toggle-icon {
        transform: rotate(-90deg);
    }
</style>

<?php
// Get prompt ID
$promptId = isset($_GET['id']) ? intval($_GET['id']) : 1;

// Fetch prompt with user info
$stmt = $pdo->prepare('
    SELECT prompts.*, users.nickname as author, users.avatar_color, users.id as author_user_id
    FROM prompts
    JOIN users ON prompts.user_id = users.id
    WHERE prompts.id = ?
');
$stmt->execute([$promptId]);
$promptRow = $stmt->fetch();

if (!$promptRow) {
    echo '<main class="pt-20"><div class="max-w-7xl mx-auto px-6 py-20 text-center"><h1 class="text-2xl font-bold mb-4">프롬프트를 찾을 수 없습니다</h1><a href="prompt_list.php" class="text-suno-accent hover:underline">목록으로 돌아가기</a></div></main>';
    include 'footer.php';
    exit;
}

// 조회수 증가
try {
    $pdo->exec("ALTER TABLE prompts ADD COLUMN view_count INTEGER NOT NULL DEFAULT 0");
} catch (Exception $e) {
    // column already exists
}
$pdo->prepare('UPDATE prompts SET view_count = view_count + 1 WHERE id = ?')->execute([$promptId]);

// DB에서 읽은 장르/스타일 문자열이 JSON 배열 형태면 풀어서 일반 문자열 배열로 만듦
function normalizePromptTagList(array $list) {
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

// Get genres
$gStmt = $pdo->prepare('SELECT genre FROM prompt_genres WHERE prompt_id = ?');
$gStmt->execute([$promptId]);
$promptGenres = normalizePromptTagList($gStmt->fetchAll(PDO::FETCH_COLUMN));

// Get styles (for tags sidebar)
$sStmt = $pdo->prepare('SELECT style FROM prompt_styles WHERE prompt_id = ?');
$sStmt->execute([$promptId]);
$promptStyles = normalizePromptTagList($sStmt->fetchAll(PDO::FETCH_COLUMN));
$allTags = array_merge($promptGenres, $promptStyles);

// Check if current user liked this prompt
$userLikedPrompt = false;
if ($currentUser) {
    $likeCheckStmt = $pdo->prepare('SELECT id FROM prompt_likes WHERE prompt_id = ? AND user_id = ?');
    $likeCheckStmt->execute([$promptId, $currentUser['id']]);
    $userLikedPrompt = (bool)$likeCheckStmt->fetch();
}

// Check if current user saved/bookmarked this prompt
$userSavedPrompt = false;
if ($currentUser) {
    $saveCheckStmt = $pdo->prepare('SELECT id FROM prompt_saves WHERE prompt_id = ? AND user_id = ?');
    $saveCheckStmt->execute([$promptId, $currentUser['id']]);
    $userSavedPrompt = (bool)$saveCheckStmt->fetch();
}

// Build finished_track data if linked
$has_finished_track = !empty($promptRow['linked_track_id']);
$finished_track = null;
if ($has_finished_track) {
    $tStmt = $pdo->prepare('SELECT tracks.*, users.nickname as artist FROM tracks JOIN users ON tracks.user_id = users.id WHERE tracks.id = ?');
    $tStmt->execute([$promptRow['linked_track_id']]);
    $trackData = $tStmt->fetch();
    if ($trackData) {
        $tgStmt = $pdo->prepare('SELECT genre FROM track_genres WHERE track_id = ? LIMIT 1');
        $tgStmt->execute([$trackData['id']]);
        $trackGenre = $tgStmt->fetchColumn() ?: '';
        $finished_track = [
            'id' => $trackData['id'],
            'title' => $trackData['title'],
            'artist' => $trackData['artist'],
            'album_art' => $trackData['cover_image_path'] ?: '',
            'gradient' => getGradient($trackData['id'], $trackGenre),
            'duration' => $trackData['duration'] ?: '',
            'plays' => $trackData['play_count'],
            'has_audio_file' => !empty($trackData['has_audio_file']),
            'audio_file_path' => $trackData['audio_file_path'] ?? '',
            'suno_link' => $trackData['suno_link'] ?: '',
        ];
    } else {
        $has_finished_track = false;
    }
}

// Build sample data (설정에 따라 on/off)
$has_sample = $useSampleSound && !empty($promptRow['sample_file_path']);
$sample = null;
if ($has_sample) {
    $ext = strtoupper(pathinfo($promptRow['sample_file_path'], PATHINFO_EXTENSION));
    $sample = [
        'label' => $promptRow['sample_label'] ?: basename($promptRow['sample_file_path']),
        'duration' => '0:32',
        'format' => $ext ?: 'WAV',
        'size' => '2.4 MB',
    ];
}

// Build prompt array matching the template expectations
$prompt = [
    'id' => $promptRow['id'],
    'title' => $promptRow['title'],
    'genres' => $promptGenres,
    'prompt_text' => $promptRow['prompt_text'],
    'description' => $promptRow['description'] ?: '',
    'author' => $promptRow['author'],
    'author_user_id' => $promptRow['author_user_id'],
    'avatar_color' => $promptRow['avatar_color'] ?: 'from-violet-500 to-purple-600',
    'date' => date('Y년 n월 j일', strtotime($promptRow['created_at'])),
    'views' => $promptRow['view_count'] ?? 0,
    'likes' => $promptRow['like_count'],
    'bookmarks' => $promptRow['save_count'],
    'copies' => $promptRow['copy_count'],
    'suno_link' => $promptRow['suno_link'] ?: '',
    'has_finished_track' => $has_finished_track,
    'finished_track' => $finished_track,
    'exclude_styles' => $promptRow['exclude_styles'] ?: '',
    'weirdness' => $promptRow['weirdness'] ?? 50,
    'style_influence' => $promptRow['style_influence'] ?? 50,
    'audio_influence' => $promptRow['audio_influence'] ?? 25,
    'has_lyrics' => !empty($promptRow['lyrics']),
    'lyrics' => $promptRow['lyrics'] ?: '',
    'has_sample' => $has_sample,
    'sample' => $sample,
];

// Prompt Comments (from prompt_comments table)
$pdo->exec("CREATE TABLE IF NOT EXISTS prompt_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    parent_id INTEGER,
    content TEXT NOT NULL,
    like_count INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");
$pdo->exec("CREATE TABLE IF NOT EXISTS prompt_comment_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(comment_id, user_id),
    FOREIGN KEY (comment_id) REFERENCES prompt_comments(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

$cStmt = $pdo->prepare('
    SELECT prompt_comments.*, users.nickname as author, users.avatar_color, users.id as comment_user_id
    FROM prompt_comments
    JOIN users ON prompt_comments.user_id = users.id
    WHERE prompt_comments.prompt_id = ?
    ORDER BY prompt_comments.created_at ASC
');
$cStmt->execute([$promptId]);
$allComments = $cStmt->fetchAll();

// Tree structure for comments
$rootComments = [];
$childComments = [];
foreach ($allComments as $c) {
    if ($c['parent_id']) {
        $childComments[$c['parent_id']][] = $c;
    } else {
        $rootComments[] = $c;
    }
}
$totalCommentCount = count($allComments);

// 유저가 좋아요 한 댓글 ID 목록
$userLikedCommentIds = [];
if ($currentUser) {
    $commentIds = array_column($allComments, 'id');
    if (!empty($commentIds)) {
        $placeholders = implode(',', array_fill(0, count($commentIds), '?'));
        $lcStmt = $pdo->prepare("SELECT comment_id FROM prompt_comment_likes WHERE user_id = ? AND comment_id IN ($placeholders)");
        $lcStmt->execute(array_merge([$currentUser['id']], $commentIds));
        $userLikedCommentIds = array_column($lcStmt->fetchAll(), 'comment_id');
    }
}

// Related prompts: same tags, sorted by latest
$relatedPrompts = [];
if (!empty($allTags)) {
    $tagPlaceholders = implode(',', array_fill(0, count($allTags), '?'));
    $rStmt = $pdo->prepare("
        SELECT DISTINCT prompts.*, users.nickname as author
        FROM prompts
        JOIN users ON prompts.user_id = users.id
        WHERE prompts.id != ?
        AND (prompts.id IN (SELECT prompt_id FROM prompt_genres WHERE genre IN ($tagPlaceholders))
             OR prompts.id IN (SELECT prompt_id FROM prompt_styles WHERE style IN ($tagPlaceholders)))
        ORDER BY prompts.created_at DESC
        LIMIT 5
    ");
    $params = array_merge([$promptId], $allTags, $allTags);
    $rStmt->execute($params);
} else {
    $rStmt = $pdo->prepare('
        SELECT prompts.*, users.nickname as author
        FROM prompts
        JOIN users ON prompts.user_id = users.id
        WHERE prompts.id != ?
        ORDER BY prompts.created_at DESC
        LIMIT 5
    ');
    $rStmt->execute([$promptId]);
}
$relatedRows = $rStmt->fetchAll();

foreach ($relatedRows as $r) {
    $rgStmt = $pdo->prepare('SELECT genre FROM prompt_genres WHERE prompt_id = ?');
    $rgStmt->execute([$r['id']]);
    $rGenres = normalizePromptTagList($rgStmt->fetchAll(PDO::FETCH_COLUMN));

    $relatedPrompts[] = [
        'id' => $r['id'],
        'title' => $r['title'],
        'genres' => $rGenres,
        'author' => $r['author'],
        'likes' => $r['like_count'],
        'copies' => $r['copy_count'],
    ];
}

// Count author's prompts
$authorCountStmt = $pdo->prepare('SELECT COUNT(*) FROM prompts WHERE user_id = ?');
$authorCountStmt->execute([$promptRow['user_id']]);
$authorPromptCount = $authorCountStmt->fetchColumn();

// Author's recent prompts (for sidebar)
$authorRecentStmt = $pdo->prepare('
    SELECT id, title, like_count, created_at
    FROM prompts
    WHERE user_id = ? AND id != ?
    ORDER BY created_at DESC
    LIMIT 3
');
$authorRecentStmt->execute([$promptRow['user_id'], $promptId]);
$authorRecentPrompts = $authorRecentStmt->fetchAll();
?>

<!-- Main Content -->
<main class="pt-20">
    <div class="max-w-7xl mx-auto px-6 py-8">
        <!-- Breadcrumb -->
        <nav class="flex items-center gap-2 text-sm mb-8">
            <a href="index.php" class="text-suno-muted hover:text-white transition-colors">홈</a>
            <svg class="w-3.5 h-3.5 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
            <a href="prompt_list.php" class="text-suno-muted hover:text-white transition-colors">프롬프트</a>
            <svg class="w-3.5 h-3.5 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
            <span class="text-white/80 truncate max-w-[200px]"><?php echo htmlspecialchars($prompt['title']); ?></span>
        </nav>

        <div class="grid lg:grid-cols-3 gap-8">
            <!-- Left: Main Content (2 cols) -->
            <div class="lg:col-span-2 space-y-8">
                <!-- Title & Author -->
                <div>
                    <!-- Genre Tags -->
                    <div class="flex flex-wrap items-center gap-2 mb-4">
                        <?php foreach($prompt['genres'] as $genre): ?>
                        <span class="text-xs px-3 py-1 rounded-full bg-suno-accent/10 text-suno-accent2 border border-suno-accent/20 font-medium">
                            <?php echo $genre; ?>
                        </span>
                        <?php endforeach; ?>
                        <?php if(!empty($prompt['has_finished_track'])): ?>
                        <span class="text-xs px-2.5 py-1 rounded-full bg-suno-accent/10 text-suno-accent2 border border-suno-accent/20 font-medium flex items-center gap-1">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/></svg>
                            완성곡
                        </span>
                        <?php endif; ?>
                        <?php if(!empty($prompt['has_sample'])): ?>
                        <span class="text-xs px-2.5 py-1 rounded-full bg-emerald-500/10 text-emerald-400 border border-emerald-500/20 font-medium flex items-center gap-1">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z"/></svg>
                            샘플
                        </span>
                        <?php endif; ?>
                    </div>

                    <h1 class="text-2xl md:text-3xl font-extrabold tracking-tight leading-tight mb-4"><?php echo htmlspecialchars($prompt['title']); ?></h1>

                    <!-- Author Info -->
                    <div class="flex items-center gap-4">
                        <div class="flex items-center gap-3">
                            <a href="profile.php?id=<?php echo $prompt['author_user_id']; ?>" class="w-10 h-10 rounded-full bg-gradient-to-r <?php echo $prompt['avatar_color']; ?> flex items-center justify-center text-sm font-bold text-white hover:ring-2 hover:ring-suno-accent/50 transition-all">
                                <?php echo mb_substr($prompt['author'], 0, 1); ?>
                            </a>
                            <div>
                                <a href="profile.php?id=<?php echo $prompt['author_user_id']; ?>" class="text-sm font-semibold hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($prompt['author']); ?></a>
                                <div class="flex items-center gap-3 text-xs text-suno-muted">
                                    <span><?php echo $prompt['date']; ?></span>
                                </div>
                            </div>
                        </div>
                        <?php if($currentUser && $currentUser['id'] == $prompt['author_user_id']): ?>
                        <a href="prompt_edit.php?id=<?php echo $prompt['id']; ?>" class="ml-auto inline-flex items-center gap-1.5 border border-suno-border bg-suno-card hover:border-suno-accent/40 hover:bg-suno-accent/5 text-suno-muted hover:text-suno-accent2 px-4 py-2 rounded-xl text-xs font-medium transition-all">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
                            수정
                        </a>
                        <?php endif; ?>
                    </div>
                </div>

                <!-- 1) 완성본 곡 (음원 게시판 연결) -->
                <?php if(!empty($prompt['has_finished_track'])): ?>
                <?php $track = $prompt['finished_track']; ?>
                <div class="bg-suno-card border border-suno-border rounded-2xl overflow-hidden">
                    <div class="flex items-center gap-2 px-5 pt-4 pb-2">
                        <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/>
                        </svg>
                        <h3 class="font-bold text-sm">완성본 곡</h3>
                        <span class="text-[10px] text-suno-muted/50 ml-auto">
                            <?php if($track['has_audio_file'] && !empty($track['suno_link'])): ?>
                                음원 파일 + Suno 링크
                            <?php elseif($track['has_audio_file']): ?>
                                음원 게시판에서 연결됨
                            <?php else: ?>
                                Suno 링크로 등록됨
                            <?php endif; ?>
                        </span>
                    </div>
                    <div class="flex items-center gap-4 px-5 pb-5 pt-2">
                        <!-- Album Art -->
                        <a href="music_detail.php?id=<?php echo $track['id']; ?>" class="relative group shrink-0 w-20 h-20 rounded-xl overflow-hidden">
                            <?php if(!empty($track['album_art'])): ?>
                            <img src="<?php echo htmlspecialchars($track['album_art']); ?>" alt="" class="w-20 h-20 rounded-xl object-cover">
                            <?php else: ?>
                            <div class="w-20 h-20 rounded-xl bg-gradient-to-br <?php echo $track['gradient']; ?> flex items-center justify-center">
                                <svg class="w-8 h-8 text-white/20" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/>
                                </svg>
                            </div>
                            <?php endif; ?>
                            <div class="absolute inset-0 bg-black/40 rounded-xl flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                <?php if($track['has_audio_file']): ?>
                                <svg class="w-8 h-8 text-white" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>
                                </svg>
                                <?php else: ?>
                                <svg class="w-6 h-6 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                                </svg>
                                <?php endif; ?>
                            </div>
                        </a>
                        <!-- Track Info -->
                        <div class="flex-1 min-w-0">
                            <a href="music_detail.php?id=<?php echo $track['id']; ?>" class="text-sm font-bold hover:text-suno-accent2 transition-colors block truncate"><?php echo htmlspecialchars($track['title']); ?></a>
                            <p class="text-xs text-suno-muted mt-0.5"><?php echo htmlspecialchars($track['artist']); ?></p>

                            <?php if($track['has_audio_file']): ?>
                            <!-- 직접 업로드된 파일: 재생 플레이어 -->
                            <?php if(!empty($track['audio_file_path'])): ?>
                            <audio id="finishedTrackAudio" src="<?php echo htmlspecialchars($track['audio_file_path']); ?>" preload="metadata"></audio>
                            <?php endif; ?>
                            <div class="flex items-center gap-3 mt-3">
                                <button onclick="toggleFinishedTrackPlay(this)" class="w-8 h-8 rounded-full bg-suno-accent hover:bg-suno-accent2 flex items-center justify-center transition-colors shrink-0">
                                    <svg class="w-3.5 h-3.5 text-white ml-px" fill="currentColor" viewBox="0 0 20 20">
                                        <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>
                                    </svg>
                                </button>
                                <div class="flex-1">
                                    <div class="flex items-center gap-2">
                                        <span id="ftCurrentTime" class="text-[10px] text-suno-muted tabular-nums">0:00</span>
                                        <div id="ftProgressWrap" class="flex-1 h-1 rounded-full bg-suno-border cursor-pointer" onclick="seekFinishedTrack(event)">
                                            <div id="ftProgress" class="h-full rounded-full bg-suno-accent" style="width: 0%"></div>
                                        </div>
                                        <span class="text-[10px] text-suno-muted tabular-nums"><?php echo $track['duration']; ?></span>
                                    </div>
                                </div>
                            </div>
                            <?php endif; ?>
                            <?php if(!empty($track['suno_link']) || (!$track['has_audio_file'] && !empty($prompt['suno_link']))): ?>
                            <!-- Suno 링크: 'Suno에서 듣기' 버튼 -->
                            <div class="mt-<?php echo $track['has_audio_file'] ? '2' : '3'; ?>">
                                <a href="<?php echo !empty($track['suno_link']) ? htmlspecialchars($track['suno_link']) : htmlspecialchars($prompt['suno_link']); ?>" target="_blank" rel="noopener noreferrer"
                                   class="inline-flex items-center gap-1.5 text-xs font-semibold text-suno-accent hover:text-suno-accent2 transition-colors bg-suno-accent/10 hover:bg-suno-accent/20 border border-suno-accent/20 px-3.5 py-2 rounded-lg">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                                    </svg>
                                    Suno에서 듣기
                                </a>
                            </div>
                            <?php endif; ?>

                            <div class="flex items-center gap-3 mt-2 text-[10px] text-suno-muted/50">
                                <span class="flex items-center gap-1">
                                    <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M10 18a8 8 0 100-16 8 8 0 000 16zM9.555 7.168A1 1 0 008 8v4a1 1 0 001.555.832l3-2a1 1 0 000-1.664l-3-2z"/></svg>
                                    <?php echo number_format($track['plays']); ?> 재생
                                </span>
                                <a href="music_detail.php?id=<?php echo $track['id']; ?>" class="hover:text-suno-accent2 transition-colors underline underline-offset-2">음원 페이지로 이동 &rarr;</a>
                            </div>
                        </div>
                    </div>
                </div>
                <?php endif; ?>

                <!-- Prompt Code Block (collapsible) -->
                <div class="prompt-code-block rounded-2xl p-6 group">
                    <div class="flex items-center justify-between mb-4">
                        <div class="section-toggle flex items-center gap-2" onclick="toggleSection('promptSection', this)">
                            <svg class="toggle-icon w-4 h-4 text-suno-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                            </svg>
                            <span class="text-xs text-suno-muted">Suno Prompt <span class="text-suno-muted/50">(Styles)</span></span>
                        </div>
                        <button onclick="copyPrompt()" class="copy-overlay flex items-center gap-1.5 bg-suno-accent/20 hover:bg-suno-accent/30 text-suno-accent2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all" id="copyBtn">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                            </svg>
                            <span id="copyText">복사하기</span>
                        </button>
                    </div>
                    <div id="promptSection">
                        <pre class="text-sm text-suno-accent2/90 leading-relaxed whitespace-pre-wrap" id="promptContent"><?php echo htmlspecialchars($prompt['prompt_text']); ?></pre>

                        <!-- Exclude Styles / Vocal Gender / Lyrics Mode -->
                        <div class="mt-5 pt-4 border-t border-suno-border/30 space-y-3">
                            <?php if(!empty($prompt['exclude_styles'])): ?>
                            <div class="flex items-start gap-3">
                                <span class="text-[10px] text-suno-muted/50 w-24 shrink-0 pt-0.5 uppercase tracking-wider font-medium">Exclude Styles</span>
                                <p class="text-xs text-rose-400/60 font-mono leading-relaxed"><?php echo htmlspecialchars($prompt['exclude_styles']); ?></p>
                            </div>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>

                <!-- Lyrics (가사) - collapsible -->
                <?php if(!empty($prompt['has_lyrics'])): ?>
                <div class="prompt-code-block rounded-2xl p-6 group">
                    <div class="flex items-center justify-between mb-4">
                        <div class="section-toggle flex items-center gap-2" onclick="toggleSection('lyricsSection', this)">
                            <svg class="toggle-icon w-4 h-4 text-suno-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                            </svg>
                            <span class="text-xs text-suno-muted">Lyrics <span class="text-suno-muted/50">(가사)</span></span>
                        </div>
                        <button onclick="copyLyrics()" class="copy-overlay flex items-center gap-1.5 bg-suno-accent/20 hover:bg-suno-accent/30 text-suno-accent2 px-3 py-1.5 rounded-lg text-xs font-medium transition-all" id="copyLyricsBtn">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                            </svg>
                            <span id="copyLyricsText">복사하기</span>
                        </button>
                    </div>
                    <div id="lyricsSection">
                        <pre class="text-sm text-white/70 leading-relaxed whitespace-pre-wrap" id="lyricsContent"><?php echo htmlspecialchars($prompt['lyrics']); ?></pre>
                    </div>
                </div>
                <?php endif; ?>

                <!-- Suno Parameters (collapsible) -->
                <div class="bg-suno-dark/60 border border-suno-border/50 rounded-xl px-5 py-4 -mt-4 space-y-3">
                    <div class="section-toggle flex items-center gap-2" onclick="toggleSection('paramsSection', this)">
                        <svg class="toggle-icon w-4 h-4 text-suno-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                        </svg>
                        <p class="text-[10px] text-suno-muted/50 font-semibold uppercase tracking-wider">Parameters</p>
                    </div>
                    <div id="paramsSection">
                        <?php
                        $params = [
                            ['label' => 'Weirdness', 'value' => $prompt['weirdness']],
                            ['label' => 'Style Influence', 'value' => $prompt['style_influence']],
                            ['label' => 'Audio Influence', 'value' => $prompt['audio_influence']],
                        ];
                        foreach($params as $p): ?>
                        <div class="flex items-center gap-3">
                            <span class="text-xs text-suno-muted w-28 shrink-0"><?php echo $p['label']; ?></span>
                            <div class="flex-1 h-1.5 rounded-full bg-suno-border/60 relative overflow-hidden">
                                <div class="absolute inset-y-0 left-0 rounded-full bg-rose-500/70" style="width: <?php echo $p['value']; ?>%"></div>
                            </div>
                            <span class="text-xs text-suno-muted/70 font-mono w-8 text-right shrink-0"><?php echo $p['value']; ?>%</span>
                        </div>
                        <?php endforeach; ?>
                    </div>
                </div>

                <!-- 샘플 사운드 첨부파일 -->
                <?php if(!empty($prompt['has_sample'])): ?>
                <?php $sample = $prompt['sample']; ?>
                <div class="bg-suno-dark/50 border border-suno-border/60 rounded-xl px-4 py-3 -mt-4">
                    <p class="text-[10px] text-emerald-400/60 font-semibold uppercase tracking-wider mb-2">사용 샘플</p>
                    <div class="flex items-center gap-3">
                    <button class="w-7 h-7 rounded-full bg-emerald-500/60 hover:bg-emerald-500 flex items-center justify-center transition-colors shrink-0">
                        <svg class="w-3 h-3 text-white ml-px" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>
                        </svg>
                    </button>
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center gap-2">
                            <svg class="w-3 h-3 text-emerald-400/60 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.172 7l-6.586 6.586a2 2 0 102.828 2.828l6.414-6.586a4 4 0 00-5.656-5.656l-6.415 6.585a6 6 0 108.486 8.486L20.5 13"/></svg>
                            <span class="text-xs text-suno-muted truncate"><?php echo htmlspecialchars($sample['label']); ?></span>
                            <span class="text-[10px] px-1.5 py-px rounded bg-emerald-500/10 text-emerald-400/70 border border-emerald-500/15 font-medium shrink-0"><?php echo $sample['format']; ?></span>
                            <span class="text-[10px] text-suno-muted/40 shrink-0"><?php echo $sample['size']; ?></span>
                            <span class="text-[10px] text-suno-muted/40 shrink-0"><?php echo $sample['duration']; ?></span>
                        </div>
                    </div>
                    <a href="#" download class="inline-flex items-center gap-1.5 text-[10px] text-emerald-400/70 hover:text-emerald-400 border border-emerald-500/20 hover:border-emerald-500/40 bg-emerald-500/5 hover:bg-emerald-500/10 rounded-lg px-2.5 py-1.5 transition-all shrink-0 font-medium">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 16v1a3 3 0 003 3h10a3 3 0 003-3v-1m-4-4l-4 4m0 0l-4-4m4 4V4"/>
                        </svg>
                        다운로드
                    </a>
                    </div>
                </div>
                <?php endif; ?>

                <!-- Description (collapsible) -->
                <?php if(!empty($prompt['description'])): ?>
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6">
                    <div class="section-toggle flex items-center gap-2 mb-3" onclick="toggleSection('descSection', this)">
                        <svg class="toggle-icon w-4 h-4 text-suno-muted" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/>
                        </svg>
                        <h3 class="font-bold text-base flex items-center gap-2">
                            <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                            </svg>
                            설명
                        </h3>
                    </div>
                    <div id="descSection">
                        <p class="text-sm text-suno-muted leading-relaxed"><?php echo htmlspecialchars($prompt['description']); ?></p>
                    </div>
                </div>
                <?php endif; ?>

                <!-- Suno Link & Actions -->
                <div class="flex flex-col sm:flex-row items-stretch sm:items-center gap-3">
                    <?php if(!empty($prompt['suno_link'])): ?>
                    <a href="<?php echo htmlspecialchars($prompt['suno_link']); ?>" target="_blank" class="suno-external-btn flex items-center justify-center gap-2 text-white font-semibold px-6 py-3.5 rounded-xl text-sm flex-1 sm:flex-none">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                        </svg>
                        Suno로 가기
                    </a>
                    <?php endif; ?>
                    <div class="flex items-center gap-2">
                        <button onclick="toggleLike(this)" class="action-btn flex items-center gap-2 border border-suno-border bg-suno-card px-4 py-3 rounded-xl text-sm <?php echo $userLikedPrompt ? 'text-pink-500 border-pink-500/30 bg-pink-500/10' : 'text-suno-muted'; ?>">
                            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/>
                            </svg>
                            <span id="promptLikeCount"><?php echo $prompt['likes']; ?></span>
                        </button>
                        <button onclick="toggleSave(this)" class="action-btn flex items-center gap-2 border border-suno-border bg-suno-card px-4 py-3 rounded-xl text-sm <?php echo $userSavedPrompt ? 'text-yellow-500 border-yellow-500/30 bg-yellow-500/10' : 'text-suno-muted'; ?>">
                            <svg class="w-4 h-4" fill="<?php echo $userSavedPrompt ? 'currentColor' : 'none'; ?>" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
                            </svg>
                            <span id="promptSaveCount"><?php echo $prompt['bookmarks']; ?></span>
                        </button>
                        <button onclick="sharePrompt()" class="action-btn flex items-center gap-2 border border-suno-border bg-suno-card px-4 py-3 rounded-xl text-sm text-suno-muted">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/>
                            </svg>
                            공유
                        </button>
                        <?php if ($currentUser && $currentUser['id'] != $prompt['author_user_id']): ?>
                        <button onclick="openReportModal('prompt', <?php echo $promptId; ?>)" class="action-btn flex items-center gap-2 border border-suno-border bg-suno-card px-4 py-3 rounded-xl text-sm text-suno-muted hover:text-red-400 hover:border-red-500/30">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
                            </svg>
                            신고
                        </button>
                        <?php endif; ?>
                    </div>
                </div>

                <!-- Comments Section -->
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6">
                    <h3 class="font-bold text-base mb-6 flex items-center gap-2">
                        <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/>
                        </svg>
                        댓글 <span class="text-suno-muted font-normal text-sm ml-1"><?php echo $totalCommentCount; ?></span>
                    </h3>

                    <!-- Comment Form (회원만) -->
                    <?php if($currentUser): ?>
                    <form action="comment_ok.php" method="POST" class="mb-8">
                        <input type="hidden" name="type" value="prompt">
                        <input type="hidden" name="target_id" value="<?php echo $promptId; ?>">
                        <div class="flex gap-3">
                            <div class="w-9 h-9 rounded-full bg-gradient-to-r <?php echo $currentUser['avatar_color'] ?: 'from-suno-accent to-purple-500'; ?> flex items-center justify-center text-xs font-bold shrink-0">
                                <?php echo mb_substr($currentUser['nickname'], 0, 1); ?>
                            </div>
                            <div class="flex-1">
                                <textarea name="content" placeholder="댓글을 입력하세요..." required class="w-full bg-suno-dark border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted focus:outline-none focus:border-suno-accent/50 transition-colors resize-none h-20"></textarea>
                                <div class="flex justify-end mt-2">
                                    <button type="submit" class="bg-suno-accent hover:bg-suno-accent2 text-white font-medium px-5 py-2 rounded-lg text-sm transition-all">등록</button>
                                </div>
                            </div>
                        </div>
                    </form>
                    <?php endif; ?>

                    <!-- Comment List -->
                    <div class="space-y-1">
                        <?php foreach($rootComments as $comment): ?>
                        <div class="comment-card flex gap-3 p-4 rounded-xl">
                            <a href="profile.php?id=<?php echo $comment['comment_user_id']; ?>" class="w-8 h-8 rounded-full bg-gradient-to-r <?php echo $comment['avatar_color'] ?: 'from-violet-500 to-purple-600'; ?> flex items-center justify-center text-[10px] font-bold text-white shrink-0 hover:ring-2 hover:ring-suno-accent/50 transition-all">
                                <?php echo mb_substr($comment['author'], 0, 1); ?>
                            </a>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2 mb-1">
                                    <a href="profile.php?id=<?php echo $comment['comment_user_id']; ?>" class="text-sm font-semibold hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($comment['author']); ?></a>
                                    <span class="text-xs text-suno-muted/50"><?php echo timeAgo($comment['created_at']); ?></span>
                                </div>
                                <p class="text-sm text-suno-muted leading-relaxed"><?php echo nl2br(htmlspecialchars($comment['content'])); ?></p>
                                <div class="flex items-center gap-4 mt-2">
                                    <?php $commentLiked = in_array($comment['id'], $userLikedCommentIds); ?>
                                    <button onclick="toggleCommentLike(this, <?php echo $comment['id']; ?>)" class="flex items-center gap-1 text-xs transition-colors <?php echo $commentLiked ? 'text-pink-500' : 'text-suno-muted/50 hover:text-suno-accent2'; ?>">
                                        <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                                            <path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/>
                                        </svg>
                                        <span><?php echo $comment['like_count']; ?></span>
                                    </button>
                                    <?php if($currentUser): ?>
                                    <button onclick="toggleReplyForm(<?php echo $comment['id']; ?>)" class="text-xs text-suno-muted/50 hover:text-suno-accent2 transition-colors">답글</button>
                                    <?php endif; ?>
                                </div>

                                <!-- Reply form (hidden) -->
                                <?php if($currentUser): ?>
                                <form id="replyForm-<?php echo $comment['id']; ?>" action="comment_ok.php" method="POST" class="hidden mt-3">
                                    <input type="hidden" name="type" value="prompt">
                                    <input type="hidden" name="target_id" value="<?php echo $promptId; ?>">
                                    <input type="hidden" name="parent_id" value="<?php echo $comment['id']; ?>">
                                    <textarea name="content" placeholder="답글을 입력하세요..." required class="w-full bg-suno-dark border border-suno-border rounded-lg px-3 py-2 text-sm text-white placeholder-suno-muted focus:outline-none focus:border-suno-accent/50 transition-colors resize-none h-16"></textarea>
                                    <div class="flex justify-end mt-1.5 gap-2">
                                        <button type="button" onclick="toggleReplyForm(<?php echo $comment['id']; ?>)" class="text-xs text-suno-muted hover:text-white px-3 py-1.5 transition-colors">취소</button>
                                        <button type="submit" class="bg-suno-accent hover:bg-suno-accent2 text-white font-medium px-4 py-1.5 rounded-lg text-xs transition-all">답글 등록</button>
                                    </div>
                                </form>
                                <?php endif; ?>

                                <!-- Child comments -->
                                <?php if(!empty($childComments[$comment['id']])): ?>
                                <div class="mt-3 space-y-1 ml-2 border-l-2 border-suno-border/30 pl-4">
                                    <?php foreach($childComments[$comment['id']] as $child): ?>
                                    <div class="comment-card flex gap-3 p-3 rounded-lg">
                                        <a href="profile.php?id=<?php echo $child['comment_user_id']; ?>" class="w-7 h-7 rounded-full bg-gradient-to-r <?php echo $child['avatar_color'] ?: 'from-violet-500 to-purple-600'; ?> flex items-center justify-center text-[10px] font-bold text-white shrink-0 hover:ring-2 hover:ring-suno-accent/50 transition-all">
                                            <?php echo mb_substr($child['author'], 0, 1); ?>
                                        </a>
                                        <div class="flex-1 min-w-0">
                                            <div class="flex items-center gap-2 mb-1">
                                                <a href="profile.php?id=<?php echo $child['comment_user_id']; ?>" class="text-xs font-semibold hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($child['author']); ?></a>
                                                <span class="text-[10px] text-suno-muted/50"><?php echo timeAgo($child['created_at']); ?></span>
                                            </div>
                                            <p class="text-xs text-suno-muted leading-relaxed"><?php echo nl2br(htmlspecialchars($child['content'])); ?></p>
                                        </div>
                                    </div>
                                    <?php endforeach; ?>
                                </div>
                                <?php endif; ?>
                            </div>
                        </div>
                        <?php endforeach; ?>
                        <?php if(empty($rootComments)): ?>
                        <div class="text-center py-8 text-suno-muted/40 text-sm">아직 댓글이 없습니다.</div>
                        <?php endif; ?>
                    </div>
                </div>

                <!-- Back to List -->
                <div class="pt-2">
                    <a href="prompt_list.php" class="inline-flex items-center gap-2 text-sm text-suno-muted hover:text-suno-accent2 transition-colors">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
                        </svg>
                        목록으로 돌아가기
                    </a>
                </div>
            </div>

            <!-- Right: Sidebar (1 col) -->
            <div class="space-y-6">
                <!-- Prompt Stats Card -->
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6">
                    <h3 class="font-bold text-sm mb-4">프롬프트 통계</h3>
                    <div class="grid grid-cols-2 gap-4">
                        <div class="text-center p-3 bg-suno-dark rounded-xl">
                            <div class="text-lg font-bold text-suno-accent"><?php echo $prompt['likes']; ?></div>
                            <div class="text-xs text-suno-muted mt-0.5">좋아요</div>
                        </div>
                        <div class="text-center p-3 bg-suno-dark rounded-xl">
                            <div class="text-lg font-bold text-suno-accent"><?php echo $prompt['views']; ?></div>
                            <div class="text-xs text-suno-muted mt-0.5">조회수</div>
                        </div>
                        <div class="text-center p-3 bg-suno-dark rounded-xl">
                            <div class="text-lg font-bold text-white"><?php echo $totalCommentCount; ?></div>
                            <div class="text-xs text-suno-muted mt-0.5">댓글</div>
                        </div>
                        <div class="text-center p-3 bg-suno-dark rounded-xl">
                            <div class="text-lg font-bold text-white"><?php echo $prompt['bookmarks']; ?></div>
                            <div class="text-xs text-suno-muted mt-0.5">북마크</div>
                        </div>
                    </div>
                </div>

                <!-- Author Card -->
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6">
                    <h3 class="font-bold text-sm mb-4">작성자</h3>
                    <div class="flex items-center gap-3 mb-4">
                        <a href="profile.php?id=<?php echo $prompt['author_user_id']; ?>" class="w-12 h-12 rounded-full bg-gradient-to-r <?php echo $prompt['avatar_color']; ?> flex items-center justify-center text-base font-bold text-white hover:ring-2 hover:ring-suno-accent/50 transition-all">
                            <?php echo mb_substr($prompt['author'], 0, 1); ?>
                        </a>
                        <div>
                            <a href="profile.php?id=<?php echo $prompt['author_user_id']; ?>" class="font-semibold text-sm hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($prompt['author']); ?></a>
                            <div class="text-xs text-suno-muted">프롬프트 <?php echo $authorPromptCount; ?>개 공유</div>
                        </div>
                    </div>
                    <div class="border-t border-suno-border/50 pt-3 mt-1">
                        <a href="prompt_list.php?q=<?php echo urlencode($prompt['author']); ?>" class="w-full inline-flex items-center justify-center gap-2 border border-suno-border bg-suno-dark hover:border-suno-accent/40 hover:bg-suno-accent/5 text-suno-muted hover:text-suno-accent2 px-4 py-2.5 rounded-xl text-xs font-medium transition-all">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/></svg>
                            <?php echo htmlspecialchars($prompt['author']); ?>님의 프롬프트 보기
                        </a>
                    </div>
                </div>

                <!-- Tags -->
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6">
                    <h3 class="font-bold text-sm mb-4">태그</h3>
                    <div class="flex flex-wrap gap-2">
                        <?php foreach($allTags as $tag): ?>
                        <a href="prompt_list.php?tag=<?php echo urlencode($tag); ?>" class="text-xs px-3 py-1.5 rounded-full border border-suno-border bg-suno-dark text-suno-muted hover:bg-suno-accent/10 hover:text-suno-accent2 hover:border-suno-accent/20 transition-all cursor-pointer">
                            <?php echo $tag; ?>
                        </a>
                        <?php endforeach; ?>
                    </div>
                </div>

                <!-- Related Prompts -->
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6">
                    <h3 class="font-bold text-sm mb-4">관련 프롬프트</h3>
                    <div class="space-y-3">
                        <?php foreach($relatedPrompts as $related): ?>
                        <a href="prompt_detail.php?id=<?php echo $related['id']; ?>" class="related-card block border border-suno-border rounded-xl p-4 bg-suno-dark">
                            <div class="flex flex-wrap gap-1.5 mb-2">
                                <?php foreach($related['genres'] as $g): ?>
                                <span class="text-[10px] px-2 py-0.5 rounded-full bg-suno-accent/10 text-suno-accent2 border border-suno-accent/20"><?php echo $g; ?></span>
                                <?php endforeach; ?>
                            </div>
                            <h4 class="related-title text-sm font-semibold leading-snug mb-2 transition-colors"><?php echo htmlspecialchars($related['title']); ?></h4>
                            <div class="flex items-center justify-between text-xs text-suno-muted/60">
                                <span><?php echo htmlspecialchars($related['author']); ?></span>
                                <span class="flex items-center gap-1">
                                    <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                                        <path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/>
                                    </svg>
                                    <?php echo $related['likes']; ?>
                                </span>
                            </div>
                        </a>
                        <?php endforeach; ?>
                    </div>
                </div>
            </div>
        </div>
    </div>
</main>

<script>
function copyPrompt() {
    const text = document.getElementById('promptContent').textContent;
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById('copyBtn');
        const textEl = document.getElementById('copyText');
        textEl.textContent = '복사됨!';
        btn.classList.add('bg-green-500/20');
        setTimeout(() => {
            textEl.textContent = '복사하기';
            btn.classList.remove('bg-green-500/20');
        }, 2000);
    });
}

function copyLyrics() {
    const text = document.getElementById('lyricsContent').textContent;
    navigator.clipboard.writeText(text).then(() => {
        const btn = document.getElementById('copyLyricsBtn');
        const textEl = document.getElementById('copyLyricsText');
        textEl.textContent = '복사됨!';
        btn.classList.add('bg-green-500/20');
        setTimeout(() => {
            textEl.textContent = '복사하기';
            btn.classList.remove('bg-green-500/20');
        }, 2000);
    });
}

function toggleLike(btn) {
    <?php if (!$currentUser): ?>
    alert('로그인이 필요합니다.');
    window.location.href = 'login.php';
    return;
    <?php endif; ?>

    const formData = new FormData();
    formData.append('type', 'prompt');
    formData.append('target_id', '<?php echo $promptId; ?>');

    fetch('like_ok.php', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            const countEl = document.getElementById('promptLikeCount');
            if (data.liked) {
                btn.classList.remove('text-suno-muted');
                btn.classList.add('text-pink-500', 'border-pink-500/30', 'bg-pink-500/10');
            } else {
                btn.classList.remove('text-pink-500', 'border-pink-500/30', 'bg-pink-500/10');
                btn.classList.add('text-suno-muted');
            }
            countEl.textContent = data.like_count;
        } else {
            alert(data.message || '오류가 발생했습니다.');
        }
    })
    .catch(() => alert('서버 오류가 발생했습니다.'));
}

function toggleSave(btn) {
    <?php if (!$currentUser): ?>
    alert('로그인이 필요합니다.');
    window.location.href = 'login.php';
    return;
    <?php endif; ?>

    const formData = new FormData();
    formData.append('type', 'prompt');
    formData.append('target_id', '<?php echo $promptId; ?>');

    fetch('bookmark_ok.php', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            const countEl = document.getElementById('promptSaveCount');
            const svgEl = btn.querySelector('svg');
            if (data.bookmarked) {
                btn.classList.remove('text-suno-muted');
                btn.classList.add('text-yellow-500', 'border-yellow-500/30', 'bg-yellow-500/10');
                svgEl.setAttribute('fill', 'currentColor');
            } else {
                btn.classList.remove('text-yellow-500', 'border-yellow-500/30', 'bg-yellow-500/10');
                btn.classList.add('text-suno-muted');
                svgEl.setAttribute('fill', 'none');
            }
            countEl.textContent = data.count;
        } else {
            alert(data.message || '오류가 발생했습니다.');
        }
    })
    .catch(() => alert('서버 오류가 발생했습니다.'));
}

function sharePrompt() {
    const shareData = {
        title: <?php echo json_encode($prompt['title']); ?>,
        text: <?php echo json_encode($prompt['title'] . ' - SUNO 프롬프트 공유'); ?>,
        url: window.location.href
    };

    if (navigator.share) {
        navigator.share(shareData).catch(() => {});
    } else {
        navigator.clipboard.writeText(window.location.href).then(() => {
            alert('링크가 클립보드에 복사되었습니다.');
        });
    }
}

function toggleSection(sectionId, toggle) {
    const section = document.getElementById(sectionId);
    if (!section) return;
    const isHidden = section.style.display === 'none';
    section.style.display = isHidden ? '' : 'none';
    if (isHidden) {
        toggle.classList.remove('collapsed');
    } else {
        toggle.classList.add('collapsed');
    }
}

function toggleCommentLike(btn, commentId) {
    <?php if (!$currentUser): ?>
    alert('로그인이 필요합니다.');
    window.location.href = 'login.php';
    return;
    <?php endif; ?>

    const formData = new FormData();
    formData.append('type', 'prompt_comment');
    formData.append('target_id', commentId);

    fetch('like_ok.php', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            const countEl = btn.querySelector('span');
            if (data.liked) {
                btn.classList.remove('text-suno-muted/50', 'hover:text-suno-accent2');
                btn.classList.add('text-pink-500');
            } else {
                btn.classList.remove('text-pink-500');
                btn.classList.add('text-suno-muted/50', 'hover:text-suno-accent2');
            }
            countEl.textContent = data.like_count;
        } else {
            alert(data.message || '오류가 발생했습니다.');
        }
    })
    .catch(() => alert('서버 오류가 발생했습니다.'));
}

function toggleReplyForm(commentId) {
    const form = document.getElementById('replyForm-' + commentId);
    if (!form) return;
    document.querySelectorAll('[id^="replyForm-"]').forEach(f => {
        if (f.id !== 'replyForm-' + commentId) f.classList.add('hidden');
    });
    form.classList.toggle('hidden');
    if (!form.classList.contains('hidden')) {
        form.querySelector('textarea').focus();
    }
}

var ftAudio = document.getElementById('finishedTrackAudio');
if (ftAudio) {
    var ftPlaying = false;
    var ftBtn = null;
    var ftProgressBar = null;
    var ftCurrentTime = null;

    ftAudio.addEventListener('loadedmetadata', function() {});
    ftAudio.addEventListener('timeupdate', function() {
        if (!ftProgressBar) return;
        var pct = (ftAudio.currentTime / ftAudio.duration) * 100;
        ftProgressBar.style.width = pct + '%';
        if (ftCurrentTime) {
            var m = Math.floor(ftAudio.currentTime / 60);
            var s = Math.floor(ftAudio.currentTime % 60);
            ftCurrentTime.textContent = m + ':' + (s < 10 ? '0' : '') + s;
        }
    });
    ftAudio.addEventListener('ended', function() {
        ftPlaying = false;
        if (ftBtn) {
            ftBtn.innerHTML = '<svg class="w-3.5 h-3.5 text-white ml-px" fill="currentColor" viewBox="0 0 20 20"><path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/></svg>';
        }
        if (ftProgressBar) ftProgressBar.style.width = '0%';
        if (ftCurrentTime) ftCurrentTime.textContent = '0:00';
    });
}

window.toggleFinishedTrackPlay = function(btn) {
    if (!ftAudio) return;
    ftBtn = btn;
    if (!ftProgressBar) ftProgressBar = document.getElementById('ftProgress');
    if (!ftCurrentTime) ftCurrentTime = document.getElementById('ftCurrentTime');

    if (ftPlaying) {
        ftAudio.pause();
        ftPlaying = false;
        btn.innerHTML = '<svg class="w-3.5 h-3.5 text-white ml-px" fill="currentColor" viewBox="0 0 20 20"><path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/></svg>';
    } else {
        ftAudio.play();
        ftPlaying = true;
        btn.innerHTML = '<svg class="w-3.5 h-3.5 text-white" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M18 10a8 8 0 11-16 0 8 8 0 0116 0zM7 8a1 1 0 012 0v4a1 1 0 11-2 0V8zm5-1a1 1 0 00-1 1v4a1 1 0 102 0V8a1 1 0 00-1-1z" clip-rule="evenodd"/></svg>';
    }
};

window.seekFinishedTrack = function(e) {
    if (!ftAudio || !ftAudio.duration) return;
    var rect = e.currentTarget.getBoundingClientRect();
    var pct = (e.clientX - rect.left) / rect.width;
    ftAudio.currentTime = pct * ftAudio.duration;
};
</script>

<?php include 'report_modal.php'; ?>
<?php include 'footer.php'; ?>
