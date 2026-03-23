<?php require_once 'db.php'; ?>
<?php $pageTitle = '음원 상세'; ?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<?php
// Get track ID
$trackId = isset($_GET['id']) ? intval($_GET['id']) : 1;

// Fetch song data
$stmt = $pdo->prepare('SELECT tracks.*, users.nickname as artist, users.id as artist_id FROM tracks JOIN users ON tracks.user_id = users.id WHERE tracks.id = ?');
$stmt->execute([$trackId]);
$song = $stmt->fetch();

if (!$song) {
    header('Location: music_list.php');
    exit;
}

// Fetch track genres
$tgStmt = $pdo->prepare('SELECT genre FROM track_genres WHERE track_id = ?');
$tgStmt->execute([$trackId]);
$song['genres'] = $tgStmt->fetchAll(PDO::FETCH_COLUMN);

$song['gradient'] = getGradient($song['id'], $song['genres'][0] ?? null);

// Fetch track moods
$tmStmt = $pdo->prepare('SELECT mood FROM track_moods WHERE track_id = ?');
$tmStmt->execute([$trackId]);
$song['moods'] = $tmStmt->fetchAll(PDO::FETCH_COLUMN);

// Artist stats
$artistStatStmt = $pdo->prepare('SELECT (SELECT COUNT(*) FROM tracks WHERE user_id = ?) as track_count, (SELECT COUNT(*) FROM follows WHERE following_id = ?) as follower_count');
$artistStatStmt->execute([$song['artist_id'], $song['artist_id']]);
$artistStats = $artistStatStmt->fetch();

// Fetch linked prompt
$promptStmt = $pdo->prepare('SELECT prompts.*, users.nickname as author FROM prompts JOIN users ON prompts.user_id = users.id WHERE prompts.linked_track_id = ? LIMIT 1');
$promptStmt->execute([$trackId]);
$linkedPrompt = $promptStmt->fetch();

if ($linkedPrompt) {
    // Fetch prompt genres
    $pgStmt = $pdo->prepare('SELECT genre FROM prompt_genres WHERE prompt_id = ?');
    $pgStmt->execute([$linkedPrompt['id']]);
    $linkedPrompt['genres'] = $pgStmt->fetchAll(PDO::FETCH_COLUMN);
}

// Fetch comments
$commentStmt = $pdo->prepare('SELECT track_comments.*, users.nickname as author, users.avatar_color FROM track_comments JOIN users ON track_comments.user_id = users.id WHERE track_id = ? ORDER BY created_at DESC');
$commentStmt->execute([$trackId]);
$comments = $commentStmt->fetchAll();

// Check if current user liked this track
$userLiked = false;
$userBookmarked = false;
if ($currentUser) {
    $likeCheckStmt = $pdo->prepare('SELECT id FROM track_likes WHERE track_id = ? AND user_id = ?');
    $likeCheckStmt->execute([$trackId, $currentUser['id']]);
    $userLiked = (bool)$likeCheckStmt->fetch();

    $pdo->exec("CREATE TABLE IF NOT EXISTS track_saves (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER NOT NULL,
        track_id INTEGER NOT NULL,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(user_id, track_id)
    )");
    $bmStmt = $pdo->prepare('SELECT id FROM track_saves WHERE track_id = ? AND user_id = ?');
    $bmStmt->execute([$trackId, $currentUser['id']]);
    $userBookmarked = (bool)$bmStmt->fetch();
}

// Fetch related tracks
$relatedStmt = $pdo->prepare('SELECT tracks.*, users.nickname as artist FROM tracks JOIN users ON tracks.user_id = users.id WHERE tracks.id != ? ORDER BY RANDOM() LIMIT 4');
$relatedStmt->execute([$trackId]);
$relatedTracks = $relatedStmt->fetchAll();

// Add gradient to related tracks (장르 기반)
foreach ($relatedTracks as &$rt) {
    $rgStmt = $pdo->prepare('SELECT genre FROM track_genres WHERE track_id = ? LIMIT 1');
    $rgStmt->execute([$rt['id']]);
    $rt['genre'] = $rgStmt->fetchColumn() ?: '';
    $rt['gradient'] = getGradient($rt['id'], $rt['genre']);
}
unset($rt);
?>

<style>
    /* Range slider 공통 리셋 */
    .range-slider {
        -webkit-appearance: none;
        appearance: none;
        width: 100%;
        height: 6px;
        border-radius: 3px;
        background: linear-gradient(to right, #8b5cf6 0%, #1e1e1e 0%);
        cursor: pointer;
        outline: none;
        margin: 0;
        padding: 0;
    }
    .range-slider::-webkit-slider-thumb {
        -webkit-appearance: none;
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #a78bfa;
        border: 2px solid #fff;
        cursor: pointer;
        box-shadow: 0 0 4px rgba(0,0,0,0.4);
        margin-top: -4px;
        transition: transform 0.1s ease;
    }
    .range-slider::-moz-range-thumb {
        width: 14px;
        height: 14px;
        border-radius: 50%;
        background: #a78bfa;
        border: 2px solid #fff;
        cursor: pointer;
        box-shadow: 0 0 4px rgba(0,0,0,0.4);
    }
    .range-slider::-webkit-slider-thumb:hover {
        transform: scale(1.2);
    }
    .range-slider::-webkit-slider-runnable-track {
        height: 6px;
        border-radius: 3px;
    }
    .range-slider::-moz-range-track {
        height: 6px;
        border-radius: 3px;
        background: transparent;
    }
    /* 프로그레스바: 호버 전에는 작은 thumb */
    .progress-slider::-webkit-slider-thumb {
        width: 0;
        height: 0;
        border: none;
        box-shadow: none;
        margin-top: -4px;
        transition: all 0.15s ease;
    }
    .player-bar:hover .progress-slider::-webkit-slider-thumb {
        width: 14px;
        height: 14px;
        border: 2px solid #fff;
        box-shadow: 0 0 4px rgba(0,0,0,0.4);
        margin-top: -4px;
    }
    /* 볼륨 슬라이더 */
    .volume-slider {
        width: 80px;
        height: 4px;
    }
    .volume-slider::-webkit-slider-thumb {
        width: 12px;
        height: 12px;
    }
    .volume-slider::-moz-range-thumb {
        width: 12px;
        height: 12px;
    }
</style>

<!-- Page Content -->
<main class="pt-20 min-h-screen">

    <!-- Breadcrumb -->
    <div class="border-b border-suno-border bg-suno-surface/30">
        <div class="max-w-7xl mx-auto px-6 py-3">
            <nav class="flex items-center gap-2 text-xs text-suno-muted">
                <a href="music_list.php" class="hover:text-white transition-colors">음원 공유</a>
                <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                </svg>
                <span class="text-white"><?php echo $song['title']; ?></span>
            </nav>
        </div>
    </div>

    <!-- Song Hero Section -->
    <section class="py-10 border-b border-suno-border">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex flex-col lg:flex-row gap-8">

                <!-- Album Art -->
                <div class="shrink-0">
                    <div class="relative w-full lg:w-72 aspect-square rounded-2xl bg-gradient-to-br <?php echo $song['gradient']; ?> border border-suno-border overflow-hidden shadow-2xl shadow-violet-900/20">
                        <?php if (!empty($song['cover_image_path'])): ?>
                        <img src="<?php echo htmlspecialchars($song['cover_image_path']); ?>" alt="" class="absolute inset-0 w-full h-full object-cover">
                        <?php else: ?>
                        <div class="absolute inset-0 flex items-center justify-center">
                            <svg class="w-20 h-20 text-white/15" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/>
                            </svg>
                        </div>
                        <?php endif; ?>
                        <!-- Genre badge -->
                        <?php if (!empty($song['genres'])): ?>
                        <div class="absolute top-4 left-4 bg-black/50 backdrop-blur-sm text-white/90 text-xs font-medium px-3 py-1 rounded-full">
                            <?php echo htmlspecialchars($song['genres'][0]); ?>
                        </div>
                        <?php endif; ?>
                    </div>
                </div>

                <!-- Song Info -->
                <div class="flex-1 min-w-0">
                    <div class="flex items-start justify-between gap-4">
                        <div class="min-w-0">
                            <h1 class="text-3xl lg:text-4xl font-extrabold truncate"><?php echo $song['title']; ?></h1>
                            <a href="profile.php?id=<?php echo $song['artist_id']; ?>" class="inline-flex items-center gap-2 mt-2 group">
                                <div class="w-7 h-7 rounded-full bg-gradient-to-r from-suno-accent to-purple-500 flex items-center justify-center text-xs font-bold">
                                    <?php echo mb_substr($song['artist'], 0, 1); ?>
                                </div>
                                <span class="text-suno-muted group-hover:text-suno-accent2 transition-colors font-medium text-sm"><?php echo $song['artist']; ?></span>
                            </a>
                        </div>
                        <?php if($currentUser && $currentUser['id'] == $song['artist_id']): ?>
                        <a href="music_edit.php?id=<?php echo $trackId; ?>" class="inline-flex items-center gap-1.5 border border-suno-border bg-suno-card hover:border-suno-accent/40 hover:bg-suno-accent/5 text-suno-muted hover:text-suno-accent2 px-4 py-2 rounded-xl text-xs font-medium transition-all shrink-0">
                            <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/></svg>
                            수정
                        </a>
                        <?php endif; ?>
                    </div>

                    <!-- Description -->
                    <?php if (!empty($song['description'])): ?>
                    <p class="text-suno-muted text-sm leading-relaxed mt-4 max-w-2xl"><?php echo nl2br(htmlspecialchars($song['description'])); ?></p>
                    <?php endif; ?>

                    <!-- Stats Row -->
                    <div class="flex items-center gap-6 mt-5">
                        <div class="flex items-center gap-1.5 text-sm text-suno-muted">
                            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>
                            </svg>
                            <span class="font-semibold text-white play-stat-count"><?php echo number_format($song['play_count']); ?></span> 재생
                        </div>
                        <div class="flex items-center gap-1.5 text-sm text-suno-muted">
                            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                <path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/>
                            </svg>
                            <span class="font-semibold text-white like-stat-count"><?php echo number_format($song['like_count']); ?></span> 좋아요
                        </div>
                        <div class="flex items-center gap-1.5 text-sm text-suno-muted">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/>
                            </svg>
                            <span class="font-semibold text-white"><?php echo number_format($song['share_count']); ?></span> 공유
                        </div>
                    </div>

                    <!-- Action Buttons -->
                    <div class="flex items-center gap-3 mt-6">
                        <button id="likeBtn" onclick="toggleLike(this)" class="like-btn inline-flex items-center gap-2 <?php echo $userLiked ? 'bg-pink-600 hover:bg-pink-700' : 'bg-suno-accent hover:bg-suno-accent2'; ?> text-white font-semibold px-6 py-2.5 rounded-xl transition-all text-sm">
                            <svg class="w-4 h-4" fill="<?php echo $userLiked ? 'currentColor' : 'none'; ?>" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 8.25c0-2.485-2.099-4.5-4.688-4.5-1.935 0-3.597 1.126-4.312 2.733-.715-1.607-2.377-2.733-4.313-2.733C5.1 3.75 3 5.765 3 8.25c0 7.22 9 12 9 12s9-4.78 9-12z"/>
                            </svg>
                            <span id="likeBtnCount"><?php echo number_format($song['like_count']); ?></span> 좋아요
                        </button>
                        <button id="bookmarkBtn" onclick="toggleBookmark(this)" class="inline-flex items-center gap-2 border <?php echo $userBookmarked ? 'border-yellow-500/40 bg-yellow-500/10 text-yellow-400' : 'border-suno-border bg-suno-card text-white'; ?> hover:border-suno-accent/40 font-medium px-5 py-2.5 rounded-xl transition-all text-sm">
                            <svg class="w-4 h-4" fill="<?php echo $userBookmarked ? 'currentColor' : 'none'; ?>" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 5a2 2 0 012-2h10a2 2 0 012 2v16l-7-3.5L5 21V5z"/>
                            </svg>
                            북마크
                        </button>
                        <button onclick="shareTrack()" class="inline-flex items-center gap-2 border border-suno-border hover:border-suno-accent/40 bg-suno-card text-white font-medium px-5 py-2.5 rounded-xl transition-all text-sm">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8.684 13.342C8.886 12.938 9 12.482 9 12c0-.482-.114-.938-.316-1.342m0 2.684a3 3 0 110-2.684m0 2.684l6.632 3.316m-6.632-6l6.632-3.316m0 0a3 3 0 105.367-2.684 3 3 0 00-5.367 2.684zm0 9.316a3 3 0 105.368 2.684 3 3 0 00-5.368-2.684z"/>
                            </svg>
                            공유
                        </button>
                        <?php if ($currentUser && $currentUser['id'] != $song['artist_id']): ?>
                        <button onclick="openReportModal('track', <?php echo $trackId; ?>)" class="inline-flex items-center gap-2 border border-suno-border hover:border-red-500/40 bg-suno-card text-suno-muted hover:text-red-400 font-medium px-5 py-2.5 rounded-xl transition-all text-sm" title="신고">
                            <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
                            </svg>
                            신고
                        </button>
                        <?php endif; ?>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <?php if($song['has_audio_file'] && !empty($song['audio_file_path'])): ?>
    <!-- Audio Player Bar (직접 업로드된 음원 파일이 있는 경우) -->
    <audio id="audioPlayer" src="<?php echo htmlspecialchars($song['audio_file_path']); ?>" preload="metadata"></audio>
    <section class="border-b border-suno-border bg-suno-card/50 player-bar">
        <div class="max-w-7xl mx-auto px-6 py-4">
            <div class="flex flex-col gap-3">
                <!-- Progress Bar -->
                <div class="flex items-center gap-3">
                    <span id="currentTime" class="text-xs text-suno-muted font-mono w-10 text-right">0:00</span>
                    <div class="flex-1">
                        <input type="range" min="0" max="1000" value="0" step="1" id="progressBar" class="range-slider progress-slider">
                    </div>
                    <span id="totalTime" class="text-xs text-suno-muted font-mono w-10">--:--</span>
                </div>
                <!-- Controls -->
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-3">
                        <button onclick="seekBy(-10)" class="text-suno-muted hover:text-white transition-colors" title="-10초">
                            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M8.445 14.832A1 1 0 0010 14V6a1 1 0 00-1.555-.832l-5 3.333a1 1 0 000 1.664l5 3.333zM15.445 14.832A1 1 0 0017 14V6a1 1 0 00-1.555-.832l-5 3.333a1 1 0 000 1.664l5 3.333z"/>
                            </svg>
                        </button>
                        <button id="playBtn" class="w-10 h-10 bg-suno-accent hover:bg-suno-accent2 rounded-full flex items-center justify-center transition-colors shadow-lg shadow-suno-accent/20" onclick="togglePlay()">
                            <svg class="w-5 h-5 text-white ml-0.5 play-icon" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>
                            </svg>
                            <svg class="w-5 h-5 text-white pause-icon hidden" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M5.75 3a.75.75 0 00-.75.75v12.5c0 .414.336.75.75.75h1.5a.75.75 0 00.75-.75V3.75A.75.75 0 007.25 3h-1.5zM12.75 3a.75.75 0 00-.75.75v12.5c0 .414.336.75.75.75h1.5a.75.75 0 00.75-.75V3.75a.75.75 0 00-.75-.75h-1.5z"/>
                            </svg>
                        </button>
                        <button onclick="seekBy(10)" class="text-suno-muted hover:text-white transition-colors" title="+10초">
                            <svg class="w-5 h-5" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M11.555 5.168A1 1 0 0010 6v8a1 1 0 001.555.832l5-3.333a1 1 0 000-1.664l-5-3.333zM4.555 5.168A1 1 0 003 6v8a1 1 0 001.555.832l5-3.333a1 1 0 000-1.664l-5-3.333z"/>
                            </svg>
                        </button>
                    </div>
                    <div class="flex items-center gap-2">
                        <button onclick="toggleMute()" class="text-suno-muted hover:text-white transition-colors" id="volumeIcon">
                            <svg class="w-4 h-4" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M10 3.75a.75.75 0 00-1.264-.546L4.703 7H3.167a.75.75 0 00-.7.48A6.985 6.985 0 002 10c0 .887.165 1.737.468 2.52.111.29.39.48.7.48h1.535l4.033 3.796A.75.75 0 0010 16.25V3.75zM15.95 5.05a.75.75 0 00-1.06 1.061 5.5 5.5 0 010 7.778.75.75 0 001.06 1.06 7 7 0 000-9.899z"/>
                                <path d="M13.829 7.172a.75.75 0 00-1.061 1.06 2.5 2.5 0 010 3.536.75.75 0 001.06 1.06 4 4 0 000-5.656z"/>
                            </svg>
                        </button>
                        <input type="range" min="0" max="100" value="75" id="volumeSlider" class="range-slider volume-slider" oninput="changeVolume(this.value)">
                    </div>
                </div>
            </div>
        </div>
    </section>
    <?php elseif(!empty($song['suno_link'])): ?>
    <!-- Suno 링크만 있는 경우: Suno에서 듣기 배너 -->
    <section class="border-b border-suno-border bg-suno-accent/5">
        <div class="max-w-7xl mx-auto px-6 py-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-suno-accent/20 rounded-full flex items-center justify-center">
                        <svg class="w-5 h-5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/>
                        </svg>
                    </div>
                    <div>
                        <p class="text-sm font-semibold">이 곡은 Suno에서 재생됩니다</p>
                        <p class="text-xs text-suno-muted">Suno 공유 링크로 등록된 곡입니다</p>
                    </div>
                </div>
                <a href="<?php echo $song['suno_link']; ?>" target="_blank" rel="noopener noreferrer" onclick="incrementPlayCount()"
                   class="inline-flex items-center gap-2 bg-suno-accent hover:bg-suno-accent2 text-white font-semibold px-5 py-2.5 rounded-xl transition-all text-sm">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M10 6H6a2 2 0 00-2 2v10a2 2 0 002 2h10a2 2 0 002-2v-4M14 4h6m0 0v6m0-6L10 14"/>
                    </svg>
                    Suno에서 듣기
                </a>
            </div>
        </div>
    </section>
    <?php endif; ?>

    <!-- Song Details & Prompt -->
    <section class="py-10">
        <div class="max-w-7xl mx-auto px-6">
            <div class="grid lg:grid-cols-3 gap-8">

                <!-- Left: Song Info & Prompt -->
                <div class="lg:col-span-2 space-y-8">

                    <!-- Suno 공유 링크 (Suno 링크가 있으면 표시) -->
                    <?php if(!empty($song['suno_link'])): ?>
                    <div class="bg-suno-card border border-suno-border rounded-2xl p-6">
                        <h2 class="text-lg font-bold mb-3">Suno 공유 링크</h2>
                        <p class="text-xs text-suno-muted mb-4">Suno에서 원곡을 직접 들어보세요</p>
                        <a href="<?php echo $song['suno_link']; ?>" target="_blank" rel="noopener noreferrer" onclick="incrementPlayCount()" class="inline-flex items-center gap-2 bg-suno-surface border border-suno-border hover:border-suno-accent/40 rounded-xl px-5 py-3 transition-colors group">
                            <svg class="w-5 h-5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"/>
                            </svg>
                            <span class="text-sm text-suno-muted group-hover:text-white transition-colors font-medium"><?php echo $song['suno_link']; ?></span>
                        </a>
                    </div>
                    <?php endif; ?>

                    <!-- 연결된 프롬프트 (프롬프트 공유에서 자동 연결) -->
                    <?php if($linkedPrompt): ?>
                    <a href="prompt_detail.php?id=<?php echo $linkedPrompt['id']; ?>" class="block bg-suno-card border border-suno-accent/20 hover:border-suno-accent/40 rounded-2xl p-5 transition-all group">
                        <div class="flex items-center gap-4">
                            <!-- Icon -->
                            <div class="w-11 h-11 bg-suno-accent/10 border border-suno-accent/20 rounded-xl flex items-center justify-center flex-shrink-0">
                                <svg class="w-5 h-5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09zM18.259 8.715L18 9.75l-.259-1.035a3.375 3.375 0 00-2.455-2.456L14.25 6l1.036-.259a3.375 3.375 0 002.455-2.456L18 2.25l.259 1.035a3.375 3.375 0 002.455 2.456L21.75 6l-1.036.259a3.375 3.375 0 00-2.455 2.456z"/>
                                </svg>
                            </div>
                            <!-- Info -->
                            <div class="flex-1 min-w-0">
                                <div class="flex items-center gap-2 mb-1">
                                    <span class="text-[10px] text-suno-accent font-semibold uppercase tracking-wider">연결된 프롬프트</span>
                                    <div class="flex gap-1">
                                        <?php foreach($linkedPrompt['genres'] as $genre): ?>
                                        <span class="text-[10px] bg-suno-surface border border-suno-border text-suno-muted px-1.5 py-px rounded"><?php echo $genre; ?></span>
                                        <?php endforeach; ?>
                                    </div>
                                </div>
                                <p class="text-sm font-semibold truncate group-hover:text-suno-accent2 transition-colors"><?php echo $linkedPrompt['title']; ?></p>
                                <div class="flex items-center gap-3 mt-1">
                                    <span class="text-xs text-suno-muted"><?php echo $linkedPrompt['author']; ?></span>
                                    <span class="flex items-center gap-1 text-xs text-suno-muted/50">
                                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/></svg>
                                        <?php echo number_format($linkedPrompt['like_count']); ?>
                                    </span>
                                    <span class="flex items-center gap-1 text-xs text-suno-muted/50">
                                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/></svg>
                                        <?php echo number_format($linkedPrompt['copy_count']); ?>
                                    </span>
                                </div>
                            </div>
                            <!-- Arrow -->
                            <svg class="w-5 h-5 text-suno-muted/30 group-hover:text-suno-accent transition-colors flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                            </svg>
                        </div>
                    </a>
                    <?php endif; ?>

                    <!-- Comments Section -->
                    <div class="bg-suno-card border border-suno-border rounded-2xl p-6">
                        <h2 class="text-lg font-bold mb-6">댓글 <span class="text-suno-muted font-normal text-sm" id="commentCount"><?php echo count($comments); ?></span></h2>

                        <?php if ($currentUser): ?>
                        <!-- Comment Input -->
                        <form action="comment_ok.php" method="POST" class="flex items-start gap-3 mb-8">
                            <input type="hidden" name="type" value="track">
                            <input type="hidden" name="target_id" value="<?php echo $trackId; ?>">
                            <div class="w-8 h-8 rounded-full bg-gradient-to-r <?php echo $currentUser['avatar_color']; ?> flex items-center justify-center text-xs font-bold shrink-0">
                                <?php echo mb_substr($currentUser['nickname'], 0, 1); ?>
                            </div>
                            <div class="flex-1">
                                <textarea name="content" class="w-full bg-suno-dark border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/60 focus:outline-none focus:border-suno-accent/50 transition-colors resize-none" rows="3" placeholder="댓글을 작성해주세요..." required></textarea>
                                <div class="flex justify-end mt-2">
                                    <button type="submit" class="bg-suno-accent hover:bg-suno-accent2 text-white text-xs font-semibold px-4 py-2 rounded-lg transition-colors">
                                        댓글 작성
                                    </button>
                                </div>
                            </div>
                        </form>
                        <?php endif; ?>

                        <!-- Comment List -->
                        <div class="space-y-6">
                            <?php foreach ($comments as $comment): ?>
                            <div class="flex items-start gap-3">
                                <a href="profile.php?id=<?php echo $comment['user_id']; ?>" class="w-8 h-8 rounded-full bg-gradient-to-r <?php echo $comment['avatar_color']; ?> flex items-center justify-center text-xs font-bold shrink-0 hover:ring-2 hover:ring-suno-accent/50 transition-all">
                                    <?php echo mb_substr($comment['author'], 0, 1); ?>
                                </a>
                                <div class="flex-1 min-w-0">
                                    <div class="flex items-center gap-2 mb-1">
                                        <a href="profile.php?id=<?php echo $comment['user_id']; ?>" class="text-sm font-semibold hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($comment['author']); ?></a>
                                        <span class="text-xs text-suno-muted/50"><?php echo timeAgo($comment['created_at']); ?></span>
                                    </div>
                                    <p class="text-sm text-suno-muted leading-relaxed"><?php echo $comment['content']; ?></p>
                                    <div class="flex items-center gap-4 mt-2">
                                        <button onclick="toggleCommentLike(this, <?php echo $comment['id']; ?>)" class="flex items-center gap-1 text-xs text-suno-muted/60 hover:text-suno-accent2 transition-colors">
                                            <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                                                <path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/>
                                            </svg>
                                            <span><?php echo number_format($comment['like_count']); ?></span>
                                        </button>
                                    </div>
                                </div>
                            </div>
                            <?php endforeach; ?>
                        </div>
                    </div>
                </div>

                <!-- Right Sidebar -->
                <div class="space-y-6">

                    <!-- Artist Card -->
                    <div class="bg-suno-card border border-suno-border rounded-2xl p-5">
                        <h3 class="text-sm font-bold mb-4 text-suno-muted">아티스트</h3>
                        <a href="profile.php?id=<?php echo $song['artist_id']; ?>" class="flex items-center gap-3 group">
                            <div class="w-12 h-12 rounded-full bg-gradient-to-r from-suno-accent to-purple-500 flex items-center justify-center text-lg font-bold">
                                <?php echo mb_substr($song['artist'], 0, 1); ?>
                            </div>
                            <div>
                                <p class="font-semibold text-sm group-hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($song['artist']); ?></p>
                                <p class="text-xs text-suno-muted">트랙 <?php echo number_format($artistStats['track_count']); ?>개 &middot; 팔로워 <?php echo number_format($artistStats['follower_count']); ?></p>
                            </div>
                        </a>
                        <?php
                        $isFollowing = false;
                        if ($currentUser && $currentUser['id'] != $song['artist_id']) {
                            $fStmt = $pdo->prepare('SELECT id FROM follows WHERE follower_id = ? AND following_id = ?');
                            $fStmt->execute([$currentUser['id'], $song['artist_id']]);
                            $isFollowing = (bool)$fStmt->fetch();
                        }
                        ?>
                        <?php if (!$currentUser || $currentUser['id'] != $song['artist_id']): ?>
                        <button id="followBtn" onclick="toggleFollow(this)" class="w-full mt-4 border <?php echo $isFollowing ? 'border-suno-accent/40 bg-suno-accent/10 text-suno-accent2' : 'border-suno-border bg-suno-surface text-white'; ?> hover:border-suno-accent/40 text-xs font-semibold py-2.5 rounded-lg transition-colors">
                            <?php echo $isFollowing ? '팔로잉' : '팔로우'; ?>
                        </button>
                        <?php endif; ?>
                    </div>

                    <!-- Quick Stats -->
                    <div class="bg-suno-card border border-suno-border rounded-2xl p-5">
                        <h3 class="text-sm font-bold mb-4 text-suno-muted">통계</h3>
                        <div class="space-y-3">
                            <div class="flex items-center justify-between">
                                <span class="text-xs text-suno-muted">재생 수</span>
                                <span class="text-sm font-semibold"><?php echo number_format($song['play_count']); ?></span>
                            </div>
                            <div class="w-full h-px bg-suno-border"></div>
                            <div class="flex items-center justify-between">
                                <span class="text-xs text-suno-muted">좋아요</span>
                                <span class="text-sm font-semibold"><?php echo number_format($song['like_count']); ?></span>
                            </div>
                            <div class="w-full h-px bg-suno-border"></div>
                            <div class="flex items-center justify-between">
                                <span class="text-xs text-suno-muted">공유</span>
                                <span class="text-sm font-semibold"><?php echo number_format($song['share_count']); ?></span>
                            </div>
                            <div class="w-full h-px bg-suno-border"></div>
                            <div class="flex items-center justify-between">
                                <span class="text-xs text-suno-muted">댓글</span>
                                <span class="text-sm font-semibold"><?php echo count($comments); ?></span>
                            </div>
                        </div>
                    </div>

                    <!-- Tags -->
                    <?php if (!empty($song['genres']) || !empty($song['moods'])): ?>
                    <div class="bg-suno-card border border-suno-border rounded-2xl p-5">
                        <h3 class="text-sm font-bold mb-3 text-suno-muted">태그</h3>
                        <div class="flex flex-wrap gap-2">
                            <?php foreach ($song['genres'] as $genre): ?>
                            <span class="border border-suno-accent/30 bg-suno-accent/10 px-3 py-1 rounded-full text-xs text-suno-accent2"><?php echo htmlspecialchars($genre); ?></span>
                            <?php endforeach; ?>
                            <?php foreach ($song['moods'] as $mood): ?>
                            <span class="border border-suno-border bg-suno-surface px-3 py-1 rounded-full text-xs text-suno-muted"><?php echo htmlspecialchars($mood); ?></span>
                            <?php endforeach; ?>
                        </div>
                    </div>
                    <?php endif; ?>
                </div>
            </div>
        </div>
    </section>

    <!-- Related Tracks -->
    <section class="py-10 border-t border-suno-border bg-suno-surface/20">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex items-center justify-between mb-6">
                <h2 class="text-xl font-bold">더 많은 음원</h2>
                <a href="music_list.php" class="text-sm text-suno-accent hover:text-suno-accent2 transition-colors font-medium flex items-center gap-1">
                    전체보기
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"/>
                    </svg>
                </a>
            </div>
            <div class="grid grid-cols-2 sm:grid-cols-3 md:grid-cols-4 gap-5">
                <?php foreach ($relatedTracks as $rt): ?>
                <a href="music_detail.php?id=<?php echo $rt['id']; ?>" class="music-card group block">
                    <div class="relative aspect-square rounded-xl bg-gradient-to-br <?php echo $rt['gradient']; ?> border border-suno-border overflow-hidden mb-3">
                        <?php if (!empty($rt['cover_image_path'])): ?>
                        <img src="<?php echo htmlspecialchars($rt['cover_image_path']); ?>" alt="" class="absolute inset-0 w-full h-full object-cover">
                        <?php else: ?>
                        <div class="absolute inset-0 flex items-center justify-center">
                            <svg class="w-10 h-10 text-white/15" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/>
                            </svg>
                        </div>
                        <?php endif; ?>
                        <?php if (!empty($rt['duration'])): ?>
                        <div class="absolute bottom-2 right-2 bg-black/60 text-white text-[10px] font-medium px-1.5 py-0.5 rounded">
                            <?php echo htmlspecialchars($rt['duration']); ?>
                        </div>
                        <?php endif; ?>
                        <div class="play-overlay absolute inset-0 bg-black/40 flex items-center justify-center">
                            <div class="w-12 h-12 bg-suno-accent rounded-full flex items-center justify-center shadow-lg shadow-suno-accent/30">
                                <svg class="w-5 h-5 text-white ml-0.5" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>
                                </svg>
                            </div>
                        </div>
                    </div>
                    <h3 class="font-semibold text-sm truncate group-hover:text-suno-accent2 transition-colors"><?php echo $rt['title']; ?></h3>
                    <p class="text-suno-muted text-xs mt-0.5 truncate"><?php echo $rt['artist']; ?></p>
                    <p class="text-suno-muted/60 text-[11px] mt-1 flex items-center gap-1">
                        <svg class="w-3 h-3" fill="currentColor" viewBox="0 0 20 20">
                            <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>
                        </svg>
                        <?php echo number_format($rt['play_count']); ?>
                    </p>
                </a>
                <?php endforeach; ?>
            </div>
        </div>
    </section>

</main>

<script>
// ── 슬라이더 배경 그라데이션 업데이트 ──
function updateSliderBg(slider, pct, colorA, colorB) {
    slider.style.background = 'linear-gradient(to right, ' + colorA + ' ' + pct + '%, ' + colorB + ' ' + pct + '%)';
}

// ── 오디오 플레이어 ──
const audio = document.getElementById('audioPlayer');
const playBtn = document.getElementById('playBtn');
const progressBar = document.getElementById('progressBar');
const currentTimeEl = document.getElementById('currentTime');
const totalTimeEl = document.getElementById('totalTime');
const volumeSlider = document.getElementById('volumeSlider');
let isSeeking = false;

function formatTime(sec) {
    if (isNaN(sec) || !isFinite(sec)) return '--:--';
    const m = Math.floor(sec / 60);
    const s = Math.floor(sec % 60);
    return m + ':' + (s < 10 ? '0' : '') + s;
}

if (audio) {
    audio.volume = 0.75;

    audio.addEventListener('loadedmetadata', function() {
        totalTimeEl.textContent = formatTime(audio.duration);
    });

    audio.addEventListener('timeupdate', function() {
        if (isSeeking) return;
        const pct = (audio.currentTime / audio.duration) * 1000 || 0;
        progressBar.value = pct;
        updateSliderBg(progressBar, (pct / 10), '#8b5cf6', '#1e1e1e');
        currentTimeEl.textContent = formatTime(audio.currentTime);
    });

    audio.addEventListener('ended', function() {
        playBtn.querySelector('.play-icon').classList.remove('hidden');
        playBtn.querySelector('.pause-icon').classList.add('hidden');
        progressBar.value = 0;
        updateSliderBg(progressBar, 0, '#8b5cf6', '#1e1e1e');
        currentTimeEl.textContent = '0:00';
    });

    // 드래그 중에는 timeupdate 차단
    progressBar.addEventListener('mousedown', function() { isSeeking = true; });
    progressBar.addEventListener('touchstart', function() { isSeeking = true; });

    progressBar.addEventListener('input', function() {
        const pct = this.value / 10;
        updateSliderBg(this, pct, '#8b5cf6', '#1e1e1e');
        currentTimeEl.textContent = formatTime((this.value / 1000) * audio.duration);
    });

    progressBar.addEventListener('change', function() {
        audio.currentTime = (this.value / 1000) * audio.duration;
        isSeeking = false;
    });
    progressBar.addEventListener('mouseup', function() { isSeeking = false; });
    progressBar.addEventListener('touchend', function() { isSeeking = false; });
}

// 볼륨 슬라이더 초기 배경
if (volumeSlider) {
    updateSliderBg(volumeSlider, 75, '#a78bfa', '#1e1e1e');
}

function togglePlay() {
    if (!audio) return;
    const playIcon = playBtn.querySelector('.play-icon');
    const pauseIcon = playBtn.querySelector('.pause-icon');
    if (audio.paused) {
        audio.play();
        playIcon.classList.add('hidden');
        pauseIcon.classList.remove('hidden');
    } else {
        audio.pause();
        playIcon.classList.remove('hidden');
        pauseIcon.classList.add('hidden');
    }
}

function seekBy(seconds) {
    if (!audio) return;
    audio.currentTime = Math.max(0, Math.min(audio.duration, audio.currentTime + seconds));
}

function changeVolume(val) {
    if (!audio) return;
    audio.volume = val / 100;
    updateSliderBg(volumeSlider, val, '#a78bfa', '#1e1e1e');
}

function toggleMute() {
    if (!audio) return;
    audio.muted = !audio.muted;
    const v = audio.muted ? 0 : audio.volume * 100;
    if (volumeSlider) {
        volumeSlider.value = v;
        updateSliderBg(volumeSlider, v, '#a78bfa', '#1e1e1e');
    }
}

function copyPrompt() {
    <?php if($linkedPrompt): ?>
    const promptText = <?php echo json_encode($linkedPrompt['prompt_text']); ?>;
    navigator.clipboard.writeText(promptText).then(() => {
        alert('프롬프트가 복사되었습니다!');
    });
    <?php endif; ?>
}

function copyLyrics() {
    <?php if($linkedPrompt && !empty($linkedPrompt['lyrics'])): ?>
    const lyricsText = <?php echo json_encode($linkedPrompt['lyrics']); ?>;
    navigator.clipboard.writeText(lyricsText).then(() => {
        alert('가사가 복사되었습니다!');
    });
    <?php endif; ?>
}

// ── 재생횟수 증가 ──
let playCountSent = false;
if (audio) {
    audio.addEventListener('play', function() {
        if (playCountSent) return;
        playCountSent = true;
        const fd = new FormData();
        fd.append('track_id', '<?php echo $trackId; ?>');
        fetch('play_ok.php', { method: 'POST', body: fd })
            .then(r => r.json())
            .then(data => {
                if (data.success) {
                    document.querySelectorAll('.play-stat-count').forEach(el => {
                        el.textContent = data.play_count.toLocaleString();
                    });
                }
            });
    });
}

// ── 공유 ──
function shareTrack() {
    const shareData = {
        title: <?php echo json_encode($song['title']); ?>,
        text: <?php echo json_encode($song['artist'] . '의 음원'); ?>,
        url: window.location.href
    };
    if (navigator.share) {
        navigator.share(shareData);
    } else {
        navigator.clipboard.writeText(window.location.href).then(() => {
            alert('링크가 복사되었습니다!');
        });
    }
    // share_count 증가
    const fd = new FormData();
    fd.append('track_id', '<?php echo $trackId; ?>');
    fetch('share_ok.php', { method: 'POST', body: fd }).catch(() => {});
}

// ── 북마크 ──
function toggleBookmark(btn) {
    <?php if (!$currentUser): ?>
    alert('로그인이 필요합니다.');
    window.location.href = 'login.php';
    return;
    <?php endif; ?>

    const fd = new FormData();
    fd.append('type', 'track');
    fd.append('target_id', '<?php echo $trackId; ?>');

    fetch('bookmark_ok.php', { method: 'POST', body: fd })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const svg = btn.querySelector('svg');
                if (data.bookmarked) {
                    btn.classList.remove('border-suno-border', 'bg-suno-card', 'text-white');
                    btn.classList.add('border-yellow-500/40', 'bg-yellow-500/10', 'text-yellow-400');
                    svg.setAttribute('fill', 'currentColor');
                } else {
                    btn.classList.remove('border-yellow-500/40', 'bg-yellow-500/10', 'text-yellow-400');
                    btn.classList.add('border-suno-border', 'bg-suno-card', 'text-white');
                    svg.setAttribute('fill', 'none');
                }
            }
        });
}

// ── 댓글 좋아요 ──
function toggleCommentLike(btn, commentId) {
    <?php if (!$currentUser): ?>
    alert('로그인이 필요합니다.');
    return;
    <?php endif; ?>

    const fd = new FormData();
    fd.append('type', 'comment');
    fd.append('target_id', commentId);

    fetch('like_ok.php', { method: 'POST', body: fd })
        .then(r => r.json())
        .then(data => {
            if (data.success) {
                const countEl = btn.querySelector('span');
                countEl.textContent = data.like_count.toLocaleString();
                if (data.liked) {
                    btn.classList.add('text-pink-500');
                    btn.classList.remove('text-suno-muted/60');
                } else {
                    btn.classList.remove('text-pink-500');
                    btn.classList.add('text-suno-muted/60');
                }
            }
        });
}

// ── 팔로우 ──
function toggleFollow(btn) {
    <?php if (!$currentUser): ?>
    alert('로그인이 필요합니다.');
    window.location.href = 'login.php';
    return;
    <?php endif; ?>

    var fd = new FormData();
    fd.append('user_id', '<?php echo $song['artist_id']; ?>');

    fetch('follow_ok.php', { method: 'POST', body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                if (data.followed) {
                    btn.textContent = '팔로잉';
                    btn.classList.remove('border-suno-border', 'bg-suno-surface', 'text-white');
                    btn.classList.add('border-suno-accent/40', 'bg-suno-accent/10', 'text-suno-accent2');
                } else {
                    btn.textContent = '팔로우';
                    btn.classList.remove('border-suno-accent/40', 'bg-suno-accent/10', 'text-suno-accent2');
                    btn.classList.add('border-suno-border', 'bg-suno-surface', 'text-white');
                }
            } else {
                alert(data.message || '오류가 발생했습니다.');
            }
        })
        .catch(function() { alert('서버 오류가 발생했습니다.'); });
}

// ── Suno 링크 재생수 증가 ──
var sunoPlayCountSent = false;
function incrementPlayCount() {
    if (sunoPlayCountSent) return;
    sunoPlayCountSent = true;
    var fd = new FormData();
    fd.append('track_id', '<?php echo $trackId; ?>');
    fetch('play_ok.php', { method: 'POST', body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                document.querySelectorAll('.play-stat-count').forEach(function(el) {
                    el.textContent = data.play_count.toLocaleString();
                });
            }
        })
        .catch(function() {});
}

// ── 좋아요 ──
function toggleLike(btn) {
    <?php if (!$currentUser): ?>
    alert('로그인이 필요합니다.');
    window.location.href = 'login.php';
    return;
    <?php endif; ?>

    const formData = new FormData();
    formData.append('type', 'track');
    formData.append('target_id', '<?php echo $trackId; ?>');

    fetch('like_ok.php', {
        method: 'POST',
        body: formData
    })
    .then(res => res.json())
    .then(data => {
        if (data.success) {
            const svg = btn.querySelector('svg');
            const countEl = document.getElementById('likeBtnCount');
            const statCount = document.querySelector('.like-stat-count');
            if (data.liked) {
                svg.setAttribute('fill', 'currentColor');
                btn.classList.remove('bg-suno-accent', 'hover:bg-suno-accent2');
                btn.classList.add('bg-pink-600', 'hover:bg-pink-700');
            } else {
                svg.setAttribute('fill', 'none');
                btn.classList.remove('bg-pink-600', 'hover:bg-pink-700');
                btn.classList.add('bg-suno-accent', 'hover:bg-suno-accent2');
            }
            countEl.textContent = data.like_count.toLocaleString();
            if (statCount) statCount.textContent = data.like_count.toLocaleString();
        } else {
            alert(data.message || '오류가 발생했습니다.');
        }
    })
    .catch(() => alert('서버 오류가 발생했습니다.'));
}
</script>

<?php include 'report_modal.php'; ?>
<?php include 'footer.php'; ?>
