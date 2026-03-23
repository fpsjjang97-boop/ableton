<?php
require_once 'db.php';
$pageTitle = '전체 게시물';

// 페이지네이션
$page = isset($_GET['page']) ? max(1, (int)$_GET['page']) : 1;
$perPage = 20;
$offset = ($page - 1) * $perPage;

// 정렬
$sort = isset($_GET['sort']) ? $_GET['sort'] : 'latest';
$orderBy = 'p.created_at DESC';
if ($sort === 'popular') {
    $orderBy = '(p.like_count * 3 + p.comment_count) DESC, p.created_at DESC';
} elseif ($sort === 'views') {
    $orderBy = 'p.view_count DESC, p.created_at DESC';
}

// 전체 게시물 수
$countStmt = $pdo->query('SELECT COUNT(*) FROM posts');
$totalPosts = (int)$countStmt->fetchColumn();
$totalPages = max(1, ceil($totalPosts / $perPage));
if ($page > $totalPages) $page = $totalPages;

// 게시물 조회
$stmt = $pdo->prepare("
    SELECT p.id, p.title, p.content, p.comment_count, p.like_count, p.view_count, p.created_at,
           u.nickname, u.avatar_color,
           b.board_key, b.board_name, b.color_class,
           bc.category_name
    FROM posts p
    JOIN users u ON p.user_id = u.id
    JOIN boards b ON p.board_id = b.id
    LEFT JOIN board_categories bc ON p.category_id = bc.id
    ORDER BY {$orderBy}
    LIMIT ? OFFSET ?
");
$stmt->execute([$perPage, $offset]);
$posts = $stmt->fetchAll();
?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<main class="pt-20 pb-16 min-h-screen">
    <div class="max-w-4xl mx-auto px-6">

        <!-- Header -->
        <div class="flex items-center justify-between mb-6 mt-4">
            <div>
                <h1 class="text-xl font-bold">전체 게시물</h1>
                <p class="text-sm text-suno-muted mt-1">총 <?php echo number_format($totalPosts); ?>개의 게시물</p>
            </div>
            <div class="flex items-center gap-2">
                <a href="all_posts.php?sort=latest" class="px-3 py-1.5 text-xs rounded-lg <?php echo $sort === 'latest' ? 'bg-suno-accent text-white font-semibold' : 'bg-suno-surface border border-suno-border text-suno-muted hover:text-white'; ?> transition-all">최신순</a>
                <a href="all_posts.php?sort=popular" class="px-3 py-1.5 text-xs rounded-lg <?php echo $sort === 'popular' ? 'bg-suno-accent text-white font-semibold' : 'bg-suno-surface border border-suno-border text-suno-muted hover:text-white'; ?> transition-all">인기순</a>
                <a href="all_posts.php?sort=views" class="px-3 py-1.5 text-xs rounded-lg <?php echo $sort === 'views' ? 'bg-suno-accent text-white font-semibold' : 'bg-suno-surface border border-suno-border text-suno-muted hover:text-white'; ?> transition-all">조회순</a>
            </div>
        </div>

        <!-- Divider -->
        <div class="border-t border-suno-border"></div>

        <!-- Post List -->
        <div class="divide-y divide-suno-border/60">
            <?php if (empty($posts)): ?>
            <div class="py-20 text-center">
                <p class="text-suno-muted">게시물이 없습니다.</p>
            </div>
            <?php else: ?>
            <?php foreach($posts as $post):
                $tag = !empty($post['category_name']) ? $post['category_name'] : $post['board_name'];
                $tag_color = !empty($post['color_class']) ? $post['color_class'] : 'text-suno-accent2';
                $created = new DateTime($post['created_at']);
                $today = new DateTime('today');
                $time = ($created >= $today) ? $created->format('H:i') : $created->format('m/d');
                $thumb = '';
                if (!empty($post['content']) && preg_match('/<img[^>]+src=["\']([^"\']+)["\']/', $post['content'], $m)) {
                    $thumb = $m[1];
                    if (strpos($thumb, 'http') !== 0) {
                        $thumb = ltrim($thumb, '/');
                    }
                }
            ?>
            <a href="board_detail.php?board=<?php echo urlencode($post['board_key']); ?>&id=<?php echo $post['id']; ?>" class="flex items-center gap-3 py-3 px-2 hover:bg-suno-surface/50 transition-colors group rounded-sm">
                <?php if(!empty($thumb)): ?>
                <div class="w-[72px] h-[52px] rounded bg-suno-surface flex-shrink-0 overflow-hidden">
                    <img src="<?php echo htmlspecialchars($thumb); ?>" alt="" class="w-full h-full object-cover" loading="lazy">
                </div>
                <?php endif; ?>
                <div class="flex-1 min-w-0">
                    <span class="text-sm text-zinc-200 group-hover:text-suno-accent2 transition-colors truncate block">
                        <?php echo htmlspecialchars($post['title']); ?>
                        <?php if($post['comment_count'] > 0): ?>
                        <span class="text-suno-accent font-bold ml-1">[<?php echo $post['comment_count']; ?>]</span>
                        <?php endif; ?>
                    </span>
                    <span class="text-xs text-suno-muted mt-0.5 block sm:hidden">
                        <?php echo htmlspecialchars($post['nickname']); ?> · <?php echo $time; ?>
                    </span>
                </div>
                <div class="hidden sm:flex items-center gap-2 flex-shrink-0 min-w-0 max-w-[140px]">
                    <span class="w-6 h-6 rounded-full bg-gradient-to-br <?php echo htmlspecialchars($post['avatar_color'] ?: 'from-suno-accent to-purple-600'); ?> flex items-center justify-center text-[10px] font-bold text-white/90 flex-shrink-0">
                        <?php echo mb_substr($post['nickname'] ?? '?', 0, 1); ?>
                    </span>
                    <span class="text-xs text-white/70 truncate"><?php echo htmlspecialchars($post['nickname'] ?? ''); ?></span>
                </div>
                <span class="hidden sm:block text-xs <?php echo $tag_color; ?> w-24 text-right flex-shrink-0 truncate"><?php echo htmlspecialchars($tag); ?></span>
                <span class="hidden sm:block text-suno-border">│</span>
                <div class="hidden sm:flex items-center gap-3 flex-shrink-0 text-xs text-suno-muted/60">
                    <span title="조회수">👁 <?php echo number_format($post['view_count']); ?></span>
                    <span title="좋아요">♥ <?php echo $post['like_count']; ?></span>
                </div>
                <span class="hidden sm:block text-suno-border">│</span>
                <span class="hidden sm:block text-xs text-suno-muted/60 w-12 text-right flex-shrink-0"><?php echo $time; ?></span>
            </a>
            <?php endforeach; ?>
            <?php endif; ?>
        </div>

        <!-- Pagination -->
        <?php if ($totalPages > 1): ?>
        <div class="flex items-center justify-center gap-1 mt-8">
            <?php if ($page > 1): ?>
            <a href="all_posts.php?page=<?php echo $page - 1; ?>&sort=<?php echo $sort; ?>" class="w-8 h-8 rounded-lg border border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/50 transition-all text-xs flex items-center justify-center">&#9664;</a>
            <?php endif; ?>

            <?php
            $startPage = max(1, $page - 4);
            $endPage = min($totalPages, $startPage + 9);
            if ($endPage - $startPage < 9) $startPage = max(1, $endPage - 9);
            for ($i = $startPage; $i <= $endPage; $i++):
            ?>
            <a href="all_posts.php?page=<?php echo $i; ?>&sort=<?php echo $sort; ?>"
               class="w-8 h-8 rounded-lg <?php echo $i === $page ? 'bg-suno-accent text-white font-bold' : 'border border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/50 transition-all'; ?> text-xs flex items-center justify-center"><?php echo $i; ?></a>
            <?php endfor; ?>

            <?php if ($page < $totalPages): ?>
            <a href="all_posts.php?page=<?php echo $page + 1; ?>&sort=<?php echo $sort; ?>" class="w-8 h-8 rounded-lg border border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/50 transition-all text-xs flex items-center justify-center">&#9654;</a>
            <?php endif; ?>
        </div>
        <?php endif; ?>

    </div>
</main>

<?php include 'footer.php'; ?>
