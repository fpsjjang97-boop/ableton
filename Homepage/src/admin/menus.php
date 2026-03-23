<?php
require_once __DIR__ . '/header.php';

// menus 테이블이 없으면 생성 + 시드
$tableExists = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name='menus'")->fetchColumn();
if (!$tableExists) {
    $pdo->exec("CREATE TABLE menus (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        parent_id INTEGER DEFAULT NULL,
        menu_type TEXT NOT NULL DEFAULT 'link' CHECK(menu_type IN ('link','dropdown','separator')),
        title TEXT NOT NULL DEFAULT '',
        subtitle TEXT,
        url TEXT,
        icon_svg TEXT,
        sort_order INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        open_new_tab INTEGER NOT NULL DEFAULT 0,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY (parent_id) REFERENCES menus(id) ON DELETE CASCADE
    )");

    // 현재 navbar.php 하드코딩 메뉴를 시드 (Font Awesome 아이콘)
    $ins = $pdo->prepare("INSERT INTO menus (id, parent_id, menu_type, title, subtitle, url, icon_svg, sort_order, is_active) VALUES (?,?,?,?,?,?,?,?,1)");
    // 최상위
    $ins->execute([1, null, 'link', '공지', null, 'board_list.php?board=notice', 'fa-solid fa-bullhorn', 1]);
    $ins->execute([2, null, 'link', '프롬프트', null, 'prompt_list.php', 'fa-solid fa-wand-magic-sparkles', 2]);
    $ins->execute([3, null, 'dropdown', '음원', null, null, 'fa-solid fa-music', 3]);
    $ins->execute([4, null, 'dropdown', '커뮤니티', null, null, 'fa-solid fa-comments', 4]);

    // 음원 하위
    $ins->execute([5, 3, 'link', '인기음원', 'HOT 트랙 모아보기', 'popular_tracks.php', 'fa-solid fa-fire', 1]);
    $ins->execute([6, 3, 'link', '전체음원', '모든 음원 둘러보기', 'music_list.php', 'fa-solid fa-compact-disc', 2]);

    // 커뮤니티 하위
    $ins->execute([7, 4, 'link', '자유게시판', '자유롭게 이야기 나누기', 'board_list.php?board=free', 'fa-solid fa-comment', 1]);
    $ins->execute([8, 4, 'link', '질문/답변', '궁금한 점 물어보기', 'board_list.php?board=qna', 'fa-solid fa-circle-question', 2]);
    $ins->execute([9, 4, 'link', '정보', '유용한 정보 공유', 'board_list.php?board=info', 'fa-solid fa-lightbulb', 3]);
    $ins->execute([10, 4, 'link', '협업', '파트너 찾기', 'board_list.php?board=collab', 'fa-solid fa-people-group', 4]);
    $ins->execute([11, 4, 'separator', '', null, null, null, 5]);
    $ins->execute([12, 4, 'link', '랭킹', '크리에이터 순위', 'ranking.php', 'fa-solid fa-ranking-star', 6]);
}

$msg = $_GET['msg'] ?? '';

// 모든 메뉴 가져오기 (최상위 + 하위)
$allMenus = $pdo->query("SELECT * FROM menus ORDER BY sort_order")->fetchAll();

// 최상위/하위 분리
$topMenus = [];
$childMenus = [];
foreach ($allMenus as $m) {
    if ($m['parent_id'] === null) {
        $topMenus[] = $m;
    } else {
        $childMenus[$m['parent_id']][] = $m;
    }
}
?>

<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">메뉴 관리</h1>
    <a href="menu_edit.php" class="px-4 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm rounded-lg transition-colors">
        + 메뉴 추가
    </a>
</div>

<?php if ($msg === 'saved'): ?>
<div class="bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg mb-6 text-sm">저장되었습니다.</div>
<?php elseif ($msg === 'deleted'): ?>
<div class="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-6 text-sm">삭제되었습니다.</div>
<?php endif; ?>

<p class="text-sm text-gray-400 mb-6">사이트 상단 네비게이션 바의 메뉴를 관리합니다. 드롭다운 메뉴 아래에 하위 항목을 추가할 수 있습니다.</p>

<div class="space-y-3">
    <?php foreach ($topMenus as $idx => $menu): ?>
    <div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
        <!-- 최상위 메뉴 -->
        <div class="flex items-center justify-between px-5 py-4">
            <div class="flex items-center gap-4">
                <div class="w-8 h-8 bg-gray-700 rounded-lg flex items-center justify-center text-gray-400">
                    <?php if ($menu['icon_svg'] && strpos($menu['icon_svg'], 'fa-') !== false): ?>
                    <i class="<?= e($menu['icon_svg']) ?>"></i>
                    <?php elseif ($menu['icon_svg']): ?>
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="<?= e($menu['icon_svg']) ?>"/></svg>
                    <?php else: ?>
                    <span class="text-xs">#<?= $menu['id'] ?></span>
                    <?php endif; ?>
                </div>
                <div>
                    <div class="flex items-center gap-2">
                        <span class="text-white font-medium"><?= e($menu['title']) ?></span>
                        <span class="px-2 py-0.5 text-xs rounded
                            <?= $menu['menu_type'] === 'dropdown' ? 'bg-blue-500/20 text-blue-400' : ($menu['menu_type'] === 'separator' ? 'bg-gray-500/20 text-gray-400' : 'bg-green-500/20 text-green-400') ?>">
                            <?= $menu['menu_type'] === 'dropdown' ? '드롭다운' : ($menu['menu_type'] === 'separator' ? '구분선' : '링크') ?>
                        </span>
                        <?php if (!$menu['is_active']): ?>
                        <span class="px-2 py-0.5 text-xs rounded bg-red-500/20 text-red-400">비활성</span>
                        <?php endif; ?>
                    </div>
                    <?php if ($menu['url']): ?>
                    <div class="text-xs text-gray-500 mt-0.5"><?= e($menu['url']) ?></div>
                    <?php endif; ?>
                </div>
            </div>
            <div class="flex items-center gap-3">
                <!-- 정렬 버튼 -->
                <div class="flex gap-1">
                    <?php if ($idx > 0): ?>
                    <a href="menu_sort_ok.php?id=<?= $menu['id'] ?>&dir=up" class="w-7 h-7 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-white rounded transition-colors" title="위로">
                        <i class="fa-solid fa-chevron-up text-xs"></i>
                    </a>
                    <?php endif; ?>
                    <?php if ($idx < count($topMenus) - 1): ?>
                    <a href="menu_sort_ok.php?id=<?= $menu['id'] ?>&dir=down" class="w-7 h-7 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-white rounded transition-colors" title="아래로">
                        <i class="fa-solid fa-chevron-down text-xs"></i>
                    </a>
                    <?php endif; ?>
                </div>
                <div class="flex gap-2">
                    <a href="menu_edit.php?id=<?= $menu['id'] ?>" class="px-3 py-1.5 text-xs bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded-lg transition-colors">수정</a>
                    <a href="menu_delete_ok.php?id=<?= $menu['id'] ?>" onclick="return confirmDelete('이 메뉴를 삭제하시겠습니까?<?= $menu['menu_type'] === 'dropdown' ? ' 하위 메뉴도 모두 삭제됩니다.' : '' ?>')"
                       class="px-3 py-1.5 text-xs bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded-lg transition-colors">삭제</a>
                </div>
            </div>
        </div>

        <!-- 하위 메뉴 -->
        <?php if (isset($childMenus[$menu['id']])): ?>
        <div class="border-t border-gray-700 bg-gray-850">
            <?php foreach ($childMenus[$menu['id']] as $cIdx => $child): ?>
            <div class="flex items-center justify-between px-5 py-3 ml-8 border-b border-gray-700/50 last:border-0">
                <div class="flex items-center gap-3">
                    <?php if ($child['menu_type'] === 'separator'): ?>
                    <div class="flex items-center gap-2">
                        <span class="text-gray-500">---</span>
                        <span class="text-xs text-gray-500">구분선</span>
                    </div>
                    <?php else: ?>
                    <div class="w-6 h-6 bg-gray-700/50 rounded flex items-center justify-center text-gray-500">
                        <?php if ($child['icon_svg'] && strpos($child['icon_svg'], 'fa-') !== false): ?>
                        <i class="<?= e($child['icon_svg']) ?> text-sm"></i>
                        <?php elseif ($child['icon_svg']): ?>
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="<?= e($child['icon_svg']) ?>"/></svg>
                        <?php else: ?>
                        <span class="text-[10px]">#</span>
                        <?php endif; ?>
                    </div>
                    <div>
                        <span class="text-sm text-gray-300"><?= e($child['title']) ?></span>
                        <?php if ($child['subtitle']): ?>
                        <span class="text-xs text-gray-500 ml-2"><?= e($child['subtitle']) ?></span>
                        <?php endif; ?>
                        <?php if (!$child['is_active']): ?>
                        <span class="px-1.5 py-0.5 text-[10px] rounded bg-red-500/20 text-red-400 ml-2">비활성</span>
                        <?php endif; ?>
                    </div>
                    <?php endif; ?>
                </div>
                <div class="flex items-center gap-3">
                    <?php if ($child['url']): ?>
                    <span class="text-xs text-gray-600"><?= e($child['url']) ?></span>
                    <?php endif; ?>
                    <!-- 하위 메뉴 정렬 버튼 -->
                    <div class="flex gap-1">
                        <?php if ($cIdx > 0): ?>
                        <a href="menu_sort_ok.php?id=<?= $child['id'] ?>&dir=up" class="w-6 h-6 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-white rounded transition-colors" title="위로">
                            <i class="fa-solid fa-chevron-up text-[10px]"></i>
                        </a>
                        <?php endif; ?>
                        <?php if ($cIdx < count($childMenus[$menu['id']]) - 1): ?>
                        <a href="menu_sort_ok.php?id=<?= $child['id'] ?>&dir=down" class="w-6 h-6 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-white rounded transition-colors" title="아래로">
                            <i class="fa-solid fa-chevron-down text-[10px]"></i>
                        </a>
                        <?php endif; ?>
                    </div>
                    <div class="flex gap-1">
                        <a href="menu_edit.php?id=<?= $child['id'] ?>" class="px-2 py-1 text-xs bg-blue-600/20 text-blue-400 hover:bg-blue-600/30 rounded transition-colors">수정</a>
                        <a href="menu_delete_ok.php?id=<?= $child['id'] ?>" onclick="return confirmDelete('이 메뉴 항목을 삭제하시겠습니까?')"
                           class="px-2 py-1 text-xs bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded transition-colors">삭제</a>
                    </div>
                </div>
            </div>
            <?php endforeach; ?>
        </div>
        <?php endif; ?>

        <?php if ($menu['menu_type'] === 'dropdown'): ?>
        <div class="border-t border-gray-700 px-5 py-2 bg-gray-800/50">
            <a href="menu_edit.php?parent_id=<?= $menu['id'] ?>" class="text-xs text-violet-400 hover:text-violet-300 transition-colors">
                + <?= e($menu['title']) ?>에 하위 메뉴 추가
            </a>
        </div>
        <?php endif; ?>
    </div>
    <?php endforeach; ?>
</div>

<?php if (empty($topMenus)): ?>
<div class="bg-gray-800 rounded-xl border border-gray-700 p-8 text-center text-gray-500">
    등록된 메뉴가 없습니다. "메뉴 추가" 버튼을 눌러 메뉴를 만드세요.
</div>
<?php endif; ?>

<?php require_once __DIR__ . '/footer.php'; ?>
