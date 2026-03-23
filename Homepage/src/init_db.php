<?php
// SQLite Database 초기화 스크립트
// 브라우저에서 한 번 실행: http://localhost/init_db.php

require_once __DIR__ . '/db.php';

echo "<h2>SUNO Community DB 초기화</h2><pre>";

// ============================================================
// 테이블 생성
// ============================================================

$pdo->exec("DROP TABLE IF EXISTS site_pages");
$pdo->exec("DROP TABLE IF EXISTS recommended_tags");
$pdo->exec("DROP TABLE IF EXISTS password_reset_tokens");
$pdo->exec("DROP TABLE IF EXISTS reports");
$pdo->exec("DROP TABLE IF EXISTS notifications");
$pdo->exec("DROP TABLE IF EXISTS rankings");
$pdo->exec("DROP TABLE IF EXISTS post_comment_likes");
$pdo->exec("DROP TABLE IF EXISTS post_likes");
$pdo->exec("DROP TABLE IF EXISTS post_comments");
$pdo->exec("DROP TABLE IF EXISTS posts");
$pdo->exec("DROP TABLE IF EXISTS board_categories");
$pdo->exec("DROP TABLE IF EXISTS menus");
$pdo->exec("DROP TABLE IF EXISTS messages");
$pdo->exec("DROP TABLE IF EXISTS prompt_saves");
$pdo->exec("DROP TABLE IF EXISTS prompt_likes");
$pdo->exec("DROP TABLE IF EXISTS prompt_styles");
$pdo->exec("DROP TABLE IF EXISTS prompt_genres");
$pdo->exec("DROP TABLE IF EXISTS prompts");
$pdo->exec("DROP TABLE IF EXISTS track_comment_likes");
$pdo->exec("DROP TABLE IF EXISTS track_comments");
$pdo->exec("DROP TABLE IF EXISTS track_likes");
$pdo->exec("DROP TABLE IF EXISTS track_moods");
$pdo->exec("DROP TABLE IF EXISTS track_genres");
$pdo->exec("DROP TABLE IF EXISTS tracks");
$pdo->exec("DROP TABLE IF EXISTS follows");
$pdo->exec("DROP TABLE IF EXISTS social_accounts");
$pdo->exec("DROP TABLE IF EXISTS users");
$pdo->exec("DROP TABLE IF EXISTS boards");
$pdo->exec("DROP TABLE IF EXISTS site_settings");

echo "기존 테이블 삭제 완료\n";

// 1. site_settings
$pdo->exec("CREATE TABLE site_settings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    setting_group TEXT NOT NULL,
    setting_key TEXT NOT NULL,
    setting_value TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(setting_group, setting_key)
)");

// 2. boards
$pdo->exec("CREATE TABLE boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_key TEXT NOT NULL UNIQUE,
    board_name TEXT NOT NULL,
    board_type TEXT NOT NULL DEFAULT 'normal' CHECK(board_type IN ('normal','qna','gallery','collab')),
    description TEXT,
    icon_svg TEXT,
    color_class TEXT,
    bg_class TEXT,
    write_title TEXT,
    use_comment INTEGER NOT NULL DEFAULT 1,
    use_like INTEGER NOT NULL DEFAULT 1,
    use_editor INTEGER NOT NULL DEFAULT 1,
    write_level INTEGER NOT NULL DEFAULT 1,
    comment_level INTEGER NOT NULL DEFAULT 1,
    list_level INTEGER NOT NULL DEFAULT 0,
    posts_per_page INTEGER NOT NULL DEFAULT 20,
    use_popular_tab INTEGER NOT NULL DEFAULT 1,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)");

// 3. board_categories
$pdo->exec("CREATE TABLE board_categories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id INTEGER NOT NULL,
    category_name TEXT NOT NULL,
    sort_order INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    UNIQUE(board_id, category_name),
    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE
)");

// 4. users
$pdo->exec("CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    nickname TEXT NOT NULL UNIQUE,
    email TEXT NOT NULL UNIQUE,
    password_hash TEXT,
    bio TEXT,
    avatar_url TEXT,
    avatar_color TEXT,
    badge TEXT DEFAULT 'Bronze' CHECK(badge IN ('Bronze','Silver','Gold','Diamond')),
    youtube_url TEXT,
    instagram_url TEXT,
    suno_profile_url TEXT,
    terms_agreed INTEGER NOT NULL DEFAULT 0,
    is_admin INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)");

// 5. social_accounts
$pdo->exec("CREATE TABLE social_accounts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    provider TEXT NOT NULL CHECK(provider IN ('google','kakao')),
    provider_id TEXT NOT NULL,
    provider_email TEXT,
    access_token TEXT,
    refresh_token TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(provider, provider_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 6. follows
$pdo->exec("CREATE TABLE follows (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    follower_id INTEGER NOT NULL,
    following_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(follower_id, following_id),
    FOREIGN KEY (follower_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (following_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 7. tracks
$pdo->exec("CREATE TABLE tracks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    suno_link TEXT,
    has_audio_file INTEGER NOT NULL DEFAULT 0,
    audio_file_path TEXT,
    cover_image_path TEXT,
    duration TEXT,
    bpm INTEGER,
    music_key TEXT,
    play_count INTEGER NOT NULL DEFAULT 0,
    like_count INTEGER NOT NULL DEFAULT 0,
    share_count INTEGER NOT NULL DEFAULT 0,
    comment_count INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 8. track_genres
$pdo->exec("CREATE TABLE track_genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    genre TEXT NOT NULL,
    UNIQUE(track_id, genre),
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
)");

// 9. track_moods
$pdo->exec("CREATE TABLE track_moods (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    mood TEXT NOT NULL,
    UNIQUE(track_id, mood),
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
)");

// 10. track_likes
$pdo->exec("CREATE TABLE track_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(track_id, user_id),
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 11. track_comments
$pdo->exec("CREATE TABLE track_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    track_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    like_count INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 12. track_comment_likes
$pdo->exec("CREATE TABLE track_comment_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(comment_id, user_id),
    FOREIGN KEY (comment_id) REFERENCES track_comments(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 13. prompts
$pdo->exec("CREATE TABLE prompts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    prompt_text TEXT NOT NULL,
    exclude_styles TEXT,
    description TEXT,
    lyrics TEXT,
    weirdness INTEGER DEFAULT 50,
    style_influence INTEGER DEFAULT 50,
    audio_influence INTEGER DEFAULT 25,
    suno_link TEXT,
    linked_track_id INTEGER,
    sample_file_path TEXT,
    sample_label TEXT,
    like_count INTEGER NOT NULL DEFAULT 0,
    copy_count INTEGER NOT NULL DEFAULT 0,
    save_count INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (linked_track_id) REFERENCES tracks(id) ON DELETE SET NULL
)");

// 14. prompt_genres
$pdo->exec("CREATE TABLE prompt_genres (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    genre TEXT NOT NULL,
    UNIQUE(prompt_id, genre),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE
)");

// 15. prompt_styles
$pdo->exec("CREATE TABLE prompt_styles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    style TEXT NOT NULL,
    UNIQUE(prompt_id, style),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE
)");

// 16. prompt_likes
$pdo->exec("CREATE TABLE prompt_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, user_id),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 17. prompt_saves
$pdo->exec("CREATE TABLE prompt_saves (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    prompt_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(prompt_id, user_id),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 18. posts
$pdo->exec("CREATE TABLE posts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    category_id INTEGER,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    view_count INTEGER NOT NULL DEFAULT 0,
    like_count INTEGER NOT NULL DEFAULT 0,
    comment_count INTEGER NOT NULL DEFAULT 0,
    is_notice INTEGER NOT NULL DEFAULT 0,
    is_answered INTEGER NOT NULL DEFAULT 0,
    recruit_count INTEGER,
    contact_info TEXT,
    is_closed INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES board_categories(id) ON DELETE SET NULL
)");

// 19. post_comments
$pdo->exec("CREATE TABLE post_comments (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    parent_id INTEGER,
    content TEXT NOT NULL,
    like_count INTEGER NOT NULL DEFAULT 0,
    is_best_answer INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES post_comments(id) ON DELETE CASCADE
)");

// 20. post_likes
$pdo->exec("CREATE TABLE post_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    post_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(post_id, user_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 21. post_comment_likes
$pdo->exec("CREATE TABLE post_comment_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(comment_id, user_id),
    FOREIGN KEY (comment_id) REFERENCES post_comments(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 22. bookmarks
$pdo->exec("CREATE TABLE bookmarks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    post_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, post_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE
)");

// 23. messages
$pdo->exec("CREATE TABLE messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    sender_id INTEGER NOT NULL,
    receiver_id INTEGER NOT NULL,
    title TEXT NOT NULL,
    content TEXT NOT NULL,
    is_read INTEGER NOT NULL DEFAULT 0,
    sender_deleted INTEGER NOT NULL DEFAULT 0,
    receiver_deleted INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (sender_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 23. rankings
$pdo->exec("CREATE TABLE rankings (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    period TEXT NOT NULL DEFAULT 'all_time' CHECK(period IN ('weekly','monthly','all_time')),
    rank_position INTEGER NOT NULL DEFAULT 0,
    total_likes INTEGER NOT NULL DEFAULT 0,
    board_likes INTEGER NOT NULL DEFAULT 0,
    prompt_likes INTEGER NOT NULL DEFAULT 0,
    music_likes INTEGER NOT NULL DEFAULT 0,
    calculated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(user_id, period),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 24. notifications
$pdo->exec("CREATE TABLE notifications (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    actor_id INTEGER,
    type TEXT NOT NULL CHECK(type IN ('like_track','like_prompt','like_post','comment','follow','message','system')),
    reference_type TEXT,
    reference_id INTEGER,
    content TEXT,
    is_read INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL
)");

// 25. reports
$pdo->exec("CREATE TABLE reports (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    reporter_id INTEGER NOT NULL,
    target_type TEXT NOT NULL CHECK(target_type IN ('track','prompt','post','comment','user','message')),
    target_id INTEGER NOT NULL,
    reason TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending' CHECK(status IN ('pending','reviewed','resolved','dismissed')),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 26. password_reset_tokens
$pdo->exec("CREATE TABLE password_reset_tokens (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    token TEXT NOT NULL UNIQUE,
    expires_at DATETIME NOT NULL,
    used INTEGER NOT NULL DEFAULT 0,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 27. prompt_comment_likes
$pdo->exec("DROP TABLE IF EXISTS prompt_comment_likes");
$pdo->exec("CREATE TABLE prompt_comment_likes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    comment_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(comment_id, user_id),
    FOREIGN KEY (comment_id) REFERENCES prompt_comments(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
)");

// 28. prompt_comments
$pdo->exec("DROP TABLE IF EXISTS prompt_comments");
$pdo->exec("CREATE TABLE prompt_comments (
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

// 28. recommended_tags (추천 메타태그)
$pdo->exec("CREATE TABLE recommended_tags (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    tag_name TEXT NOT NULL UNIQUE,
    tag_group TEXT NOT NULL DEFAULT 'general' CHECK(tag_group IN ('popular','genre','instrument','mood','style','general')),
    sort_order INTEGER NOT NULL DEFAULT 0,
    search_count INTEGER NOT NULL DEFAULT 0,
    is_active INTEGER NOT NULL DEFAULT 1,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
)");

// 29. site_pages (약관/정책 등 장문 콘텐츠)
$pdo->exec("CREATE TABLE site_pages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    slug TEXT NOT NULL UNIQUE,
    title TEXT NOT NULL,
    content TEXT,
    is_active INTEGER DEFAULT 1,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
)");

echo "테이블 생성 완료\n";

// ============================================================
// 사이트 설정 시드 데이터
// ============================================================
$settingsData = [
    ['prompt', 'use_sample_sound', '1'],
    ['general', 'site_title', 'SUNO 커뮤니티'],
    ['general', 'site_description', 'AI 음악 크리에이터 커뮤니티'],
    ['footer', 'company_name', 'SUNO Community'],
    ['footer', 'ceo_name', '김수노'],
    ['footer', 'business_number', '485-12-01987'],
    ['footer', 'telecom_number', '2025-서울마포-03821'],
    ['footer', 'address', '서울특별시 마포구 양화로 127, 7층 701호'],
    ['footer', 'phone', '02-6247-7203'],
    ['footer', 'email', 'admin@sunocommunity.kr'],
    ['footer', 'kakao_url', ''],
    ['footer', 'description', 'SUNO Community는 AI 음악 크리에이터를 위한 커뮤니티 플랫폼으로, 본 사이트에 게시된 콘텐츠는 각 게시자에게 저작권이 있으며 무단 전재 및 재배포를 금지합니다. 본 사이트는 통신판매중개자로서 통신판매의 당사자가 아니며, 입점 크리에이터가 등록한 상품정보 및 거래에 대한 책임은 각 크리에이터에게 있습니다. 단, 본 사이트가 직접 운영하는 서비스의 경우 해당 내용에 대한 책임은 SUNO Community에 있습니다. 본 사이트의 콘텐츠 중 AI를 이용하여 제작된 것이 포함되어 있습니다.'],
    ['footer', 'copyright', '© 2026 SUNO Community. All rights reserved.'],
];
$ssStmt = $pdo->prepare('INSERT INTO site_settings (setting_group, setting_key, setting_value) VALUES (?, ?, ?)');
foreach ($settingsData as $s) { $ssStmt->execute($s); }
echo "사이트 설정 " . count($settingsData) . "개 생성\n";

// site_pages 시드 데이터
$pagesData = [
    ['about', '사이트소개', ''],
    ['terms', '이용약관', ''],
    ['privacy', '개인정보처리방침', ''],
    ['legal', '책임한계 및 법적고지', ''],
];
$pgInsert = $pdo->prepare('INSERT INTO site_pages (slug, title, content) VALUES (?, ?, ?)');
foreach ($pagesData as $pg) { $pgInsert->execute($pg); }
echo "사이트 페이지 " . count($pagesData) . "개 생성\n";

// ============================================================
// 시드 데이터 삽입
// ============================================================

// --- Users ---
$users = [
    ['SynthWave_크리에이터', 'synth@test.com', '80년대 신스웨이브 전문 크리에이터', 'Gold'],
    ['UrbanBeat_민수', 'urban@test.com', 'K-Pop & Urban 비트메이커', 'Silver'],
    ['AI_Composer', 'ai@test.com', 'AI 음악의 무한한 가능성을 탐구합니다', 'Diamond'],
    ['가을바람_지현', 'autumn@test.com', '감성 발라드 전문', 'Silver'],
    ['FutureFunk_진호', 'funk@test.com', '퓨처 펑크 & 일렉트로 프로듀서', 'Gold'],
    ['별빛_소윤', 'star@test.com', '몽환적인 사운드스케이프', 'Bronze'],
    ['RetroVibes_태양', 'retro@test.com', '레트로 시티팝 & 80s 바이브', 'Gold'],
    ['LofiMaster_수민', 'lofi@test.com', 'Lo-fi 힙합 & 칠 비트', 'Silver'],
    ['MusicLover_서연', 'lover@test.com', '음악을 사랑하는 크리에이터', 'Bronze'],
    ['K-PopMaker_지우', 'kpop@test.com', 'K-Pop 스타일 전문가', 'Diamond'],
    ['DreamPop_하은', 'dream@test.com', '드림팝 & 인디 사운드', 'Bronze'],
    ['HipHop_대현', 'hiphop@test.com', '힙합 & 래퍼', 'Silver'],
    ['PrompterKing_재윤', 'prompt@test.com', '프롬프트 엔지니어링 전문', 'Diamond'],
    ['ChillMaster_수진', 'chill@test.com', '칠아웃 & 릴렉스', 'Gold'],
    ['BeatDrop_민수2', 'beat@test.com', 'EDM & 프로그레시브 하우스', 'Silver'],
    ['JazzCat_하은2', 'jazz@test.com', '재즈 & 소울', 'Gold'],
    ['FilmScore_태양2', 'film@test.com', '시네마틱 스코어', 'Silver'],
    ['SoulVibes_현우', 'soul@test.com', 'R&B & 소울', 'Bronze'],
    ['RockStar_도현', 'rock@test.com', '인디 록 & 얼터너티브', 'Bronze'],
    ['ZenSound_은지', 'zen@test.com', '명상 & 앰비언트', 'Gold'],
    ['운영팀', 'admin@sunocommunity.kr', 'SUNO Community 운영팀', 'Diamond'],
];

$userStmt = $pdo->prepare('INSERT INTO users (nickname, email, password_hash, bio, badge, avatar_color, terms_agreed, is_admin, created_at) VALUES (?, ?, ?, ?, ?, ?, 1, ?, datetime("now", ?))');
$avatarColors = [
    'from-violet-500 to-purple-600', 'from-pink-500 to-rose-600', 'from-cyan-500 to-blue-600',
    'from-amber-500 to-yellow-600', 'from-emerald-500 to-teal-600', 'from-sky-500 to-blue-600',
    'from-red-500 to-orange-600', 'from-indigo-500 to-violet-600', 'from-teal-500 to-cyan-600',
];
$passwordHash = password_hash('test1234', PASSWORD_DEFAULT);
foreach ($users as $i => $u) {
    $isAdmin = ($u[0] === '운영팀') ? 1 : 0;
    $offset = '-' . ($i * 2) . ' days';
    $color = $avatarColors[$i % count($avatarColors)];
    $userStmt->execute([$u[0], $u[1], $passwordHash, $u[2], $u[3], $color, $isAdmin, $offset]);
}
echo "사용자 " . count($users) . "명 생성\n";

// --- Boards ---
$boardsData = [
    ['notice', '공지사항', 'normal', '운영팀의 공지사항을 확인하세요', 'text-rose-400', 'bg-rose-500/10 border-rose-500/20', '공지 작성'],
    ['free', '자유게시판', 'normal', '자유롭게 이야기를 나눠보세요', 'text-emerald-400', 'bg-emerald-500/10 border-emerald-500/20', '글쓰기'],
    ['qna', '질문/답변', 'qna', 'Suno AI에 대한 궁금한 점을 물어보세요', 'text-blue-400', 'bg-blue-500/10 border-blue-500/20', '질문하기'],
    ['info', '정보', 'normal', '유용한 정보와 팁을 공유해보세요', 'text-teal-400', 'bg-teal-500/10 border-teal-500/20', '정보 공유'],
    ['collab', '협업', 'collab', '함께 만들 파트너를 찾아보세요', 'text-amber-400', 'bg-amber-500/10 border-amber-500/20', '협업 제안'],
];
$boardStmt = $pdo->prepare('INSERT INTO boards (board_key, board_name, board_type, description, color_class, bg_class, write_title, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?, ?)');
foreach ($boardsData as $i => $b) {
    $boardStmt->execute([$b[0], $b[1], $b[2], $b[3], $b[4], $b[5], $b[6], $i]);
}
echo "게시판 " . count($boardsData) . "개 생성\n";

// --- Board Categories ---
$categories = [
    [2, '잡담'], [2, '후기'], [2, '토론'], [2, '작품 공유'], [2, '추천'],
    [3, '프롬프트'], [3, '저작권'], [3, '기술'], [3, '수익화'], [3, 'Suno 기본'],
    [4, '업데이트'], [4, '가이드'], [4, '뉴스'], [4, '팁'],
    [5, '보컬 구함'], [5, '프로젝트'], [5, '믹싱/마스터링'], [5, '영상 제작'], [5, '작사'],
    [1, '공지'], [1, '업데이트'], [1, '이벤트'], [1, '점검'],
];
$catStmt = $pdo->prepare('INSERT INTO board_categories (board_id, category_name, sort_order) VALUES (?, ?, ?)');
foreach ($categories as $i => $c) {
    $catStmt->execute([$c[0], $c[1], $i]);
}
echo "카테고리 " . count($categories) . "개 생성\n";

// --- Tracks ---
$tracksData = [
    [1, 'Midnight Neon', '80년대 레트로 신스웨이브 감성을 담은 트랙입니다.', 'https://suno.com/song/midnight-neon', 0, '3:42', 128, 'C# Minor', 14230, 892, 156],
    [2, 'Seoul Nights', 'K-Pop과 어반 비트가 만난 서울의 밤.', 'https://suno.com/song/seoul-nights', 0, '4:15', 95, 'A Minor', 11840, 654, 89],
    [3, 'Digital Dreams', 'EDM 스타일의 디지털 드림 트랙.', 'https://suno.com/song/digital-dreams', 0, '3:28', 128, 'F Major', 9412, 531, 72],
    [4, 'Autumn Whisper', '가을 감성의 서정적 발라드.', 'https://suno.com/song/autumn-whisper', 0, '4:52', 72, 'D Major', 8105, 478, 65],
    [5, 'Electric Soul', '펑키한 일렉트릭 소울 트랙.', 'https://suno.com/song/electric-soul', 0, '3:55', 110, 'E Minor', 7320, 412, 58],
    [6, 'Rainy Cafe', 'Lo-fi 감성의 비 오는 카페 BGM.', 'https://suno.com/song/rainy-cafe', 1, '5:10', 85, 'G Major', 6891, 389, 43],
    [7, 'Neon Tokyo', '시티팝 스타일의 네온 도쿄.', 'https://suno.com/song/neon-tokyo', 0, '4:08', 100, 'B♭ Major', 6240, 356, 51],
    [8, 'Starlight Sonata', '클래식과 일렉트로닉이 만난 소나타.', 'https://suno.com/song/starlight-sonata', 0, '6:22', 60, 'C Major', 5780, 341, 38],
    [9, 'Underground Flow', '힙합 언더그라운드 플로우.', 'https://suno.com/song/underground-flow', 1, '3:16', 90, 'D Minor', 5410, 298, 29],
    [10, 'Ocean Breeze', '앰비언트 오션 브리즈.', 'https://suno.com/song/ocean-breeze', 0, '7:45', 65, 'A Major', 4920, 267, 22],
    [11, 'Velvet Moon', '재즈 벨벳 문.', 'https://suno.com/song/velvet-moon', 0, '5:33', 110, 'F Minor', 4580, 245, 18],
    [12, 'Cherry Blossom Road', '포크 스타일의 벚꽃길.', 'https://suno.com/song/cherry-blossom', 0, '4:27', 80, 'G Major', 4120, 223, 15],
    [13, 'Velvet Moon (Monthly)', '월간 인기 곡 - 벨벳 문.', 'https://suno.com/song/velvet-moon2', 0, '4:10', 95, 'E♭ Major', 82300, 3421, 567],
    [14, 'Cherry Blossom', '봄날의 벚꽃 트랙.', 'https://suno.com/song/cherry-blossom2', 0, '3:45', 100, 'C Major', 76100, 2987, 423],
    [15, 'Hyperdrive', '테크노 하이퍼드라이브.', 'https://suno.com/song/hyperdrive', 1, '5:20', 140, 'A Minor', 68500, 2654, 389],
    [16, 'Dreamy K-Pop Ballad', '몽환적인 K-Pop 발라드 완성본.', 'https://suno.com/song/dreamy-kpop', 1, '3:24', 72, 'D Major', 1283, 342, 45],
];

$trackStmt = $pdo->prepare('INSERT INTO tracks (user_id, title, description, suno_link, has_audio_file, duration, bpm, music_key, play_count, like_count, share_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime("now", ?))');
foreach ($tracksData as $i => $t) {
    $offset = '-' . ($i * 1) . ' days';
    $trackStmt->execute([$t[0], $t[1], $t[2], $t[3], $t[4], $t[5], $t[6], $t[7], $t[8], $t[9], $t[10], $offset]);
}
echo "트랙 " . count($tracksData) . "개 생성\n";

// --- Track Genres ---
$trackGenres = [
    [1, 'Synthwave'], [1, 'Electronic'],
    [2, 'K-Pop'], [2, 'R&B'],
    [3, 'EDM'], [3, 'Electronic'],
    [4, 'Ballad'], [4, 'Acoustic'],
    [5, 'Funk'], [5, 'Electronic'],
    [6, 'Lo-fi'], [6, 'Hip-Hop'],
    [7, 'City Pop'], [7, 'Retro'],
    [8, 'Classical'], [8, 'Electronic'],
    [9, 'Hip-Hop'], [9, 'Rap'],
    [10, 'Ambient'], [10, 'Chill'],
    [11, 'Jazz'], [11, 'Soul'],
    [12, 'Folk'], [12, 'Acoustic'],
    [13, 'R&B'], [14, 'K-Pop'], [15, 'EDM'],
    [16, 'K-Pop'], [16, 'Ballad'],
];
$tgStmt = $pdo->prepare('INSERT INTO track_genres (track_id, genre) VALUES (?, ?)');
foreach ($trackGenres as $tg) { $tgStmt->execute($tg); }

// --- Track Moods ---
$trackMoods = [
    [1, '레트로'], [1, '몽환적'], [2, '에너지틱'], [3, '신나는'],
    [4, '슬픈'], [4, '감성적'], [5, '그루비'], [6, '잔잔한'],
    [7, '레트로'], [8, '드라마틱'], [9, '파워풀'], [10, '힐링'],
    [11, '로맨틱'], [12, '밝은'],
];
$tmStmt = $pdo->prepare('INSERT INTO track_moods (track_id, mood) VALUES (?, ?)');
foreach ($trackMoods as $tm) { $tmStmt->execute($tm); }

// --- Track Comments ---
$trackComments = [
    [1, 9, '정말 80년대 감성이 물씬 나네요! 이런 스타일 더 많이 만들어주세요.', 24],
    [1, 13, '프롬프트가 굉장히 디테일하네요. 아르페지오 부분 프롬프트 작성법 따로 공유해주실 수 있나요?', 18],
    [1, 7, 'BPM 128에서 이 정도 퀄리티면 대단합니다. 저도 비슷한 스타일로 시도해봐야겠어요.', 12],
    [1, 11, '초보자인데 이런 결과물 보면 동기부여가 됩니다. 프롬프트 참고하겠습니다!', 9],
    [2, 1, 'K-Pop 감성 잘 살렸네요!', 15],
    [3, 5, 'EDM 드롭이 미쳤어요!', 20],
];
$tcStmt = $pdo->prepare('INSERT INTO track_comments (track_id, user_id, content, like_count, created_at) VALUES (?, ?, ?, ?, datetime("now", ?))');
foreach ($trackComments as $i => $tc) {
    $offset = '-' . ($i * 2 + 1) . ' hours';
    $tcStmt->execute([$tc[0], $tc[1], $tc[2], $tc[3], $offset]);
}

// Update comment counts
$pdo->exec("UPDATE tracks SET comment_count = (SELECT COUNT(*) FROM track_comments WHERE track_comments.track_id = tracks.id)");

echo "트랙 댓글 생성\n";

// --- Prompts ---
$promptsData = [
    [13, '몽환적인 K-Pop 발라드 프롬프트', "Dreamy K-pop ballad, ethereal female vocals with gentle vibrato,\nsoft piano melody in D major, lush string arrangement with cellos and violins,\nemotional bridge section with soaring high notes,\nminimalist verse building to powerful chorus,\nreverb-heavy production, ambient synth pads,\nsubtle electronic beats underneath acoustic instruments,\n72 BPM, 4/4 time signature", 'autotune, screaming, heavy distortion', '이 프롬프트는 몽환적인 K-Pop 발라드를 생성하기 위해 만들었습니다.', "[Verse 1]\nHere comes the morning light\nShining through the window bright\nMemories of you and I\nDancing underneath the sky\n\n[Chorus]\nWe're lost in time, we're lost in space\nI see the tears upon your face\nBut don't you cry, don't say goodbye\nThis love will never truly die", 50, 50, 25, 'https://suno.com/song/dreamy-kpop', 16, '/samples/piano-loop.wav', '피아노 멜로디 + 스트링 루프', 342, 128, 89],
    [14, '새벽 감성 Lo-fi 힙합 비트', "Late night lo-fi hip hop, vinyl crackle, mellow jazz piano chords, boom bap drums, warm bass, rain ambience, nostalgic melody, 85 BPM, study music vibes", '', 'Lo-fi 힙합 비트 프롬프트입니다.', '', 30, 60, 40, 'https://suno.com/song/lofi-session', 6, '', '', 287, 203, 56],
    [15, '강렬한 EDM 드롭 만들기', "Intense EDM buildup, progressive house style, massive synth lead, punchy kick drum, side-chain compression, euphoric drop, festival anthem, 128 BPM, big room energy", '', 'EDM 드롭 프롬프트.', '', 70, 40, 20, '', NULL, '', '', 198, 87, 34],
    [16, '재즈 카페 분위기 BGM + 드럼 루프', "Smooth jazz cafe background music, warm saxophone melody, gentle brushed drums, upright bass walking line, cozy piano comping, 110 BPM, intimate atmosphere", '', '재즈 카페 BGM 프롬프트.', '', 20, 70, 50, 'https://suno.com/song/jazz-cafe', 11, '/samples/jazz-drum-loop.wav', '재즈 브러시 드럼 루프', 456, 312, 78],
    [10, 'NewJeans 스타일 Y2K 팝', "Y2K inspired K-pop, NewJeans style, breathy female vocals, groovy bass guitar, retro synth pads, catchy hook, minimalist production, 100 BPM, fresh and youthful", '', 'NewJeans 스타일 프롬프트.', '', 40, 65, 35, 'https://suno.com/song/y2k-pop', 2, '/samples/y2k-synth.wav', 'Y2K 신스 패드', 523, 445, 112],
    [17, '시네마틱 오케스트라 배경음악', "Epic cinematic orchestral score, dramatic strings, powerful brass section, timpani rolls, building intensity, heroic theme, Hans Zimmer inspired, 90 BPM, movie trailer", '', '시네마틱 스코어 프롬프트.', '', 60, 45, 30, '', NULL, '', '', 178, 64, 23],
    [18, '감성 R&B 미드나잇 바이브 + 808 베이스 팩', "Smooth R&B midnight vibes, silky male vocals, slow groove, warm Rhodes piano, subtle 808 bass, atmospheric pads, sensual mood, 78 BPM, late night drive", '', 'R&B 바이브 프롬프트.', '', 25, 55, 45, '', NULL, '/samples/808-bass-pack.wav', '808 베이스 팩', 267, 156, 45],
    [19, '인디 록 기타 리프 중심 프롬프트', "Indie rock anthem, jangly guitar riffs, driving drums, catchy chorus, distorted power chords, raw energy, garage band feel, 140 BPM, alternative vibes", '', '인디 록 프롬프트.', '', 55, 50, 25, '', NULL, '/samples/guitar-riff.wav', '기타 리프 샘플', 145, 78, 19],
    [20, '명상을 위한 앰비언트 사운드스케이프', "Meditation ambient soundscape, gentle drone, crystal singing bowls, nature sounds, flowing water, ethereal pads, healing frequencies, 60 BPM, deep relaxation", '', '명상 앰비언트 프롬프트.', '', 15, 80, 60, '', NULL, '', '', 389, 267, 67],
];

$promptStmt = $pdo->prepare('INSERT INTO prompts (user_id, title, prompt_text, exclude_styles, description, lyrics, weirdness, style_influence, audio_influence, suno_link, linked_track_id, sample_file_path, sample_label, like_count, copy_count, save_count, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, datetime("now", ?))');
foreach ($promptsData as $i => $p) {
    $offset = '-' . ($i * 2) . ' hours';
    $promptStmt->execute([$p[0], $p[1], $p[2], $p[3], $p[4], $p[5], $p[6], $p[7], $p[8], $p[9], $p[10], $p[11], $p[12], $p[13], $p[14], $p[15], $offset]);
}
echo "프롬프트 " . count($promptsData) . "개 생성\n";

// --- Prompt Genres ---
$pgData = [
    [1, 'K-Pop'], [1, 'Ballad'], [1, 'Dreamy'],
    [2, 'Lo-fi'], [2, 'Hip-Hop'],
    [3, 'EDM'],
    [4, 'Jazz'], [4, 'Ambient'],
    [5, 'K-Pop'], [5, 'R&B'],
    [6, 'Cinematic'],
    [7, 'R&B'],
    [8, 'Rock'],
    [9, 'Ambient'],
];
$pgStmt = $pdo->prepare('INSERT INTO prompt_genres (prompt_id, genre) VALUES (?, ?)');
foreach ($pgData as $pg) { $pgStmt->execute($pg); }

// --- Prompt Styles ---
$psData = [
    [1, 'Dreamy'], [1, 'Emotional'],
    [2, 'Chill'], [2, 'Retro'],
    [3, 'Energetic'],
    [4, 'Chill'], [4, 'Acoustic'],
    [5, 'Retro'], [5, 'Futuristic'],
    [6, 'Orchestral'], [6, 'Dark'],
    [7, 'Dark'], [7, 'Chill'],
    [8, 'Energetic'],
    [9, 'Chill'], [9, 'Minimal'],
];
$psStmt = $pdo->prepare('INSERT INTO prompt_styles (prompt_id, style) VALUES (?, ?)');
foreach ($psData as $ps) { $psStmt->execute($ps); }

// --- Prompt Comments ---
// Uses post_comments will handle this via board posts

echo "프롬프트 장르/스타일 태그 생성\n";

// --- Board Posts ---
$postsData = [
    // notice board (board_id=1)
    [1, 21, '[필독] SUNO Community 이용 규칙 안내 (2026년 개정)', '<p>SUNO Community의 이용 규칙이 개정되었습니다. 모든 회원분들께서는 꼭 읽어주시기 바랍니다.</p>', 1520, 312, 1, 0],
    [1, 21, 'v2.5 사이트 업데이트 안내 - 쪽지 기능 추가', '<p>사이트 v2.5 업데이트가 완료되었습니다. 쪽지 기능이 추가되었습니다.</p>', 980, 234, 1, 0],
    [1, 21, '2월 프롬프트 공유 이벤트 - 총 상금 100만원', '<p>2월 한 달간 프롬프트 공유 이벤트를 진행합니다!</p>', 2340, 567, 1, 0],
    [1, 21, '저작권 관련 정책 업데이트 안내', '<p>AI 음악 저작권 관련 정책이 업데이트되었습니다.</p>', 1120, 389, 1, 0],
    [1, 21, '2/10(월) 새벽 2시~5시 서버 점검 안내', '<p>서버 점검 예정입니다.</p>', 450, 45, 1, 0],
    // free board (board_id=2)
    [2, 9, '오늘 처음으로 AI 음악 만들어봤는데 소름 돋네요', '<p>처음 사용해봤는데 진짜 대박이네요. 이게 진짜 AI가 만든 건가요?</p>', 340, 67, 0, 0],
    [2, 18, 'Suno 1년 사용 후기 - 솔직 담백하게', '<p>Suno를 1년간 사용한 솔직한 후기입니다.</p>', 1560, 312, 0, 0],
    [2, 9, 'AI 음악이 실제 카페에서 나올 때의 감동', '<p>도쿄 카페에서 내 AI 음악이 흘러나왔을 때의 감동을 공유합니다.</p>', 890, 156, 0, 0],
    [2, 18, 'AI 음악과 인간 음악가의 공존에 대해 어떻게 생각하세요?', '<p>AI 음악의 발전과 인간 음악가의 공존에 대한 토론입니다.</p>', 2100, 234, 0, 0],
    [2, 9, '첫 AI 앨범 완성했습니다! 들어보세요', '<p>드디어 첫 앨범을 완성했습니다. 총 10곡으로 구성했어요.</p>', 1230, 214, 0, 0],
    [2, 7, '90년대 시티팝 감성 AI 음악 만들어봤습니다', '<p>90년대 시티팝 감성으로 만든 트랙을 공유합니다.</p>', 780, 289, 0, 0],
    [2, 8, '일부러 Lo-fi 느낌으로 만들었는데 반응이 폭발적이네요', '<p>Lo-fi 느낌의 트랙을 만들었더니 반응이 좋네요.</p>', 980, 312, 0, 0],
    // qna board (board_id=3)
    [3, 9, 'Suno v4에서 한국어 가사를 자연스럽게 만드는 방법 있나요?', '<p>한국어 가사가 자연스럽지 않은데 팁이 있을까요?</p>', 340, 23, 0, 1],
    [3, 4, 'AI 생성 음악의 저작권 관련 법적 이슈가 궁금합니다', '<p>AI로 만든 음악의 저작권은 누구에게 있나요?</p>', 890, 67, 0, 1],
    [3, 5, 'Suno에서 특정 악기 소리만 추출할 수 있나요?', '<p>특정 악기만 분리하고 싶은데 방법이 있나요?</p>', 230, 12, 0, 0],
    [3, 18, 'Suno로 만든 음악으로 실제 수익화하는 현실적인 방법들', '<p>수익화 관련 질문입니다.</p>', 670, 89, 0, 1],
    [3, 12, '프롬프트에 BPM과 키를 지정하는 정확한 문법이 뭔가요?', '<p>BPM과 키 지정 문법이 궁금합니다.</p>', 450, 34, 0, 1],
    // info board (board_id=4)
    [4, 13, 'Suno v4.5 업데이트 변경사항 총정리', '<p>Suno v4.5의 모든 변경사항을 정리했습니다.</p>', 3200, 612, 0, 0],
    [4, 20, '초보자를 위한 Suno 완전 정복 가이드 (2026 최신판)', '<p>Suno 초보자를 위한 완벽 가이드입니다.</p>', 5670, 523, 0, 0],
    [4, 13, 'K-Pop 스타일 만들기 프롬프트 모음집', '<p>K-Pop 스타일 프롬프트를 모아봤습니다.</p>', 2890, 341, 0, 0],
    // collab board (board_id=5)
    [5, 12, 'AI 트랙 위에 라이브 보컬 녹음 해주실 분 구합니다', '<p>보컬리스트를 찾고 있습니다.</p>', 560, 45, 0, 0],
    [5, 6, 'AI 음악 앨범 프로젝트 팀원 모집 (3~5인)', '<p>앨범 프로젝트를 함께할 팀원을 모집합니다.</p>', 890, 78, 0, 0],
    [5, 14, '믹싱/마스터링 해주실 분 찾습니다 (유료)', '<p>믹싱/마스터링 전문가를 찾습니다.</p>', 340, 34, 0, 0],
];

$postStmt = $pdo->prepare('INSERT INTO posts (board_id, user_id, title, content, view_count, like_count, is_notice, is_answered, created_at) VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime("now", ?))');
foreach ($postsData as $i => $p) {
    $offset = '-' . ($i * 3) . ' hours';
    $postStmt->execute([$p[0], $p[1], $p[2], $p[3], $p[4], $p[5], $p[6], $p[7], $offset]);
}
echo "게시물 " . count($postsData) . "개 생성\n";

// --- Post Comments ---
$postComments = [
    [1, 9, '좋은 규칙 안내 감사합니다!', 15],
    [1, 13, '잘 읽었습니다.', 8],
    [3, 10, '이벤트 참여할게요!', 22],
    [6, 1, '저도 처음에 소름 돋았어요!', 12],
    [6, 13, '환영합니다!', 8],
    [7, 9, '좋은 후기 감사합니다.', 18],
    [9, 7, '좋은 토론 주제네요.', 10],
    [10, 1, '앨범 들어봤는데 정말 좋아요!', 25],
    [13, 13, '한국어 가사는 영어로 먼저 쓰고 번역하는 게 좋아요.', 30],
    [14, 21, 'AI 음악 저작권은 현재 각 국가별로 다릅니다.', 45],
];
$pcStmt = $pdo->prepare('INSERT INTO post_comments (post_id, user_id, content, like_count, created_at) VALUES (?, ?, ?, ?, datetime("now", ?))');
foreach ($postComments as $i => $pc) {
    $offset = '-' . ($i + 1) . ' hours';
    $pcStmt->execute([$pc[0], $pc[1], $pc[2], $pc[3], $offset]);
}
$pdo->exec("UPDATE posts SET comment_count = (SELECT COUNT(*) FROM post_comments WHERE post_comments.post_id = posts.id)");
echo "게시물 댓글 생성\n";

// --- Messages ---
$messagesData = [
    [13, 1, '프롬프트 관련 질문', '안녕하세요! 공유해주신 Synthwave 프롬프트 잘 봤습니다. 혹시 BPM을 조절하면 어떤 느낌이 나는지 궁금해요.', 1],
    [1, 13, 'RE: 프롬프트 관련 질문', 'BPM을 낮추면 더 몽환적인 느낌이 나고, 높이면 에너지틱한 느낌이 됩니다!', 1],
    [10, 1, '협업 제안', 'K-Pop 스타일 곡을 같이 만들어보지 않으실래요?', 0],
    [9, 1, '음원 피드백 부탁드려요', '제가 만든 곡 한번 들어봐주시고 피드백 부탁드립니다!', 0],
    [5, 13, '프롬프트 구매 문의', '프롬프트 팩 판매하시나요?', 0],
    [7, 1, '콜라보 제안', '시티팝 스타일로 함께 작업해보면 좋겠어요.', 1],
    [1, 7, 'RE: 콜라보 제안', '좋은 제안이네요! 구체적인 계획을 세워볼까요?', 0],
];
$msgStmt = $pdo->prepare('INSERT INTO messages (sender_id, receiver_id, title, content, is_read, created_at) VALUES (?, ?, ?, ?, ?, datetime("now", ?))');
foreach ($messagesData as $i => $m) {
    $offset = '-' . ($i * 5) . ' hours';
    $msgStmt->execute([$m[0], $m[1], $m[2], $m[3], $m[4], $offset]);
}
echo "쪽지 " . count($messagesData) . "개 생성\n";

// --- Rankings ---
$rankUsers = [3, 10, 13, 1, 16, 7, 5, 20, 14, 4, 9, 2, 8, 18, 12, 6, 11, 15, 17, 19];
$rankStmt = $pdo->prepare('INSERT INTO rankings (user_id, period, rank_position, total_likes, board_likes, prompt_likes, music_likes) VALUES (?, ?, ?, ?, ?, ?, ?)');
foreach ($rankUsers as $i => $uid) {
    $total = max(100, 3500 - $i * 150 + rand(-50, 50));
    $board = intval($total * 0.3);
    $prompt = intval($total * 0.35);
    $music = $total - $board - $prompt;
    $rankStmt->execute([$uid, 'all_time', $i + 1, $total, $board, $prompt, $music]);
}
echo "랭킹 " . count($rankUsers) . "명 생성\n";

// --- Follows ---
$followPairs = [[1,3],[1,10],[1,13],[2,1],[2,10],[3,1],[3,13],[5,1],[5,3],[7,1],[9,1],[9,13],[10,1],[10,3],[13,1],[13,10]];
$followStmt = $pdo->prepare('INSERT INTO follows (follower_id, following_id) VALUES (?, ?)');
foreach ($followPairs as $f) { $followStmt->execute($f); }
echo "팔로우 관계 생성\n";

// --- Recommended Tags ---
$recTags = [
    // Popular searches
    ['vocals', 'popular', 0, 320],
    ['snare', 'popular', 1, 280],
    ['bass', 'popular', 2, 250],
    ['808', 'popular', 3, 210],
    ['clap', 'popular', 4, 190],
    // Top genres
    ['hip hop', 'genre', 0, 450],
    ['trap', 'genre', 1, 380],
    ['pop', 'genre', 2, 350],
    ['rnb', 'genre', 3, 310],
    ['edm', 'genre', 4, 290],
    ['K-Pop', 'genre', 5, 520],
    ['Lo-fi', 'genre', 6, 410],
    ['Ballad', 'genre', 7, 330],
    ['Jazz', 'genre', 8, 270],
    ['Rock', 'genre', 9, 240],
    ['R&B', 'genre', 10, 300],
    ['Ambient', 'genre', 11, 220],
    ['Cinematic', 'genre', 12, 200],
    ['Synthwave', 'genre', 13, 180],
    ['City Pop', 'genre', 14, 160],
    // Top instruments
    ['drums', 'instrument', 0, 400],
    ['synth', 'instrument', 1, 370],
    ['percussion', 'instrument', 2, 320],
    ['keys', 'instrument', 3, 280],
    ['guitar', 'instrument', 4, 260],
    ['piano', 'instrument', 5, 230],
    ['saxophone', 'instrument', 6, 150],
    ['strings', 'instrument', 7, 140],
    // Moods
    ['Dreamy', 'mood', 0, 340],
    ['Energetic', 'mood', 1, 290],
    ['Chill', 'mood', 2, 360],
    ['Dark', 'mood', 3, 170],
    ['Emotional', 'mood', 4, 200],
    ['Retro', 'mood', 5, 180],
    // Styles
    ['Orchestral', 'style', 0, 160],
    ['Acoustic', 'style', 1, 140],
    ['Minimal', 'style', 2, 120],
    ['Futuristic', 'style', 3, 110],
    ['vocal chop', 'popular', 5, 170],
    ['techno', 'genre', 15, 150],
];
$rtStmt = $pdo->prepare('INSERT INTO recommended_tags (tag_name, tag_group, sort_order, search_count) VALUES (?, ?, ?, ?)');
foreach ($recTags as $rt) { $rtStmt->execute($rt); }
echo "추천 태그 " . count($recTags) . "개 생성\n";

echo "\n============================================================\n";
echo "DB 초기화 완료! database.sqlite 파일이 생성되었습니다.\n";
echo "테스트 계정: 아무 이메일/비밀번호 test1234 로 로그인 가능\n";
echo "============================================================\n";
echo "</pre>";
echo '<br><a href="index.php" style="color:#8b5cf6;font-weight:bold;">메인 페이지로 이동 &rarr;</a>';
