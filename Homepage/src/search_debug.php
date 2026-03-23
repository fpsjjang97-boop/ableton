<?php
/**
 * 검색 디버그: 브라우저에서 열어서 사용 중인 DB 경로와 '태초' 검색 결과 확인
 * 예: http://localhost:8888/search_debug.php?q=태초
 * 확인 후 삭제해도 됨.
 */
require_once 'db.php';

header('Content-Type: text/html; charset=utf-8');

$db_path = __DIR__ . '/database.sqlite';
$q = isset($_GET['q']) ? trim($_GET['q']) : '태초';
$term = '%' . $q . '%';

echo "<h2>검색 디버그</h2>";
echo "<p><strong>사용 중인 DB 파일:</strong> <code>" . htmlspecialchars(realpath($db_path) ?: $db_path) . "</code></p>";
echo "<p>파일 존재: " . (file_exists($db_path) ? '예' : '아니오') . "</p>";

echo "<h3>게시물 수</h3>";
$total = $pdo->query("SELECT COUNT(*) FROM posts")->fetchColumn();
echo "<p>전체 게시물: {$total}건</p>";

echo "<h3>제목/본문에 '" . htmlspecialchars($q) . "' 포함 (LIKE '%...%')</h3>";
$stmt = $pdo->prepare("SELECT id, board_id, title, length(content) as clen FROM posts WHERE title LIKE ? OR content LIKE ?");
$stmt->execute([$term, $term]);
$rows = $stmt->fetchAll(PDO::FETCH_ASSOC);
echo "<p>매칭: " . count($rows) . "건</p>";
echo "<pre>" . print_r($rows, true) . "</pre>";

echo "<h3>댓글에 '" . htmlspecialchars($q) . "' 포함</h3>";
$stmt = $pdo->prepare("SELECT c.id, c.post_id, substr(c.content,1,100) as content FROM post_comments c WHERE c.content LIKE ?");
$stmt->execute([$term]);
$comments = $stmt->fetchAll(PDO::FETCH_ASSOC);
echo "<p>매칭 댓글: " . count($comments) . "건</p>";
echo "<pre>" . print_r($comments, true) . "</pre>";

echo "<h3>전체 게시물 제목 목록 (최근 20건)</h3>";
$stmt = $pdo->query("SELECT id, board_id, title FROM posts ORDER BY id DESC LIMIT 20");
echo "<ul>";
while ($r = $stmt->fetch(PDO::FETCH_ASSOC)) {
    echo "<li>id={$r['id']} board_id={$r['board_id']} " . htmlspecialchars($r['title']) . "</li>";
}
echo "</ul>";
echo "<p><a href='search.php?q=" . urlencode($q) . "'>검색 페이지로 이동</a></p>";
