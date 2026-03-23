<?php
require_once 'db.php';
$pageTitle = '유저 프로필';
?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<?php
// 프로필 대상 유저 결정
$profileUserId = null;
if (isset($_GET['id'])) {
    $profileUserId = (int)$_GET['id'];
} elseif ($currentUser) {
    $profileUserId = $currentUser['id'];
}

if (!$profileUserId) {
    header('Location: login.php');
    exit;
}

// 유저 정보 조회
$stmt = $pdo->prepare('SELECT * FROM users WHERE id = ?');
$stmt->execute([$profileUserId]);
$user = $stmt->fetch();

if (!$user) {
    echo '<div class="pt-20 text-center py-20"><p class="text-suno-muted">존재하지 않는 유저입니다.</p></div>';
    include 'footer.php';
    exit;
}

// 정렬 옵션
$trackSort = $_GET['sort'] ?? 'latest';

// 내 곡 조회
$trackOrderBy = ($trackSort === 'likes') ? 'tracks.like_count DESC, tracks.created_at DESC' : 'tracks.created_at DESC';
$stmt = $pdo->prepare('
    SELECT tracks.*, tracks.audio_file_path,
           (SELECT genre FROM track_genres WHERE track_id = tracks.id LIMIT 1) as genre_name
    FROM tracks
    WHERE tracks.user_id = ?
    ORDER BY ' . $trackOrderBy . '
');
$stmt->execute([$profileUserId]);
$mySongs = $stmt->fetchAll();

// 내 프롬프트 조회
$stmt = $pdo->prepare('
    SELECT prompts.*,
           (SELECT genre FROM prompt_genres WHERE prompt_id = prompts.id LIMIT 1) as genre_name
    FROM prompts
    WHERE user_id = ?
    ORDER BY created_at DESC
');
$stmt->execute([$profileUserId]);
$myPrompts = $stmt->fetchAll();

// 좋아요한 곡 조회
$stmt = $pdo->prepare('
    SELECT tracks.*, users.nickname as artist_name,
           (SELECT genre FROM track_genres WHERE track_id = tracks.id LIMIT 1) as genre_name
    FROM track_likes
    JOIN tracks ON track_likes.track_id = tracks.id
    JOIN users ON tracks.user_id = users.id
    WHERE track_likes.user_id = ?
    ORDER BY track_likes.created_at DESC
');
$stmt->execute([$profileUserId]);
$likedSongs = $stmt->fetchAll();

// 팔로워/팔로잉 수
$stmt = $pdo->prepare('SELECT COUNT(*) FROM follows WHERE following_id = ?');
$stmt->execute([$profileUserId]);
$followerCount = $stmt->fetchColumn();

$stmt = $pdo->prepare('SELECT COUNT(*) FROM follows WHERE follower_id = ?');
$stmt->execute([$profileUserId]);
$followingCount = $stmt->fetchColumn();

$songCount = count($mySongs);

// 자기 자신인지 여부
$isMyProfile = ($currentUser && (int)$currentUser['id'] === $profileUserId);

// 팔로우 상태 확인
$isFollowing = false;
if ($currentUser && !$isMyProfile) {
    $stmt = $pdo->prepare('SELECT id FROM follows WHERE follower_id = ? AND following_id = ?');
    $stmt->execute([$currentUser['id'], $profileUserId]);
    $isFollowing = (bool)$stmt->fetch();
}

// 총 좋아요 수 계산
$stmt = $pdo->prepare('SELECT COALESCE(SUM(like_count), 0) FROM tracks WHERE user_id = ?');
$stmt->execute([$profileUserId]);
$totalLikes = (int)$stmt->fetchColumn();
$stmt = $pdo->prepare('SELECT COALESCE(SUM(like_count), 0) FROM prompts WHERE user_id = ?');
$stmt->execute([$profileUserId]);
$totalLikes += (int)$stmt->fetchColumn();

// 현재 유저가 좋아요 한 트랙 ID 목록
$myLikedTrackIds = [];
if ($currentUser) {
    $stmt = $pdo->prepare('SELECT track_id FROM track_likes WHERE user_id = ?');
    $stmt->execute([$currentUser['id']]);
    $myLikedTrackIds = array_column($stmt->fetchAll(), 'track_id');
}

// 현재 유저가 좋아요 한 프롬프트 ID 목록
$myLikedPromptIds = [];
if ($currentUser) {
    $stmt = $pdo->prepare('SELECT prompt_id FROM prompt_likes WHERE user_id = ?');
    $stmt->execute([$currentUser['id']]);
    $myLikedPromptIds = array_column($stmt->fetchAll(), 'prompt_id');
}

// 북마크한 게시물 조회
$bookmarkedPosts = [];
if ($isMyProfile) {
    $stmt = $pdo->prepare('
        SELECT posts.*, users.nickname as author, users.avatar_color,
               boards.board_key, boards.board_name
        FROM bookmarks
        JOIN posts ON bookmarks.post_id = posts.id
        JOIN users ON posts.user_id = users.id
        JOIN boards ON posts.board_id = boards.id
        WHERE bookmarks.user_id = ?
        ORDER BY bookmarks.created_at DESC
    ');
    $stmt->execute([$profileUserId]);
    $bookmarkedPosts = $stmt->fetchAll();
}

// 스크랩한 프롬프트 조회
$savedPrompts = [];
if ($isMyProfile) {
    $stmt = $pdo->prepare('
        SELECT prompts.*, users.nickname as author, users.avatar_color,
               prompt_saves.created_at as saved_at
        FROM prompt_saves
        JOIN prompts ON prompt_saves.prompt_id = prompts.id
        JOIN users ON prompts.user_id = users.id
        WHERE prompt_saves.user_id = ?
        ORDER BY prompt_saves.created_at DESC
    ');
    $stmt->execute([$profileUserId]);
    $savedPrompts = $stmt->fetchAll();
}

// 북마크한 음원 조회
$savedTracks = [];
if ($isMyProfile) {
    $pdo->exec('CREATE TABLE IF NOT EXISTS track_saves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        track_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, track_id)
    )');
    $stmt = $pdo->prepare('
        SELECT tracks.*, users.nickname as artist_name, users.avatar_color,
               track_saves.created_at as saved_at,
               (SELECT genre FROM track_genres WHERE track_id = tracks.id LIMIT 1) as genre_name
        FROM track_saves
        JOIN tracks ON track_saves.track_id = tracks.id
        JOIN users ON tracks.user_id = users.id
        WHERE track_saves.user_id = ?
        ORDER BY track_saves.created_at DESC
    ');
    $stmt->execute([$profileUserId]);
    $savedTracks = $stmt->fetchAll();
}

// 선택된 뱃지 조회
$selectedBadge = null;
if (!empty($user['selected_badge_id'])) {
    $stmt = $pdo->prepare('SELECT * FROM badges WHERE id = ?');
    $stmt->execute([$user['selected_badge_id']]);
    $selectedBadge = $stmt->fetch();
}

// 아바타/배경 URL
$avatarUrl = $user['avatar_url'] ?? '';
$backgroundUrl = $user['background_url'] ?? '';
?>

<style>
    .track-item { transition: background 0.2s; }
    .track-item:hover { background: rgba(255,255,255,0.02); }
    .track-item:hover .track-play-btn { opacity: 1; }
    .track-play-btn { opacity: 0; transition: opacity 0.2s; }
    .stat-block { text-align: center; line-height: 1.2; }
    .stat-block .stat-number { font-size: 1.25rem; font-weight: 800; }
    .stat-block .stat-label { font-size: 0.6875rem; color: #71717a; margin-top: 2px; }
    .profile-banner {
        position: relative;
        background: linear-gradient(135deg,
            rgba(139,92,246,0.25) 0%, rgba(88,28,135,0.3) 25%,
            rgba(15,23,42,0.8) 50%, rgba(10,10,10,0.95) 100%);
        overflow: hidden;
    }
    .profile-banner::before {
        content: ''; position: absolute; inset: 0;
        background: radial-gradient(ellipse at 20% 50%, rgba(139,92,246,0.3) 0%, transparent 50%),
                    radial-gradient(ellipse at 80% 30%, rgba(168,85,247,0.15) 0%, transparent 50%);
    }
    .liked-track-item { transition: background 0.15s; }
    .liked-track-item:hover { background: rgba(255,255,255,0.03); }
    .sc-btn {
        display: inline-flex; align-items: center; gap: 6px; padding: 6px 14px;
        border: 1px solid #333; border-radius: 4px; font-size: 0.75rem; font-weight: 500;
        color: #a1a1aa; background: transparent; cursor: pointer; transition: all 0.2s; white-space: nowrap;
    }
    .sc-btn:hover { border-color: #8b5cf6; color: white; }
    .sc-btn-primary { background: #8b5cf6; border-color: #8b5cf6; color: white; }
    .sc-btn-primary:hover { background: #a78bfa; border-color: #a78bfa; }
    .sc-btn-icon { padding: 6px 10px; }
    .social-link {
        display: flex; align-items: center; gap: 8px; font-size: 0.75rem;
        color: #71717a; transition: color 0.2s; padding: 3px 0;
    }
    .social-link:hover { color: #a78bfa; }
    .sc-tabs { display: flex; gap: 0; border-bottom: 1px solid #1e1e1e; }
    .sc-tab {
        padding: 12px 20px; font-size: 0.8125rem; font-weight: 500; color: #71717a;
        border-bottom: 2px solid transparent; cursor: pointer; transition: all 0.2s; white-space: nowrap;
    }
    .sc-tab:hover { color: #d4d4d8; }
    .sc-tab.active { color: white; border-bottom-color: #8b5cf6; }
    .track-num { width: 32px; text-align: center; font-size: 0.8125rem; color: #52525b; flex-shrink: 0; }
    .sort-select {
        background: transparent; border: 1px solid #333; border-radius: 6px;
        padding: 4px 10px; font-size: 0.75rem; color: #a1a1aa; cursor: pointer;
    }
    .sort-select:focus { outline: none; border-color: #8b5cf6; }
    .sort-select option { background: #18181b; }
</style>

<main class="pt-20">
    <!-- Profile Banner -->
    <section class="profile-banner h-[260px] md:h-[300px]" <?php if($backgroundUrl): ?>style="background: url('<?php echo htmlspecialchars($backgroundUrl); ?>') center/cover no-repeat;"<?php endif; ?>>
        <?php if(!$backgroundUrl): ?>
        <div class="absolute inset-0 overflow-hidden pointer-events-none">
            <div class="absolute top-1/4 left-1/3 w-2 h-2 bg-suno-accent/30 rounded-full animate-pulse"></div>
            <div class="absolute top-1/2 right-1/4 w-1 h-1 bg-purple-400/40 rounded-full animate-pulse" style="animation-delay:1s"></div>
            <div class="absolute bottom-1/3 left-2/3 w-1.5 h-1.5 bg-violet-400/25 rounded-full animate-pulse" style="animation-delay:2s"></div>
        </div>
        <?php endif; ?>
        <div class="absolute inset-0 bg-gradient-to-t from-suno-dark via-suno-dark/40 to-transparent"></div>
        <div class="absolute inset-0 z-10">
            <div class="max-w-7xl mx-auto px-6 h-full flex items-end pb-8">
                <div class="flex items-end gap-6">
                    <!-- Profile Avatar -->
                    <div class="relative flex-shrink-0">
                        <?php if($avatarUrl): ?>
                        <div class="w-[140px] h-[140px] md:w-[180px] md:h-[180px] rounded-full ring-4 ring-suno-dark/80 shadow-2xl shadow-purple-900/50 overflow-hidden">
                            <img src="<?php echo htmlspecialchars($avatarUrl); ?>" alt="<?php echo htmlspecialchars($user['nickname']); ?>" class="w-full h-full object-cover">
                        </div>
                        <?php else: ?>
                        <div class="w-[140px] h-[140px] md:w-[180px] md:h-[180px] rounded-full bg-gradient-to-br <?php echo $user['avatar_color'] ?: 'from-suno-accent via-purple-600 to-indigo-800'; ?> flex items-center justify-center text-5xl md:text-6xl font-black ring-4 ring-suno-dark/80 shadow-2xl shadow-purple-900/50 overflow-hidden">
                            <span class="text-white/90"><?php echo mb_substr($user['nickname'], 0, 1); ?></span>
                        </div>
                        <?php endif; ?>
                        <!-- Badge -->
                        <?php if($selectedBadge): ?>
                        <div class="absolute -bottom-1 right-2 bg-gradient-to-r <?php echo htmlspecialchars($selectedBadge['color']); ?> text-white text-xs font-extrabold px-2.5 py-1 rounded-full shadow-lg"><?php echo htmlspecialchars($selectedBadge['name']); ?></div>
                        <?php endif; ?>
                    </div>

                    <!-- Username on Banner -->
                    <div class="pb-2">
                        <div class="flex items-center gap-3 mb-1.5">
                            <h1 class="text-2xl md:text-3xl font-extrabold tracking-tight text-white bg-suno-dark/60 px-3 py-1 backdrop-blur-sm"><?php echo htmlspecialchars($user['nickname']); ?></h1>
                        </div>
                        <?php if($selectedBadge): ?>
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-bold px-2.5 py-1 bg-gradient-to-r <?php echo htmlspecialchars($selectedBadge['color']); ?> text-white/90 backdrop-blur-sm rounded">
                                <?php echo htmlspecialchars($selectedBadge['name']); ?>
                            </span>
                        </div>
                        <?php endif; ?>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Mobile: Stats + Actions (인스타 스타일) -->
    <section class="md:hidden border-b border-suno-border bg-suno-card/50">
        <div class="max-w-7xl mx-auto px-6 py-4">
            <!-- Stats Row -->
            <div class="flex items-center justify-around mb-4">
                <button onclick="openFollowModal('followers')" class="stat-block hover:opacity-80 transition-opacity cursor-pointer flex-1">
                    <div class="stat-number text-white" id="followerCountMobile"><?php echo number_format($followerCount); ?></div>
                    <div class="stat-label">팔로워</div>
                </button>
                <button onclick="openFollowModal('following')" class="stat-block hover:opacity-80 transition-opacity cursor-pointer flex-1">
                    <div class="stat-number text-white" id="followingCountMobile"><?php echo number_format($followingCount); ?></div>
                    <div class="stat-label">팔로잉</div>
                </button>
                <div class="stat-block flex-1">
                    <div class="stat-number text-white"><?php echo number_format($songCount); ?></div>
                    <div class="stat-label">트랙</div>
                </div>
                <div class="stat-block flex-1">
                    <div class="stat-number text-white"><?php echo number_format($totalLikes); ?></div>
                    <div class="stat-label">좋아요</div>
                </div>
            </div>
            <!-- Action Buttons -->
            <div class="flex items-center gap-2">
                <?php if ($isMyProfile): ?>
                <a href="profile_edit.php" class="sc-btn sc-btn-primary flex-1 justify-center">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
                    프로필 편집
                </a>
                <?php else: ?>
                <?php if ($currentUser): ?>
                <button id="followBtnMobile" onclick="toggleFollow(<?= $profileUserId ?>)" class="sc-btn <?= $isFollowing ? '' : 'sc-btn-primary' ?> flex-1 justify-center">
                    <span id="followBtnTextMobile"><?= $isFollowing ? '팔로잉' : '팔로우' ?></span>
                </button>
                <a href="message_write.php?to=<?php echo urlencode($user['nickname']); ?>" class="sc-btn flex-1 justify-center">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                    쪽지
                </a>
                <?php else: ?>
                <a href="login.php" class="sc-btn sc-btn-primary flex-1 justify-center">팔로우</a>
                <?php endif; ?>
                <?php endif; ?>
            </div>
            <!-- Bio (mobile) -->
            <?php if(!empty($user['bio'])): ?>
            <div class="mt-3">
                <p class="text-sm text-zinc-300 leading-relaxed"><?php echo nl2br(htmlspecialchars($user['bio'])); ?></p>
            </div>
            <?php endif; ?>
            <!-- Social Links (mobile) -->
            <?php
            $socialLinksMobile = [];
            if (!empty($user['social_links'])) {
                $decodedM = json_decode($user['social_links'], true);
                if (is_array($decodedM)) $socialLinksMobile = $decodedM;
            }
            if (empty($socialLinksMobile)) {
                if (!empty($user['instagram_url'])) $socialLinksMobile[] = ['type' => 'instagram', 'value' => $user['instagram_url']];
                if (!empty($user['youtube_url'])) $socialLinksMobile[] = ['type' => 'youtube', 'value' => $user['youtube_url']];
                if (!empty($user['suno_profile_url'])) $socialLinksMobile[] = ['type' => 'suno', 'value' => $user['suno_profile_url']];
            }
            $socialIconsM = [
                'instagram' => ['label' => 'Instagram', 'color' => 'text-pink-400 hover:text-pink-300'],
                'youtube' => ['label' => 'YouTube', 'color' => 'text-red-400 hover:text-red-300'],
                'spotify' => ['label' => 'Spotify', 'color' => 'text-green-400 hover:text-green-300'],
                'soundcloud' => ['label' => 'SoundCloud', 'color' => 'text-orange-400 hover:text-orange-300'],
                'twitter' => ['label' => 'X (Twitter)', 'color' => 'text-white hover:text-zinc-300'],
                'suno' => ['label' => 'Suno', 'color' => 'text-suno-accent2 hover:text-suno-accent'],
                'other' => ['label' => '링크', 'color' => 'text-suno-muted hover:text-white'],
            ];
            ?>
            <?php if (!empty($socialLinksMobile)): ?>
            <div class="flex flex-wrap gap-2 mt-3">
                <?php foreach ($socialLinksMobile as $slm):
                    $smType = $slm['type'] ?? 'other';
                    $smVal = $slm['value'] ?? '';
                    if (empty($smVal)) continue;
                    $smCfg = $socialIconsM[$smType] ?? $socialIconsM['other'];
                    if ($smType === 'instagram') {
                        $smDisplay = '@' . ltrim($smVal, '@');
                        $smHref = 'https://instagram.com/' . ltrim($smVal, '@');
                    } elseif ($smType === 'twitter') {
                        $smDisplay = '@' . ltrim($smVal, '@');
                        $smHref = 'https://x.com/' . ltrim($smVal, '@');
                    } else {
                        $smDisplay = $smVal;
                        $smHref = (strpos($smVal, 'http') === 0) ? $smVal : 'https://' . $smVal;
                    }
                ?>
                <a href="<?php echo htmlspecialchars($smHref); ?>" target="_blank" class="inline-flex items-center gap-1.5 px-2.5 py-1.5 rounded-full bg-suno-surface/50 border border-suno-border/50 <?php echo $smCfg['color']; ?> transition-colors text-xs font-medium">
                    <span class="opacity-60"><?php echo $smCfg['label']; ?></span>
                    <span class="truncate max-w-[120px]"><?php echo htmlspecialchars($smDisplay); ?></span>
                </a>
                <?php endforeach; ?>
            </div>
            <?php endif; ?>
        </div>
    </section>

    <!-- Action Bar -->
    <section class="border-b border-suno-border bg-suno-card/50">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex items-center justify-between py-4">
                <!-- Tab Navigation -->
                <div class="sc-tabs border-b-0 overflow-x-auto">
                    <button onclick="switchProfileTab('tracks', this)" class="sc-tab active" data-tab="tracks">트랙</button>
                    <button onclick="switchProfileTab('prompts', this)" class="sc-tab" data-tab="prompts">프롬프트</button>
                    <button onclick="switchProfileTab('liked', this)" class="sc-tab" data-tab="liked">좋아요</button>
                    <?php if($isMyProfile): ?>
                    <button onclick="switchProfileTab('bookmarks', this)" class="sc-tab" data-tab="bookmarks">북마크</button>
                    <?php endif; ?>
                </div>
                <!-- Action Buttons (Desktop) -->
                <div class="hidden md:flex items-center gap-2">
                    <?php if ($isMyProfile): ?>
                    <a href="profile_edit.php" class="sc-btn sc-btn-primary">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
                        프로필 편집
                    </a>
                    <?php else: ?>
                    <?php if ($currentUser): ?>
                    <button id="followBtn" onclick="toggleFollow(<?= $profileUserId ?>)" class="sc-btn <?= $isFollowing ? '' : 'sc-btn-primary' ?>">
                        <svg class="w-3.5 h-3.5" fill="<?= $isFollowing ? 'none' : 'currentColor' ?>" stroke="currentColor" viewBox="0 0 24 24">
                            <?php if ($isFollowing): ?>
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M22 10.5h-6m-2.25-4.125a3.375 3.375 0 11-6.75 0 3.375 3.375 0 016.75 0zM4 19.235v-.11a6.375 6.375 0 0112.75 0v.109A12.318 12.318 0 0110.374 21c-2.331 0-4.512-.645-6.374-1.766z"/>
                            <?php else: ?>
                            <path d="M10 3a1 1 0 011 1v5h5a1 1 0 110 2h-5v5a1 1 0 11-2 0v-5H4a1 1 0 110-2h5V4a1 1 0 011-1z"/>
                            <?php endif; ?>
                        </svg>
                        <span id="followBtnText"><?= $isFollowing ? '팔로잉' : '팔로우' ?></span>
                    </button>
                    <a href="message_write.php?to=<?php echo urlencode($user['nickname']); ?>" class="sc-btn sc-btn-icon" title="쪽지 보내기">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/></svg>
                    </a>
                    <?php endif; ?>
                    <?php endif; ?>
                </div>
            </div>
        </div>
    </section>

    <!-- Main Content + Sidebar Layout -->
    <section class="py-8">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex flex-col lg:flex-row gap-8">

                <!-- Left: Main Content -->
                <div class="flex-1 min-w-0">

                    <!-- Tab: Tracks -->
                    <div id="tab-tracks" class="tab-content">
                        <div class="flex items-center justify-between mb-4">
                            <h3 class="text-sm font-semibold text-suno-muted">트랙 <span class="text-suno-muted/50"><?php echo $songCount; ?></span></h3>
                            <select class="sort-select" onchange="location.href='profile.php?id=<?php echo $profileUserId; ?>&sort='+this.value">
                                <option value="latest" <?php echo $trackSort === 'latest' ? 'selected' : ''; ?>>최신순</option>
                                <option value="likes" <?php echo $trackSort === 'likes' ? 'selected' : ''; ?>>좋아요순</option>
                            </select>
                        </div>

                        <?php if(empty($mySongs)): ?>
                        <div class="py-12 text-center text-sm text-suno-muted/50">아직 트랙이 없습니다.</div>
                        <?php else: ?>

                        <?php $featLiked = in_array($mySongs[0]['id'], $myLikedTrackIds); ?>
                        <!-- Featured Track Card (첫 번째 트랙) -->
                        <div class="bg-suno-card/50 border border-suno-border rounded-lg overflow-hidden mb-6">
                            <div class="flex flex-col sm:flex-row">
                                <a href="music_detail.php?id=<?php echo $mySongs[0]['id']; ?>" class="w-full sm:w-[200px] h-[200px] flex-shrink-0 bg-gradient-to-br <?php echo getGradient($mySongs[0]['id'] ?? 0, $mySongs[0]['genre_name'] ?? null); ?> relative flex items-center justify-center group block">
                                    <?php if(!empty($mySongs[0]['cover_image_path'])): ?>
                                    <img src="<?php echo htmlspecialchars($mySongs[0]['cover_image_path']); ?>" class="w-full h-full object-cover absolute inset-0" alt="">
                                    <?php else: ?>
                                    <svg class="w-12 h-12 text-white/20" fill="currentColor" viewBox="0 0 20 20"><path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/></svg>
                                    <?php endif; ?>
                                    <div class="absolute inset-0 bg-black/30 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity">
                                        <div class="w-14 h-14 bg-suno-accent rounded-full flex items-center justify-center shadow-lg shadow-suno-accent/40">
                                            <svg class="w-6 h-6 text-white ml-0.5" fill="currentColor" viewBox="0 0 20 20"><path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/></svg>
                                        </div>
                                    </div>
                                </a>
                                <div class="flex-1 p-5">
                                    <a href="music_detail.php?id=<?php echo $mySongs[0]['id']; ?>" class="block">
                                        <div class="flex items-start justify-between mb-1">
                                            <div>
                                                <p class="text-suno-muted text-xs"><?php echo htmlspecialchars($user['nickname']); ?></p>
                                                <h3 class="text-lg font-bold hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($mySongs[0]['title']); ?></h3>
                                            </div>
                                            <div class="flex items-center gap-2">
                                                <?php if(!empty($mySongs[0]['genre_name'])): ?>
                                                <span class="text-xs px-2.5 py-0.5 rounded-full bg-suno-accent/10 text-suno-accent2 border border-suno-accent/20"># <?php echo htmlspecialchars($mySongs[0]['genre_name']); ?></span>
                                                <?php endif; ?>
                                                <span class="text-xs text-suno-muted/50"><?php echo timeAgo($mySongs[0]['created_at']); ?></span>
                                            </div>
                                        </div>
                                    </a>
                                    <?php if(!empty($mySongs[0]['audio_file_path'])): ?>
                                    <div class="my-4 bg-suno-dark/80 border border-suno-border/50 rounded-xl px-4 py-3 flex items-center gap-4">
                                        <button onclick="toggleProfileAudio(this, '<?php echo htmlspecialchars($mySongs[0]['audio_file_path'], ENT_QUOTES); ?>')" class="w-10 h-10 bg-suno-accent hover:bg-suno-accent2 rounded-full flex items-center justify-center flex-shrink-0 transition-colors shadow-lg shadow-suno-accent/20">
                                            <svg class="play-icon w-4 h-4 text-white ml-px" fill="currentColor" viewBox="0 0 20 20"><path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/></svg>
                                        </button>
                                        <span class="profile-audio-time text-xs text-suno-muted font-mono tabular-nums w-10">0:00</span>
                                        <div class="flex-1 h-[6px] rounded-full bg-suno-border/60 cursor-pointer profile-audio-bar relative group" onclick="seekProfileAudio(event, this)">
                                            <div class="h-full rounded-l-full bg-gradient-to-r from-suno-accent to-purple-400 profile-audio-progress" style="width:0%"></div>
                                            <div class="profile-audio-thumb absolute top-1/2 -translate-y-1/2 w-3 h-3 rounded-full bg-white border-2 border-suno-accent shadow-md pointer-events-none" style="left:0%"></div>
                                        </div>
                                        <span class="profile-audio-duration text-xs text-suno-muted font-mono tabular-nums w-10 text-right"><?php echo $mySongs[0]['duration'] ?: '--:--'; ?></span>
                                    </div>
                                    <?php endif; ?>
                                    <div class="flex items-center gap-3 flex-wrap">
                                        <button onclick="toggleLike(this, 'track', <?php echo $mySongs[0]['id']; ?>)" class="sc-btn <?php echo $featLiked ? 'text-pink-400 border-pink-500/30' : ''; ?>" style="font-size:0.6875rem" data-liked="<?php echo $featLiked ? '1' : '0'; ?>">
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/></svg>
                                            <span class="like-count"><?php echo formatCount($mySongs[0]['like_count'] ?? 0); ?></span>
                                        </button>
                                        <a href="music_detail.php?id=<?php echo $mySongs[0]['id']; ?>" class="sc-btn" style="font-size:0.6875rem;">
                                            <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/></svg>
                                            <?php echo formatCount($mySongs[0]['play_count'] ?? 0); ?>
                                        </a>
                                    </div>
                                </div>
                            </div>
                        </div>

                        <!-- Track List -->
                        <div class="space-y-0">
                            <?php foreach($mySongs as $idx => $song): if($idx === 0) continue;
                                $songLiked = in_array($song['id'], $myLikedTrackIds);
                            ?>
                            <div class="track-item flex items-center gap-4 py-3 px-3 border-b border-suno-border/50 rounded-sm group">
                                <a href="music_detail.php?id=<?php echo $song['id']; ?>" class="relative flex-shrink-0 block">
                                    <div class="w-10 h-10 rounded bg-gradient-to-br <?php echo getGradient($song['id'] ?? $idx, $song['genre_name'] ?? null); ?> flex items-center justify-center relative overflow-hidden">
                                        <?php if(!empty($song['cover_image_path'])): ?>
                                        <img src="<?php echo htmlspecialchars($song['cover_image_path']); ?>" class="absolute inset-0 w-full h-full object-cover" alt="">
                                        <?php else: ?>
                                        <svg class="w-4 h-4 text-white/30" fill="currentColor" viewBox="0 0 20 20"><path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/></svg>
                                        <?php endif; ?>
                                        <div class="track-play-btn absolute inset-0 bg-black/50 flex items-center justify-center">
                                            <svg class="w-3.5 h-3.5 text-white ml-px" fill="currentColor" viewBox="0 0 20 20"><path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/></svg>
                                        </div>
                                    </div>
                                </a>
                                <span class="track-num"><?php echo $idx + 1; ?></span>
                                <a href="music_detail.php?id=<?php echo $song['id']; ?>" class="flex-1 min-w-0 block">
                                    <span class="font-semibold text-sm truncate hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($song['title']); ?></span>
                                </a>
                                <?php if(!empty($song['genre_name'])): ?>
                                <span class="hidden sm:block text-[11px] px-2 py-0.5 rounded-full bg-suno-surface border border-suno-border text-suno-muted"># <?php echo htmlspecialchars($song['genre_name']); ?></span>
                                <?php endif; ?>
                                <div class="flex items-center gap-3 text-xs text-suno-muted/60">
                                    <button onclick="toggleLike(this, 'track', <?php echo $song['id']; ?>)" class="flex items-center gap-1 hover:text-pink-400 transition-colors <?php echo $songLiked ? 'text-pink-400' : ''; ?>" data-liked="<?php echo $songLiked ? '1' : '0'; ?>">
                                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/></svg>
                                        <span class="like-count"><?php echo formatCount($song['like_count'] ?? 0); ?></span>
                                    </button>
                                    <span class="flex items-center gap-1">
                                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/></svg>
                                        <?php echo formatCount($song['play_count'] ?? 0); ?>
                                    </span>
                                </div>
                            </div>
                            <?php endforeach; ?>
                        </div>
                        <?php endif; ?>
                    </div>

                    <!-- Tab: Prompts -->
                    <div id="tab-prompts" class="tab-content hidden">
                        <h3 class="text-sm font-semibold text-suno-muted mb-4">프롬프트 <span class="text-suno-muted/50"><?php echo count($myPrompts); ?></span></h3>
                        <?php if(empty($myPrompts)): ?>
                        <div class="py-12 text-center text-sm text-suno-muted/50">아직 프롬프트가 없습니다.</div>
                        <?php else: ?>
                        <div class="grid sm:grid-cols-2 gap-4">
                            <?php foreach($myPrompts as $prompt):
                                $promptLiked = in_array($prompt['id'], $myLikedPromptIds);
                            ?>
                            <div class="bg-suno-card/60 border border-suno-border rounded-lg p-5 hover:border-suno-accent/30 transition-all">
                                <a href="prompt_detail.php?id=<?php echo $prompt['id']; ?>" class="block">
                                    <div class="flex items-center gap-2 mb-3">
                                        <?php if(!empty($prompt['genre_name'])): ?>
                                        <span class="text-xs px-2.5 py-0.5 rounded-full bg-suno-accent/10 text-suno-accent2 border border-suno-accent/20"><?php echo htmlspecialchars($prompt['genre_name']); ?></span>
                                        <?php endif; ?>
                                    </div>
                                    <h3 class="font-bold text-sm mb-2 hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($prompt['title']); ?></h3>
                                </a>
                                <div class="flex items-center justify-between mt-3">
                                    <button onclick="toggleLike(this, 'prompt', <?php echo $prompt['id']; ?>)" class="flex items-center gap-1 text-xs transition-colors <?php echo $promptLiked ? 'text-pink-400' : 'text-suno-muted/60 hover:text-pink-400'; ?>" data-liked="<?php echo $promptLiked ? '1' : '0'; ?>">
                                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/></svg>
                                        <span class="like-count"><?php echo formatCount($prompt['like_count'] ?? 0); ?></span>
                                    </button>
                                    <div class="flex items-center gap-1 text-xs text-suno-muted">
                                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17.593 3.322c1.1.128 1.907 1.077 1.907 2.185V21L12 17.25 4.5 21V5.507c0-1.108.806-2.057 1.907-2.185a48.507 48.507 0 0111.186 0z"/></svg>
                                        <?php echo number_format($prompt['save_count'] ?? 0); ?>명 저장
                                    </div>
                                </div>
                            </div>
                            <?php endforeach; ?>
                        </div>
                        <?php endif; ?>
                    </div>

                    <!-- Tab: Bookmarks -->
                    <?php if($isMyProfile): ?>
                    <div id="tab-bookmarks" class="tab-content hidden">
                        <?php $hasAnyBookmark = !empty($savedTracks) || !empty($savedPrompts) || !empty($bookmarkedPosts); ?>

                        <?php if(!$hasAnyBookmark): ?>
                        <div class="py-12 text-center text-sm text-suno-muted/50">북마크/스크랩한 항목이 없습니다.</div>
                        <?php else: ?>

                        <!-- 북마크한 음원 -->
                        <?php if(!empty($savedTracks)): ?>
                        <h3 class="text-sm font-semibold text-suno-muted mb-4">북마크한 음원 <span class="text-suno-muted/50"><?php echo count($savedTracks); ?></span></h3>
                        <div class="space-y-0 mb-8">
                            <?php foreach($savedTracks as $st): ?>
                            <a href="music_detail.php?id=<?php echo $st['id']; ?>" class="track-item flex items-center gap-4 py-3.5 px-3 border-b border-suno-border/50 group block">
                                <div class="flex-shrink-0">
                                    <div class="w-10 h-10 rounded bg-gradient-to-br <?php echo getGradient($st['id'], $st['genre_name'] ?? null); ?> flex items-center justify-center relative overflow-hidden">
                                        <?php if(!empty($st['cover_image_path'])): ?>
                                        <img src="<?php echo htmlspecialchars($st['cover_image_path']); ?>" class="absolute inset-0 w-full h-full object-cover" alt="">
                                        <?php else: ?>
                                        <svg class="w-4 h-4 text-white/30" fill="currentColor" viewBox="0 0 20 20"><path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/></svg>
                                        <?php endif; ?>
                                    </div>
                                </div>
                                <div class="flex-1 min-w-0">
                                    <span class="font-semibold text-sm truncate block group-hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($st['title']); ?></span>
                                    <span class="text-xs text-suno-muted/60"><?php echo htmlspecialchars($st['artist_name']); ?> · <?php echo timeAgo($st['saved_at']); ?></span>
                                </div>
                                <div class="flex items-center gap-3 text-xs text-suno-muted/50 flex-shrink-0">
                                    <?php if(!empty($st['genre_name'])): ?>
                                    <span class="hidden sm:block text-[10px] px-2 py-0.5 rounded-full bg-suno-surface border border-suno-border"># <?php echo htmlspecialchars($st['genre_name']); ?></span>
                                    <?php endif; ?>
                                    <span class="flex items-center gap-1">
                                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/></svg>
                                        <?php echo formatCount($st['play_count'] ?? 0); ?>
                                    </span>
                                    <span class="flex items-center gap-1">
                                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/></svg>
                                        <?php echo formatCount($st['like_count'] ?? 0); ?>
                                    </span>
                                </div>
                            </a>
                            <?php endforeach; ?>
                        </div>
                        <?php endif; ?>

                        <!-- 스크랩한 프롬프트 -->
                        <?php if(!empty($savedPrompts)): ?>
                        <h3 class="text-sm font-semibold text-suno-muted mb-4">스크랩한 프롬프트 <span class="text-suno-muted/50"><?php echo count($savedPrompts); ?></span></h3>
                        <div class="space-y-0 mb-8">
                            <?php foreach($savedPrompts as $sp): ?>
                            <a href="prompt_detail.php?id=<?php echo $sp['id']; ?>" class="track-item flex items-center gap-4 py-3.5 px-3 border-b border-suno-border/50 group block">
                                <div class="flex-shrink-0">
                                    <span class="text-[10px] font-semibold px-2 py-0.5 rounded bg-suno-accent/10 border border-suno-accent/20 text-suno-accent2">프롬프트</span>
                                </div>
                                <div class="flex-1 min-w-0">
                                    <span class="font-semibold text-sm truncate block group-hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($sp['title']); ?></span>
                                    <span class="text-xs text-suno-muted/60"><?php echo htmlspecialchars($sp['author']); ?> · <?php echo timeAgo($sp['saved_at']); ?></span>
                                </div>
                                <div class="flex items-center gap-3 text-xs text-suno-muted/50 flex-shrink-0">
                                    <span class="flex items-center gap-1">
                                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/></svg>
                                        <?php echo $sp['like_count']; ?>
                                    </span>
                                    <span class="flex items-center gap-1">
                                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
                                        <?php echo $sp['copy_count']; ?>
                                    </span>
                                </div>
                            </a>
                            <?php endforeach; ?>
                        </div>
                        <?php endif; ?>

                        <!-- 북마크한 게시글 -->
                        <?php if(!empty($bookmarkedPosts)): ?>
                        <h3 class="text-sm font-semibold text-suno-muted mb-4">북마크한 글 <span class="text-suno-muted/50"><?php echo count($bookmarkedPosts); ?></span></h3>
                        <div class="space-y-0">
                            <?php foreach($bookmarkedPosts as $bp): ?>
                            <a href="board_detail.php?board=<?php echo htmlspecialchars($bp['board_key']); ?>&id=<?php echo $bp['id']; ?>" class="track-item flex items-center gap-4 py-3.5 px-3 border-b border-suno-border/50 group block">
                                <div class="flex-shrink-0">
                                    <span class="text-[10px] font-semibold px-2 py-0.5 rounded bg-suno-surface border border-suno-border text-suno-muted"><?php echo htmlspecialchars($bp['board_name']); ?></span>
                                </div>
                                <div class="flex-1 min-w-0">
                                    <span class="font-semibold text-sm truncate block group-hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($bp['title']); ?></span>
                                    <span class="text-xs text-suno-muted/60"><?php echo htmlspecialchars($bp['author']); ?> · <?php echo timeAgo($bp['created_at']); ?></span>
                                </div>
                                <div class="flex items-center gap-3 text-xs text-suno-muted/50 flex-shrink-0">
                                    <span class="flex items-center gap-1">
                                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/></svg>
                                        <?php echo $bp['like_count']; ?>
                                    </span>
                                    <span class="flex items-center gap-1">
                                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 12h.01M12 12h.01M16 12h.01M21 12c0 4.418-4.03 8-9 8a9.863 9.863 0 01-4.255-.949L3 20l1.395-3.72C3.512 15.042 3 13.574 3 12c0-4.418 4.03-8 9-8s9 3.582 9 8z"/></svg>
                                        <?php echo $bp['comment_count']; ?>
                                    </span>
                                </div>
                            </a>
                            <?php endforeach; ?>
                        </div>
                        <?php endif; ?>

                        <?php endif; ?>
                    </div>
                    <?php endif; ?>

                    <!-- Tab: Liked -->
                    <div id="tab-liked" class="tab-content hidden">
                        <h3 class="text-sm font-semibold text-suno-muted mb-4">좋아요한 트랙 <span class="text-suno-muted/50"><?php echo count($likedSongs); ?></span></h3>
                        <?php if(empty($likedSongs)): ?>
                        <div class="py-12 text-center text-sm text-suno-muted/50">아직 좋아요한 트랙이 없습니다.</div>
                        <?php else: ?>
                        <div class="space-y-0">
                            <?php foreach($likedSongs as $idx => $ls):
                                $lsLiked = in_array($ls['id'], $myLikedTrackIds);
                            ?>
                            <div class="track-item flex items-center gap-4 py-4 px-3 border-b border-suno-border/50 group">
                                <a href="music_detail.php?id=<?php echo $ls['id']; ?>" class="relative flex-shrink-0 block">
                                    <div class="w-12 h-12 rounded bg-gradient-to-br <?php echo getGradient($ls['id'] ?? $idx, $ls['genre_name'] ?? null); ?> flex items-center justify-center relative overflow-hidden">
                                        <?php if(!empty($ls['cover_image_path'])): ?>
                                        <img src="<?php echo htmlspecialchars($ls['cover_image_path']); ?>" class="absolute inset-0 w-full h-full object-cover" alt="">
                                        <?php else: ?>
                                        <svg class="w-5 h-5 text-white/30" fill="currentColor" viewBox="0 0 20 20"><path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/></svg>
                                        <?php endif; ?>
                                        <div class="track-play-btn absolute inset-0 bg-black/50 flex items-center justify-center">
                                            <svg class="w-4 h-4 text-white ml-px" fill="currentColor" viewBox="0 0 20 20"><path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/></svg>
                                        </div>
                                    </div>
                                </a>
                                <a href="music_detail.php?id=<?php echo $ls['id']; ?>" class="flex-1 min-w-0 block">
                                    <span class="font-bold text-sm hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($ls['title']); ?></span>
                                    <p class="text-xs text-suno-muted mt-0.5"><?php echo htmlspecialchars($ls['artist_name'] ?? ''); ?></p>
                                </a>
                                <div class="flex items-center gap-4 text-xs text-suno-muted/60">
                                    <span class="flex items-center gap-1">
                                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/></svg>
                                        <?php echo formatCount($ls['play_count'] ?? 0); ?>
                                    </span>
                                    <button onclick="toggleLike(this, 'track', <?php echo $ls['id']; ?>)" class="flex items-center gap-1 hover:text-pink-400 transition-colors <?php echo $lsLiked ? 'text-pink-400' : ''; ?>" data-liked="<?php echo $lsLiked ? '1' : '0'; ?>">
                                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/></svg>
                                        <span class="like-count"><?php echo formatCount($ls['like_count'] ?? 0); ?></span>
                                    </button>
                                </div>
                            </div>
                            <?php endforeach; ?>
                        </div>
                        <?php endif; ?>
                    </div>

                </div>

                <!-- Right: Sidebar -->
                <div class="w-full lg:w-[280px] flex-shrink-0">
                    <!-- Stats (desktop only, mobile version is above) -->
                    <div class="hidden md:flex justify-between mb-6 px-2">
                        <button onclick="openFollowModal('followers')" class="stat-block hover:opacity-80 transition-opacity cursor-pointer">
                            <div class="stat-number text-white" id="followerCount"><?php echo number_format($followerCount); ?></div>
                            <div class="stat-label">Followers</div>
                        </button>
                        <button onclick="openFollowModal('following')" class="stat-block hover:opacity-80 transition-opacity cursor-pointer">
                            <div class="stat-number text-white" id="followingCount"><?php echo number_format($followingCount); ?></div>
                            <div class="stat-label">Following</div>
                        </button>
                        <div class="stat-block">
                            <div class="stat-number text-white"><?php echo number_format($songCount); ?></div>
                            <div class="stat-label">Tracks</div>
                        </div>
                    </div>

                    <div class="hidden md:block border-t border-suno-border mb-5"></div>

                    <!-- Bio (desktop only, mobile version is above) -->
                    <?php if(!empty($user['bio'])): ?>
                    <div class="hidden md:block mb-5 px-2">
                        <p class="text-sm text-zinc-300 leading-relaxed"><?php echo nl2br(htmlspecialchars($user['bio'])); ?></p>
                    </div>
                    <?php endif; ?>

                    <!-- Social Links (desktop only, mobile version is above) -->
                    <div class="hidden md:block mb-6 px-2">
                        <?php
                        $socialLinks = [];
                        if (!empty($user['social_links'])) {
                            $decoded = json_decode($user['social_links'], true);
                            if (is_array($decoded)) $socialLinks = $decoded;
                        }
                        // Fallback: old columns
                        if (empty($socialLinks)) {
                            if (!empty($user['instagram_url'])) $socialLinks[] = ['type' => 'instagram', 'value' => $user['instagram_url']];
                            if (!empty($user['youtube_url'])) $socialLinks[] = ['type' => 'youtube', 'value' => $user['youtube_url']];
                            if (!empty($user['suno_profile_url'])) $socialLinks[] = ['type' => 'suno', 'value' => $user['suno_profile_url']];
                        }
                        $socialIcons = [
                            'instagram' => ['label' => 'Instagram', 'color' => 'text-pink-400 hover:text-pink-300', 'prefix' => 'https://instagram.com/'],
                            'youtube' => ['label' => 'YouTube', 'color' => 'text-red-400 hover:text-red-300', 'prefix' => ''],
                            'spotify' => ['label' => 'Spotify', 'color' => 'text-green-400 hover:text-green-300', 'prefix' => ''],
                            'soundcloud' => ['label' => 'SoundCloud', 'color' => 'text-orange-400 hover:text-orange-300', 'prefix' => ''],
                            'twitter' => ['label' => 'X (Twitter)', 'color' => 'text-white hover:text-zinc-300', 'prefix' => 'https://x.com/'],
                            'suno' => ['label' => 'Suno', 'color' => 'text-suno-accent2 hover:text-suno-accent', 'prefix' => ''],
                            'other' => ['label' => '링크', 'color' => 'text-suno-muted hover:text-white', 'prefix' => ''],
                        ];
                        ?>
                        <?php if (!empty($socialLinks)): ?>
                        <div class="space-y-2">
                            <?php foreach ($socialLinks as $sl):
                                $sType = $sl['type'] ?? 'other';
                                $sVal = $sl['value'] ?? '';
                                if (empty($sVal)) continue;
                                $sCfg = $socialIcons[$sType] ?? $socialIcons['other'];
                                // Build URL
                                if ($sType === 'instagram') {
                                    $displayVal = '@' . ltrim($sVal, '@');
                                    $href = 'https://instagram.com/' . ltrim($sVal, '@');
                                } elseif ($sType === 'twitter') {
                                    $displayVal = '@' . ltrim($sVal, '@');
                                    $href = 'https://x.com/' . ltrim($sVal, '@');
                                } else {
                                    $displayVal = $sVal;
                                    $href = (strpos($sVal, 'http') === 0) ? $sVal : 'https://' . $sVal;
                                }
                            ?>
                            <a href="<?php echo htmlspecialchars($href); ?>" target="_blank" class="flex items-center gap-2.5 px-3 py-2 rounded-lg bg-suno-surface/50 border border-suno-border/50 <?php echo $sCfg['color']; ?> transition-colors text-sm font-medium">
                                <span class="text-xs opacity-60"><?php echo $sCfg['label']; ?></span>
                                <span class="truncate flex-1 text-right"><?php echo htmlspecialchars($displayVal); ?></span>
                                <svg class="w-3 h-3 opacity-40 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/></svg>
                            </a>
                            <?php endforeach; ?>
                        </div>
                        <?php endif; ?>
                        <p class="text-[10px] text-suno-muted/40 mt-3">가입일: <?php echo date('Y.m', strtotime($user['created_at'] ?? 'now')); ?></p>
                    </div>

                </div>
            </div>
        </div>
    </section>

    <div class="py-8"></div>

<!-- Follower/Following Modal -->
<div id="followModal" class="fixed inset-0 z-[100] hidden">
    <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" onclick="closeFollowModal()"></div>
    <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-md bg-suno-card border border-suno-border rounded-2xl overflow-hidden shadow-2xl">
        <div class="flex items-center justify-between px-6 py-4 border-b border-suno-border">
            <h3 id="followModalTitle" class="font-bold text-base">팔로워</h3>
            <button onclick="closeFollowModal()" class="text-suno-muted hover:text-white transition-colors">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
            </button>
        </div>
        <div id="followModalContent" class="max-h-[400px] overflow-y-auto p-4">
            <div class="text-center py-8 text-suno-muted text-sm">로딩 중...</div>
        </div>
    </div>
</div>
</main>

<script>
// 좋아요 토글 (AJAX)
function toggleLike(btn, type, targetId) {
    const formData = new FormData();
    formData.append('type', type);
    formData.append('target_id', targetId);
    fetch('like_ok.php', { method: 'POST', body: formData })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const countEl = btn.querySelector('.like-count');
                if (countEl) countEl.textContent = data.like_count >= 1000 ? (data.like_count / 1000).toFixed(1) + 'K' : data.like_count.toLocaleString();
                btn.dataset.liked = data.liked ? '1' : '0';
                if (data.liked) {
                    btn.classList.add('text-pink-400');
                    if (btn.classList.contains('sc-btn')) btn.classList.add('border-pink-500/30');
                } else {
                    btn.classList.remove('text-pink-400');
                    if (btn.classList.contains('sc-btn')) btn.classList.remove('border-pink-500/30');
                }
            } else {
                if (data.message) alert(data.message);
            }
        })
        .catch(() => alert('서버 오류가 발생했습니다.'));
}

function toggleFollow(userId) {
    var formData = new FormData();
    formData.append('user_id', userId);
    fetch('follow_ok.php', { method: 'POST', body: formData })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                // Update all follow buttons (desktop + mobile)
                ['followBtn', 'followBtnMobile'].forEach(function(id) {
                    var btn = document.getElementById(id);
                    if (!btn) return;
                    if (data.followed) {
                        btn.classList.remove('sc-btn-primary');
                    } else {
                        btn.classList.add('sc-btn-primary');
                    }
                });
                ['followBtnText', 'followBtnTextMobile'].forEach(function(id) {
                    var el = document.getElementById(id);
                    if (el) el.textContent = data.followed ? '팔로잉' : '팔로우';
                });
                // Update all follower count elements
                ['followerCount', 'followerCountMobile'].forEach(function(id) {
                    var el = document.getElementById(id);
                    if (el) el.textContent = data.follower_count.toLocaleString();
                });
            } else {
                alert(data.message || '오류가 발생했습니다.');
            }
        })
        .catch(function() { alert('서버 오류가 발생했습니다.'); });
}

function switchProfileTab(tabName, el) {
    document.querySelectorAll('.tab-content').forEach(tc => tc.classList.add('hidden'));
    document.getElementById('tab-' + tabName).classList.remove('hidden');
    document.querySelectorAll('.sc-tab').forEach(tab => tab.classList.remove('active'));
    el.classList.add('active');
}

// ── 프로필 오디오 플레이어 ──
var profileAudio = null;
var profileAudioBtn = null;
var profileRAF = null;

function toggleProfileAudio(btn, src) {
    if (profileAudio && profileAudioBtn === btn) {
        if (profileAudio.paused) {
            profileAudio.play();
            btn.querySelector('.play-icon').innerHTML = '<rect x="5" y="3" width="4" height="14" rx="1"/><rect x="13" y="3" width="4" height="14" rx="1"/>';
        } else {
            profileAudio.pause();
            btn.querySelector('.play-icon').innerHTML = '<path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>';
        }
        return;
    }
    if (profileAudio) {
        profileAudio.pause();
        profileAudio.currentTime = 0;
        if (profileAudioBtn) {
            profileAudioBtn.querySelector('.play-icon').innerHTML = '<path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>';
            var oldRow = profileAudioBtn.parentElement;
            if (oldRow) { var op = oldRow.querySelector('.profile-audio-progress'); var ot = oldRow.querySelector('.profile-audio-time'); var oThumb = oldRow.querySelector('.profile-audio-thumb'); if(op) op.style.width='0%'; if(oThumb) oThumb.style.left='0%'; if(ot) ot.textContent='0:00'; }
        }
        cancelAnimationFrame(profileRAF);
    }
    profileAudio = new Audio(src);
    profileAudioBtn = btn;
    var row = btn.parentElement;
    var progress = row.querySelector('.profile-audio-progress');
    var thumb = row.querySelector('.profile-audio-thumb');
    var timeEl = row.querySelector('.profile-audio-time');
    var durEl = row.querySelector('.profile-audio-duration');

    profileAudio.addEventListener('loadedmetadata', function() {
        if (durEl && profileAudio.duration && isFinite(profileAudio.duration)) {
            var dm = Math.floor(profileAudio.duration / 60);
            var ds = Math.floor(profileAudio.duration % 60);
            durEl.textContent = dm + ':' + (ds < 10 ? '0' : '') + ds;
        }
    });

    profileAudio.play();
    btn.querySelector('.play-icon').innerHTML = '<rect x="5" y="3" width="4" height="14" rx="1"/><rect x="13" y="3" width="4" height="14" rx="1"/>';

    function update() {
        if (!profileAudio || profileAudio.paused) return;
        var pct = (profileAudio.currentTime / profileAudio.duration) * 100;
        if (progress) progress.style.width = pct + '%';
        if (thumb) thumb.style.left = pct + '%';
        if (timeEl) { var m=Math.floor(profileAudio.currentTime/60); var s=Math.floor(profileAudio.currentTime%60); timeEl.textContent=m+':'+(s<10?'0':'')+s; }
        profileRAF = requestAnimationFrame(update);
    }
    profileAudio.addEventListener('play', function() { profileRAF = requestAnimationFrame(update); });
    profileAudio.addEventListener('ended', function() {
        btn.querySelector('.play-icon').innerHTML = '<path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>';
        if (progress) progress.style.width = '0%';
        if (thumb) thumb.style.left = '0%';
        if (timeEl) timeEl.textContent = '0:00';
        profileAudio = null; profileAudioBtn = null;
    });
}

function seekProfileAudio(e, bar) {
    if (!profileAudio || !profileAudio.duration) return;
    var rect = bar.getBoundingClientRect();
    var pct = (e.clientX - rect.left) / rect.width;
    profileAudio.currentTime = pct * profileAudio.duration;
}

function openFollowModal(type) {
    var modal = document.getElementById('followModal');
    var title = document.getElementById('followModalTitle');
    var content = document.getElementById('followModalContent');
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    title.textContent = type === 'followers' ? '팔로워' : '팔로잉';
    content.innerHTML = '<div class="text-center py-8 text-suno-muted text-sm">로딩 중...</div>';
    
    fetch('api_follow_list.php?user_id=<?php echo $profileUserId; ?>&type=' + type)
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (!data.users || data.users.length === 0) {
                content.innerHTML = '<div class="text-center py-8 text-suno-muted text-sm">' + (type === 'followers' ? '팔로워가' : '팔로잉이') + ' 없습니다.</div>';
                return;
            }
            var html = '<div class="space-y-2">';
            data.users.forEach(function(u) {
                html += '<a href="profile.php?id=' + u.id + '" class="flex items-center gap-3 p-3 rounded-xl hover:bg-suno-surface/50 transition-colors">'
                    + '<div class="w-10 h-10 rounded-full bg-gradient-to-r ' + (u.avatar_color || 'from-violet-500 to-purple-600') + ' flex items-center justify-center text-sm font-bold flex-shrink-0">' + u.initial + '</div>'
                    + '<div class="flex-1 min-w-0"><p class="text-sm font-semibold truncate">' + u.nickname + '</p></div>'
                    + '</a>';
            });
            html += '</div>';
            content.innerHTML = html;
        })
        .catch(function() { content.innerHTML = '<div class="text-center py-8 text-suno-muted text-sm">오류가 발생했습니다.</div>'; });
}

function closeFollowModal() {
    document.getElementById('followModal').classList.add('hidden');
    document.body.style.overflow = '';
}
</script>

<?php include 'footer.php'; ?>
