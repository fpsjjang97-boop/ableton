<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$id = intval($_GET['id'] ?? 0);
$dir = $_GET['dir'] ?? '';

if (!$id || !in_array($dir, ['up', 'down'])) {
    header('Location: menus.php');
    exit;
}

// 현재 메뉴 정보
$stmt = $pdo->prepare("SELECT id, parent_id, sort_order FROM menus WHERE id = ?");
$stmt->execute([$id]);
$current = $stmt->fetch();

if (!$current) {
    header('Location: menus.php');
    exit;
}

// 같은 레벨(같은 parent_id)의 메뉴들을 sort_order 기준 정렬
if ($current['parent_id'] === null) {
    $siblings = $pdo->query("SELECT id, sort_order FROM menus WHERE parent_id IS NULL ORDER BY sort_order")->fetchAll();
} else {
    $stmt = $pdo->prepare("SELECT id, sort_order FROM menus WHERE parent_id = ? ORDER BY sort_order");
    $stmt->execute([$current['parent_id']]);
    $siblings = $stmt->fetchAll();
}

// 현재 메뉴의 인덱스 찾기
$currentIdx = null;
foreach ($siblings as $i => $s) {
    if ($s['id'] == $id) {
        $currentIdx = $i;
        break;
    }
}

if ($currentIdx === null) {
    header('Location: menus.php');
    exit;
}

// 교환할 대상 찾기
$swapIdx = $dir === 'up' ? $currentIdx - 1 : $currentIdx + 1;

if ($swapIdx < 0 || $swapIdx >= count($siblings)) {
    header('Location: menus.php');
    exit;
}

$swap = $siblings[$swapIdx];

// sort_order 교환
$pdo->prepare("UPDATE menus SET sort_order = ? WHERE id = ?")->execute([$swap['sort_order'], $current['id']]);
$pdo->prepare("UPDATE menus SET sort_order = ? WHERE id = ?")->execute([$current['sort_order'], $swap['id']]);

// sort_order가 같은 경우 처리: 전체 재정렬
if ($swap['sort_order'] == $current['sort_order']) {
    foreach ($siblings as $i => $s) {
        $newOrder = $i;
        if ($s['id'] == $id) $newOrder = $swapIdx;
        elseif ($s['id'] == $swap['id']) $newOrder = $currentIdx;
        $pdo->prepare("UPDATE menus SET sort_order = ? WHERE id = ?")->execute([$newOrder, $s['id']]);
    }
}

header('Location: menus.php');
exit;
