<?php
require_once __DIR__ . '/header.php';

$id = intval($_GET['id'] ?? 0);
$board = null;
$categories = [];

if ($id) {
    $stmt = $pdo->prepare("SELECT * FROM boards WHERE id = ?");
    $stmt->execute([$id]);
    $board = $stmt->fetch();
    if (!$board) { header('Location: boards.php'); exit; }

    $catStmt = $pdo->prepare("SELECT * FROM board_categories WHERE board_id = ? ORDER BY sort_order");
    $catStmt->execute([$id]);
    $categories = $catStmt->fetchAll();
}

$defaults = [
    'board_key' => '', 'board_name' => '', 'board_type' => 'normal',
    'description' => '', 'icon_svg' => '', 'color_class' => 'text-gray-400', 'bg_class' => 'bg-gray-500/10 border-gray-500/20',
    'write_title' => '글쓰기', 'use_comment' => 1, 'use_like' => 1, 'use_editor' => 1,
    'write_level' => 1, 'comment_level' => 1, 'list_level' => 0, 'posts_per_page' => 20,
    'use_popular_tab' => 1, 'sort_order' => 0, 'is_active' => 1,
];
$b = $board ?: $defaults;
?>

<div class="flex items-center gap-3 mb-6">
    <a href="boards.php" class="text-gray-500 hover:text-gray-300 transition-colors">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
    </a>
    <h1 class="text-2xl font-bold text-white"><?= $id ? '게시판 수정' : '게시판 추가' ?></h1>
</div>

<form action="board_edit_ok.php" method="POST" class="max-w-2xl">
    <input type="hidden" name="id" value="<?= $id ?>">

    <div class="bg-gray-800 rounded-xl border border-gray-700 p-6 space-y-5">
        <div class="grid grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">게시판 키 (URL용)</label>
                <input type="text" name="board_key" value="<?= e($b['board_key']) ?>" required
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                    placeholder="free, notice, qna...">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">게시판 이름</label>
                <input type="text" name="board_name" value="<?= e($b['board_name']) ?>" required
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">게시판 타입</label>
                <select name="board_type" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                    <?php foreach (['normal'=>'일반', 'qna'=>'질문/답변', 'gallery'=>'갤러리', 'collab'=>'협업'] as $k => $v): ?>
                    <option value="<?= $k ?>" <?= $b['board_type'] === $k ? 'selected' : '' ?>><?= $v ?></option>
                    <?php endforeach; ?>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">작성 버튼 텍스트</label>
                <input type="text" name="write_title" value="<?= e($b['write_title']) ?>"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
        </div>

        <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">설명</label>
            <textarea name="description" rows="2"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500"><?= e($b['description']) ?></textarea>
        </div>

        <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">아이콘</label>
            <input type="hidden" name="icon_svg" value="<?= e($b['icon_svg'] ?? '') ?>">
            <div class="flex items-center gap-3">
                <div id="iconPreview" class="w-10 h-10 bg-gray-700 border border-gray-600 rounded-lg flex items-center justify-center">
                    <?php if (!empty($b['icon_svg'])): ?>
                    <i class="<?= e($b['icon_svg']) ?> text-xl text-white"></i>
                    <?php else: ?>
                    <span class="text-gray-500 text-sm">없음</span>
                    <?php endif; ?>
                </div>
                <button type="button" onclick="openIconPicker('icon_svg')"
                    class="px-4 py-2 bg-gray-700 hover:bg-gray-600 border border-gray-600 text-gray-300 text-sm rounded-lg transition-colors">
                    <i class="fa-solid fa-icons mr-2"></i>아이콘 선택
                </button>
                <?php if (!empty($b['icon_svg'])): ?>
                <span class="text-xs text-gray-500 font-mono"><?= e($b['icon_svg']) ?></span>
                <?php endif; ?>
            </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">색상 클래스</label>
                <input type="text" name="color_class" value="<?= e($b['color_class']) ?>"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                    placeholder="text-blue-400">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">배경 클래스</label>
                <input type="text" name="bg_class" value="<?= e($b['bg_class']) ?>"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                    placeholder="bg-blue-500/10 border-blue-500/20">
            </div>
        </div>

        <div class="grid grid-cols-4 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">페이지당 글수</label>
                <input type="number" name="posts_per_page" value="<?= $b['posts_per_page'] ?>" min="5" max="100"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">작성 레벨</label>
                <input type="number" name="write_level" value="<?= $b['write_level'] ?>" min="0" max="10"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">댓글 레벨</label>
                <input type="number" name="comment_level" value="<?= $b['comment_level'] ?>" min="0" max="10"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">열람 레벨</label>
                <input type="number" name="list_level" value="<?= $b['list_level'] ?>" min="0" max="10"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">정렬 순서</label>
                <input type="number" name="sort_order" value="<?= $b['sort_order'] ?>" min="0"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
            <div class="flex items-end pb-1">
                <label class="flex items-center gap-4">
                    <span class="text-sm text-gray-300">기능 설정:</span>
                </label>
            </div>
        </div>

        <div class="flex flex-wrap gap-6">
            <?php
            $toggles = [
                'use_comment' => '댓글 사용', 'use_like' => '좋아요 사용',
                'use_editor' => '에디터 사용', 'use_popular_tab' => '인기탭 사용',
                'is_active' => '활성화',
            ];
            foreach ($toggles as $key => $label):
            ?>
            <label class="flex items-center gap-2 cursor-pointer">
                <input type="checkbox" name="<?= $key ?>" value="1" <?= $b[$key] ? 'checked' : '' ?>
                    class="w-4 h-4 rounded bg-gray-700 border-gray-600 text-violet-600 focus:ring-violet-500">
                <span class="text-sm text-gray-300"><?= $label ?></span>
            </label>
            <?php endforeach; ?>
        </div>

    </div>

    <div class="flex gap-3 mt-6">
        <button type="submit" class="px-6 py-2 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg transition-colors">저장</button>
        <a href="boards.php" class="px-6 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors">취소</a>
    </div>
</form>

<?php if ($id): ?>
<!-- 카테고리 관리 -->
<div class="max-w-2xl mt-8">
    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <div class="px-6 py-4 border-b border-gray-700 flex items-center justify-between">
            <h2 class="text-white font-semibold">카테고리 관리</h2>
            <span class="text-sm text-gray-500"><?= count($categories) ?>개</span>
        </div>

        <!-- 기존 카테고리 목록 -->
        <?php if (!empty($categories)): ?>
        <div class="divide-y divide-gray-700">
            <?php foreach ($categories as $cat): ?>
            <div class="flex items-center justify-between px-6 py-3">
                <div class="flex items-center gap-3">
                    <span class="text-gray-400 text-xs w-6">#<?= $cat['id'] ?></span>
                    <span class="text-white"><?= e($cat['category_name']) ?></span>
                    <span class="text-xs text-gray-500">순서: <?= $cat['sort_order'] ?></span>
                    <?php if (!$cat['is_active']): ?>
                    <span class="px-1.5 py-0.5 text-[10px] rounded bg-red-500/20 text-red-400">비활성</span>
                    <?php endif; ?>
                </div>
                <div class="flex items-center gap-2">
                    <?php if ($cat['is_active']): ?>
                    <a href="board_cat_ok.php?action=deactivate&cat_id=<?= $cat['id'] ?>&board_id=<?= $id ?>"
                       class="px-2 py-1 text-xs bg-yellow-600/20 text-yellow-400 hover:bg-yellow-600/30 rounded transition-colors">비활성</a>
                    <?php else: ?>
                    <a href="board_cat_ok.php?action=activate&cat_id=<?= $cat['id'] ?>&board_id=<?= $id ?>"
                       class="px-2 py-1 text-xs bg-green-600/20 text-green-400 hover:bg-green-600/30 rounded transition-colors">활성</a>
                    <?php endif; ?>
                    <a href="board_cat_ok.php?action=delete&cat_id=<?= $cat['id'] ?>&board_id=<?= $id ?>"
                       onclick="return confirmDelete('이 카테고리를 삭제하시겠습니까?')"
                       class="px-2 py-1 text-xs bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded transition-colors">삭제</a>
                </div>
            </div>
            <?php endforeach; ?>
        </div>
        <?php else: ?>
        <div class="px-6 py-4 text-sm text-gray-500">등록된 카테고리가 없습니다.</div>
        <?php endif; ?>

        <!-- 카테고리 추가 -->
        <div class="px-6 py-4 border-t border-gray-700 bg-gray-800/50">
            <form action="board_cat_ok.php" method="POST" class="flex gap-2">
                <input type="hidden" name="action" value="add">
                <input type="hidden" name="board_id" value="<?= $id ?>">
                <input type="text" name="category_name" required placeholder="새 카테고리 이름"
                    class="flex-1 px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500">
                <input type="number" name="sort_order" value="0" min="0" placeholder="순서"
                    class="w-20 px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500">
                <button type="submit" class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm rounded-lg transition-colors whitespace-nowrap">추가</button>
            </form>
        </div>
    </div>
</div>
<?php endif; ?>

<?php $iconPickerTarget = 'icon_svg'; include __DIR__ . '/icon_picker.php'; ?>

<?php require_once __DIR__ . '/footer.php'; ?>
