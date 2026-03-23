<?php
require_once 'db.php';

// 게시판 시각 설정
$boardVisual = [
    'notice' => ['name' => '공지사항', 'color' => 'text-rose-400', 'bg' => 'bg-rose-500/10 border-rose-500/20',
        'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 110-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511l-.657.38a.75.75 0 01-1.021-.27l-.112-.194a4.504 4.504 0 01-.585-1.422M10.34 15.84a24.1 24.1 0 005.292-1.692"/>'],
    'free' => ['name' => '자유게시판', 'color' => 'text-emerald-400', 'bg' => 'bg-emerald-500/10 border-emerald-500/20',
        'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"/>'],
    'qna' => ['name' => '질문/답변', 'color' => 'text-blue-400', 'bg' => 'bg-blue-500/10 border-blue-500/20',
        'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z"/>'],
    'info' => ['name' => '정보', 'color' => 'text-teal-400', 'bg' => 'bg-teal-500/10 border-teal-500/20',
        'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18"/>'],
    'collab' => ['name' => '협업', 'color' => 'text-amber-400', 'bg' => 'bg-amber-500/10 border-amber-500/20',
        'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z"/>'],
];

// 카테고리 색상 매핑
$categoryColorMap = [
    '공지' => 'text-rose-400', '업데이트' => 'text-cyan-400', '이벤트' => 'text-amber-400', '점검' => 'text-zinc-400',
    '잡담' => 'text-zinc-400', '후기' => 'text-amber-400', '토론' => 'text-rose-400',
    '작품 공유' => 'text-suno-accent2', '추천' => 'text-violet-400',
    '프롬프트' => 'text-violet-400', '저작권' => 'text-rose-400', '기술' => 'text-cyan-400',
    '수익화' => 'text-amber-400', 'Suno 기본' => 'text-blue-400',
    '가이드' => 'text-cyan-400', '뉴스' => 'text-blue-400', '팁' => 'text-amber-400',
    '보컬 구함' => 'text-pink-400', '프로젝트' => 'text-emerald-400',
    '믹싱/마스터링' => 'text-cyan-400', '영상 제작' => 'text-amber-400', '작사' => 'text-violet-400',
    '기타' => 'text-zinc-400',
];

// 현재 게시판 결정 - DB 우선 검증
$currentBoard = isset($_GET['board']) ? $_GET['board'] : 'free';
$_boardCheck = $pdo->prepare('SELECT * FROM boards WHERE board_key = ? AND is_active = 1');
$_boardCheck->execute([$currentBoard]);
$_boardRow = $_boardCheck->fetch();
if (!$_boardRow) $currentBoard = 'free';
if (isset($boardVisual[$currentBoard])) {
    $board = $boardVisual[$currentBoard];
    if (!empty($_boardRow['icon_svg']) && strpos($_boardRow['icon_svg'], 'fa-') !== false) {
        $board['icon'] = $_boardRow['icon_svg'];
        $board['icon_type'] = 'fa';
    } else {
        $board['icon_type'] = 'svg';
    }
} else {
    $iconSvg = $_boardRow['icon_svg'] ?? '';
    $isFa = !empty($iconSvg) && strpos($iconSvg, 'fa-') !== false;
    $board = [
        'name' => $_boardRow['board_name'] ?? $currentBoard,
        'color' => ($_boardRow['color_class'] ?? '') ?: 'text-zinc-400',
        'bg' => ($_boardRow['bg_class'] ?? '') ?: 'bg-zinc-500/10 border-zinc-500/20',
        'icon' => $iconSvg,
        'icon_type' => $isFa ? 'fa' : 'svg',
    ];
}

// 게시물 ID 가져오기
$postId = isset($_GET['id']) ? (int)$_GET['id'] : 0;
if ($postId <= 0) {
    header('Location: board_list.php?board=' . $currentBoard);
    exit;
}

// 게시물 조회 (조회수 증가 포함)
$pdo->prepare('UPDATE posts SET view_count = view_count + 1 WHERE id = ?')->execute([$postId]);

$stmtPost = $pdo->prepare('
    SELECT posts.*, users.nickname as author, users.avatar_color, users.id as author_id,
           board_categories.category_name as category,
           boards.board_type
    FROM posts
    JOIN users ON posts.user_id = users.id
    LEFT JOIN board_categories ON posts.category_id = board_categories.id
    JOIN boards ON posts.board_id = boards.id
    WHERE posts.id = ?
');
$stmtPost->execute([$postId]);
$post = $stmtPost->fetch();

if (!$post) {
    header('Location: board_list.php?board=' . $currentBoard);
    exit;
}

// 카테고리 색상
$categoryName = $post['category'] ? $post['category'] : '';
$categoryColor = isset($categoryColorMap[$categoryName]) ? $categoryColorMap[$categoryName] : 'text-zinc-400';

// 댓글 조회
$stmtComments = $pdo->prepare('
    SELECT post_comments.*, users.nickname as author, users.avatar_color
    FROM post_comments
    JOIN users ON post_comments.user_id = users.id
    WHERE post_comments.post_id = ?
    ORDER BY post_comments.is_best_answer DESC, post_comments.created_at ASC
');
$stmtComments->execute([$postId]);
$comments = $stmtComments->fetchAll();

// 댓글을 트리 구조로 정리 (부모 → 자식)
$rootComments = [];
$childComments = [];
foreach ($comments as $c) {
    if ($c['parent_id']) {
        $childComments[$c['parent_id']][] = $c;
    } else {
        $rootComments[] = $c;
    }
}

// 현재 유저 좋아요 여부
$userLikedPost = false;
$userLikedCommentIds = [];
if ($currentUser) {
    $likeCheckStmt = $pdo->prepare('SELECT id FROM post_likes WHERE post_id = ? AND user_id = ?');
    $likeCheckStmt->execute([$postId, $currentUser['id']]);
    $userLikedPost = (bool)$likeCheckStmt->fetch();

    // 댓글 좋아요 목록
    $clStmt = $pdo->prepare('SELECT comment_id FROM post_comment_likes WHERE user_id = ?');
    $clStmt->execute([$currentUser['id']]);
    $userLikedCommentIds = array_column($clStmt->fetchAll(), 'comment_id');
}

// 현재 유저 북마크 여부
$userBookmarked = false;
if ($currentUser) {
    $bmStmt = $pdo->prepare('SELECT id FROM bookmarks WHERE user_id = ? AND post_id = ?');
    $bmStmt->execute([$currentUser['id'], $postId]);
    $userBookmarked = (bool)$bmStmt->fetch();
}

// 이전/다음글 조회
$stmtNext = $pdo->prepare('
    SELECT id, title FROM posts
    WHERE board_id = ? AND created_at > ? AND id != ?
    ORDER BY created_at ASC LIMIT 1
');
$stmtNext->execute([$post['board_id'], $post['created_at'], $postId]);
$nextPost = $stmtNext->fetch();

$stmtPrev = $pdo->prepare('
    SELECT id, title FROM posts
    WHERE board_id = ? AND created_at < ? AND id != ?
    ORDER BY created_at DESC LIMIT 1
');
$stmtPrev->execute([$post['board_id'], $post['created_at'], $postId]);
$prevPost = $stmtPrev->fetch();

$pageTitle = $post['title'];
?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<style>
    .comment-item { transition: all 0.2s ease; }
    .comment-item:hover { background: rgba(139,92,246,0.02); }
    .like-btn { transition: all 0.2s ease; }
    .like-btn:hover { color: #f43f5e; }
    .like-btn.liked { color: #f43f5e; }
    .action-btn { transition: all 0.15s ease; }
    .action-btn:hover { background: rgba(255,255,255,0.05); }
    /* Article content styling */
    .article-content h1, .article-content h2, .article-content h3 { font-weight: 700; margin: 1.2em 0 0.5em; }
    .article-content h1 { font-size: 1.5em; }
    .article-content h2 { font-size: 1.3em; }
    .article-content h3 { font-size: 1.1em; }
    .article-content p { margin-bottom: 0.6em; line-height: 1.8; color: #d4d4d8; }
    .article-content ul, .article-content ol { padding-left: 1.5em; margin-bottom: 0.8em; }
    .article-content li { margin-bottom: 0.4em; line-height: 1.7; color: #d4d4d8; }
    .article-content strong { color: #fff; font-weight: 600; }
    .article-content a { color: #a78bfa; text-decoration: underline; }
    .article-content img { border-radius: 12px; margin: 1em 0; max-width: 100%; }
    .article-content blockquote {
        border-left: 3px solid #8b5cf6;
        padding: 0.5em 1em;
        margin: 1em 0;
        background: rgba(139,92,246,0.05);
        border-radius: 0 8px 8px 0;
        color: #a1a1aa;
    }
    .best-badge {
        background: linear-gradient(135deg, rgba(139,92,246,0.15), rgba(167,139,250,0.1));
        border: 1px solid rgba(139,92,246,0.3);
    }
</style>

<div class="pt-20">

    <!-- Breadcrumb -->
    <section class="border-b border-suno-border bg-suno-surface/20">
        <div class="max-w-4xl mx-auto px-6 py-3">
            <div class="flex items-center gap-2 text-xs text-suno-muted">
                <a href="board_list.php?board=<?php echo $currentBoard; ?>" class="hover:text-white transition-colors"><?php echo htmlspecialchars($board['name']); ?></a>
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                <span class="text-suno-muted/60 truncate max-w-[200px] sm:max-w-none"><?php echo htmlspecialchars($post['title']); ?></span>
            </div>
        </div>
    </section>

    <!-- Post Content -->
    <section class="py-8">
        <div class="max-w-4xl mx-auto px-6">

            <!-- Post Header -->
            <div class="mb-6">
                <!-- Category + Title -->
                <div class="flex items-center gap-2 mb-3 flex-wrap">
                    <?php if ($categoryName): ?>
                    <span class="text-xs font-semibold <?php echo $categoryColor; ?> bg-suno-surface border border-suno-border px-2.5 py-0.5 rounded-full"><?php echo htmlspecialchars($categoryName); ?></span>
                    <?php endif; ?>
                </div>
                <h1 class="text-xl sm:text-2xl font-bold leading-snug mb-4"><?php echo htmlspecialchars($post['title']); ?></h1>

                <!-- Author + Meta -->
                <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 pb-5 border-b border-suno-border">
                    <div class="flex items-center gap-3">
                        <a href="profile.php?id=<?php echo $post['author_id']; ?>" class="w-9 h-9 rounded-full bg-gradient-to-r <?php echo $post['avatar_color'] ? $post['avatar_color'] : getAvatarColor($post['author_id']); ?> flex items-center justify-center text-xs font-bold shrink-0 hover:ring-2 hover:ring-suno-accent/50 transition-all">
                            <?php echo mb_substr($post['author'], 0, 1); ?>
                        </a>
                        <div>
                            <a href="profile.php?id=<?php echo $post['author_id']; ?>" class="text-sm font-semibold hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($post['author']); ?></a>
                            <p class="text-xs text-suno-muted"><?php echo $post['created_at']; ?> · 조회 <?php echo number_format($post['view_count']); ?></p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        <button onclick="sharePost()" class="action-btn flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-suno-muted" id="shareBtn">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.367 2.684 3 3 0 00-5.367-2.684z"/></svg>
                            <span>공유</span>
                        </button>
                        <button onclick="toggleBookmark(this)" class="action-btn flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs <?php echo $userBookmarked ? 'text-suno-accent' : 'text-suno-muted'; ?>" id="bookmarkBtn">
                            <svg class="w-3.5 h-3.5" fill="<?php echo $userBookmarked ? 'currentColor' : 'none'; ?>" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/></svg>
                            <span><?php echo $userBookmarked ? '북마크됨' : '북마크'; ?></span>
                        </button>
                        <?php if ($currentUser && $currentUser['id'] != $post['author_id']): ?>
                        <button onclick="openReportModal('post', <?php echo $postId; ?>)" class="action-btn flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-suno-muted" title="신고">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/></svg>
                            <span>신고</span>
                        </button>
                        <?php endif; ?>
                        <?php if ($currentUser && $currentUser['id'] == $post['author_id']): ?>
                        <div class="relative" id="moreMenuWrapper">
                            <button onclick="toggleMoreMenu(event)" class="action-btn flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-suno-muted">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 5v.01M12 12v.01M12 19v.01M12 6a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2zm0 7a1 1 0 110-2 1 1 0 010 2z"/></svg>
                            </button>
                            <div id="moreMenu" class="hidden absolute right-0 top-full mt-1 w-28 bg-suno-card border border-suno-border rounded-xl shadow-2xl shadow-black/40 py-1.5 z-50">
                                <a href="board_edit.php?board=<?php echo $currentBoard; ?>&id=<?php echo $postId; ?>" class="flex items-center gap-2 px-4 py-2 text-sm text-white/80 hover:bg-suno-surface/80 transition-colors rounded-lg mx-1">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
                                    수정
                                </a>
                                <button onclick="deletePost()" class="w-full flex items-center gap-2 px-4 py-2 text-sm text-red-400 hover:bg-suno-surface/80 transition-colors rounded-lg mx-1">
                                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M14.74 9l-.346 9m-4.788 0L9.26 9m9.968-3.21c.342.052.682.107 1.022.166m-1.022-.165L18.16 19.673a2.25 2.25 0 01-2.244 2.077H8.084a2.25 2.25 0 01-2.244-2.077L4.772 5.79m14.456 0a48.108 48.108 0 00-3.478-.397m-12 .562c.34-.059.68-.114 1.022-.165m0 0a48.11 48.11 0 013.478-.397m7.5 0v-.916c0-1.18-.91-2.164-2.09-2.201a51.964 51.964 0 00-3.32 0c-1.18.037-2.09 1.022-2.09 2.201v.916m7.5 0a48.667 48.667 0 00-7.5 0"/></svg>
                                    삭제
                                </button>
                            </div>
                        </div>
                        <?php endif; ?>
                    </div>
                </div>
            </div>

            <?php if($currentBoard === 'collab'): ?>
            <!-- 협업 정보 카드 -->
            <div class="bg-suno-card border border-amber-500/20 rounded-xl p-5 mb-6">
                <div class="grid grid-cols-2 sm:grid-cols-3 gap-4">
                    <div>
                        <p class="text-[10px] text-suno-muted uppercase tracking-wider mb-1">상태</p>
                        <div class="flex items-center gap-2">
                            <span id="collabStatusBadge" class="inline-flex items-center gap-1 text-xs font-semibold <?php echo !$post['is_closed'] ? 'text-emerald-400' : 'text-suno-muted'; ?>">
                                <span class="w-1.5 h-1.5 rounded-full <?php echo !$post['is_closed'] ? 'bg-emerald-400' : 'bg-suno-muted'; ?>"></span>
                                <span id="collabStatusText"><?php echo $post['is_closed'] ? '모집완료' : '모집중'; ?></span>
                            </span>
                            <?php if($currentUser && $currentUser['id'] == $post['user_id']): ?>
                            <button onclick="toggleCollabStatus()" class="text-[11px] font-medium <?php echo $post['is_closed'] ? 'text-emerald-400 hover:text-emerald-300 border-emerald-500/30 hover:border-emerald-400/50 bg-emerald-500/5 hover:bg-emerald-500/10' : 'text-amber-400 hover:text-amber-300 border-amber-500/30 hover:border-amber-400/50 bg-amber-500/5 hover:bg-amber-500/10'; ?> border px-3 py-1 rounded-lg transition-all" id="collabToggleBtn">
                                <?php echo $post['is_closed'] ? '↩ 모집중으로 변경' : '✓ 모집완료로 변경'; ?>
                            </button>
                            <?php endif; ?>
                        </div>
                    </div>
                    <div>
                        <p class="text-[10px] text-suno-muted uppercase tracking-wider mb-1">모집 인원</p>
                        <p class="text-sm font-semibold"><?php echo $post['recruit_count'] ? $post['recruit_count'] : '-'; ?>명</p>
                    </div>
                    <div class="col-span-2 sm:col-span-1">
                        <p class="text-[10px] text-suno-muted uppercase tracking-wider mb-1">연락 방법</p>
                        <?php
                        $contactType = $post['contact_type'] ?? '';
                        $contactInfo = $post['contact_info'] ?? '';
                        ?>
                        <div id="contactClosed" class="<?php echo $post['is_closed'] ? '' : 'hidden'; ?>">
                            <span class="text-sm text-suno-muted/60">모집 완료</span>
                        </div>
                        <div id="contactOpen" class="<?php echo $post['is_closed'] ? 'hidden' : ''; ?>">
                        <?php if ($contactInfo):
                            if ($contactType === 'openchat'): ?>
                            <a href="<?php echo htmlspecialchars($contactInfo); ?>" target="_blank" class="text-sm text-suno-accent hover:text-suno-accent2 transition-colors truncate block flex items-center gap-1">
                                <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"/></svg>
                                오픈채팅 참여하기
                            </a>
                            <?php elseif ($contactType === 'instagram'):
                                $instaId = ltrim($contactInfo, '@');
                            ?>
                            <a href="https://instagram.com/<?php echo htmlspecialchars($instaId); ?>" target="_blank" class="text-sm text-suno-accent hover:text-suno-accent2 transition-colors truncate block flex items-center gap-1">
                                <svg class="w-3.5 h-3.5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"/></svg>
                                @<?php echo htmlspecialchars($instaId); ?>
                            </a>
                            <?php elseif ($contactType === 'phone'):
                                $maskedPhone = mb_substr($contactInfo, 0, 3) . '-****-' . mb_substr($contactInfo, -4);
                            ?>
                            <div class="flex items-center gap-2">
                                <span class="text-sm text-white" id="phoneDisplay"><?php echo $maskedPhone; ?></span>
                                <button onclick="revealPhone(this)" class="text-[10px] text-suno-accent hover:text-suno-accent2 border border-suno-accent/30 px-2 py-0.5 rounded transition-all" data-phone="<?php echo htmlspecialchars($contactInfo); ?>">보기</button>
                            </div>
                            <?php elseif ($contactType === 'email'): ?>
                            <span class="text-sm text-white"><?php echo htmlspecialchars($contactInfo); ?></span>
                            <?php else: ?>
                            <span class="text-sm text-white"><?php echo htmlspecialchars($contactInfo); ?></span>
                            <?php endif;
                        else: ?>
                        <p class="text-sm text-suno-muted">-</p>
                        <?php endif; ?>
                        </div>
                    </div>
                </div>
            </div>
            <?php endif; ?>

            <!-- Article Body -->
            <div class="article-content text-sm mb-8">
                <?php echo $post['content']; ?>
            </div>

            <!-- Like / Actions Bar -->
            <div class="flex items-center justify-center py-6 border-t border-b border-suno-border mb-8">
                <button onclick="toggleLike(this)" class="like-btn flex flex-col items-center gap-1.5 px-8 py-3 rounded-xl hover:bg-suno-surface/50 <?php echo $userLikedPost ? 'text-pink-500' : 'text-suno-muted'; ?> transition-colors">
                    <svg class="w-6 h-6" fill="<?php echo $userLikedPost ? 'currentColor' : 'none'; ?>" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z"/>
                    </svg>
                    <span class="text-sm font-semibold" id="likeCount"><?php echo $post['like_count']; ?></span>
                </button>
            </div>

            <!-- Comments Section -->
            <div class="mb-10">
                <div class="flex items-center justify-between mb-5">
                    <h2 class="text-base font-bold">댓글 <span class="text-suno-accent ml-1"><?php echo count($comments); ?></span></h2>
                </div>

                <!-- Comment Write -->
                <?php if($currentUser): ?>
                <form action="comment_ok.php" method="POST" class="flex gap-3 mb-6">
                    <input type="hidden" name="type" value="post">
                    <input type="hidden" name="target_id" value="<?php echo $postId; ?>">
                    <div class="w-8 h-8 rounded-full bg-gradient-to-r <?php echo $currentUser['avatar_color'] ?: 'from-suno-accent to-suno-accent2'; ?> flex items-center justify-center text-xs font-bold shrink-0"><?php echo mb_substr($currentUser['nickname'], 0, 1); ?></div>
                    <div class="flex-1">
                        <textarea name="content" placeholder="댓글을 작성해주세요..." rows="3" required
                            class="w-full bg-suno-card border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/40 focus:outline-none focus:border-suno-accent/50 resize-none transition-all"></textarea>
                        <div class="flex justify-end mt-2">
                            <button type="submit" class="bg-suno-accent hover:bg-suno-accent2 text-white text-xs font-semibold px-5 py-2 rounded-lg transition-all">등록</button>
                        </div>
                    </div>
                </form>
                <?php else: ?>
                <div class="mb-6 p-4 bg-suno-surface border border-suno-border rounded-xl text-center">
                    <p class="text-sm text-suno-muted">댓글을 작성하려면 <a href="login.php" class="text-suno-accent hover:text-suno-accent2">로그인</a>해주세요.</p>
                </div>
                <?php endif; ?>

                <!-- Comment List -->
                <div class="space-y-0 divide-y divide-suno-border/50">
                    <?php foreach($rootComments as $c): ?>
                    <?php $isAuthor = ($c['user_id'] == $post['user_id']); $commentLiked = in_array($c['id'], $userLikedCommentIds); ?>
                    <div class="comment-item py-4 <?php echo $c['is_best_answer'] ? 'relative' : ''; ?>">
                        <?php if($c['is_best_answer'] && $currentBoard === 'qna'): ?>
                        <div class="best-badge inline-flex items-center gap-1 text-[10px] font-semibold text-suno-accent2 px-2 py-0.5 rounded-full mb-2">
                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M16.707 5.293a1 1 0 010 1.414l-8 8a1 1 0 01-1.414 0l-4-4a1 1 0 011.414-1.414L8 12.586l7.293-7.293a1 1 0 011.414 0z" clip-rule="evenodd"/></svg>
                            채택된 답변
                        </div>
                        <?php endif; ?>

                        <div class="flex gap-3">
                            <a href="profile.php?id=<?php echo $c['user_id']; ?>" class="w-7 h-7 rounded-full bg-gradient-to-r <?php echo $c['avatar_color'] ? $c['avatar_color'] : getAvatarColor($c['user_id']); ?> flex items-center justify-center text-[10px] font-bold shrink-0 mt-0.5 hover:ring-2 hover:ring-suno-accent/50 transition-all">
                                <?php echo mb_substr($c['author'], 0, 1); ?>
                            </a>
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2 mb-1">
                                    <a href="profile.php?id=<?php echo $c['user_id']; ?>" class="text-xs font-semibold hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($c['author']); ?></a>
                                    <?php if($isAuthor): ?>
                                    <span class="text-[9px] font-semibold bg-suno-accent/15 text-suno-accent2 px-1.5 py-px rounded">작성자</span>
                                    <?php endif; ?>
                                    <span class="text-[11px] text-suno-muted/50"><?php echo timeAgo($c['created_at']); ?></span>
                                </div>
                                <p class="text-sm text-zinc-300 leading-relaxed mb-2"><?php echo nl2br(htmlspecialchars($c['content'])); ?></p>
                                <div class="flex items-center gap-3">
                                    <button onclick="toggleCommentLike(this, <?php echo $c['id']; ?>)" class="like-btn flex items-center gap-1 text-xs <?php echo $commentLiked ? 'text-pink-500 liked' : 'text-suno-muted'; ?>" data-liked="<?php echo $commentLiked ? '1' : '0'; ?>">
                                        <svg class="w-3.5 h-3.5" fill="<?php echo $commentLiked ? 'currentColor' : 'none'; ?>" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
                                        </svg>
                                        <span class="comment-like-count"><?php echo $c['like_count']; ?></span>
                                    </button>
                                    <?php if($currentUser): ?>
                                    <button onclick="toggleReplyForm(<?php echo $c['id']; ?>)" class="text-xs text-suno-muted hover:text-white transition-colors">답글</button>
                                    <?php endif; ?>
                                </div>

                                <!-- 답글 입력 폼 (숨김) -->
                                <?php if($currentUser): ?>
                                <div id="replyForm-<?php echo $c['id']; ?>" class="hidden mt-3">
                                    <form action="comment_ok.php" method="POST" class="flex gap-2">
                                        <input type="hidden" name="type" value="post">
                                        <input type="hidden" name="target_id" value="<?php echo $postId; ?>">
                                        <input type="hidden" name="parent_id" value="<?php echo $c['id']; ?>">
                                        <div class="w-6 h-6 rounded-full bg-gradient-to-r <?php echo $currentUser['avatar_color'] ?: 'from-suno-accent to-suno-accent2'; ?> flex items-center justify-center text-[9px] font-bold shrink-0 mt-1"><?php echo mb_substr($currentUser['nickname'], 0, 1); ?></div>
                                        <div class="flex-1">
                                            <textarea name="content" placeholder="@<?php echo htmlspecialchars($c['author']); ?>에게 답글..." rows="2" required
                                                class="w-full bg-suno-surface border border-suno-border rounded-lg px-3 py-2 text-xs text-white placeholder-suno-muted/40 focus:outline-none focus:border-suno-accent/50 resize-none transition-all"></textarea>
                                            <div class="flex justify-end gap-2 mt-1.5">
                                                <button type="button" onclick="toggleReplyForm(<?php echo $c['id']; ?>)" class="text-xs text-suno-muted hover:text-white px-3 py-1.5 rounded-lg transition-colors">취소</button>
                                                <button type="submit" class="bg-suno-accent hover:bg-suno-accent2 text-white text-xs font-semibold px-4 py-1.5 rounded-lg transition-all">등록</button>
                                            </div>
                                        </div>
                                    </form>
                                </div>
                                <?php endif; ?>
                            </div>
                        </div>

                        <!-- 대댓글 (자식 댓글) -->
                        <?php if(!empty($childComments[$c['id']])): ?>
                        <div class="ml-10 mt-1 border-l-2 border-suno-border/30 pl-4 space-y-0">
                            <?php foreach($childComments[$c['id']] as $reply):
                                $replyIsAuthor = ($reply['user_id'] == $post['user_id']);
                                $replyLiked = in_array($reply['id'], $userLikedCommentIds);
                            ?>
                            <div class="comment-item py-3">
                                <div class="flex gap-2.5">
                                    <a href="profile.php?id=<?php echo $reply['user_id']; ?>" class="w-6 h-6 rounded-full bg-gradient-to-r <?php echo $reply['avatar_color'] ? $reply['avatar_color'] : getAvatarColor($reply['user_id']); ?> flex items-center justify-center text-[9px] font-bold shrink-0 mt-0.5 hover:ring-2 hover:ring-suno-accent/50 transition-all">
                                        <?php echo mb_substr($reply['author'], 0, 1); ?>
                                    </a>
                                    <div class="flex-1 min-w-0">
                                        <div class="flex items-center gap-2 mb-0.5">
                                            <a href="profile.php?id=<?php echo $reply['user_id']; ?>" class="text-xs font-semibold hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($reply['author']); ?></a>
                                            <?php if($replyIsAuthor): ?>
                                            <span class="text-[9px] font-semibold bg-suno-accent/15 text-suno-accent2 px-1.5 py-px rounded">작성자</span>
                                            <?php endif; ?>
                                            <span class="text-[11px] text-suno-muted/50"><?php echo timeAgo($reply['created_at']); ?></span>
                                        </div>
                                        <p class="text-[13px] text-zinc-300 leading-relaxed mb-1.5"><?php echo nl2br(htmlspecialchars($reply['content'])); ?></p>
                                        <div class="flex items-center gap-3">
                                            <button onclick="toggleCommentLike(this, <?php echo $reply['id']; ?>)" class="like-btn flex items-center gap-1 text-xs <?php echo $replyLiked ? 'text-pink-500 liked' : 'text-suno-muted'; ?>" data-liked="<?php echo $replyLiked ? '1' : '0'; ?>">
                                                <svg class="w-3 h-3" fill="<?php echo $replyLiked ? 'currentColor' : 'none'; ?>" stroke="currentColor" viewBox="0 0 24 24">
                                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4.318 6.318a4.5 4.5 0 000 6.364L12 20.364l7.682-7.682a4.5 4.5 0 00-6.364-6.364L12 7.636l-1.318-1.318a4.5 4.5 0 00-6.364 0z"/>
                                                </svg>
                                                <span class="comment-like-count"><?php echo $reply['like_count']; ?></span>
                                            </button>
                                        </div>
                                    </div>
                                </div>
                            </div>
                            <?php endforeach; ?>
                        </div>
                        <?php endif; ?>
                    </div>
                    <?php endforeach; ?>
                    <?php if (empty($comments)): ?>
                    <div class="py-8 text-center text-suno-muted text-sm">아직 댓글이 없습니다. 첫 댓글을 작성해보세요!</div>
                    <?php endif; ?>
                </div>
            </div>

            <!-- Navigation -->
            <div class="border-t border-suno-border pt-4 mb-8">
                <div class="space-y-0 divide-y divide-suno-border/50">
                    <?php if ($nextPost): ?>
                    <a href="board_detail.php?board=<?php echo $currentBoard; ?>&id=<?php echo $nextPost['id']; ?>" class="flex items-center gap-3 py-3 group">
                        <span class="text-xs text-suno-muted w-16 shrink-0">다음글</span>
                        <span class="text-sm text-zinc-300 group-hover:text-suno-accent2 transition-colors truncate"><?php echo htmlspecialchars($nextPost['title']); ?></span>
                    </a>
                    <?php else: ?>
                    <div class="flex items-center gap-3 py-3">
                        <span class="text-xs text-suno-muted w-16 shrink-0">다음글</span>
                        <span class="text-sm text-suno-muted/50">다음글이 없습니다.</span>
                    </div>
                    <?php endif; ?>
                    <?php if ($prevPost): ?>
                    <a href="board_detail.php?board=<?php echo $currentBoard; ?>&id=<?php echo $prevPost['id']; ?>" class="flex items-center gap-3 py-3 group">
                        <span class="text-xs text-suno-muted w-16 shrink-0">이전글</span>
                        <span class="text-sm text-zinc-300 group-hover:text-suno-accent2 transition-colors truncate"><?php echo htmlspecialchars($prevPost['title']); ?></span>
                    </a>
                    <?php else: ?>
                    <div class="flex items-center gap-3 py-3">
                        <span class="text-xs text-suno-muted w-16 shrink-0">이전글</span>
                        <span class="text-sm text-suno-muted/50">이전글이 없습니다.</span>
                    </div>
                    <?php endif; ?>
                </div>
            </div>

            <!-- Back to List -->
            <div class="flex items-center justify-center mb-6">
                <a href="board_list.php?board=<?php echo $currentBoard; ?>" class="inline-flex items-center gap-2 border border-suno-border hover:border-suno-accent/40 text-sm text-suno-muted hover:text-white px-6 py-2.5 rounded-xl transition-all">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M4 6h16M4 10h16M4 14h16M4 18h16"/></svg>
                    목록으로
                </a>
            </div>
        </div>
    </section>
</div>

<script>
function toggleLike(btn) {
    <?php if (!$currentUser): ?>
    alert('로그인이 필요합니다.');
    window.location.href = 'login.php';
    return;
    <?php endif; ?>

    const formData = new FormData();
    formData.append('type', 'post');
    formData.append('target_id', '<?php echo $postId; ?>');

    fetch('like_ok.php', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            const svg = btn.querySelector('svg');
            const count = document.getElementById('likeCount');
            if (data.liked) {
                svg.setAttribute('fill', 'currentColor');
                btn.classList.remove('text-suno-muted');
                btn.classList.add('text-pink-500', 'liked');
            } else {
                svg.setAttribute('fill', 'none');
                btn.classList.remove('text-pink-500', 'liked');
                btn.classList.add('text-suno-muted');
            }
            count.textContent = data.like_count;
        } else {
            alert(data.message || '오류가 발생했습니다.');
        }
    })
    .catch(() => alert('서버 오류가 발생했습니다.'));
}

function toggleReplyForm(commentId) {
    const form = document.getElementById('replyForm-' + commentId);
    if (!form) return;
    // 다른 열린 답글 폼 닫기
    document.querySelectorAll('[id^="replyForm-"]').forEach(f => {
        if (f.id !== 'replyForm-' + commentId) f.classList.add('hidden');
    });
    form.classList.toggle('hidden');
    if (!form.classList.contains('hidden')) {
        form.querySelector('textarea').focus();
    }
}

function toggleCommentLike(btn, commentId) {
    <?php if (!$currentUser): ?>
    alert('로그인이 필요합니다.');
    window.location.href = 'login.php';
    return;
    <?php endif; ?>

    const formData = new FormData();
    formData.append('type', 'comment');
    formData.append('target_id', commentId);

    fetch('like_ok.php', { method: 'POST', body: formData })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            const svg = btn.querySelector('svg');
            const count = btn.querySelector('.comment-like-count');
            if (data.liked) {
                svg.setAttribute('fill', 'currentColor');
                btn.classList.remove('text-suno-muted');
                btn.classList.add('text-pink-500', 'liked');
            } else {
                svg.setAttribute('fill', 'none');
                btn.classList.remove('text-pink-500', 'liked');
                btn.classList.add('text-suno-muted');
            }
            count.textContent = data.like_count;
        }
    })
    .catch(() => alert('서버 오류가 발생했습니다.'));
}

// 공유: 네이티브 공유 API 우선, 폴백으로 클립보드 복사
function sharePost() {
    const url = window.location.href;
    const title = <?php echo json_encode($post['title']); ?>;

    if (navigator.share) {
        navigator.share({ title: title, url: url }).catch(() => {});
    } else {
        navigator.clipboard.writeText(url).then(() => {
            const btn = document.getElementById('shareBtn');
            const span = btn.querySelector('span');
            span.textContent = '복사됨!';
            btn.classList.add('text-suno-accent');
            setTimeout(() => {
                span.textContent = '공유';
                btn.classList.remove('text-suno-accent');
            }, 2000);
        }).catch(() => {
            const textarea = document.createElement('textarea');
            textarea.value = url;
            document.body.appendChild(textarea);
            textarea.select();
            document.execCommand('copy');
            document.body.removeChild(textarea);
            alert('링크가 복사되었습니다.');
        });
    }
}

// 북마크: DB 기반 AJAX
function toggleBookmark(btn) {
    <?php if (!$currentUser): ?>
    alert('로그인이 필요합니다.');
    window.location.href = 'login.php';
    return;
    <?php endif; ?>

    const formData = new FormData();
    formData.append('post_id', '<?php echo $postId; ?>');

    fetch('bookmark_ok.php', { method: 'POST', body: formData })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            const svg = btn.querySelector('svg');
            const span = btn.querySelector('span');
            if (data.bookmarked) {
                svg.setAttribute('fill', 'currentColor');
                span.textContent = '북마크됨';
                btn.classList.add('text-suno-accent');
                btn.classList.remove('text-suno-muted');
            } else {
                svg.setAttribute('fill', 'none');
                span.textContent = '북마크';
                btn.classList.remove('text-suno-accent');
                btn.classList.add('text-suno-muted');
            }
        }
    })
    .catch(() => alert('서버 오류가 발생했습니다.'));
}

function toggleMoreMenu(e) {
    e.stopPropagation();
    document.getElementById('moreMenu').classList.toggle('hidden');
}

document.addEventListener('click', function(e) {
    var wrapper = document.getElementById('moreMenuWrapper');
    var menu = document.getElementById('moreMenu');
    if (wrapper && menu && !wrapper.contains(e.target)) {
        menu.classList.add('hidden');
    }
});

function deletePost() {
    if (!confirm('정말 삭제하시겠습니까? 이 작업은 되돌릴 수 없습니다.')) return;
    var form = document.createElement('form');
    form.method = 'POST';
    form.action = 'board_delete_ok.php';
    var bi = document.createElement('input');
    bi.type = 'hidden'; bi.name = 'board'; bi.value = '<?php echo $currentBoard; ?>';
    form.appendChild(bi);
    var pi = document.createElement('input');
    pi.type = 'hidden'; pi.name = 'id'; pi.value = '<?php echo $postId; ?>';
    form.appendChild(pi);
    document.body.appendChild(form);
    form.submit();
}

function toggleCollabStatus() {
    var fd = new FormData();
    fd.append('post_id', '<?php echo $postId; ?>');
    fetch('collab_toggle_ok.php', { method: 'POST', body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                var badge = document.getElementById('collabStatusBadge');
                var text = document.getElementById('collabStatusText');
                var btn = document.getElementById('collabToggleBtn');
                var contactClosed = document.getElementById('contactClosed');
                var contactOpen = document.getElementById('contactOpen');
                if (data.is_closed) {
                    text.textContent = '모집완료';
                    badge.className = 'inline-flex items-center gap-1 text-xs font-semibold text-suno-muted';
                    badge.querySelector('span').className = 'w-1.5 h-1.5 rounded-full bg-suno-muted';
                    btn.innerHTML = '↩ 모집중으로 변경';
                    btn.className = 'text-[11px] font-medium text-emerald-400 hover:text-emerald-300 border-emerald-500/30 hover:border-emerald-400/50 bg-emerald-500/5 hover:bg-emerald-500/10 border px-3 py-1 rounded-lg transition-all';
                    if (contactClosed) contactClosed.classList.remove('hidden');
                    if (contactOpen) contactOpen.classList.add('hidden');
                } else {
                    text.textContent = '모집중';
                    badge.className = 'inline-flex items-center gap-1 text-xs font-semibold text-emerald-400';
                    badge.querySelector('span').className = 'w-1.5 h-1.5 rounded-full bg-emerald-400';
                    btn.innerHTML = '✓ 모집완료로 변경';
                    btn.className = 'text-[11px] font-medium text-amber-400 hover:text-amber-300 border-amber-500/30 hover:border-amber-400/50 bg-amber-500/5 hover:bg-amber-500/10 border px-3 py-1 rounded-lg transition-all';
                    if (contactClosed) contactClosed.classList.add('hidden');
                    if (contactOpen) contactOpen.classList.remove('hidden');
                }
            } else {
                alert(data.message || '오류가 발생했습니다.');
            }
        })
        .catch(function() { alert('서버 오류가 발생했습니다.'); });
}

function revealPhone(btn) {
    var phone = btn.getAttribute('data-phone');
    document.getElementById('phoneDisplay').textContent = phone;
    btn.remove();
}
</script>

<?php include 'report_modal.php'; ?>
<?php include 'footer.php'; ?>
