<?php
require_once 'db.php';
$pageTitle = '프로필 편집';

if (!$currentUser) {
    header('Location: login.php');
    exit;
}

$stmt = $pdo->prepare('SELECT * FROM users WHERE id = ?');
$stmt->execute([$currentUser['id']]);
$user = $stmt->fetch();

// 내가 보유한 뱃지 목록
$stmt = $pdo->prepare('
    SELECT badges.* FROM user_badges
    JOIN badges ON user_badges.badge_id = badges.id
    WHERE user_badges.user_id = ?
    ORDER BY user_badges.granted_at DESC
');
$stmt->execute([$currentUser['id']]);
$myBadges = $stmt->fetchAll();

$success = $_GET['success'] ?? '';
$error = $_GET['error'] ?? '';
?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<style>
    .upload-zone {
        border: 2px dashed #333;
        transition: all 0.2s;
        cursor: pointer;
    }
    .upload-zone:hover, .upload-zone.dragover {
        border-color: #8b5cf6;
        background: rgba(139,92,246,0.05);
    }
    .badge-option { transition: all 0.15s; cursor: pointer; }
    .badge-option:hover { border-color: rgba(139,92,246,0.4); }
    .badge-option.selected { border-color: #8b5cf6; background: rgba(139,92,246,0.1); }
</style>

<main class="pt-20 min-h-screen px-6 py-12">
    <div class="max-w-2xl mx-auto">

        <div class="mb-8">
            <h1 class="text-2xl font-extrabold tracking-tight">프로필 편집</h1>
            <p class="text-sm text-suno-muted mt-1">내 정보를 수정합니다.</p>
        </div>

        <!-- 성공/에러 메시지 -->
        <?php if ($success === 'profile'): ?>
        <div class="mb-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-sm text-emerald-400">프로필이 수정되었습니다.</div>
        <?php elseif ($success === 'password'): ?>
        <div class="mb-6 p-4 bg-emerald-500/10 border border-emerald-500/30 rounded-xl text-sm text-emerald-400">비밀번호가 변경되었습니다.</div>
        <?php endif; ?>

        <?php
        $errorMessages = [
            'nickname_exists' => '이미 사용 중인 닉네임입니다.',
            'email_exists' => '이미 사용 중인 이메일입니다.',
            'password_wrong' => '현재 비밀번호가 일치하지 않습니다.',
            'password_mismatch' => '새 비밀번호가 일치하지 않습니다.',
            'password_short' => '새 비밀번호는 8자 이상이어야 합니다.',
            'empty' => '닉네임과 이메일은 필수 항목입니다.',
            'upload_fail' => '이미지 업로드에 실패했습니다.',
            'file_too_large' => '파일 크기가 너무 큽니다. (최대 5MB)',
            'invalid_type' => '지원하지 않는 파일 형식입니다. (JPG, PNG, GIF, WEBP만 가능)',
        ];
        if (!empty($error) && isset($errorMessages[$error])):
        ?>
        <div class="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-sm text-red-400"><?php echo $errorMessages[$error]; ?></div>
        <?php endif; ?>

        <!-- 프로필 이미지 수정 -->
        <div class="bg-suno-card border border-suno-border rounded-2xl p-6 mb-6">
            <h2 class="text-lg font-bold mb-6 flex items-center gap-2">
                <svg class="w-5 h-5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"/></svg>
                프로필 이미지
            </h2>

            <form action="profile_edit_ok.php" method="POST" enctype="multipart/form-data" class="space-y-6">
                <input type="hidden" name="action" value="images">

                <!-- 프로필 사진 -->
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-2">프로필 사진</label>
                    <div class="flex items-center gap-5">
                        <div class="relative shrink-0">
                            <?php if(!empty($user['avatar_url'])): ?>
                            <div class="w-20 h-20 rounded-full overflow-hidden ring-2 ring-suno-border" id="avatarPreview">
                                <img src="<?php echo htmlspecialchars($user['avatar_url']); ?>" class="w-full h-full object-cover" id="avatarImg">
                            </div>
                            <?php else: ?>
                            <div class="w-20 h-20 rounded-full bg-gradient-to-br <?php echo htmlspecialchars($user['avatar_color'] ?: 'from-suno-accent via-purple-600 to-indigo-800'); ?> flex items-center justify-center text-2xl font-black text-white/90 ring-2 ring-suno-border" id="avatarPreview">
                                <span id="avatarLetter"><?php echo mb_substr($user['nickname'], 0, 1); ?></span>
                            </div>
                            <?php endif; ?>
                        </div>
                        <div class="flex-1">
                            <label class="upload-zone block rounded-xl p-4 text-center" id="avatarDropZone">
                                <input type="file" name="avatar" accept="image/jpeg,image/png,image/gif,image/webp" class="hidden" id="avatarInput" onchange="previewAvatar(this)">
                                <svg class="w-6 h-6 mx-auto text-suno-muted/40 mb-1" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M3 16.5v2.25A2.25 2.25 0 005.25 21h13.5A2.25 2.25 0 0021 18.75V16.5m-13.5-9L12 3m0 0l4.5 4.5M12 3v13.5"/></svg>
                                <p class="text-xs text-suno-muted">클릭하여 이미지 선택</p>
                                <p class="text-[10px] text-suno-muted/40 mt-0.5">JPG, PNG, GIF, WEBP / 최대 2MB</p>
                            </label>
                        </div>
                    </div>
                </div>

                <!-- 배경 이미지 -->
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-2">배경 이미지</label>
                    <?php if(!empty($user['background_url'])): ?>
                    <div class="mb-3 rounded-xl overflow-hidden h-[120px] relative" id="bgPreviewWrap">
                        <img src="<?php echo htmlspecialchars($user['background_url']); ?>" class="w-full h-full object-cover" id="bgImg">
                        <div class="absolute inset-0 bg-gradient-to-t from-black/40 to-transparent"></div>
                    </div>
                    <?php else: ?>
                    <div class="mb-3 rounded-xl overflow-hidden h-[120px] bg-gradient-to-r from-suno-accent/20 via-purple-900/30 to-suno-dark hidden" id="bgPreviewWrap">
                        <img src="" class="w-full h-full object-cover" id="bgImg">
                    </div>
                    <?php endif; ?>
                    <label class="upload-zone block rounded-xl p-6 text-center" id="bgDropZone">
                        <input type="file" name="background" accept="image/jpeg,image/png,image/gif,image/webp" class="hidden" id="bgInput" onchange="previewBg(this)">
                        <svg class="w-8 h-8 mx-auto text-suno-muted/40 mb-2" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"/></svg>
                        <p class="text-xs text-suno-muted">배경 이미지를 선택하세요</p>
                        <p class="text-[10px] text-suno-muted/40 mt-0.5">권장 크기: 1400 x 400px</p>
                    </label>
                </div>

                <div class="pt-2">
                    <button type="submit" class="bg-suno-accent hover:bg-suno-accent2 text-white font-bold py-3 px-8 rounded-xl transition-all text-sm">
                        이미지 저장
                    </button>
                </div>
            </form>
        </div>

        <!-- 프로필 정보 수정 -->
        <div class="bg-suno-card border border-suno-border rounded-2xl p-6 mb-6">
            <h2 class="text-lg font-bold mb-6 flex items-center gap-2">
                <svg class="w-5 h-5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"/></svg>
                기본 정보
            </h2>

            <form action="profile_edit_ok.php" method="POST" class="space-y-5">
                <input type="hidden" name="action" value="profile">

                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">닉네임 <span class="text-red-400">*</span></label>
                    <input type="text" name="nickname" value="<?= htmlspecialchars($user['nickname']) ?>" required
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>

                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">이메일 <span class="text-red-400">*</span></label>
                    <input type="email" name="email" value="<?= htmlspecialchars($user['email']) ?>" required
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>

                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">소개</label>
                    <textarea name="bio" rows="3" placeholder="자신을 소개해주세요"
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors resize-none"><?= htmlspecialchars($user['bio'] ?? '') ?></textarea>
                </div>

                <div class="border-t border-suno-border pt-5 mt-2">
                    <p class="text-xs text-suno-muted mb-2 font-medium uppercase tracking-wider">소셜 링크</p>
                    <p class="text-xs text-suno-muted/50 mb-4">여러 개의 소셜 링크를 등록할 수 있습니다.</p>
                    <input type="hidden" name="social_links" id="socialLinksJson" value="">
                    <div id="socialLinksContainer" class="space-y-3">
                        <?php
                        $existingSocials = [];
                        if (!empty($user['social_links'])) {
                            $decoded = json_decode($user['social_links'], true);
                            if (is_array($decoded)) $existingSocials = $decoded;
                        }
                        if (empty($existingSocials)) {
                            if (!empty($user['instagram_url'])) $existingSocials[] = ['type' => 'instagram', 'value' => $user['instagram_url']];
                            if (!empty($user['youtube_url'])) $existingSocials[] = ['type' => 'youtube', 'value' => $user['youtube_url']];
                            if (!empty($user['suno_profile_url'])) $existingSocials[] = ['type' => 'suno', 'value' => $user['suno_profile_url']];
                        }
                        ?>
                    </div>
                    <button type="button" onclick="addSocialRow()" class="mt-3 inline-flex items-center gap-1.5 text-xs text-suno-accent hover:text-suno-accent2 font-medium transition-colors">
                        <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/></svg>
                        소셜 링크 추가
                    </button>
                </div>

                <div class="flex items-center gap-3 pt-2">
                    <button type="submit" class="bg-suno-accent hover:bg-suno-accent2 text-white font-bold py-3 px-8 rounded-xl transition-all text-sm">저장</button>
                    <a href="profile.php" class="text-sm text-suno-muted hover:text-white transition-colors px-4 py-3">취소</a>
                </div>
            </form>
        </div>

        <!-- 뱃지 선택 -->
        <?php if(!empty($myBadges)): ?>
        <div class="bg-suno-card border border-suno-border rounded-2xl p-6 mb-6">
            <h2 class="text-lg font-bold mb-6 flex items-center gap-2">
                <svg class="w-5 h-5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 12.75L11.25 15 15 9.75M21 12c0 1.268-.63 2.39-1.593 3.068a3.745 3.745 0 01-1.043 3.296 3.745 3.745 0 01-3.296 1.043A3.745 3.745 0 0112 21c-1.268 0-2.39-.63-3.068-1.593a3.746 3.746 0 01-3.296-1.043 3.745 3.745 0 01-1.043-3.296A3.745 3.745 0 013 12c0-1.268.63-2.39 1.593-3.068a3.745 3.745 0 011.043-3.296 3.746 3.746 0 013.296-1.043A3.746 3.746 0 0112 3c1.268 0 2.39.63 3.068 1.593a3.746 3.746 0 013.296 1.043 3.745 3.745 0 011.043 3.296A3.745 3.745 0 0121 12z"/></svg>
                뱃지 선택
            </h2>
            <p class="text-xs text-suno-muted mb-4">프로필에 표시할 뱃지를 선택하세요.</p>

            <form action="profile_edit_ok.php" method="POST">
                <input type="hidden" name="action" value="badge">

                <div class="grid grid-cols-2 sm:grid-cols-3 gap-3 mb-5">
                    <!-- 뱃지 없음 옵션 -->
                    <label class="badge-option block border border-suno-border rounded-xl p-4 text-center <?php echo empty($user['selected_badge_id']) ? 'selected' : ''; ?>">
                        <input type="radio" name="selected_badge_id" value="0" class="hidden" <?php echo empty($user['selected_badge_id']) ? 'checked' : ''; ?>>
                        <div class="w-8 h-8 mx-auto mb-2 rounded-full bg-suno-surface border border-suno-border flex items-center justify-center">
                            <svg class="w-4 h-4 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                        </div>
                        <p class="text-xs font-medium text-suno-muted">없음</p>
                    </label>

                    <?php foreach($myBadges as $badge): ?>
                    <label class="badge-option block border border-suno-border rounded-xl p-4 text-center <?php echo ((int)$user['selected_badge_id'] === (int)$badge['id']) ? 'selected' : ''; ?>">
                        <input type="radio" name="selected_badge_id" value="<?php echo $badge['id']; ?>" class="hidden" <?php echo ((int)$user['selected_badge_id'] === (int)$badge['id']) ? 'checked' : ''; ?>>
                        <div class="w-8 h-8 mx-auto mb-2 rounded-full bg-gradient-to-r <?php echo htmlspecialchars($badge['color']); ?> flex items-center justify-center">
                            <svg class="w-4 h-4 text-white" fill="currentColor" viewBox="0 0 20 20"><path fill-rule="evenodd" d="M10.868 2.884c-.321-.772-1.415-.772-1.736 0l-1.83 4.401-4.753.381c-.833.067-1.171 1.107-.536 1.651l3.62 3.102-1.106 4.637c-.194.813.691 1.456 1.405 1.02L10 15.591l4.069 2.485c.713.436 1.598-.207 1.404-1.02l-1.106-4.637 3.62-3.102c.635-.544.297-1.584-.536-1.65l-4.752-.382-1.831-4.401z" clip-rule="evenodd"/></svg>
                        </div>
                        <p class="text-xs font-medium"><?php echo htmlspecialchars($badge['name']); ?></p>
                        <?php if(!empty($badge['description'])): ?>
                        <p class="text-[10px] text-suno-muted/50 mt-0.5"><?php echo htmlspecialchars($badge['description']); ?></p>
                        <?php endif; ?>
                    </label>
                    <?php endforeach; ?>
                </div>

                <button type="submit" class="bg-suno-accent hover:bg-suno-accent2 text-white font-bold py-3 px-8 rounded-xl transition-all text-sm">
                    뱃지 저장
                </button>
            </form>
        </div>
        <?php endif; ?>

        <!-- 비밀번호 변경 -->
        <div class="bg-suno-card border border-suno-border rounded-2xl p-6">
            <h2 class="text-lg font-bold mb-6 flex items-center gap-2">
                <svg class="w-5 h-5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16.5 10.5V6.75a4.5 4.5 0 10-9 0v3.75m-.75 11.25h10.5a2.25 2.25 0 002.25-2.25v-6.75a2.25 2.25 0 00-2.25-2.25H6.75a2.25 2.25 0 00-2.25 2.25v6.75a2.25 2.25 0 002.25 2.25z"/></svg>
                비밀번호 변경
            </h2>

            <form action="profile_edit_ok.php" method="POST" class="space-y-5">
                <input type="hidden" name="action" value="password">
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">현재 비밀번호</label>
                    <input type="password" name="current_password" required placeholder="현재 비밀번호를 입력하세요"
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">새 비밀번호</label>
                    <input type="password" name="new_password" required placeholder="8자 이상"
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">새 비밀번호 확인</label>
                    <input type="password" name="new_password_confirm" required placeholder="새 비밀번호를 다시 입력하세요"
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>
                <div class="pt-2">
                    <button type="submit" class="bg-red-500/80 hover:bg-red-500 text-white font-bold py-3 px-8 rounded-xl transition-all text-sm">
                        비밀번호 변경
                    </button>
                </div>
            </form>
        </div>

    </div>
</main>

<script>
// 프로필 사진 미리보기
function previewAvatar(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const preview = document.getElementById('avatarPreview');
            preview.innerHTML = '<img src="' + e.target.result + '" class="w-full h-full object-cover">';
            preview.className = 'w-20 h-20 rounded-full overflow-hidden ring-2 ring-suno-accent';
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// 배경 이미지 미리보기
function previewBg(input) {
    if (input.files && input.files[0]) {
        const reader = new FileReader();
        reader.onload = function(e) {
            const wrap = document.getElementById('bgPreviewWrap');
            const img = document.getElementById('bgImg');
            img.src = e.target.result;
            wrap.classList.remove('hidden');
        };
        reader.readAsDataURL(input.files[0]);
    }
}

// 뱃지 선택 UI
document.querySelectorAll('.badge-option').forEach(el => {
    el.addEventListener('click', function() {
        document.querySelectorAll('.badge-option').forEach(b => b.classList.remove('selected'));
        this.classList.add('selected');
    });
});

// 드래그앤드롭
['avatarDropZone', 'bgDropZone'].forEach(zoneId => {
    const zone = document.getElementById(zoneId);
    if (!zone) return;
    const input = zone.querySelector('input[type=file]');
    zone.addEventListener('dragover', e => { e.preventDefault(); zone.classList.add('dragover'); });
    zone.addEventListener('dragleave', () => zone.classList.remove('dragover'));
    zone.addEventListener('drop', e => {
        e.preventDefault();
        zone.classList.remove('dragover');
        if (e.dataTransfer.files.length) {
            input.files = e.dataTransfer.files;
            input.dispatchEvent(new Event('change'));
        }
    });
});

// ── 소셜 링크 다중 등록 ──
var socialTypes = {
    instagram: { label: 'Instagram', ph: '@아이디 입력', hint: '@ 자동 추가' },
    youtube: { label: 'YouTube', ph: 'https://youtube.com/@...', hint: '' },
    spotify: { label: 'Spotify', ph: 'https://open.spotify.com/...', hint: '' },
    soundcloud: { label: 'SoundCloud', ph: 'https://soundcloud.com/...', hint: '' },
    twitter: { label: 'X (Twitter)', ph: '@아이디 입력', hint: '@ 자동 추가' },
    suno: { label: 'Suno', ph: 'https://suno.com/@...', hint: '' },
    other: { label: '기타', ph: 'URL 입력', hint: '' }
};

var socialData = <?php echo json_encode($existingSocials); ?>;
if (!socialData || !socialData.length) socialData = [];

function renderSocialRows() {
    var container = document.getElementById('socialLinksContainer');
    container.innerHTML = '';
    socialData.forEach(function(item, idx) {
        container.appendChild(createSocialRow(idx, item.type, item.value));
    });
}

function createSocialRow(idx, type, value) {
    var row = document.createElement('div');
    row.className = 'flex items-center gap-2';
    row.dataset.idx = idx;
    var selectHtml = '<select onchange="updateSocialType(' + idx + ', this.value)" class="bg-suno-surface border border-suno-border rounded-l-xl px-3 py-3 text-sm text-white focus:outline-none focus:border-suno-accent/50 w-32 flex-shrink-0 appearance-none cursor-pointer">';
    Object.keys(socialTypes).forEach(function(k) {
        selectHtml += '<option value="' + k + '"' + (k === type ? ' selected' : '') + '>' + socialTypes[k].label + '</option>';
    });
    selectHtml += '</select>';
    var cfg = socialTypes[type] || socialTypes.other;
    var displayVal = value || '';
    if ((type === 'instagram' || type === 'twitter') && displayVal && !displayVal.startsWith('@')) displayVal = '@' + displayVal;
    row.innerHTML = selectHtml
        + '<input type="text" value="' + escAttr(displayVal) + '" placeholder="' + cfg.ph + '" onchange="updateSocialValue(' + idx + ', this.value)" onblur="updateSocialValue(' + idx + ', this.value)" class="flex-1 bg-suno-surface border border-suno-border border-l-0 rounded-r-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">'
        + '<button type="button" onclick="removeSocialRow(' + idx + ')" class="text-suno-muted hover:text-red-400 transition-colors flex-shrink-0 p-1"><svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg></button>';
    return row;
}

function escAttr(s) { return (s||'').replace(/"/g, '&quot;').replace(/</g, '&lt;'); }

function addSocialRow() {
    socialData.push({ type: 'instagram', value: '' });
    renderSocialRows();
}

function removeSocialRow(idx) {
    socialData.splice(idx, 1);
    renderSocialRows();
    syncSocialJson();
}

function updateSocialType(idx, type) {
    socialData[idx].type = type;
    if ((type === 'instagram' || type === 'twitter') && socialData[idx].value && !socialData[idx].value.startsWith('@')) {
        socialData[idx].value = '@' + socialData[idx].value.replace(/^@/, '');
    }
    renderSocialRows();
    syncSocialJson();
}

function updateSocialValue(idx, val) {
    var type = socialData[idx].type;
    if (type === 'instagram' || type === 'twitter') {
        val = val.replace(/^@/, '');
        if (val) val = '@' + val;
    }
    socialData[idx].value = val;
    syncSocialJson();
}

function syncSocialJson() {
    var clean = socialData.filter(function(s) { return s.value && s.value.trim(); }).map(function(s) {
        var v = s.value.trim();
        if (s.type === 'instagram' || s.type === 'twitter') v = v.replace(/^@/, '');
        return { type: s.type, value: v };
    });
    document.getElementById('socialLinksJson').value = JSON.stringify(clean);
}

// 폼 제출 시 JSON 동기화
document.querySelectorAll('form').forEach(function(form) {
    form.addEventListener('submit', function() { syncSocialJson(); });
});

// 초기 렌더링
renderSocialRows();
syncSocialJson();
</script>

<?php include 'footer.php'; ?>
