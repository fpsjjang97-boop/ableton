<?php
require_once 'db.php';

// ── JSON 응답 헤더 ──
header('Content-Type: application/json; charset=utf-8');

// ── 로그인 확인 ──
if (!$currentUser) {
    http_response_code(401);
    echo json_encode(['success' => false, 'message' => '로그인이 필요합니다.']);
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    http_response_code(405);
    echo json_encode(['success' => false, 'message' => '잘못된 요청입니다.']);
    exit;
}

// ── 입력값 수집 ──
$type      = trim($_POST['type'] ?? '');       // 'track', 'prompt', 'post'
$target_id = (int)($_POST['target_id'] ?? 0);

// ── 필수값 검증 ──
if (empty($type) || $target_id <= 0) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => '잘못된 파라미터입니다.']);
    exit;
}

// ── 타입별 테이블/컬럼 매핑 ──
$config = [
    'track' => [
        'target_table' => 'tracks',
        'like_table'   => 'track_likes',
        'fk_column'    => 'track_id',
    ],
    'prompt' => [
        'target_table' => 'prompts',
        'like_table'   => 'prompt_likes',
        'fk_column'    => 'prompt_id',
    ],
    'post' => [
        'target_table' => 'posts',
        'like_table'   => 'post_likes',
        'fk_column'    => 'post_id',
    ],
    'comment' => [
        'target_table' => 'post_comments',
        'like_table'   => 'post_comment_likes',
        'fk_column'    => 'comment_id',
    ],
    'prompt_comment' => [
        'target_table' => 'prompt_comments',
        'like_table'   => 'prompt_comment_likes',
        'fk_column'    => 'comment_id',
    ],
];

if (!isset($config[$type])) {
    http_response_code(400);
    echo json_encode(['success' => false, 'message' => '지원하지 않는 타입입니다.']);
    exit;
}

$conf         = $config[$type];
$target_table = $conf['target_table'];
$like_table   = $conf['like_table'];
$fk_column    = $conf['fk_column'];

try {
    $pdo->beginTransaction();

    // ── 대상 존재 확인 ──
    $stmt = $pdo->prepare("SELECT id FROM {$target_table} WHERE id = ?");
    $stmt->execute([$target_id]);
    if (!$stmt->fetch()) {
        $pdo->rollBack();
        http_response_code(404);
        echo json_encode(['success' => false, 'message' => '대상을 찾을 수 없습니다.']);
        exit;
    }

    // ── 기존 좋아요 확인 ──
    $stmt = $pdo->prepare("SELECT id FROM {$like_table} WHERE {$fk_column} = ? AND user_id = ?");
    $stmt->execute([$target_id, $currentUser['id']]);
    $existingLike = $stmt->fetch();

    if ($existingLike) {
        // ── 좋아요 취소 (DELETE) ──
        $stmt = $pdo->prepare("DELETE FROM {$like_table} WHERE id = ?");
        $stmt->execute([$existingLike['id']]);

        // ── like_count 감소 ──
        $stmt = $pdo->prepare("UPDATE {$target_table} SET like_count = MAX(0, like_count - 1) WHERE id = ?");
        $stmt->execute([$target_id]);

        $liked = false;
    } else {
        // ── 좋아요 추가 (INSERT) ──
        $stmt = $pdo->prepare("INSERT INTO {$like_table} ({$fk_column}, user_id, created_at) VALUES (?, ?, datetime('now'))");
        $stmt->execute([$target_id, $currentUser['id']]);

        // ── like_count 증가 ──
        $stmt = $pdo->prepare("UPDATE {$target_table} SET like_count = like_count + 1 WHERE id = ?");
        $stmt->execute([$target_id]);

        $liked = true;
    }

    // ── 최신 like_count 조회 ──
    $stmt = $pdo->prepare("SELECT like_count FROM {$target_table} WHERE id = ?");
    $stmt->execute([$target_id]);
    $result    = $stmt->fetch();
    $likeCount = $result ? (int)$result['like_count'] : 0;

    $pdo->commit();

    echo json_encode([
        'success'    => true,
        'liked'      => $liked,
        'like_count' => $likeCount,
    ]);

} catch (Exception $e) {
    $pdo->rollBack();
    http_response_code(500);
    echo json_encode(['success' => false, 'message' => '서버 오류가 발생했습니다.']);
}

exit;
