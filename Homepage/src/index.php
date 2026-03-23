<?php require_once 'db.php'; ?>
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SUNO Community - AI 음악 커뮤니티</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: {
                        'inter': ['Inter', 'sans-serif'],
                    },
                    colors: {
                        'suno': {
                            'dark': '#0a0a0a',
                            'card': '#141414',
                            'border': '#1e1e1e',
                            'accent': '#8b5cf6',
                            'accent2': '#a78bfa',
                            'hover': '#1a1a2e',
                            'muted': '#71717a',
                            'surface': '#18181b',
                        }
                    }
                }
            }
        }
    </script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; }
        
        /* Custom scrollbar */
        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0a0a0a; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }
        
        /* Card hover effect */
        .music-card {
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .music-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 40px rgba(139,92,246,0.15);
        }
        .music-card:hover .play-overlay {
            opacity: 1;
        }
        .play-overlay {
            opacity: 0;
            transition: opacity 0.3s ease;
        }

        /* Slide indicators */
        .slide-dot {
            transition: all 0.3s ease;
        }
        .slide-dot.active {
            width: 24px;
            background: #8b5cf6;
        }

        /* Waveform animation */
        @keyframes wave {
            0%, 100% { height: 8px; }
            50% { height: 24px; }
        }
        .wave-bar {
            animation: wave 1.2s ease-in-out infinite;
        }

        /* Genre tag hover */
        .genre-tag {
            transition: all 0.3s ease;
        }
        .genre-tag:hover {
            background: rgba(139,92,246,0.2);
            border-color: #8b5cf6;
            color: #a78bfa;
        }

        /* Navbar blur */
        .nav-blur {
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
        }

        /* Dropdown menu */
        .nav-dropdown {
            opacity: 0;
            visibility: hidden;
            transform: translateY(8px);
            transition: all 0.2s ease;
        }
        .nav-item:hover .nav-dropdown {
            opacity: 1;
            visibility: visible;
            transform: translateY(0);
        }
        .nav-dropdown-item {
            transition: all 0.15s ease;
        }
        .nav-dropdown-item:hover {
            background: rgba(139,92,246,0.08);
        }
        .nav-dropdown-item:hover .dropdown-icon {
            color: #8b5cf6;
        }

        /* Mobile menu */
        .mobile-menu {
            max-height: 0;
            overflow: hidden;
            transition: max-height 0.4s ease;
        }
        .mobile-menu.open {
            max-height: 80vh;
            overflow-y: auto;
        }

        /* Carousel */
        .carousel-track {
            display: flex;
            transition: transform 0.5s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .carousel-track:hover { }
        .carousel-btn {
            transition: all 0.2s ease;
        }
        .carousel-btn:hover {
            background: rgba(139,92,246,0.15);
            border-color: rgba(139,92,246,0.4);
        }
        .carousel-indicator {
            transition: all 0.3s ease;
        }
        .carousel-indicator.active {
            width: 24px;
            background: #8b5cf6;
        }

        /* Hide scrollbar */
        .scrollbar-hide::-webkit-scrollbar { display: none; }
        .scrollbar-hide { -ms-overflow-style: none; scrollbar-width: none; }
    </style>
</head>
<body class="bg-suno-dark text-white font-inter">

    <?php include 'navbar.php'; ?>

    <!-- Community Board (리스트형) -->
    <section class="pt-24 pb-8">
        <div class="max-w-7xl mx-auto px-6">
            <?php
            // 주간 인기 음원: like_count + play_count 기준 상위 12개
            $weeklyStmt = $pdo->query('
                SELECT t.id, t.title, t.cover_image_path, u.nickname, t.play_count, t.like_count,
                       (SELECT genre FROM track_genres WHERE track_id = t.id LIMIT 1) as genre
                FROM tracks t
                JOIN users u ON t.user_id = u.id
                WHERE t.created_at >= datetime("now", "-7 days")
                ORDER BY (t.like_count * 3 + t.play_count) DESC
                LIMIT 12
            ');
            $weeklyRows = $weeklyStmt->fetchAll();
            if (count($weeklyRows) < 12) {
                $weeklyStmt = $pdo->query('
                    SELECT t.id, t.title, t.cover_image_path, u.nickname, t.play_count, t.like_count,
                           (SELECT genre FROM track_genres WHERE track_id = t.id LIMIT 1) as genre
                    FROM tracks t
                    JOIN users u ON t.user_id = u.id
                    ORDER BY (t.like_count * 3 + t.play_count) DESC, t.created_at DESC
                    LIMIT 12
                ');
                $weeklyRows = $weeklyStmt->fetchAll();
            }
            $weeklyTracks = array_map(function($row) {
                return [
                    'id' => (int)$row['id'],
                    'title' => $row['title'],
                    'artist' => $row['nickname'],
                    'plays' => formatCount($row['play_count']),
                    'cover' => $row['cover_image_path'] ?: '',
                    'gradient' => getGradient($row['id'], $row['genre'] ?? null),
                ];
            }, $weeklyRows);

            // 월간 인기 음원
            $monthlyStmt = $pdo->query('
                SELECT t.id, t.title, t.cover_image_path, u.nickname, t.play_count, t.like_count,
                       (SELECT genre FROM track_genres WHERE track_id = t.id LIMIT 1) as genre
                FROM tracks t
                JOIN users u ON t.user_id = u.id
                WHERE t.created_at >= datetime("now", "-30 days")
                ORDER BY (t.like_count * 3 + t.play_count) DESC
                LIMIT 12
            ');
            $monthlyRows = $monthlyStmt->fetchAll();
            if (count($monthlyRows) < 12) {
                $monthlyStmt = $pdo->query('
                    SELECT t.id, t.title, t.cover_image_path, u.nickname, t.play_count, t.like_count,
                           (SELECT genre FROM track_genres WHERE track_id = t.id LIMIT 1) as genre
                    FROM tracks t
                    JOIN users u ON t.user_id = u.id
                    ORDER BY (t.like_count * 3 + t.play_count) DESC, t.created_at DESC
                    LIMIT 12
                ');
                $monthlyRows = $monthlyStmt->fetchAll();
            }
            $monthlyTracks = array_map(function($row) {
                return [
                    'id' => (int)$row['id'],
                    'title' => $row['title'],
                    'artist' => $row['nickname'],
                    'plays' => formatCount($row['play_count']),
                    'cover' => $row['cover_image_path'] ?: '',
                    'gradient' => getGradient($row['id'], $row['genre'] ?? null),
                ];
            }, $monthlyRows);

            // 게시판 글 목록: 최신순 14개, boards/users 조인 + content(썸네일용)
            $postsStmt = $pdo->query('
                SELECT p.id, p.title, p.content, p.comment_count, p.like_count, p.created_at,
                       u.nickname, u.avatar_color,
                       b.board_key, b.board_name, b.color_class,
                       bc.category_name
                FROM posts p
                JOIN users u ON p.user_id = u.id
                JOIN boards b ON p.board_id = b.id
                LEFT JOIN board_categories bc ON p.category_id = bc.id
                ORDER BY p.created_at DESC
                LIMIT 14
            ');
            $postRows = $postsStmt->fetchAll();
            $formatPost = function($row) {
                $tag = !empty($row['category_name']) ? $row['category_name'] : $row['board_name'];
                $tag_color = !empty($row['color_class']) ? $row['color_class'] : 'text-suno-accent2';
                $created = new DateTime($row['created_at']);
                $today = new DateTime('today');
                $time = ($created >= $today) ? $created->format('H:i') : $created->format('m/d');
                $thumb = '';
                if (!empty($row['content']) && preg_match('/<img[^>]+src=["\']([^"\']+)["\']/', $row['content'], $m)) {
                    $thumb = $m[1];
                    if (strpos($thumb, 'http') !== 0) {
                        $thumb = ltrim($thumb, '/');
                    }
                }
                return [
                    'id' => (int)$row['id'],
                    'board_key' => $row['board_key'],
                    'tag' => $tag,
                    'tag_color' => $tag_color,
                    'title' => $row['title'],
                    'author' => $row['nickname'],
                    'avatar_color' => $row['avatar_color'] ?: 'from-suno-accent to-purple-600',
                    'time' => $time,
                    'comments' => (int)$row['comment_count'],
                    'likes' => (int)$row['like_count'],
                    'thumb' => $thumb,
                ];
            };
            $posts = array_map($formatPost, $postRows);
            ?>

            <!-- Hot Tracks Header: 주간/월간 탭 -->
            <div class="flex items-center justify-between mb-3">
                <div class="flex items-center gap-3">
                    <h3 class="text-sm font-bold text-white">🔥 인기 음원</h3>
                    <div class="flex items-center bg-suno-surface/80 border border-suno-border rounded-lg overflow-hidden">
                        <button onclick="switchTrackPeriod('weekly', this)" class="track-period-tab px-3 py-1 text-xs font-semibold text-white bg-suno-accent/80 transition-all">주간</button>
                        <button onclick="switchTrackPeriod('monthly', this)" class="track-period-tab px-3 py-1 text-xs font-medium text-suno-muted hover:text-white transition-all">월간</button>
                    </div>
                </div>
                <a href="popular_tracks.php" class="text-xs text-suno-muted hover:text-suno-accent2 transition-colors">전체보기 →</a>
            </div>

            <!-- 주간 인기 -->
            <div id="tracks-weekly" class="track-period-content flex gap-4 overflow-x-auto pb-4 mb-4 -mx-1 px-1 scrollbar-hide">
                <?php foreach($weeklyTracks as $ht): ?>
                <a href="music_detail.php?id=<?php echo $ht['id']; ?>" class="flex-shrink-0 group cursor-pointer" style="width:140px">
                    <div class="relative w-[140px] h-[140px] rounded-lg overflow-hidden mb-2 shadow-lg shadow-black/30 bg-gradient-to-br <?php echo $ht['gradient']; ?>">
                        <?php if (!empty($ht['cover'])): ?>
                        <img src="<?php echo htmlspecialchars($ht['cover']); ?>" alt="<?php echo htmlspecialchars($ht['title']); ?>" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" loading="lazy">
                        <?php else: ?>
                        <div class="absolute inset-0 flex items-center justify-center">
                            <svg class="w-10 h-10 text-white/15" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/>
                            </svg>
                        </div>
                        <?php endif; ?>
                        <div class="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                            <div class="w-10 h-10 bg-suno-accent rounded-full flex items-center justify-center shadow-lg shadow-suno-accent/30 opacity-0 group-hover:opacity-100 transition-opacity">
                                <svg class="w-4 h-4 text-white ml-0.5" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>
                                </svg>
                            </div>
                        </div>
                    </div>
                    <p class="text-xs font-bold truncate group-hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($ht['title']); ?></p>
                    <p class="text-[11px] text-suno-muted truncate"><?php echo htmlspecialchars($ht['artist']); ?></p>
                    <p class="text-[10px] text-suno-muted/50 mt-0.5">▶ <?php echo $ht['plays']; ?></p>
                </a>
                <?php endforeach; ?>
            </div>

            <!-- 월간 인기 -->
            <div id="tracks-monthly" class="track-period-content hidden flex gap-4 overflow-x-auto pb-4 mb-4 -mx-1 px-1 scrollbar-hide">
                <?php foreach($monthlyTracks as $ht): ?>
                <a href="music_detail.php?id=<?php echo $ht['id']; ?>" class="flex-shrink-0 group cursor-pointer" style="width:140px">
                    <div class="relative w-[140px] h-[140px] rounded-lg overflow-hidden mb-2 shadow-lg shadow-black/30 bg-gradient-to-br <?php echo $ht['gradient']; ?>">
                        <?php if (!empty($ht['cover'])): ?>
                        <img src="<?php echo htmlspecialchars($ht['cover']); ?>" alt="<?php echo htmlspecialchars($ht['title']); ?>" class="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300" loading="lazy">
                        <?php else: ?>
                        <div class="absolute inset-0 flex items-center justify-center">
                            <svg class="w-10 h-10 text-white/15" fill="currentColor" viewBox="0 0 20 20">
                                <path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/>
                            </svg>
                        </div>
                        <?php endif; ?>
                        <div class="absolute inset-0 bg-black/0 group-hover:bg-black/30 transition-colors flex items-center justify-center">
                            <div class="w-10 h-10 bg-suno-accent rounded-full flex items-center justify-center shadow-lg shadow-suno-accent/30 opacity-0 group-hover:opacity-100 transition-opacity">
                                <svg class="w-4 h-4 text-white ml-0.5" fill="currentColor" viewBox="0 0 20 20">
                                    <path d="M6.3 2.841A1.5 1.5 0 004 4.11V15.89a1.5 1.5 0 002.3 1.269l9.344-5.89a1.5 1.5 0 000-2.538L6.3 2.84z"/>
                                </svg>
                            </div>
                        </div>
                    </div>
                    <p class="text-xs font-bold truncate group-hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($ht['title']); ?></p>
                    <p class="text-[11px] text-suno-muted truncate"><?php echo htmlspecialchars($ht['artist']); ?></p>
                    <p class="text-[10px] text-suno-muted/50 mt-0.5">▶ <?php echo $ht['plays']; ?></p>
                </a>
                <?php endforeach; ?>
            </div>

            <script>
            function switchTrackPeriod(period, el) {
                document.querySelectorAll('.track-period-content').forEach(c => c.classList.add('hidden'));
                document.getElementById('tracks-' + period).classList.remove('hidden');
                document.querySelectorAll('.track-period-tab').forEach(t => {
                    t.className = 'track-period-tab px-3 py-1 text-xs font-medium text-suno-muted hover:text-white transition-all';
                });
                el.className = 'track-period-tab px-3 py-1 text-xs font-semibold text-white bg-suno-accent/80 transition-all';
            }
            </script>

            <!-- Board Header -->
            <div class="flex items-center justify-between mb-1 mt-2">
                <h3 class="text-sm font-bold text-white">최신 게시물</h3>
            </div>

            <!-- Divider -->
            <div class="border-t border-suno-border"></div>

            <!-- 최신 게시물 목록 -->
            <div class="divide-y divide-suno-border/60">
                <?php foreach($posts as $post): ?>
                <a href="board_detail.php?board=<?php echo urlencode($post['board_key']); ?>&id=<?php echo $post['id']; ?>" class="flex items-center gap-3 py-2.5 px-2 hover:bg-suno-surface/50 transition-colors group rounded-sm">
                    <?php if(!empty($post['thumb'])): ?>
                    <div class="w-[72px] h-[52px] rounded bg-suno-surface flex-shrink-0 overflow-hidden">
                        <img src="<?php echo htmlspecialchars($post['thumb']); ?>" alt="" class="w-full h-full object-cover" loading="lazy">
                    </div>
                    <?php endif; ?>
                    <div class="flex-1 min-w-0">
                        <span class="text-sm text-zinc-200 group-hover:text-suno-accent2 transition-colors truncate block">
                            <?php echo htmlspecialchars($post['title']); ?>
                            <?php if($post['comments'] > 0): ?>
                            <span class="text-suno-accent font-bold ml-1">[<?php echo $post['comments']; ?>]</span>
                            <?php endif; ?>
                        </span>
                    </div>
                    <div class="flex items-center gap-2 flex-shrink-0 min-w-0 max-w-[120px] sm:max-w-[140px]">
                        <span class="w-6 h-6 rounded-full bg-gradient-to-br <?php echo htmlspecialchars($post['avatar_color']); ?> flex items-center justify-center text-[10px] font-bold text-white/90 flex-shrink-0">
                            <?php echo mb_substr($post['author'] ?? '?', 0, 1); ?>
                        </span>
                        <span class="text-xs text-white/70 truncate"><?php echo htmlspecialchars($post['author'] ?? ''); ?></span>
                    </div>
                    <span class="hidden sm:block text-xs <?php echo $post['tag_color']; ?> w-24 text-right flex-shrink-0 truncate"><?php echo htmlspecialchars($post['tag']); ?></span>
                    <span class="hidden sm:block text-suno-border">│</span>
                    <span class="text-xs text-suno-muted/60 w-12 text-right flex-shrink-0"><?php echo htmlspecialchars($post['time']); ?></span>
                </a>
                <?php endforeach; ?>
            </div>

            <!-- Board Footer: 전체보기 -->
            <div class="flex items-center justify-center mt-5">
                <a href="all_posts.php" class="inline-flex items-center gap-1.5 text-sm text-suno-accent hover:text-suno-accent2 transition-colors font-semibold">
                    전체 게시물 보기
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 8l4 4m0 0l-4 4m4-4H3"/>
                    </svg>
                </a>
            </div>
        </div>
    </section>

    <?php include 'footer.php'; ?>
