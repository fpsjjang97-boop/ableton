<?php
// 아이콘 피커 컴포넌트
// 사용법: $iconPickerTarget = 'icon_svg'; include 'icon_picker.php';
// $iconPickerTarget: 아이콘 값을 넣을 input의 name 속성
$iconPickerTarget = $iconPickerTarget ?? 'icon_svg';

$_iconCategories = [
    '일반' => [
        'fa-solid fa-house', 'fa-solid fa-gear', 'fa-solid fa-bell', 'fa-solid fa-bookmark',
        'fa-solid fa-calendar', 'fa-solid fa-clock', 'fa-solid fa-star', 'fa-solid fa-heart',
        'fa-solid fa-thumbs-up', 'fa-solid fa-fire', 'fa-solid fa-bolt', 'fa-solid fa-crown',
        'fa-solid fa-trophy', 'fa-solid fa-medal', 'fa-solid fa-gem', 'fa-solid fa-gift',
        'fa-solid fa-tag', 'fa-solid fa-tags', 'fa-solid fa-flag', 'fa-solid fa-map-pin',
    ],
    '커뮤니케이션' => [
        'fa-solid fa-envelope', 'fa-solid fa-comment', 'fa-solid fa-comments',
        'fa-solid fa-message', 'fa-solid fa-paper-plane', 'fa-solid fa-phone',
        'fa-solid fa-share-nodes', 'fa-solid fa-reply', 'fa-solid fa-bullhorn',
        'fa-solid fa-at', 'fa-solid fa-hashtag',
    ],
    '미디어 & 음악' => [
        'fa-solid fa-music', 'fa-solid fa-headphones', 'fa-solid fa-microphone',
        'fa-solid fa-guitar', 'fa-solid fa-drum', 'fa-solid fa-record-vinyl',
        'fa-solid fa-radio', 'fa-solid fa-volume-high', 'fa-solid fa-play',
        'fa-solid fa-compact-disc', 'fa-solid fa-sliders', 'fa-solid fa-wave-square',
        'fa-solid fa-film', 'fa-solid fa-camera', 'fa-solid fa-image',
        'fa-solid fa-video', 'fa-solid fa-tv',
    ],
    '콘텐츠 & 편집' => [
        'fa-solid fa-pen', 'fa-solid fa-pen-to-square', 'fa-solid fa-pencil',
        'fa-solid fa-wand-magic-sparkles', 'fa-solid fa-palette', 'fa-solid fa-paintbrush',
        'fa-solid fa-file', 'fa-solid fa-file-lines', 'fa-solid fa-folder',
        'fa-solid fa-book', 'fa-solid fa-book-open', 'fa-solid fa-newspaper',
        'fa-solid fa-quote-left', 'fa-solid fa-list', 'fa-solid fa-table-cells',
        'fa-solid fa-clipboard', 'fa-solid fa-copy', 'fa-solid fa-note-sticky',
    ],
    '사용자 & 소셜' => [
        'fa-solid fa-user', 'fa-solid fa-users', 'fa-solid fa-user-group',
        'fa-solid fa-user-plus', 'fa-solid fa-user-gear', 'fa-solid fa-people-group',
        'fa-solid fa-handshake', 'fa-solid fa-hand-holding-heart',
        'fa-solid fa-ranking-star', 'fa-solid fa-chart-line', 'fa-solid fa-chart-bar',
        'fa-brands fa-youtube', 'fa-brands fa-instagram', 'fa-brands fa-discord',
    ],
    '네비게이션 & UI' => [
        'fa-solid fa-bars', 'fa-solid fa-grip', 'fa-solid fa-table-columns',
        'fa-solid fa-arrow-right', 'fa-solid fa-chevron-right',
        'fa-solid fa-angles-right', 'fa-solid fa-arrow-up-right-from-square',
        'fa-solid fa-magnifying-glass', 'fa-solid fa-filter', 'fa-solid fa-sort',
        'fa-solid fa-ellipsis', 'fa-solid fa-ellipsis-vertical',
        'fa-solid fa-layer-group', 'fa-solid fa-sitemap', 'fa-solid fa-diagram-project',
    ],
    '상태 & 알림' => [
        'fa-solid fa-check', 'fa-solid fa-xmark', 'fa-solid fa-circle-check',
        'fa-solid fa-circle-xmark', 'fa-solid fa-circle-info',
        'fa-solid fa-circle-question', 'fa-solid fa-circle-exclamation',
        'fa-solid fa-triangle-exclamation', 'fa-solid fa-shield',
        'fa-solid fa-lock', 'fa-solid fa-unlock', 'fa-solid fa-eye',
        'fa-solid fa-eye-slash', 'fa-solid fa-ban', 'fa-solid fa-trash',
    ],
    '기타' => [
        'fa-solid fa-globe', 'fa-solid fa-earth-asia', 'fa-solid fa-link',
        'fa-solid fa-code', 'fa-solid fa-terminal', 'fa-solid fa-database',
        'fa-solid fa-server', 'fa-solid fa-cloud', 'fa-solid fa-download',
        'fa-solid fa-upload', 'fa-solid fa-rocket', 'fa-solid fa-lightbulb',
        'fa-solid fa-puzzle-piece', 'fa-solid fa-cube', 'fa-solid fa-cubes',
        'fa-solid fa-plug', 'fa-solid fa-toolbox', 'fa-solid fa-wrench',
    ],
];
?>
<!-- 아이콘 피커 모달 -->
<div id="iconPickerModal" class="fixed inset-0 z-50 hidden">
    <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="closeIconPicker()"></div>
    <div class="relative z-10 flex items-center justify-center min-h-screen p-4">
        <div class="bg-gray-800 border border-gray-700 rounded-2xl shadow-2xl w-full max-w-2xl max-h-[80vh] flex flex-col">
            <!-- 헤더 -->
            <div class="flex items-center justify-between px-6 py-4 border-b border-gray-700">
                <h3 class="text-white font-semibold text-lg">아이콘 선택</h3>
                <div class="flex items-center gap-3">
                    <input type="text" id="iconSearchInput" placeholder="아이콘 검색..." oninput="filterIcons(this.value)"
                        class="px-3 py-1.5 bg-gray-700 border border-gray-600 rounded-lg text-white text-sm placeholder-gray-500 focus:outline-none focus:ring-2 focus:ring-violet-500 w-48">
                    <button onclick="closeIconPicker()" class="text-gray-400 hover:text-white transition-colors">
                        <i class="fa-solid fa-xmark text-lg"></i>
                    </button>
                </div>
            </div>

            <!-- 아이콘 그리드 -->
            <div class="overflow-y-auto flex-1 p-6 space-y-5" id="iconPickerContent">
                <!-- 선택 해제 -->
                <div>
                    <button type="button" onclick="selectIcon('')"
                        class="px-4 py-2 text-sm bg-gray-700 hover:bg-gray-600 text-gray-400 rounded-lg transition-colors">
                        <i class="fa-solid fa-xmark mr-2"></i>아이콘 없음
                    </button>
                </div>

                <?php foreach ($_iconCategories as $catName => $icons): ?>
                <div class="icon-category" data-category="<?= htmlspecialchars($catName) ?>">
                    <h4 class="text-sm font-medium text-gray-400 mb-3"><?= htmlspecialchars($catName) ?></h4>
                    <div class="grid grid-cols-8 sm:grid-cols-10 gap-1">
                        <?php foreach ($icons as $icon): ?>
                        <button type="button" onclick="selectIcon('<?= htmlspecialchars($icon) ?>')"
                            class="icon-btn w-10 h-10 flex items-center justify-center rounded-lg hover:bg-violet-600/30 hover:text-violet-400 text-gray-400 transition-all border border-transparent hover:border-violet-500/30"
                            data-icon="<?= htmlspecialchars($icon) ?>"
                            title="<?= htmlspecialchars($icon) ?>">
                            <i class="<?= htmlspecialchars($icon) ?>"></i>
                        </button>
                        <?php endforeach; ?>
                    </div>
                </div>
                <?php endforeach; ?>
            </div>
        </div>
    </div>
</div>

<script>
let _iconPickerTarget = '<?= $iconPickerTarget ?>';

function openIconPicker(targetInputName) {
    _iconPickerTarget = targetInputName || _iconPickerTarget;
    document.getElementById('iconPickerModal').classList.remove('hidden');
    document.getElementById('iconSearchInput').value = '';
    filterIcons('');

    // 현재 선택된 아이콘 하이라이트
    const current = document.querySelector('input[name="' + _iconPickerTarget + '"]').value;
    document.querySelectorAll('#iconPickerContent .icon-btn').forEach(btn => {
        if (btn.dataset.icon === current) {
            btn.classList.add('bg-violet-600/40', 'text-violet-300', 'border-violet-500/50');
        } else {
            btn.classList.remove('bg-violet-600/40', 'text-violet-300', 'border-violet-500/50');
        }
    });
}

function closeIconPicker() {
    document.getElementById('iconPickerModal').classList.add('hidden');
}

function selectIcon(iconClass) {
    const input = document.querySelector('input[name="' + _iconPickerTarget + '"]');
    input.value = iconClass;

    // 미리보기 업데이트
    const preview = document.getElementById('iconPreview');
    if (preview) {
        if (iconClass) {
            preview.innerHTML = '<i class="' + iconClass + ' text-xl"></i>';
        } else {
            preview.innerHTML = '<span class="text-gray-500 text-sm">없음</span>';
        }
    }
    closeIconPicker();
}

function filterIcons(query) {
    query = query.toLowerCase().trim();
    document.querySelectorAll('#iconPickerContent .icon-btn').forEach(btn => {
        const match = !query || btn.dataset.icon.toLowerCase().includes(query);
        btn.style.display = match ? '' : 'none';
    });
    document.querySelectorAll('#iconPickerContent .icon-category').forEach(cat => {
        const visible = cat.querySelectorAll('.icon-btn[style=""], .icon-btn:not([style])');
        cat.style.display = visible.length === 0 && query ? 'none' : '';
    });
}

// ESC 닫기
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closeIconPicker();
});
</script>
