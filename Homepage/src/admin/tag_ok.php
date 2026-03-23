<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$action = $_REQUEST['action'] ?? '';
$tab = $_REQUEST['tab'] ?? 'track_genre';

switch ($action) {
    case 'add':
        $tagType = $_POST['tag_type'] ?? '';
        $tagNameRaw = trim($_POST['tag_name'] ?? '');

        $validTypes = ['track_genre', 'track_mood', 'prompt_genre', 'prompt_style'];
        if (!in_array($tagType, $validTypes) || $tagNameRaw === '') {
            header("Location: tags.php?tab=$tab");
            exit;
        }

        // 쉼표로 구분된 여러 태그 지원
        $names = array_filter(array_map('trim', explode(',', $tagNameRaw)));

        // 현재 최대 sort_order
        $maxOrder = $pdo->prepare("SELECT MAX(sort_order) FROM tag_options WHERE tag_type = ?");
        $maxOrder->execute([$tagType]);
        $nextOrder = ((int)$maxOrder->fetchColumn()) + 1;

        $ins = $pdo->prepare("INSERT OR IGNORE INTO tag_options (tag_type, tag_name, sort_order) VALUES (?, ?, ?)");
        $added = 0;
        foreach ($names as $name) {
            if (mb_strlen($name) > 0 && mb_strlen($name) <= 50) {
                $ins->execute([$tagType, $name, $nextOrder]);
                if ($ins->rowCount() > 0) {
                    $added++;
                    $nextOrder++;
                }
            }
        }

        $msg = $added > 0 ? 'added' : 'exists';
        header("Location: tags.php?tab=$tab&msg=$msg");
        break;

    case 'delete':
        $id = intval($_GET['id'] ?? 0);
        if ($id) {
            $pdo->prepare("DELETE FROM tag_options WHERE id = ?")->execute([$id]);
        }
        header("Location: tags.php?tab=$tab&msg=deleted");
        break;

    case 'activate':
        $id = intval($_GET['id'] ?? 0);
        if ($id) {
            $pdo->prepare("UPDATE tag_options SET is_active = 1 WHERE id = ?")->execute([$id]);
        }
        header("Location: tags.php?tab=$tab&msg=updated");
        break;

    case 'deactivate':
        $id = intval($_GET['id'] ?? 0);
        if ($id) {
            $pdo->prepare("UPDATE tag_options SET is_active = 0 WHERE id = ?")->execute([$id]);
        }
        header("Location: tags.php?tab=$tab&msg=updated");
        break;

    case 'move_up':
    case 'move_down':
        $id = intval($_GET['id'] ?? 0);
        if (!$id) { header("Location: tags.php?tab=$tab"); exit; }

        $stmt = $pdo->prepare("SELECT id, tag_type, sort_order FROM tag_options WHERE id = ?");
        $stmt->execute([$id]);
        $current = $stmt->fetch();
        if (!$current) { header("Location: tags.php?tab=$tab"); exit; }

        // 같은 타입의 태그들을 sort_order 순으로
        $siblings = $pdo->prepare("SELECT id, sort_order FROM tag_options WHERE tag_type = ? ORDER BY sort_order, id");
        $siblings->execute([$current['tag_type']]);
        $all = $siblings->fetchAll();

        $currentIdx = null;
        foreach ($all as $i => $s) {
            if ($s['id'] == $id) { $currentIdx = $i; break; }
        }

        if ($currentIdx === null) { header("Location: tags.php?tab=$tab"); exit; }

        $swapIdx = $action === 'move_up' ? $currentIdx - 1 : $currentIdx + 1;
        if ($swapIdx < 0 || $swapIdx >= count($all)) { header("Location: tags.php?tab=$tab"); exit; }

        $swap = $all[$swapIdx];

        // sort_order 교환
        $pdo->prepare("UPDATE tag_options SET sort_order = ? WHERE id = ?")->execute([$swap['sort_order'], $current['id']]);
        $pdo->prepare("UPDATE tag_options SET sort_order = ? WHERE id = ?")->execute([$current['sort_order'], $swap['id']]);

        // sort_order가 같은 경우 재정렬
        if ($swap['sort_order'] == $current['sort_order']) {
            foreach ($all as $i => $s) {
                $newOrder = $i;
                if ($s['id'] == $id) $newOrder = $swapIdx;
                elseif ($s['id'] == $swap['id']) $newOrder = $currentIdx;
                $pdo->prepare("UPDATE tag_options SET sort_order = ? WHERE id = ?")->execute([$newOrder, $s['id']]);
            }
        }

        header("Location: tags.php?tab=$tab");
        break;

    default:
        header("Location: tags.php?tab=$tab");
}
exit;
