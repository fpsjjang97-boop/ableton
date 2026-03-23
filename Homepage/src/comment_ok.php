<?php
require_once 'db.php';

// ── 로그인 확인 ──
if (!$currentUser) {
    header('Location: login.php');
    exit;
}

if ($_SERVER['REQUEST_METHOD'] !== 'POST') {
    header('Location: index.php');
    exit;
}

// ── 입력값 수집 ──
$type      = trim($_POST['type'] ?? '');       // 'track' 또는 'post'
$target_id = (int)($_POST['target_id'] ?? 0);
$content   = trim($_POST['content'] ?? '');
$parent_id = !empty($_POST['parent_id']) ? (int)$_POST['parent_id'] : null;

// ── 필수값 검증 ──
if (empty($type) || $target_id <= 0 || empty($content)) {
    $referer = $_SERVER['HTTP_REFERER'] ?? 'index.php';
    header('Location: ' . $referer);
    exit;
}

// ── 타입 검증 ──
if (!in_array($type, ['track', 'post', 'prompt'])) {
    header('Location: index.php');
    exit;
}

// ── 내용 길이 제한 ──
if (mb_strlen($content) > 2000) {
    $content = mb_substr($content, 0, 2000);
}

// ── XSS 방지 ──
$content = htmlspecialchars($content, ENT_QUOTES, 'UTF-8');

// ── prompt_comments 테이블 보장 ──
if ($type === 'prompt') {
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
}

try {
    $pdo->beginTransaction();

    if ($type === 'track') {
        // ── 트랙 존재 확인 ──
        $stmt = $pdo->prepare('SELECT id FROM tracks WHERE id = ?');
        $stmt->execute([$target_id]);
        if (!$stmt->fetch()) {
            $pdo->rollBack();
            header('Location: index.php?error=not_found');
            exit;
        }

        // ── track_comments INSERT ──
        $stmt = $pdo->prepare('
            INSERT INTO track_comments (track_id, user_id, content, created_at)
            VALUES (?, ?, ?, datetime("now"))
        ');
        $stmt->execute([$target_id, $currentUser['id'], $content]);

        // ── tracks 댓글 수 갱신 ──
        $stmt = $pdo->prepare('UPDATE tracks SET comment_count = comment_count + 1 WHERE id = ?');
        $stmt->execute([$target_id]);

    } elseif ($type === 'prompt') {
        // ── 프롬프트 존재 확인 ──
        $stmt = $pdo->prepare('SELECT id FROM prompts WHERE id = ?');
        $stmt->execute([$target_id]);
        if (!$stmt->fetch()) {
            $pdo->rollBack();
            header('Location: index.php?error=not_found');
            exit;
        }

        // ── prompt_comments INSERT (대댓글 지원) ──
        $stmt = $pdo->prepare('
            INSERT INTO prompt_comments (prompt_id, user_id, parent_id, content, created_at)
            VALUES (?, ?, ?, ?, datetime("now"))
        ');
        $stmt->execute([$target_id, $currentUser['id'], $parent_id, $content]);

    } elseif ($type === 'post') {
        // ── 게시글 존재 확인 ──
        $stmt = $pdo->prepare('SELECT id FROM posts WHERE id = ?');
        $stmt->execute([$target_id]);
        if (!$stmt->fetch()) {
            $pdo->rollBack();
            header('Location: index.php?error=not_found');
            exit;
        }

        // ── post_comments INSERT (대댓글 지원) ──
        $stmt = $pdo->prepare('
            INSERT INTO post_comments (post_id, user_id, parent_id, content, created_at)
            VALUES (?, ?, ?, ?, datetime("now"))
        ');
        $stmt->execute([$target_id, $currentUser['id'], $parent_id, $content]);

        // ── posts 댓글 수 갱신 ──
        $stmt = $pdo->prepare('UPDATE posts SET comment_count = comment_count + 1 WHERE id = ?');
        $stmt->execute([$target_id]);
    }

    $pdo->commit();
} catch (Exception $e) {
    $pdo->rollBack();
}

// ── 이전 페이지로 리다이렉트 ──
$referer = $_SERVER['HTTP_REFERER'] ?? 'index.php';
header('Location: ' . $referer);
exit;
