<?php
require_once __DIR__ . '/header.php';

// tag_options 테이블이 없으면 생성 + 시드
$tableExists = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name='tag_options'")->fetchColumn();
if (!$tableExists) {
    $pdo->exec("CREATE TABLE tag_options (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tag_type TEXT NOT NULL CHECK(tag_type IN ('track_genre','track_mood','prompt_genre','prompt_style')),
        tag_name TEXT NOT NULL,
        sort_order INTEGER NOT NULL DEFAULT 0,
        is_active INTEGER NOT NULL DEFAULT 1,
        created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
        UNIQUE(tag_type, tag_name)
    )");

    // 기존 하드코딩 데이터 시드
    $ins = $pdo->prepare("INSERT INTO tag_options (tag_type, tag_name, sort_order) VALUES (?, ?, ?)");

    $trackGenres = ['K-Pop', 'Lo-fi', 'Hip-Hop', 'R&B', 'Rock', 'Jazz', 'Classical', 'EDM', 'Ambient', 'Synthwave', 'City Pop', 'Ballad', 'Folk', 'Funk', 'Cinematic', 'Country', 'Reggae', 'Metal'];
    foreach ($trackGenres as $i => $t) $ins->execute(['track_genre', $t, $i]);

    $trackMoods = ['신나는', '잔잔한', '슬픈', '몽환적', '에너지틱', '로맨틱', '다크', '밝은', '레트로', '모던', '감성적', '파워풀', '힐링', '드라마틱', '그루비'];
    foreach ($trackMoods as $i => $t) $ins->execute(['track_mood', $t, $i]);

    $promptGenres = ['K-Pop', 'Lo-fi', 'Hip-Hop', 'R&B', 'Rock', 'Jazz', 'EDM', 'Ambient', 'Cinematic', 'Classical', 'Ballad', 'Folk', 'Reggae', 'Metal', 'Country', 'Latin'];
    foreach ($promptGenres as $i => $t) $ins->execute(['prompt_genre', $t, $i]);

    $promptStyles = ['Dreamy', 'Energetic', 'Chill', 'Dark', 'Uplifting', 'Melancholic', 'Retro', 'Futuristic', 'Acoustic', 'Electronic', 'Orchestral', 'Minimal'];
    foreach ($promptStyles as $i => $t) $ins->execute(['prompt_style', $t, $i]);
}

$msg = $_GET['msg'] ?? '';
$activeTab = $_GET['tab'] ?? 'track_genre';
$validTabs = ['track_genre', 'track_mood', 'prompt_genre', 'prompt_style'];
if (!in_array($activeTab, $validTabs)) $activeTab = 'track_genre';

$tabLabels = [
    'track_genre' => ['음원 장르', 'fa-solid fa-music', 'music_upload.php에서 표시되는 장르 태그'],
    'track_mood' => ['음원 분위기', 'fa-solid fa-face-smile', 'music_upload.php에서 표시되는 분위기 태그'],
    'prompt_genre' => ['프롬프트 장르', 'fa-solid fa-wand-magic-sparkles', 'prompt_write.php에서 표시되는 장르 태그'],
    'prompt_style' => ['프롬프트 스타일', 'fa-solid fa-palette', 'prompt_write.php에서 표시되는 스타일 태그'],
];

// 현재 탭의 태그 목록
$stmt = $pdo->prepare("SELECT * FROM tag_options WHERE tag_type = ? ORDER BY sort_order, id");
$stmt->execute([$activeTab]);
$tags = $stmt->fetchAll();

// 각 탭별 태그 수
$countStmt = $pdo->query("SELECT tag_type, COUNT(*) as cnt FROM tag_options GROUP BY tag_type");
$tabCounts = [];
while ($row = $countStmt->fetch()) {
    $tabCounts[$row['tag_type']] = $row['cnt'];
}
?>

<div class="flex items-center justify-between mb-6">
    <h1 class="text-2xl font-bold text-white">태그 관리</h1>
</div>

<?php if ($msg === 'added'): ?>
<div class="bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg mb-6 text-sm">태그가 추가되었습니다.</div>
<?php elseif ($msg === 'deleted'): ?>
<div class="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-6 text-sm">태그가 삭제되었습니다.</div>
<?php elseif ($msg === 'updated'): ?>
<div class="bg-blue-500/10 border border-blue-500/30 text-blue-400 px-4 py-3 rounded-lg mb-6 text-sm">태그 상태가 변경되었습니다.</div>
<?php elseif ($msg === 'exists'): ?>
<div class="bg-yellow-500/10 border border-yellow-500/30 text-yellow-400 px-4 py-3 rounded-lg mb-6 text-sm">이미 존재하는 태그입니다.</div>
<?php endif; ?>

<!-- 탭 -->
<div class="flex gap-1 mb-6 bg-gray-800 rounded-xl p-1 border border-gray-700">
    <?php foreach ($tabLabels as $tabKey => $tabInfo): ?>
    <a href="tags.php?tab=<?= $tabKey ?>"
       class="flex-1 flex items-center justify-center gap-2 px-4 py-2.5 rounded-lg text-sm font-medium transition-colors
              <?= $activeTab === $tabKey ? 'bg-violet-600 text-white' : 'text-gray-400 hover:text-gray-200 hover:bg-gray-700' ?>">
        <i class="<?= $tabInfo[1] ?> text-xs"></i>
        <?= $tabInfo[0] ?>
        <span class="text-xs opacity-60">(<?= $tabCounts[$tabKey] ?? 0 ?>)</span>
    </a>
    <?php endforeach; ?>
</div>

<p class="text-sm text-gray-400 mb-4"><?= $tabLabels[$activeTab][2] ?></p>

<!-- 태그 추가 -->
<div class="bg-gray-800 rounded-xl border border-gray-700 p-5 mb-6">
    <form action="tag_ok.php" method="POST" class="flex gap-3">
        <input type="hidden" name="action" value="add">
        <input type="hidden" name="tag_type" value="<?= $activeTab ?>">
        <input type="text" name="tag_name" required placeholder="새 태그 이름 입력"
            class="flex-1 px-4 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm focus:outline-none focus:ring-2 focus:ring-violet-500">
        <button type="submit" class="px-5 py-2 bg-violet-600 hover:bg-violet-700 text-white text-sm font-medium rounded-lg transition-colors whitespace-nowrap">
            <i class="fa-solid fa-plus mr-1"></i> 추가
        </button>
    </form>
    <p class="text-xs text-gray-500 mt-2">여러 개를 한번에 추가하려면 쉼표(,)로 구분하세요. 예: K-Pop, Lo-fi, Jazz</p>
</div>

<!-- 태그 목록 -->
<div class="bg-gray-800 rounded-xl border border-gray-700 overflow-hidden">
    <div class="px-5 py-4 border-b border-gray-700 flex items-center justify-between">
        <h2 class="text-white font-semibold"><?= $tabLabels[$activeTab][0] ?> 목록</h2>
        <span class="text-sm text-gray-500"><?= count($tags) ?>개</span>
    </div>

    <?php if (empty($tags)): ?>
    <div class="px-5 py-8 text-center text-gray-500">등록된 태그가 없습니다.</div>
    <?php else: ?>
    <div class="divide-y divide-gray-700">
        <?php foreach ($tags as $idx => $tag): ?>
        <div class="flex items-center justify-between px-5 py-3 hover:bg-gray-700/30 transition-colors">
            <div class="flex items-center gap-3">
                <span class="text-gray-600 text-xs w-8">#<?= $tag['sort_order'] + 1 ?></span>
                <span class="px-3 py-1 rounded-full text-sm font-medium
                    <?= $tag['is_active'] ? 'bg-violet-500/20 text-violet-300 border border-violet-500/30' : 'bg-gray-700 text-gray-500 border border-gray-600 line-through' ?>">
                    <?= e($tag['tag_name']) ?>
                </span>
                <?php if (!$tag['is_active']): ?>
                <span class="text-[10px] text-red-400">비활성</span>
                <?php endif; ?>
            </div>
            <div class="flex items-center gap-2">
                <!-- 정렬 -->
                <?php if ($idx > 0): ?>
                <a href="tag_ok.php?action=move_up&id=<?= $tag['id'] ?>&tab=<?= $activeTab ?>"
                   class="w-7 h-7 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-white rounded transition-colors" title="위로">
                    <i class="fa-solid fa-chevron-up text-xs"></i>
                </a>
                <?php endif; ?>
                <?php if ($idx < count($tags) - 1): ?>
                <a href="tag_ok.php?action=move_down&id=<?= $tag['id'] ?>&tab=<?= $activeTab ?>"
                   class="w-7 h-7 flex items-center justify-center bg-gray-700 hover:bg-gray-600 text-gray-400 hover:text-white rounded transition-colors" title="아래로">
                    <i class="fa-solid fa-chevron-down text-xs"></i>
                </a>
                <?php endif; ?>

                <div class="w-px h-5 bg-gray-700 mx-1"></div>

                <!-- 활성/비활성 -->
                <?php if ($tag['is_active']): ?>
                <a href="tag_ok.php?action=deactivate&id=<?= $tag['id'] ?>&tab=<?= $activeTab ?>"
                   class="px-2.5 py-1 text-xs bg-yellow-600/20 text-yellow-400 hover:bg-yellow-600/30 rounded-lg transition-colors">비활성</a>
                <?php else: ?>
                <a href="tag_ok.php?action=activate&id=<?= $tag['id'] ?>&tab=<?= $activeTab ?>"
                   class="px-2.5 py-1 text-xs bg-green-600/20 text-green-400 hover:bg-green-600/30 rounded-lg transition-colors">활성</a>
                <?php endif; ?>

                <!-- 삭제 -->
                <a href="tag_ok.php?action=delete&id=<?= $tag['id'] ?>&tab=<?= $activeTab ?>"
                   onclick="return confirmDelete('태그 \'<?= e($tag['tag_name']) ?>\'을(를) 삭제하시겠습니까?')"
                   class="px-2.5 py-1 text-xs bg-red-600/20 text-red-400 hover:bg-red-600/30 rounded-lg transition-colors">삭제</a>
            </div>
        </div>
        <?php endforeach; ?>
    </div>
    <?php endif; ?>
</div>

<?php require_once __DIR__ . '/footer.php'; ?>
