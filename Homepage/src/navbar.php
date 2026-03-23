<?php
// 아이콘 렌더 헬퍼: FA 클래스면 <i>, SVG path면 <svg>
function _navIcon($iconSvg, $class = 'w-4 h-4 opacity-70') {
    if (empty($iconSvg)) return '';
    if (strpos($iconSvg, 'fa-') !== false) {
        return '<i class="' . htmlspecialchars($iconSvg) . ' ' . $class . '"></i>';
    }
    return '<svg class="' . $class . '" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="' . htmlspecialchars($iconSvg) . '"/></svg>';
}

// DB에서 메뉴 로드 (menus 테이블이 없으면 빈 배열)
$_navMenus = [];
$_navChildren = [];
try {
    $tableCheck = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name='menus'")->fetchColumn();
    if ($tableCheck) {
        $allNav = $pdo->query("SELECT * FROM menus WHERE is_active = 1 ORDER BY sort_order")->fetchAll();
        foreach ($allNav as $nm) {
            if ($nm['parent_id'] === null) {
                $_navMenus[] = $nm;
            } else {
                $_navChildren[$nm['parent_id']][] = $nm;
            }
        }
    }
} catch (Exception $e) {
    $_navMenus = [];
}
$_useDbMenus = !empty($_navMenus);
?>
<!-- Navigation -->
<nav class="fixed top-0 left-0 right-0 z-50 nav-blur bg-suno-dark/80 border-b border-suno-border">
    <div class="max-w-7xl mx-auto px-6 py-3.5 flex items-center justify-between">
        <!-- Logo -->
        <a href="index.php" class="flex items-center gap-1.5 shrink-0">
            <div class="flex gap-[2px] items-end h-6">
                <div class="w-[3px] bg-suno-accent rounded-full h-3 wave-bar"></div>
                <div class="w-[3px] bg-suno-accent rounded-full h-5 wave-bar" style="animation-delay:0.15s"></div>
                <div class="w-[3px] bg-suno-accent rounded-full h-4 wave-bar" style="animation-delay:0.3s"></div>
                <div class="w-[3px] bg-suno-accent rounded-full h-6 wave-bar" style="animation-delay:0.45s"></div>
                <div class="w-[3px] bg-suno-accent rounded-full h-3 wave-bar" style="animation-delay:0.6s"></div>
            </div>
            <span class="text-xl font-extrabold tracking-tight ml-1">SUNO</span>
            <span class="text-[10px] font-medium text-suno-muted bg-suno-surface px-1.5 py-0.5 rounded ml-1 leading-none">Community</span>
        </a>

        <!-- Nav Links (Desktop) -->
        <div class="hidden lg:flex items-center gap-1">
<?php if ($_useDbMenus): ?>
<?php foreach ($_navMenus as $_m): ?>
<?php if ($_m['menu_type'] === 'link'): ?>
            <a href="<?= htmlspecialchars($_m['url']) ?>"<?= $_m['open_new_tab'] ? ' target="_blank"' : '' ?> class="text-sm text-white/90 hover:text-white transition-colors px-3.5 py-2 rounded-lg hover:bg-white/5 flex items-center gap-1.5">
                <?= _navIcon($_m['icon_svg']) ?>
                <?= htmlspecialchars($_m['title']) ?>
            </a>
<?php elseif ($_m['menu_type'] === 'dropdown' && isset($_navChildren[$_m['id']])): ?>
            <div class="nav-item relative">
                <button class="text-sm text-white/90 hover:text-white transition-colors px-3.5 py-2 rounded-lg hover:bg-white/5 flex items-center gap-1.5">
                    <?= _navIcon($_m['icon_svg']) ?>
                    <?= htmlspecialchars($_m['title']) ?>
                    <svg class="w-3 h-3 opacity-60" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M19 9l-7 7-7-7"/></svg>
                </button>
                <div class="nav-dropdown absolute top-full left-0 mt-1 w-56 bg-suno-card/95 nav-blur border border-suno-border rounded-xl shadow-2xl shadow-black/40 py-2 overflow-hidden">
<?php foreach ($_navChildren[$_m['id']] as $_child): ?>
<?php if ($_child['menu_type'] === 'separator'): ?>
                    <div class="border-t border-suno-border my-1.5"></div>
<?php else: ?>
                    <a href="<?= htmlspecialchars($_child['url']) ?>"<?= $_child['open_new_tab'] ? ' target="_blank"' : '' ?> class="nav-dropdown-item flex items-center gap-3 px-4 py-2.5">
<?php if ($_child['icon_svg']): ?>
                        <span class="dropdown-icon text-suno-muted">
                            <?= _navIcon($_child['icon_svg'], 'w-4 h-4') ?>
                        </span>
<?php endif; ?>
                        <div>
                            <span class="text-sm text-white/90 block"><?= htmlspecialchars($_child['title']) ?></span>
<?php if ($_child['subtitle']): ?>
                            <span class="text-xs text-suno-muted/70"><?= htmlspecialchars($_child['subtitle']) ?></span>
<?php endif; ?>
                        </div>
                    </a>
<?php endif; ?>
<?php endforeach; ?>
                </div>
            </div>
<?php endif; ?>
<?php endforeach; ?>
<?php else: ?>
            <!-- Fallback: DB 메뉴 없을 때 기본 메뉴 -->
            <a href="board_list.php?board=notice" class="text-sm text-white/90 hover:text-white transition-colors px-3.5 py-2 rounded-lg hover:bg-white/5 flex items-center gap-1.5">공지</a>
            <a href="prompt_list.php" class="text-sm text-white/90 hover:text-white transition-colors px-3.5 py-2 rounded-lg hover:bg-white/5 flex items-center gap-1.5">프롬프트</a>
            <a href="music_list.php" class="text-sm text-white/90 hover:text-white transition-colors px-3.5 py-2 rounded-lg hover:bg-white/5 flex items-center gap-1.5">음원</a>
<?php endif; ?>
        </div>

        <!-- Right: Search + Auth + Mobile Toggle -->
        <div class="flex items-center gap-2">
            <!-- Desktop Search Bar -->
            <div class="hidden lg:block relative">
                <form action="search.php" method="GET" class="relative">
                    <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-3.5 h-3.5 text-suno-muted pointer-events-none" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                    </svg>
                    <input type="text" name="q" placeholder="검색..."
                        class="w-44 xl:w-56 bg-suno-surface/80 border border-suno-border rounded-lg pl-9 pr-3 py-1.5 text-xs text-white placeholder-suno-muted/60 focus:outline-none focus:border-suno-accent/50 focus:w-72 transition-all duration-300"
                        id="navSearchInput">
                </form>
            </div>

            <!-- Mobile Search Button -->
            <button onclick="openSearchModal()" class="lg:hidden flex items-center justify-center w-9 h-9 rounded-lg hover:bg-white/5 transition-colors text-suno-muted hover:text-white">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                </svg>
            </button>

            <?php if (isset($currentUser) && $currentUser): ?>
            <!-- 쪽지 아이콘 (로그인 시에만 표시) -->
            <?php
                $unreadCount = 0;
                if (isset($pdo) && $currentUser) {
                    $stmtMsg = $pdo->prepare('SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND is_read = 0 AND receiver_deleted = 0');
                    $stmtMsg->execute([$currentUser['id']]);
                    $unreadCount = (int)$stmtMsg->fetchColumn();
                }
            ?>
            <a href="message_list.php" class="relative flex items-center justify-center w-9 h-9 rounded-lg hover:bg-white/5 transition-colors text-suno-muted hover:text-white" title="쪽지함">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"/>
                </svg>
                <?php if ($unreadCount > 0): ?>
                <span class="absolute -top-0.5 -right-0.5 w-4 h-4 bg-suno-accent text-white text-[9px] font-bold rounded-full flex items-center justify-center"><?= $unreadCount > 99 ? '99+' : $unreadCount ?></span>
                <?php endif; ?>
            </a>

            <!-- 프로필 / 로그아웃 -->
            <a href="profile.php" class="text-sm text-white/90 hover:text-white transition-colors px-3 py-2 hidden sm:block"><?= htmlspecialchars($currentUser['nickname']) ?></a>
            <a href="logout.php" class="text-sm text-suno-muted hover:text-white transition-colors px-2 py-2 hidden sm:block">로그아웃</a>
            <?php else: ?>
            <a href="login.php" class="text-sm text-white/90 hover:text-white transition-colors px-3 py-2 hidden sm:block">로그인</a>
            <a href="register.php" class="text-sm bg-suno-accent hover:bg-suno-accent2 text-white font-medium px-4 py-2 rounded-lg transition-all hidden sm:block">회원가입</a>
            <?php endif; ?>

            <!-- Mobile Hamburger -->
            <button onclick="toggleMobileMenu()" class="lg:hidden flex flex-col gap-1.5 p-2 rounded-lg hover:bg-white/5 transition-colors" id="mobileMenuBtn">
                <span class="block w-5 h-[1.5px] bg-white/70 transition-all" id="hamburger1"></span>
                <span class="block w-5 h-[1.5px] bg-white/70 transition-all" id="hamburger2"></span>
                <span class="block w-5 h-[1.5px] bg-white/70 transition-all" id="hamburger3"></span>
            </button>
        </div>
    </div>

    <!-- Mobile Menu -->
    <div class="mobile-menu lg:hidden border-t border-suno-border" id="mobileMenu">
        <div class="max-w-7xl mx-auto px-6 py-4 space-y-1">
<?php if ($_useDbMenus): ?>
<?php foreach ($_navMenus as $_m): ?>
<?php if ($_m['menu_type'] === 'link'): ?>
            <a href="<?= htmlspecialchars($_m['url']) ?>"<?= $_m['open_new_tab'] ? ' target="_blank"' : '' ?> class="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 text-sm text-suno-muted hover:text-white transition-colors">
                <?= _navIcon($_m['icon_svg'], 'w-4 h-4 opacity-50') ?>
                <?= htmlspecialchars($_m['title']) ?>
            </a>
<?php elseif ($_m['menu_type'] === 'dropdown' && isset($_navChildren[$_m['id']])): ?>
            <div class="border-t border-suno-border my-2"></div>
            <div class="flex items-center gap-3 px-3 py-2.5 text-sm text-suno-muted">
                <?= _navIcon($_m['icon_svg'], 'w-4 h-4 opacity-50') ?>
                <?= htmlspecialchars($_m['title']) ?>
            </div>
<?php foreach ($_navChildren[$_m['id']] as $_child): ?>
<?php if ($_child['menu_type'] === 'separator'): ?>
            <div class="border-t border-suno-border my-1"></div>
<?php else: ?>
            <a href="<?= htmlspecialchars($_child['url']) ?>"<?= $_child['open_new_tab'] ? ' target="_blank"' : '' ?> class="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 text-sm text-suno-muted hover:text-white transition-colors pl-6"><?= htmlspecialchars($_child['title']) ?></a>
<?php endif; ?>
<?php endforeach; ?>
<?php endif; ?>
<?php endforeach; ?>
<?php else: ?>
            <a href="board_list.php?board=notice" class="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 text-sm text-suno-muted hover:text-white transition-colors">공지</a>
            <a href="prompt_list.php" class="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 text-sm text-suno-muted hover:text-white transition-colors">프롬프트</a>
            <a href="music_list.php" class="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 text-sm text-suno-muted hover:text-white transition-colors">음원</a>
<?php endif; ?>
            <div class="border-t border-suno-border my-2"></div>
<?php if (isset($currentUser) && $currentUser): ?>
            <div class="px-3 pt-1 pb-4 sm:hidden">
                <a href="profile.php" class="flex items-center gap-3 px-3 py-2.5 rounded-lg hover:bg-white/5 transition-colors">
                    <div class="w-8 h-8 rounded-full bg-gradient-to-r <?= htmlspecialchars($currentUser['avatar_color'] ?: 'from-suno-accent to-purple-600') ?> flex items-center justify-center text-xs font-bold shrink-0">
                        <?= mb_substr($currentUser['nickname'], 0, 1) ?>
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-sm font-semibold text-white truncate"><?= htmlspecialchars($currentUser['nickname']) ?></p>
                        <p class="text-[11px] text-suno-muted">마이페이지</p>
                    </div>
                </a>
                <div class="flex gap-2 mt-2">
                    <a href="message_list.php" class="flex-1 flex items-center justify-center gap-1.5 text-xs text-suno-muted border border-suno-border py-2.5 rounded-lg hover:text-white transition-colors">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M21.75 6.75v10.5a2.25 2.25 0 01-2.25 2.25h-15a2.25 2.25 0 01-2.25-2.25V6.75m19.5 0A2.25 2.25 0 0019.5 4.5h-15a2.25 2.25 0 00-2.25 2.25m19.5 0v.243a2.25 2.25 0 01-1.07 1.916l-7.5 4.615a2.25 2.25 0 01-2.36 0L3.32 8.91a2.25 2.25 0 01-1.07-1.916V6.75"/></svg>
                        쪽지<?php if ($unreadCount > 0): ?> <span class="bg-suno-accent text-white text-[9px] font-bold px-1.5 py-0.5 rounded-full"><?= $unreadCount ?></span><?php endif; ?>
                    </a>
                    <a href="logout.php" class="flex-1 text-xs text-suno-muted border border-suno-border py-2.5 rounded-lg hover:text-white transition-colors text-center">로그아웃</a>
                </div>
            </div>
<?php else: ?>
            <div class="flex gap-2 px-3 pt-1 pb-4 sm:hidden">
                <a href="login.php" class="flex-1 text-sm text-suno-muted border border-suno-border py-2.5 rounded-lg hover:text-white transition-colors text-center">로그인</a>
                <a href="register.php" class="flex-1 text-sm bg-suno-accent text-white font-medium py-2.5 rounded-lg text-center">회원가입</a>
            </div>
<?php endif; ?>
        </div>
    </div>
</nav>

<!-- Mobile Search Modal -->
<div id="searchModal" class="fixed inset-0 z-[100] hidden">
    <!-- Backdrop -->
    <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" onclick="closeSearchModal()"></div>
    <!-- Modal Content -->
    <div class="relative z-10 w-full px-4 pt-16">
        <div class="max-w-lg mx-auto bg-suno-card border border-suno-border rounded-2xl shadow-2xl shadow-black/50 overflow-hidden">
            <form action="search.php" method="GET">
                <div class="flex items-center gap-3 px-4 py-3 border-b border-suno-border">
                    <svg class="w-5 h-5 text-suno-accent flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/>
                    </svg>
                    <input type="text" name="q" placeholder="아티스트, 곡, 장르, 프롬프트 검색..."
                        class="flex-1 bg-transparent text-sm text-white placeholder-suno-muted/60 focus:outline-none"
                        id="mobileSearchInput" autocomplete="off">
                    <button type="button" onclick="closeSearchModal()" class="text-suno-muted hover:text-white text-xs font-medium px-2 py-1">취소</button>
                </div>
            </form>
            <!-- Quick Links -->
            <div class="px-4 py-3">
                <p class="text-[10px] text-suno-muted/50 font-medium uppercase tracking-wider mb-2">인기 검색어</p>
                <div class="flex flex-wrap gap-2">
                    <a href="#" class="text-xs px-3 py-1.5 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">K-Pop</a>
                    <a href="#" class="text-xs px-3 py-1.5 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">Lo-fi</a>
                    <a href="#" class="text-xs px-3 py-1.5 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">프롬프트 팁</a>
                    <a href="#" class="text-xs px-3 py-1.5 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">Hip-Hop</a>
                    <a href="#" class="text-xs px-3 py-1.5 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">수익화</a>
                    <a href="#" class="text-xs px-3 py-1.5 bg-suno-surface border border-suno-border rounded-full text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">Suno v4</a>
                </div>
            </div>
        </div>
    </div>
</div>

<script>
function toggleMobileMenu() {
    const menu = document.getElementById('mobileMenu');
    menu.classList.toggle('open');
}

function openSearchModal() {
    const modal = document.getElementById('searchModal');
    modal.classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    setTimeout(() => {
        document.getElementById('mobileSearchInput').focus();
    }, 100);
}

function closeSearchModal() {
    const modal = document.getElementById('searchModal');
    modal.classList.add('hidden');
    document.body.style.overflow = '';
}

// ESC로 모달 닫기
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') {
        closeSearchModal();
    }
});

// Ctrl+K / Cmd+K 로 검색 포커스 (데스크탑)
document.addEventListener('keydown', function(e) {
    if ((e.metaKey || e.ctrlKey) && e.key === 'k') {
        e.preventDefault();
        const desktopInput = document.getElementById('navSearchInput');
        const isMobile = window.innerWidth < 1024;
        if (isMobile) {
            openSearchModal();
        } else if (desktopInput) {
            desktopInput.focus();
        }
    }
});
</script>
