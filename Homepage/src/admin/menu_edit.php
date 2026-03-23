<?php
require_once __DIR__ . '/header.php';

$id = intval($_GET['id'] ?? 0);
$parentIdParam = intval($_GET['parent_id'] ?? 0);
$menu = null;

if ($id) {
    $stmt = $pdo->prepare("SELECT * FROM menus WHERE id = ?");
    $stmt->execute([$id]);
    $menu = $stmt->fetch();
    if (!$menu) { header('Location: menus.php'); exit; }
}

// 드롭다운 목록 (하위메뉴 추가 시 부모 선택용)
$dropdowns = $pdo->query("SELECT id, title FROM menus WHERE menu_type = 'dropdown' AND parent_id IS NULL ORDER BY sort_order")->fetchAll();

// 게시판 목록 (빠른 연결용)
$boardsList = $pdo->query("SELECT id, board_key, board_name, board_type, color_class FROM boards ORDER BY sort_order")->fetchAll();

$defaults = [
    'parent_id' => $parentIdParam ?: null,
    'menu_type' => $parentIdParam ? 'link' : 'link',
    'title' => '',
    'subtitle' => '',
    'url' => '',
    'icon_svg' => '',
    'sort_order' => 0,
    'is_active' => 1,
    'open_new_tab' => 0,
];
$m = $menu ?: $defaults;
$msg = $_GET['msg'] ?? '';
?>

<div class="flex items-center gap-3 mb-6">
    <a href="menus.php" class="text-gray-500 hover:text-gray-300 transition-colors">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
    </a>
    <h1 class="text-2xl font-bold text-white"><?= $id ? '메뉴 수정' : '메뉴 추가' ?></h1>
</div>

<?php if ($msg === 'saved'): ?>
<div class="bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg mb-6 text-sm">저장되었습니다.</div>
<?php endif; ?>

<form action="menu_edit_ok.php" method="POST" class="max-w-2xl">
    <input type="hidden" name="id" value="<?= $id ?>">

    <div class="bg-gray-800 rounded-xl border border-gray-700 p-6 space-y-5">

        <div class="grid grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">메뉴 유형</label>
                <select name="menu_type" id="menuType" onchange="toggleFields()"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                    <option value="link" <?= $m['menu_type'] === 'link' ? 'selected' : '' ?>>링크</option>
                    <option value="dropdown" <?= $m['menu_type'] === 'dropdown' ? 'selected' : '' ?>>드롭다운 (하위 메뉴 그룹)</option>
                    <option value="separator" <?= $m['menu_type'] === 'separator' ? 'selected' : '' ?>>구분선</option>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">상위 메뉴 (하위 항목이면 선택)</label>
                <select name="parent_id"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                    <option value="">없음 (최상위 메뉴)</option>
                    <?php foreach ($dropdowns as $dd): ?>
                    <?php if ($dd['id'] != $id): // 자기 자신은 제외 ?>
                    <option value="<?= $dd['id'] ?>" <?= ($m['parent_id'] ?? '') == $dd['id'] ? 'selected' : '' ?>><?= e($dd['title']) ?></option>
                    <?php endif; ?>
                    <?php endforeach; ?>
                </select>
            </div>
        </div>

        <div id="titleField">
            <label class="block text-sm font-medium text-gray-300 mb-1">메뉴 이름</label>
            <input type="text" name="title" value="<?= e($m['title']) ?>"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                placeholder="메뉴에 표시될 이름">
        </div>

        <div id="boardLinkField">
            <label class="block text-sm font-medium text-gray-300 mb-1">게시판 바로 연결</label>
            <select id="boardSelect" onchange="applyBoardLink()"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                <option value="">직접 입력 (아래 URL 필드 사용)</option>
                <?php foreach ($boardsList as $bl): ?>
                <option value="<?= e($bl['board_key']) ?>"
                    data-name="<?= e($bl['board_name']) ?>"
                    data-type="<?= e($bl['board_type']) ?>"
                    <?= ($m['url'] === 'board_list.php?board=' . $bl['board_key']) ? 'selected' : '' ?>>
                    <?= e($bl['board_name']) ?> (<?= e($bl['board_key']) ?>) - <?= e($bl['board_type']) ?>
                </option>
                <?php endforeach; ?>
            </select>
            <p class="text-xs text-gray-500 mt-1">게시판을 선택하면 URL과 이름이 자동으로 채워집니다</p>
        </div>

        <div id="urlField">
            <label class="block text-sm font-medium text-gray-300 mb-1">URL</label>
            <input type="text" name="url" id="urlInput" value="<?= e($m['url']) ?>"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                placeholder="board_list.php?board=free 또는 외부 URL">
            <p class="text-xs text-gray-500 mt-1">사이트 내부 링크는 상대경로, 외부 링크는 https://로 시작</p>
        </div>

        <div id="subtitleField">
            <label class="block text-sm font-medium text-gray-300 mb-1">부제목 (드롭다운 항목에서 표시)</label>
            <input type="text" name="subtitle" value="<?= e($m['subtitle']) ?>"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                placeholder="예: 자유롭게 이야기 나누기">
        </div>

        <div id="iconField">
            <label class="block text-sm font-medium text-gray-300 mb-1">아이콘</label>
            <input type="hidden" name="icon_svg" value="<?= e($m['icon_svg']) ?>">
            <div class="flex items-center gap-3">
                <div id="iconPreview" class="w-10 h-10 bg-gray-700 border border-gray-600 rounded-lg flex items-center justify-center">
                    <?php if ($m['icon_svg']): ?>
                    <i class="<?= e($m['icon_svg']) ?> text-xl text-white"></i>
                    <?php else: ?>
                    <span class="text-gray-500 text-sm">없음</span>
                    <?php endif; ?>
                </div>
                <button type="button" onclick="openIconPicker('icon_svg')"
                    class="px-4 py-2 bg-gray-700 hover:bg-gray-600 border border-gray-600 text-gray-300 text-sm rounded-lg transition-colors">
                    <i class="fa-solid fa-icons mr-2"></i>아이콘 선택
                </button>
                <?php if ($m['icon_svg']): ?>
                <span class="text-xs text-gray-500 font-mono"><?= e($m['icon_svg']) ?></span>
                <?php endif; ?>
            </div>
        </div>

        <div class="grid grid-cols-3 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">정렬 순서</label>
                <input type="number" name="sort_order" value="<?= $m['sort_order'] ?>" min="0"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
            <div class="flex items-end pb-1">
                <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" name="is_active" value="1" <?= $m['is_active'] ? 'checked' : '' ?>
                        class="w-4 h-4 rounded bg-gray-700 border-gray-600 text-violet-600 focus:ring-violet-500">
                    <span class="text-sm text-gray-300">활성화</span>
                </label>
            </div>
            <div class="flex items-end pb-1">
                <label class="flex items-center gap-2 cursor-pointer">
                    <input type="checkbox" name="open_new_tab" value="1" <?= $m['open_new_tab'] ? 'checked' : '' ?>
                        class="w-4 h-4 rounded bg-gray-700 border-gray-600 text-violet-600 focus:ring-violet-500">
                    <span class="text-sm text-gray-300">새 탭에서 열기</span>
                </label>
            </div>
        </div>
    </div>

    <div class="flex gap-3 mt-6">
        <button type="submit" class="px-6 py-2 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg transition-colors">저장</button>
        <a href="menus.php" class="px-6 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors">취소</a>
    </div>
</form>

<script>
function toggleFields() {
    const type = document.getElementById('menuType').value;
    const titleField = document.getElementById('titleField');
    const urlField = document.getElementById('urlField');
    const boardLinkField = document.getElementById('boardLinkField');
    const subtitleField = document.getElementById('subtitleField');
    const iconField = document.getElementById('iconField');

    if (type === 'separator') {
        titleField.style.display = 'none';
        urlField.style.display = 'none';
        boardLinkField.style.display = 'none';
        subtitleField.style.display = 'none';
        iconField.style.display = 'none';
    } else if (type === 'dropdown') {
        titleField.style.display = '';
        urlField.style.display = 'none';
        boardLinkField.style.display = 'none';
        subtitleField.style.display = 'none';
        iconField.style.display = '';
    } else {
        titleField.style.display = '';
        urlField.style.display = '';
        boardLinkField.style.display = '';
        subtitleField.style.display = '';
        iconField.style.display = '';
    }
}

function applyBoardLink() {
    const sel = document.getElementById('boardSelect');
    const opt = sel.options[sel.selectedIndex];
    const boardKey = sel.value;

    if (!boardKey) return;

    const boardName = opt.getAttribute('data-name');
    const urlInput = document.getElementById('urlInput');
    const titleInput = document.querySelector('input[name="title"]');

    urlInput.value = 'board_list.php?board=' + boardKey;

    // 이름이 비어있으면 게시판 이름으로 채워줌
    if (!titleInput.value.trim()) {
        titleInput.value = boardName;
    }
}

toggleFields();
</script>

<?php $iconPickerTarget = 'icon_svg'; include __DIR__ . '/icon_picker.php'; ?>

<?php require_once __DIR__ . '/footer.php'; ?>
