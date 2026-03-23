-- ============================================================
-- SUNO Community Database Schema
-- 생성일: 2026-02-09
-- 데이터베이스: MySQL 8.0+
-- 문자셋: utf8mb4 (이모지 지원)
-- ============================================================

SET NAMES utf8mb4;
SET CHARACTER SET utf8mb4;


-- ************************************************************
-- A. 관리자/사이트 설정 (Admin & Site Configuration)
-- ************************************************************

-- ============================================================
-- 1. 사이트 설정 (Site Settings) - Key-Value 방식
-- ============================================================
CREATE TABLE site_settings (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    setting_group   VARCHAR(50)     NOT NULL COMMENT 'general, main, footer, seo 등 그룹 분류',
    setting_key     VARCHAR(100)    NOT NULL,
    setting_value   TEXT            NULL,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    UNIQUE KEY uq_group_key (setting_group, setting_key)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- 기본 데이터 예시:
-- ('general', 'site_title',       'SUNO 커뮤니티')
-- ('general', 'site_description', 'AI 음악 크리에이터 커뮤니티')
-- ('general', 'site_logo_url',    '/assets/logo.png')
-- ('general', 'site_favicon_url', '/assets/favicon.ico')
-- ('general', 'primary_color',    '#8b5cf6')
-- ('general', 'accent_color',     '#7c3aed')
-- ('main',    'hero_title',       'AI 음악의 새로운 시대')
-- ('main',    'hero_subtitle',    'Suno AI로 만든 음악을 공유하고 영감을 나누세요')
-- ('main',    'show_trending',    '1')
-- ('main',    'trending_count',   '8')
-- ('main',    'show_featured',    '1')
-- ('main',    'featured_count',   '4')
-- ('main',    'show_ranking',     '1')
-- ('footer',  'company_name',     'SUNO Community')
-- ('footer',  'business_number',  '123-45-67890')
-- ('footer',  'representative',   '홍길동')
-- ('footer',  'address',          '서울특별시 ...')
-- ('footer',  'contact_email',    'contact@suno.community')
-- ('footer',  'copyright_text',   '© 2026 SUNO Community. All rights reserved.')
-- ('footer',  'terms_url',        '/terms')
-- ('footer',  'privacy_url',      '/privacy')
-- ('seo',     'meta_keywords',    'AI 음악, Suno, 프롬프트, 커뮤니티')
-- ('seo',     'meta_description', 'AI 음악 크리에이터 커뮤니티')
-- ('seo',     'og_image_url',     '/assets/og-image.png')


-- ============================================================
-- 2. 게시판 관리 (Boards) - 동적 게시판 CRUD
-- ============================================================
CREATE TABLE boards (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    board_key       VARCHAR(50)     NOT NULL UNIQUE COMMENT '영문 식별자 (free, qna, notice 등 URL용)',
    board_name      VARCHAR(100)    NOT NULL COMMENT '게시판 표시명 (자유게시판, 질문/답변 등)',
    board_type      ENUM('normal','qna','gallery','collab') NOT NULL DEFAULT 'normal'
                    COMMENT 'normal=일반, qna=질문답변, gallery=갤러리형, collab=협업/구인구직',
    description     VARCHAR(300)    NULL COMMENT '게시판 설명',
    icon_svg        TEXT            NULL COMMENT '아이콘 SVG path 데이터',
    color_class     VARCHAR(50)     NULL COMMENT 'CSS 색상 클래스 (text-rose-400 등)',
    bg_class        VARCHAR(100)    NULL COMMENT 'CSS 배경 클래스 (bg-rose-500/10 등)',
    write_title     VARCHAR(100)    NULL COMMENT '글쓰기 버튼/페이지 제목 (글쓰기, 질문하기 등)',
    use_comment     TINYINT(1)      NOT NULL DEFAULT 1 COMMENT '댓글 사용 여부',
    use_like        TINYINT(1)      NOT NULL DEFAULT 1 COMMENT '좋아요 사용 여부',
    use_editor      TINYINT(1)      NOT NULL DEFAULT 1 COMMENT '에디터(Summernote) 사용 여부',
    write_level     TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '글쓰기 권한 (0=비회원, 1=회원, 9=관리자)',
    comment_level   TINYINT UNSIGNED NOT NULL DEFAULT 1 COMMENT '댓글 권한',
    list_level      TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '목록 보기 권한',
    posts_per_page  SMALLINT UNSIGNED NOT NULL DEFAULT 20,
    sort_order      INT             NOT NULL DEFAULT 0 COMMENT '게시판 정렬 순서',
    is_active       TINYINT(1)      NOT NULL DEFAULT 1 COMMENT '활성화 여부',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_sort (sort_order),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 3. 게시판 카테고리 (Board Categories)
-- ============================================================
CREATE TABLE board_categories (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    board_id        BIGINT UNSIGNED NOT NULL,
    category_name   VARCHAR(50)     NOT NULL,
    sort_order      INT             NOT NULL DEFAULT 0,
    is_active       TINYINT(1)      NOT NULL DEFAULT 1,

    UNIQUE KEY uq_board_cat (board_id, category_name),
    FOREIGN KEY (board_id) REFERENCES boards(id) ON DELETE CASCADE,
    INDEX idx_sort (board_id, sort_order)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 4. 메뉴 관리 (Menus)
-- ============================================================
CREATE TABLE menus (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    parent_id       BIGINT UNSIGNED NULL COMMENT '상위 메뉴 ID (NULL이면 최상위)',
    menu_name       VARCHAR(100)    NOT NULL COMMENT '메뉴 표시명',
    menu_type       ENUM('link','board','page','separator') NOT NULL DEFAULT 'link'
                    COMMENT 'link=URL링크, board=게시판연결, page=내부페이지, separator=구분선',
    menu_url        VARCHAR(500)    NULL COMMENT 'link 타입일 때 URL',
    board_id        BIGINT UNSIGNED NULL COMMENT 'board 타입일 때 연결할 게시판 ID',
    page_slug       VARCHAR(100)    NULL COMMENT 'page 타입일 때 (music, prompt, ranking, search 등)',
    icon_svg        TEXT            NULL COMMENT '아이콘 SVG (모바일 메뉴용)',
    target          ENUM('_self','_blank') NOT NULL DEFAULT '_self',
    location        ENUM('header','footer','both') NOT NULL DEFAULT 'header' COMMENT '메뉴 위치',
    sort_order      INT             NOT NULL DEFAULT 0,
    is_active       TINYINT(1)      NOT NULL DEFAULT 1,
    visible_level   TINYINT UNSIGNED NOT NULL DEFAULT 0 COMMENT '표시 권한 (0=전체, 1=회원, 9=관리자)',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (parent_id) REFERENCES menus(id) ON DELETE CASCADE,
    FOREIGN KEY (board_id)  REFERENCES boards(id) ON DELETE SET NULL,
    INDEX idx_location_sort (location, sort_order),
    INDEX idx_active (is_active)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ************************************************************
-- B. 사용자 (Users & Authentication)
-- ************************************************************

-- ============================================================
-- 5. 사용자 (Users)
-- ============================================================
CREATE TABLE users (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    nickname        VARCHAR(50)     NOT NULL UNIQUE,
    email           VARCHAR(255)    NOT NULL UNIQUE,
    password_hash   VARCHAR(255)    NULL COMMENT 'OAuth 로그인 시 NULL 가능',
    bio             TEXT            NULL,
    avatar_url      VARCHAR(500)    NULL,
    avatar_color    VARCHAR(100)    NULL COMMENT 'CSS gradient 클래스 (from-xxx to-xxx)',
    badge           ENUM('Bronze','Silver','Gold','Diamond') DEFAULT 'Bronze',
    youtube_url     VARCHAR(500)    NULL,
    instagram_url   VARCHAR(500)    NULL,
    suno_profile_url VARCHAR(500)   NULL,
    terms_agreed    TINYINT(1)      NOT NULL DEFAULT 0,
    is_admin        TINYINT(1)      NOT NULL DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    INDEX idx_nickname (nickname),
    INDEX idx_email (email),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 6. OAuth 소셜 로그인 (Social Accounts)
-- ============================================================
CREATE TABLE social_accounts (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED NOT NULL,
    provider        ENUM('google','kakao') NOT NULL,
    provider_id     VARCHAR(255)    NOT NULL,
    provider_email  VARCHAR(255)    NULL,
    access_token    TEXT            NULL,
    refresh_token   TEXT            NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_provider_id (provider, provider_id),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 7. 팔로우 관계 (Follows)
-- ============================================================
CREATE TABLE follows (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    follower_id     BIGINT UNSIGNED NOT NULL,
    following_id    BIGINT UNSIGNED NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_follow (follower_id, following_id),
    FOREIGN KEY (follower_id)  REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (following_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_following (following_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ************************************************************
-- C. 음원 (Tracks / Music)
-- ************************************************************

-- ============================================================
-- 8. 음원/트랙 (Tracks)
-- ============================================================
CREATE TABLE tracks (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED NOT NULL,
    title           VARCHAR(200)    NOT NULL,
    description     TEXT            NULL,
    suno_link       VARCHAR(500)    NULL,
    has_audio_file  TINYINT(1)      NOT NULL DEFAULT 0,
    audio_file_path VARCHAR(500)    NULL,
    cover_image_path VARCHAR(500)   NULL,
    duration        VARCHAR(10)     NULL COMMENT '예: 3:42',
    bpm             SMALLINT UNSIGNED NULL,
    music_key       VARCHAR(20)     NULL COMMENT '예: C# Minor',
    play_count      INT UNSIGNED    NOT NULL DEFAULT 0,
    like_count      INT UNSIGNED    NOT NULL DEFAULT 0,
    share_count     INT UNSIGNED    NOT NULL DEFAULT 0,
    comment_count   INT UNSIGNED    NOT NULL DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_like_count (like_count),
    INDEX idx_play_count (play_count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 9. 트랙 장르 태그 (Track Genre Tags)
-- ============================================================
CREATE TABLE track_genres (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    track_id        BIGINT UNSIGNED NOT NULL,
    genre           VARCHAR(50)     NOT NULL COMMENT 'K-Pop, Lo-fi, Hip-Hop, R&B, Rock, Jazz 등',

    UNIQUE KEY uq_track_genre (track_id, genre),
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 10. 트랙 분위기 태그 (Track Mood Tags)
-- ============================================================
CREATE TABLE track_moods (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    track_id        BIGINT UNSIGNED NOT NULL,
    mood            VARCHAR(50)     NOT NULL COMMENT '신나는, 잔잔한, 슬픈, 몽환적 등',

    UNIQUE KEY uq_track_mood (track_id, mood),
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 11. 트랙 좋아요 (Track Likes)
-- ============================================================
CREATE TABLE track_likes (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    track_id        BIGINT UNSIGNED NOT NULL,
    user_id         BIGINT UNSIGNED NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_track_like (track_id, user_id),
    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)  REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 12. 트랙 댓글 (Track Comments)
-- ============================================================
CREATE TABLE track_comments (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    track_id        BIGINT UNSIGNED NOT NULL,
    user_id         BIGINT UNSIGNED NOT NULL,
    content         TEXT            NOT NULL,
    like_count      INT UNSIGNED    NOT NULL DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (track_id) REFERENCES tracks(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)  REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_track_id (track_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 13. 트랙 댓글 좋아요 (Track Comment Likes)
-- ============================================================
CREATE TABLE track_comment_likes (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    comment_id      BIGINT UNSIGNED NOT NULL,
    user_id         BIGINT UNSIGNED NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_comment_like (comment_id, user_id),
    FOREIGN KEY (comment_id) REFERENCES track_comments(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)    REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ************************************************************
-- D. 프롬프트 (Prompts)
-- ************************************************************

-- ============================================================
-- 14. 프롬프트 (Prompts)
-- ============================================================
CREATE TABLE prompts (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED NOT NULL,
    title           VARCHAR(100)    NOT NULL,
    prompt_text     TEXT            NOT NULL COMMENT 'Suno Styles 필드에 들어갈 프롬프트',
    exclude_styles  VARCHAR(500)    NULL COMMENT '제외할 스타일',
    description     TEXT            NULL COMMENT '프롬프트 설명/사용 팁',
    lyrics          TEXT            NULL COMMENT '가사 (선택)',
    weirdness       TINYINT UNSIGNED NULL DEFAULT 50 COMMENT '0~100',
    style_influence TINYINT UNSIGNED NULL DEFAULT 50 COMMENT '0~100',
    audio_influence TINYINT UNSIGNED NULL DEFAULT 25 COMMENT '0~100',
    suno_link       VARCHAR(500)    NULL,
    linked_track_id BIGINT UNSIGNED NULL COMMENT '완성본 곡 연결 (tracks.id)',
    sample_file_path VARCHAR(500)   NULL COMMENT '샘플 사운드 파일 경로',
    sample_label    VARCHAR(50)     NULL COMMENT '샘플 설명',
    like_count      INT UNSIGNED    NOT NULL DEFAULT 0,
    copy_count      INT UNSIGNED    NOT NULL DEFAULT 0,
    save_count      INT UNSIGNED    NOT NULL DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)         REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (linked_track_id) REFERENCES tracks(id) ON DELETE SET NULL,
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_like_count (like_count),
    INDEX idx_copy_count (copy_count)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 15. 프롬프트 장르 태그 (Prompt Genre Tags)
-- ============================================================
CREATE TABLE prompt_genres (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    prompt_id       BIGINT UNSIGNED NOT NULL,
    genre           VARCHAR(50)     NOT NULL,

    UNIQUE KEY uq_prompt_genre (prompt_id, genre),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 16. 프롬프트 스타일 태그 (Prompt Style Tags)
-- ============================================================
CREATE TABLE prompt_styles (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    prompt_id       BIGINT UNSIGNED NOT NULL,
    style           VARCHAR(50)     NOT NULL COMMENT 'Dreamy, Energetic, Chill 등',

    UNIQUE KEY uq_prompt_style (prompt_id, style),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 17. 프롬프트 좋아요 (Prompt Likes)
-- ============================================================
CREATE TABLE prompt_likes (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    prompt_id       BIGINT UNSIGNED NOT NULL,
    user_id         BIGINT UNSIGNED NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_prompt_like (prompt_id, user_id),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)   REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 18. 프롬프트 저장/북마크 (Prompt Saves)
-- ============================================================
CREATE TABLE prompt_saves (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    prompt_id       BIGINT UNSIGNED NOT NULL,
    user_id         BIGINT UNSIGNED NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_prompt_save (prompt_id, user_id),
    FOREIGN KEY (prompt_id) REFERENCES prompts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)   REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ************************************************************
-- E. 게시판 (Board Posts & Comments)
-- ************************************************************

-- ============================================================
-- 19. 게시판 글 (Board Posts)
-- ============================================================
CREATE TABLE posts (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    board_id        BIGINT UNSIGNED NOT NULL COMMENT '소속 게시판 (boards.id)',
    user_id         BIGINT UNSIGNED NOT NULL,
    category_id     BIGINT UNSIGNED NULL COMMENT '카테고리 (board_categories.id)',
    title           VARCHAR(200)    NOT NULL,
    content         MEDIUMTEXT      NOT NULL COMMENT 'Summernote HTML 컨텐츠',
    view_count      INT UNSIGNED    NOT NULL DEFAULT 0,
    like_count      INT UNSIGNED    NOT NULL DEFAULT 0,
    comment_count   INT UNSIGNED    NOT NULL DEFAULT 0,
    is_notice       TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '공지 고정 여부',
    is_answered     TINYINT(1)      NOT NULL DEFAULT 0 COMMENT 'QNA 게시판: 답변 완료 여부',
    -- 협업(collab) 게시판 전용 필드
    recruit_count   TINYINT UNSIGNED NULL COMMENT '협업: 모집 인원',
    contact_info    VARCHAR(300)    NULL COMMENT '협업: 연락 방법 (오픈채팅, 이메일 등)',
    is_closed       TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '협업: 모집 마감 여부',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,

    FOREIGN KEY (board_id)    REFERENCES boards(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)     REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (category_id) REFERENCES board_categories(id) ON DELETE SET NULL,
    INDEX idx_board_id (board_id),
    INDEX idx_user_id (user_id),
    INDEX idx_created_at (created_at),
    INDEX idx_board_created (board_id, created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 20. 게시판 댓글 (Post Comments)
-- ============================================================
CREATE TABLE post_comments (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    post_id         BIGINT UNSIGNED NOT NULL,
    user_id         BIGINT UNSIGNED NOT NULL,
    parent_id       BIGINT UNSIGNED NULL COMMENT '대댓글 시 부모 댓글 ID',
    content         TEXT            NOT NULL,
    like_count      INT UNSIGNED    NOT NULL DEFAULT 0,
    is_best_answer  TINYINT(1)      NOT NULL DEFAULT 0 COMMENT 'QNA 베스트 답변 여부',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (post_id)   REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)   REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (parent_id) REFERENCES post_comments(id) ON DELETE CASCADE,
    INDEX idx_post_id (post_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 21. 게시판 글 좋아요 (Post Likes)
-- ============================================================
CREATE TABLE post_likes (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    post_id         BIGINT UNSIGNED NOT NULL,
    user_id         BIGINT UNSIGNED NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_post_like (post_id, user_id),
    FOREIGN KEY (post_id) REFERENCES posts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 22. 게시판 댓글 좋아요 (Post Comment Likes)
-- ============================================================
CREATE TABLE post_comment_likes (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    comment_id      BIGINT UNSIGNED NOT NULL,
    user_id         BIGINT UNSIGNED NOT NULL,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_post_comment_like (comment_id, user_id),
    FOREIGN KEY (comment_id) REFERENCES post_comments(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id)    REFERENCES users(id) ON DELETE CASCADE
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ************************************************************
-- F. 쪽지 (Messages)
-- ************************************************************

-- ============================================================
-- 23. 쪽지/메시지 (Messages)
-- ============================================================
CREATE TABLE messages (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    sender_id       BIGINT UNSIGNED NOT NULL,
    receiver_id     BIGINT UNSIGNED NOT NULL,
    title           VARCHAR(200)    NOT NULL,
    content         TEXT            NOT NULL,
    is_read         TINYINT(1)      NOT NULL DEFAULT 0,
    sender_deleted  TINYINT(1)      NOT NULL DEFAULT 0 COMMENT '발신자 삭제 여부',
    receiver_deleted TINYINT(1)     NOT NULL DEFAULT 0 COMMENT '수신자 삭제 여부',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (sender_id)   REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (receiver_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_receiver (receiver_id, is_read),
    INDEX idx_sender (sender_id),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ************************************************************
-- G. 랭킹 / 알림 / 신고 (System)
-- ************************************************************

-- ============================================================
-- 24. 랭킹 (Rankings)
-- ============================================================
CREATE TABLE rankings (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED NOT NULL,
    period          ENUM('weekly','monthly','all_time') NOT NULL DEFAULT 'all_time',
    rank_position   INT UNSIGNED    NOT NULL DEFAULT 0,
    total_likes     INT UNSIGNED    NOT NULL DEFAULT 0,
    board_likes     INT UNSIGNED    NOT NULL DEFAULT 0,
    prompt_likes    INT UNSIGNED    NOT NULL DEFAULT 0,
    music_likes     INT UNSIGNED    NOT NULL DEFAULT 0,
    calculated_at   DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    UNIQUE KEY uq_user_period (user_id, period),
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_period_rank (period, rank_position)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 25. 알림 (Notifications)
-- ============================================================
CREATE TABLE notifications (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    user_id         BIGINT UNSIGNED NOT NULL COMMENT '알림 받는 사용자',
    actor_id        BIGINT UNSIGNED NULL COMMENT '알림 발생시킨 사용자',
    type            ENUM('like_track','like_prompt','like_post','comment','follow','message','system') NOT NULL,
    reference_type  VARCHAR(50)     NULL COMMENT 'track, prompt, post, message 등',
    reference_id    BIGINT UNSIGNED NULL COMMENT '참조 대상 ID',
    content         VARCHAR(500)    NULL COMMENT '알림 내용 텍스트',
    is_read         TINYINT(1)      NOT NULL DEFAULT 0,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (user_id)  REFERENCES users(id) ON DELETE CASCADE,
    FOREIGN KEY (actor_id) REFERENCES users(id) ON DELETE SET NULL,
    INDEX idx_user_read (user_id, is_read),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 26. 신고 (Reports)
-- ============================================================
CREATE TABLE reports (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    reporter_id     BIGINT UNSIGNED NOT NULL,
    target_type     ENUM('track','prompt','post','comment','user','message') NOT NULL,
    target_id       BIGINT UNSIGNED NOT NULL,
    reason          VARCHAR(500)    NOT NULL,
    status          ENUM('pending','reviewed','resolved','dismissed') NOT NULL DEFAULT 'pending',
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    FOREIGN KEY (reporter_id) REFERENCES users(id) ON DELETE CASCADE,
    INDEX idx_status (status),
    INDEX idx_created_at (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;


-- ============================================================
-- 27. 추천 태그 (Recommended Tags) - 메타태그 검색 추천용
-- ============================================================
CREATE TABLE recommended_tags (
    id              BIGINT UNSIGNED AUTO_INCREMENT PRIMARY KEY,
    tag_name        VARCHAR(100)    NOT NULL UNIQUE,
    tag_group       ENUM('popular','genre','instrument','mood','style','general') NOT NULL DEFAULT 'general'
                    COMMENT 'popular=인기검색어, genre=장르, instrument=악기, mood=분위기, style=스타일',
    sort_order      INT             NOT NULL DEFAULT 0,
    search_count    INT UNSIGNED    NOT NULL DEFAULT 0 COMMENT '검색 횟수 (인기도 산정용)',
    is_active       TINYINT(1)      NOT NULL DEFAULT 1,
    created_at      DATETIME        NOT NULL DEFAULT CURRENT_TIMESTAMP,

    INDEX idx_group_sort (tag_group, sort_order),
    INDEX idx_search_count (search_count DESC)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
