<?php
require_once 'db.php';

header('Content-Type: application/json; charset=utf-8');

$query = isset($_GET['q']) ? trim($_GET['q']) : '';

$tableExists = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name='recommended_tags'")->fetch();

if ($query === '') {
    $popular = [];
    $genres = [];
    $instruments = [];
    $moods = [];

    if ($tableExists) {
        $stmt = $pdo->query("SELECT tag_name, tag_group FROM recommended_tags WHERE is_active = 1 ORDER BY tag_group, sort_order ASC");
        while ($row = $stmt->fetch()) {
            switch ($row['tag_group']) {
                case 'popular': $popular[] = $row['tag_name']; break;
                case 'genre': $genres[] = $row['tag_name']; break;
                case 'instrument': $instruments[] = $row['tag_name']; break;
                case 'mood': case 'style': $moods[] = $row['tag_name']; break;
            }
        }
    }

    if (empty($genres)) {
        $gStmt = $pdo->query("SELECT DISTINCT genre FROM prompt_genres ORDER BY genre LIMIT 15");
        $genres = $gStmt->fetchAll(PDO::FETCH_COLUMN);
    }

    echo json_encode([
        'type' => 'recommended',
        'popular' => array_slice($popular, 0, 6),
        'genres' => array_slice($genres, 0, 8),
        'instruments' => array_slice($instruments, 0, 6),
        'moods' => array_slice($moods, 0, 8),
    ], JSON_UNESCAPED_UNICODE);
    exit;
}

$results = [];
$seen = [];

if ($tableExists) {
    $stmt = $pdo->prepare("SELECT tag_name, tag_group, search_count FROM recommended_tags WHERE is_active = 1 AND tag_name LIKE ? ORDER BY search_count DESC LIMIT 10");
    $stmt->execute(['%' . $query . '%']);
    while ($row = $stmt->fetch()) {
        $key = mb_strtolower($row['tag_name']);
        if (!isset($seen[$key])) {
            $results[] = ['name' => $row['tag_name'], 'group' => $row['tag_group'], 'count' => $row['search_count']];
            $seen[$key] = true;
        }
    }
}

$gStmt = $pdo->prepare("SELECT DISTINCT genre FROM prompt_genres WHERE genre LIKE ? ORDER BY genre LIMIT 10");
$gStmt->execute(['%' . $query . '%']);
while ($row = $gStmt->fetch()) {
    $key = mb_strtolower($row['genre']);
    if (!isset($seen[$key])) {
        $cnt = $pdo->prepare("SELECT COUNT(*) FROM prompt_genres WHERE genre = ?");
        $cnt->execute([$row['genre']]);
        $results[] = ['name' => $row['genre'], 'group' => 'genre', 'count' => (int)$cnt->fetchColumn()];
        $seen[$key] = true;
    }
}

$sStmt = $pdo->prepare("SELECT DISTINCT style FROM prompt_styles WHERE style LIKE ? ORDER BY style LIMIT 10");
$sStmt->execute(['%' . $query . '%']);
while ($row = $sStmt->fetch()) {
    $key = mb_strtolower($row['style']);
    if (!isset($seen[$key])) {
        $cnt = $pdo->prepare("SELECT COUNT(*) FROM prompt_styles WHERE style = ?");
        $cnt->execute([$row['style']]);
        $results[] = ['name' => $row['style'], 'group' => 'style', 'count' => (int)$cnt->fetchColumn()];
        $seen[$key] = true;
    }
}

usort($results, function($a, $b) { return $b['count'] - $a['count']; });
$results = array_slice($results, 0, 10);

echo json_encode([
    'type' => 'search',
    'query' => $query,
    'results' => $results,
], JSON_UNESCAPED_UNICODE);
