<?php
// SQLite Database Connection
// 모든 PHP 페이지에서 include 'db.php'; 로 사용

$db_path = __DIR__ . '/database.sqlite';

try {
    $pdo = new PDO('sqlite:' . $db_path);
    $pdo->setAttribute(PDO::ATTR_ERRMODE, PDO::ERRMODE_EXCEPTION);
    $pdo->setAttribute(PDO::ATTR_DEFAULT_FETCH_MODE, PDO::FETCH_ASSOC);
    $pdo->exec('PRAGMA journal_mode=WAL');
    $pdo->exec('PRAGMA foreign_keys=ON');
} catch (PDOException $e) {
    die('DB 연결 실패: ' . $e->getMessage());
}

// 세션 시작 (로그인 등에서 사용)
if (session_status() === PHP_SESSION_NONE) {
    session_start();
}

// 현재 로그인 사용자 정보
$currentUser = null;
if (isset($_SESSION['user_id'])) {
    $stmt = $pdo->prepare('SELECT * FROM users WHERE id = ?');
    $stmt->execute([$_SESSION['user_id']]);
    $currentUser = $stmt->fetch();
}

// 헬퍼 함수: 사이트 설정값 조회
function getSiteSetting($pdo, $group, $key, $default = null) {
    static $cache = [];
    $cacheKey = $group . '.' . $key;
    if (isset($cache[$cacheKey])) return $cache[$cacheKey];
    try {
        $stmt = $pdo->prepare('SELECT setting_value FROM site_settings WHERE setting_group = ? AND setting_key = ?');
        $stmt->execute([$group, $key]);
        $row = $stmt->fetch();
        $cache[$cacheKey] = $row ? $row['setting_value'] : $default;
    } catch (Exception $e) {
        $cache[$cacheKey] = $default;
    }
    return $cache[$cacheKey];
}

// 프롬프트 샘플 사운드 기능 활성화 여부
$useSampleSound = getSiteSetting($pdo, 'prompt', 'use_sample_sound', '1') === '1';

// 헬퍼 함수: 시간 차이 표시 (DB는 UTC로 저장됨)
function timeAgo($datetime) {
    $utc = new DateTimeZone('UTC');
    $now = new DateTime('now', $utc);
    $past = new DateTime($datetime, $utc);
    $diff = $now->diff($past);

    if ($diff->y > 0) return $diff->y . '년 전';
    if ($diff->m > 0) return $diff->m . '개월 전';
    if ($diff->d > 0) return $diff->d . '일 전';
    if ($diff->h > 0) return $diff->h . '시간 전';
    if ($diff->i > 0) return $diff->i . '분 전';
    return '방금 전';
}

// 헬퍼 함수: 숫자 포맷 (1000 -> 1K)
function formatCount($num) {
    if ($num >= 1000) {
        return number_format($num / 1000, 1) . 'K';
    }
    return number_format($num);
}

// 헬퍼 함수: 장르별 고정 그래디언트 색상
function getGenreGradient($genre) {
    static $genreMap = [
        'K-Pop'      => 'from-pink-500 to-rose-900',
        'Lo-fi'      => 'from-slate-500 to-zinc-800',
        'Hip-Hop'    => 'from-amber-500 to-orange-900',
        'R&B'        => 'from-fuchsia-500 to-purple-900',
        'Rock'       => 'from-red-600 to-rose-900',
        'Jazz'       => 'from-indigo-500 to-violet-900',
        'EDM'        => 'from-cyan-500 to-blue-900',
        'Ambient'    => 'from-emerald-500 to-teal-900',
        'Cinematic'  => 'from-violet-600 to-indigo-900',
        'Classical'  => 'from-purple-500 to-indigo-900',
        'Ballad'     => 'from-rose-400 to-pink-900',
        'Folk'       => 'from-yellow-500 to-amber-900',
        'Reggae'     => 'from-green-500 to-emerald-900',
        'Metal'      => 'from-zinc-500 to-neutral-900',
        'Country'    => 'from-orange-500 to-amber-900',
        'Latin'      => 'from-red-500 to-orange-900',
    ];

    if (!$genre) return null;

    $normalized = trim($genre);
    foreach ($genreMap as $key => $val) {
        if (strcasecmp($key, $normalized) === 0) {
            return $val;
        }
    }

    // 알 수 없는 장르: 해시 기반 매핑
    $hash = crc32(strtolower($normalized));
    $values = array_values($genreMap);
    return $values[abs($hash) % count($values)];
}

// 헬퍼 함수: 그래디언트 (장르 우선, 없으면 ID 기반 폴백)
function getGradient($id, $genre = null) {
    if ($genre) {
        $result = getGenreGradient($genre);
        if ($result) return $result;
    }

    $gradients = [
        'from-violet-600 to-indigo-900',
        'from-pink-600 to-rose-900',
        'from-cyan-600 to-blue-900',
        'from-amber-600 to-orange-900',
        'from-emerald-600 to-teal-900',
        'from-slate-600 to-zinc-900',
        'from-fuchsia-600 to-purple-900',
        'from-yellow-600 to-amber-900',
        'from-red-600 to-rose-900',
        'from-sky-600 to-cyan-900',
        'from-indigo-600 to-violet-900',
        'from-pink-500 to-fuchsia-900',
    ];
    return $gradients[$id % count($gradients)];
}

// 헬퍼 함수: 아바타 색상 배열
function getAvatarColor($id) {
    $colors = [
        'from-violet-500 to-purple-600',
        'from-pink-500 to-rose-600',
        'from-cyan-500 to-blue-600',
        'from-amber-500 to-yellow-600',
        'from-emerald-500 to-teal-600',
        'from-red-500 to-orange-600',
        'from-indigo-500 to-violet-600',
        'from-teal-500 to-cyan-600',
        'from-slate-500 to-gray-600',
    ];
    return $colors[$id % count($colors)];
}
