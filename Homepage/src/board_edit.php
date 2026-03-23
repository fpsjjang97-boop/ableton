<?php
require_once 'db.php';

if (!$currentUser) {
    header('Location: login.php');
    exit;
}

$boardVisual = [
    'notice' => ['write_title' => '공지 수정', 'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M10.34 15.84c-.688-.06-1.386-.09-2.09-.09H7.5a4.5 4.5 0 110-9h.75c.704 0 1.402-.03 2.09-.09m0 9.18c.253.962.584 1.892.985 2.783.247.55.06 1.21-.463 1.511l-.657.38a.75.75 0 01-1.021-.27l-.112-.194a4.504 4.504 0 01-.585-1.422M10.34 15.84a24.1 24.1 0 005.292-1.692"/>', 'color' => 'text-rose-400', 'bg' => 'bg-rose-500/10 border-rose-500/20'],
    'free' => ['write_title' => '글 수정', 'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M7.5 8.25h9m-9 3H12m-9.75 1.51c0 1.6 1.123 2.994 2.707 3.227 1.087.16 2.185.283 3.293.369V21l4.076-4.076a1.526 1.526 0 011.037-.443 48.282 48.282 0 005.68-.494c1.584-.233 2.707-1.626 2.707-3.228V6.741c0-1.602-1.123-2.995-2.707-3.228A48.394 48.394 0 0012 3c-2.392 0-4.744.175-7.043.513C3.373 3.746 2.25 5.14 2.25 6.741v6.018z"/>', 'color' => 'text-emerald-400', 'bg' => 'bg-emerald-500/10 border-emerald-500/20'],
    'qna' => ['write_title' => '질문 수정', 'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.879 7.519c1.171-1.025 3.071-1.025 4.242 0 1.172 1.025 1.172 2.687 0 3.712-.203.179-.43.326-.67.442-.745.361-1.45.999-1.45 1.827v.75M21 12a9 9 0 11-18 0 9 9 0 0118 0zm-9 5.25h.008v.008H12v-.008z"/>', 'color' => 'text-blue-400', 'bg' => 'bg-blue-500/10 border-blue-500/20'],
    'info' => ['write_title' => '정보 수정', 'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M12 18v-5.25m0 0a6.01 6.01 0 001.5-.189m-1.5.189a6.01 6.01 0 01-1.5-.189m3.75 7.478a12.06 12.06 0 01-4.5 0m3.75 2.383a14.406 14.406 0 01-3 0M14.25 18v-.192c0-.983.658-1.823 1.508-2.316a7.5 7.5 0 10-7.517 0c.85.493 1.509 1.333 1.509 2.316V18"/>', 'color' => 'text-teal-400', 'bg' => 'bg-teal-500/10 border-teal-500/20'],
    'collab' => ['write_title' => '협업 수정', 'icon' => '<path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M18 18.72a9.094 9.094 0 003.741-.479 3 3 0 00-4.682-2.72m.94 3.198l.001.031c0 .225-.012.447-.037.666A11.944 11.944 0 0112 21c-2.17 0-4.207-.576-5.963-1.584A6.062 6.062 0 016 18.719m12 0a5.971 5.971 0 00-.941-3.197m0 0A5.995 5.995 0 0012 12.75a5.995 5.995 0 00-5.058 2.772m0 0a3 3 0 00-4.681 2.72 8.986 8.986 0 003.74.477m.94-3.197a5.971 5.971 0 00-.94 3.197M15 6.75a3 3 0 11-6 0 3 3 0 016 0zm6 3a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0zm-13.5 0a2.25 2.25 0 11-4.5 0 2.25 2.25 0 014.5 0z"/>', 'color' => 'text-amber-400', 'bg' => 'bg-amber-500/10 border-amber-500/20'],
];

$currentBoard = isset($_GET['board']) ? $_GET['board'] : 'free';

$stmtBoard = $pdo->prepare('SELECT * FROM boards WHERE board_key = ? AND is_active = 1');
$stmtBoard->execute([$currentBoard]);
$boardDB = $stmtBoard->fetch();
if (!$boardDB) { header('Location: board_list.php?board=free'); exit; }

if (isset($boardVisual[$currentBoard])) {
    $boardVis = $boardVisual[$currentBoard];
    if (!empty($boardDB['icon_svg']) && strpos($boardDB['icon_svg'], 'fa-') !== false) {
        $boardVis['icon'] = $boardDB['icon_svg'];
        $boardVis['icon_type'] = 'fa';
    } else {
        $boardVis['icon_type'] = 'svg';
    }
} else {
    $iconSvg = $boardDB['icon_svg'] ?? '';
    $isFa = !empty($iconSvg) && strpos($iconSvg, 'fa-') !== false;
    $boardVis = [
        'write_title' => ($boardDB['write_title'] ?: '글 수정'),
        'icon' => $iconSvg,
        'icon_type' => $isFa ? 'fa' : 'svg',
        'color' => $boardDB['color_class'] ?: 'text-zinc-400',
        'bg' => $boardDB['bg_class'] ?: 'bg-zinc-500/10 border-zinc-500/20',
    ];
}

$postId = isset($_GET['id']) ? (int)$_GET['id'] : 0;
$stmtPost = $pdo->prepare('SELECT * FROM posts WHERE id = ? AND board_id = ?');
$stmtPost->execute([$postId, $boardDB['id']]);
$post = $stmtPost->fetch();

if (!$post || $post['user_id'] != $currentUser['id']) {
    header('Location: board_list.php?board=' . $currentBoard);
    exit;
}

$stmtCats = $pdo->prepare('SELECT * FROM board_categories WHERE board_id = ? AND is_active = 1 ORDER BY sort_order ASC');
$stmtCats->execute([$boardDB['id']]);
$categories = $stmtCats->fetchAll();

$board = array_merge($boardDB, $boardVis);
$pageTitle = $board['write_title'];
?>
<?php include 'head.php'; ?>

<script src="https://code.jquery.com/jquery-3.7.1.min.js"></script>
<link href="https://cdn.jsdelivr.net/npm/summernote@0.8.20/dist/summernote-lite.min.css" rel="stylesheet">
<script src="https://cdn.jsdelivr.net/npm/summernote@0.8.20/dist/summernote-lite.min.js"></script>
<script src="https://cdn.jsdelivr.net/npm/summernote@0.8.20/dist/lang/summernote-ko-KR.min.js"></script>

<?php include 'navbar.php'; ?>

<style>
    .form-input { transition: all 0.2s ease; }
    .form-input:focus { border-color: rgba(139,92,246,0.5); box-shadow: 0 0 0 3px rgba(139,92,246,0.1); }
    .cat-chip { transition: all 0.2s ease; cursor: pointer; }
    .cat-chip:hover { background: rgba(139,92,246,0.15); border-color: rgba(139,92,246,0.4); color: #a78bfa; }
    .cat-chip.selected { background: rgba(139,92,246,0.2); border-color: #8b5cf6; color: #a78bfa; }
    .submit-btn { transition: all 0.3s ease; background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
    .submit-btn:hover { background: linear-gradient(135deg, #a78bfa, #8b5cf6); box-shadow: 0 8px 30px rgba(139,92,246,0.3); transform: translateY(-1px); }
    .cancel-btn { transition: all 0.2s ease; }
    .cancel-btn:hover { background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.2); }
    .note-editor.note-frame { border: 1px solid #1e1e1e !important; border-radius: 12px !important; overflow: hidden; background: #141414 !important; }
    .note-toolbar { background: #18181b !important; border-bottom: 1px solid #1e1e1e !important; padding: 6px 8px !important; }
    .note-toolbar .note-btn { background: transparent !important; border: 1px solid transparent !important; color: #a1a1aa !important; border-radius: 6px !important; padding: 4px 7px !important; font-size: 13px !important; }
    .note-toolbar .note-btn:hover { background: rgba(139,92,246,0.12) !important; border-color: rgba(139,92,246,0.3) !important; color: #c4b5fd !important; }
    .note-toolbar .note-btn.active { background: rgba(139,92,246,0.2) !important; border-color: rgba(139,92,246,0.4) !important; color: #a78bfa !important; }
    .note-toolbar .note-btn-group { margin-right: 4px !important; }
    .note-editing-area { background: #141414 !important; }
    .note-editing-area .note-editable { background: #141414 !important; color: #e4e4e7 !important; padding: 16px 20px !important; font-size: 14px !important; line-height: 1.8 !important; min-height: 320px !important; }
    .note-editing-area .note-editable:focus { outline: none !important; }
    .note-statusbar { background: #18181b !important; border-top: 1px solid #1e1e1e !important; }
    .note-statusbar .note-resizebar .note-icon-bar { border-top-color: #333 !important; }
    .note-dropdown-menu { background: #1e1e1e !important; border: 1px solid #2a2a2a !important; border-radius: 8px !important; box-shadow: 0 12px 40px rgba(0,0,0,0.5) !important; padding: 4px !important; }
    .note-dropdown-menu .note-dropdown-item { color: #a1a1aa !important; border-radius: 4px !important; padding: 6px 12px !important; }
    .note-dropdown-menu .note-dropdown-item:hover { background: rgba(139,92,246,0.12) !important; color: #e4e4e7 !important; }
    .note-modal .note-modal-content { background: #1e1e1e !important; border: 1px solid #2a2a2a !important; border-radius: 12px !important; color: #e4e4e7 !important; }
    .note-modal .note-modal-header { border-bottom-color: #2a2a2a !important; }
    .note-modal .note-modal-title { color: #e4e4e7 !important; }
    .note-modal .note-modal-footer { border-top-color: #2a2a2a !important; }
    .note-modal .note-input { background: #141414 !important; border: 1px solid #333 !important; color: #e4e4e7 !important; border-radius: 6px !important; padding: 6px 10px !important; }
    .note-modal .note-btn-primary { background: #8b5cf6 !important; border-color: #8b5cf6 !important; border-radius: 6px !important; }
    .note-modal-backdrop { background: rgba(0,0,0,0.6) !important; }
    .note-placeholder { color: rgba(113,113,122,0.4) !important; padding: 16px 20px !important; }
    .note-popover .popover-content { background: #1e1e1e !important; border: 1px solid #2a2a2a !important; border-radius: 8px !important; padding: 4px !important; }
    .note-popover .popover-content .note-btn { background: transparent !important; color: #a1a1aa !important; border: none !important; }
    .note-popover .popover-content .note-btn:hover { background: rgba(139,92,246,0.12) !important; color: #e4e4e7 !important; }
</style>

<div class="pt-20">
    <section class="border-b border-suno-border">
        <div class="max-w-3xl mx-auto px-6 py-8">
            <div class="flex items-center gap-3">
                <a href="board_detail.php?board=<?php echo $currentBoard; ?>&id=<?php echo $postId; ?>" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                </a>
                <div class="flex items-center gap-2.5">
                    <div class="w-9 h-9 <?php echo $board['bg']; ?> border rounded-lg flex items-center justify-center">
                        <?php if (isset($board['icon_type']) && $board['icon_type'] === 'fa' && !empty($board['icon'])): ?>
                        <i class="<?php echo htmlspecialchars($board['icon']); ?> <?php echo $board['color']; ?>"></i>
                        <?php elseif (!empty($board['icon'])): ?>
                        <svg class="w-4.5 h-4.5 <?php echo $board['color']; ?>" fill="none" stroke="currentColor" viewBox="0 0 24 24"><?php echo $board['icon']; ?></svg>
                        <?php else: ?>
                        <span class="<?php echo $board['color']; ?> font-bold">#</span>
                        <?php endif; ?>
                    </div>
                    <div>
                        <h1 class="text-lg font-bold"><?php echo htmlspecialchars($board['write_title']); ?></h1>
                        <p class="text-xs text-suno-muted"><?php echo htmlspecialchars($board['board_name']); ?></p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <section class="py-8">
        <div class="max-w-3xl mx-auto px-6">
            <form action="board_edit_ok.php" method="POST">
                <input type="hidden" name="board" value="<?php echo $currentBoard; ?>">
                <input type="hidden" name="id" value="<?php echo $postId; ?>">
                <input type="hidden" name="board_id" value="<?php echo $boardDB['id']; ?>">
                <input type="hidden" name="category_id" id="category_id" value="<?php echo $post['category_id'] ?: ''; ?>">

                <?php if (!empty($categories)): ?>
                <div class="mb-6">
                    <label class="block text-sm font-bold mb-3">카테고리</label>
                    <div class="flex flex-wrap gap-2">
                        <?php foreach($categories as $cat): ?>
                        <button type="button" class="cat-chip text-xs border border-suno-border bg-suno-surface rounded-lg px-3.5 py-2 text-suno-muted <?php echo $post['category_id'] == $cat['id'] ? 'selected' : ''; ?>" data-cat-id="<?php echo $cat['id']; ?>" onclick="selectCategory(this)">
                            <?php echo htmlspecialchars($cat['category_name']); ?>
                        </button>
                        <?php endforeach; ?>
                    </div>
                </div>
                <?php endif; ?>

                <div class="mb-6">
                    <label class="block text-sm font-bold mb-2">제목</label>
                    <input type="text" name="title" required placeholder="제목을 입력하세요" value="<?php echo htmlspecialchars($post['title']); ?>"
                        class="form-input w-full bg-suno-card border border-suno-border rounded-xl px-4 py-3.5 text-sm text-white placeholder-suno-muted/40 focus:outline-none">
                </div>

                <div class="mb-6">
                    <label class="block text-sm font-bold mb-2">내용</label>
                    <textarea id="summernote" name="content"><?php echo htmlspecialchars($post['content']); ?></textarea>
                </div>

                <?php if($currentBoard === 'collab'): ?>
                <div class="mb-6">
                    <label class="block text-sm font-bold mb-2">모집 인원</label>
                    <div class="flex items-center gap-3">
                        <input type="number" name="recruit_count" min="1" max="20" value="<?php echo $post['recruit_count'] ?: 1; ?>"
                            class="form-input w-24 bg-suno-card border border-suno-border rounded-xl px-4 py-3 text-sm text-white text-center focus:outline-none">
                        <span class="text-sm text-suno-muted">명</span>
                    </div>
                </div>
                <div class="mb-6">
                    <label class="block text-sm font-bold mb-2">연락 방법</label>
                    <div class="flex gap-2">
                        <?php $editContactType = $post['contact_type'] ?: 'other'; ?>
                        <select name="contact_type" id="contactType" onchange="updateContactPlaceholder()" class="form-input bg-suno-card border border-suno-border rounded-xl px-3 py-3.5 text-sm text-white focus:outline-none w-36 flex-shrink-0 appearance-none bg-[url('data:image/svg+xml;charset=UTF-8,%3Csvg%20xmlns%3D%22http%3A%2F%2Fwww.w3.org%2F2000%2Fsvg%22%20width%3D%2210%22%20height%3D%226%22%20viewBox%3D%220%200%2010%206%22%3E%3Cpath%20d%3D%22M1%201l4%204%204-4%22%20stroke%3D%22%2371717a%22%20stroke-width%3D%221.5%22%20fill%3D%22none%22%20stroke-linecap%3D%22round%22%20stroke-linejoin%3D%22round%22%2F%3E%3C%2Fsvg%3E')] bg-no-repeat bg-[right_12px_center] pr-7 cursor-pointer">
                            <option value="openchat" <?php echo $editContactType === 'openchat' ? 'selected' : ''; ?>>오픈채팅</option>
                            <option value="instagram" <?php echo $editContactType === 'instagram' ? 'selected' : ''; ?>>인스타그램</option>
                            <option value="phone" <?php echo $editContactType === 'phone' ? 'selected' : ''; ?>>전화번호</option>
                            <option value="email" <?php echo $editContactType === 'email' ? 'selected' : ''; ?>>이메일</option>
                            <option value="other" <?php echo $editContactType === 'other' ? 'selected' : ''; ?>>기타</option>
                        </select>
                        <input type="text" name="contact_info" id="contactInfo" value="<?php echo htmlspecialchars($post['contact_info'] ?: ''); ?>" placeholder="연락 방법을 입력하세요"
                            class="form-input flex-1 bg-suno-card border border-suno-border rounded-xl px-4 py-3.5 text-sm text-white placeholder-suno-muted/40 focus:outline-none">
                    </div>
                    <p id="contactHint" class="text-xs text-suno-muted/50 mt-1.5"></p>
                </div>
                <?php endif; ?>

                <div class="flex items-center justify-end gap-3 pt-4 border-t border-suno-border">
                    <a href="board_detail.php?board=<?php echo $currentBoard; ?>&id=<?php echo $postId; ?>" class="cancel-btn px-6 py-3 border border-suno-border rounded-xl text-sm text-suno-muted font-medium">취소</a>
                    <button type="submit" class="submit-btn px-8 py-3 rounded-xl text-sm text-white font-semibold">수정 완료</button>
                </div>
            </form>
        </div>
    </section>
</div>

<script>
$(document).ready(function() {
    $('#summernote').summernote({
        lang: 'ko-KR',
        placeholder: '내용을 작성해주세요...',
        height: 350,
        focus: false,
        toolbar: [
            ['style', ['style']],
            ['font', ['bold', 'italic', 'underline', 'strikethrough', 'clear']],
            ['fontsize', ['fontsize']],
            ['color', ['color']],
            ['para', ['ul', 'ol', 'paragraph']],
            ['table', ['table']],
            ['insert', ['link', 'picture', 'video', 'hr']],
            ['view', ['codeview', 'help']],
        ],
        fontSizes: ['8','9','10','11','12','13','14','15','16','18','20','24','28','36'],
        callbacks: {
            onImageUpload: function(files) {
                for (let i = 0; i < files.length; i++) {
                    if (files[i].size > 10 * 1024 * 1024) { alert('이미지 크기는 10MB 이하만 가능합니다.'); continue; }
                    var fd = new FormData();
                    fd.append('image', files[i]);
                    $.ajax({
                        url: 'board_upload_image.php', type: 'POST', data: fd,
                        processData: false, contentType: false, dataType: 'json',
                        success: function(res) {
                            if (res.success && res.url) { $('#summernote').summernote('insertImage', res.url); }
                            else { alert(res.message || '업로드에 실패했습니다.'); }
                        },
                        error: function() { alert('업로드에 실패했습니다.'); }
                    });
                }
            }
        }
    });
});

function selectCategory(el) {
    document.querySelectorAll('.cat-chip:not(.point-chip)').forEach(c => c.classList.remove('selected'));
    el.classList.add('selected');
    document.getElementById('category_id').value = el.getAttribute('data-cat-id');
}

var contactPlaceholders = {
    'openchat': { ph: '오픈채팅 링크를 입력하세요', hint: 'https://open.kakao.com/... 형태의 링크' },
    'instagram': { ph: '@아이디를 입력하세요', hint: '@ 없이 아이디만 입력해도 자동으로 추가됩니다' },
    'phone': { ph: '전화번호를 입력하세요', hint: '숫자만 입력 (예: 01012345678)' },
    'email': { ph: '이메일 주소를 입력하세요', hint: '예: example@email.com' },
    'other': { ph: '연락 방법을 입력하세요', hint: '' }
};
function updateContactPlaceholder() {
    var sel = document.getElementById('contactType');
    var input = document.getElementById('contactInfo');
    var hint = document.getElementById('contactHint');
    if (!sel || !input) return;
    var cfg = contactPlaceholders[sel.value] || contactPlaceholders['other'];
    input.placeholder = cfg.ph;
    if (hint) hint.textContent = cfg.hint;
    if (sel.value === 'instagram' && !input.value.startsWith('@')) {
        input.value = '@' + input.value.replace(/^@/, '');
    }
}
function validateContact() {
    var sel = document.getElementById('contactType');
    var input = document.getElementById('contactInfo');
    if (!sel || !input) return true;
    var type = sel.value;
    var val = input.value.trim();
    if (!val) return true;
    if (type === 'instagram') {
        val = val.replace(/^@/, '');
        if (!/^[a-zA-Z0-9._]{1,30}$/.test(val)) { alert('올바른 인스타그램 아이디를 입력해주세요.'); input.focus(); return false; }
        input.value = '@' + val;
    } else if (type === 'phone') {
        val = val.replace(/[^0-9]/g, '');
        if (!/^01[0-9]{8,9}$/.test(val)) { alert('올바른 전화번호를 입력해주세요. (예: 01012345678)'); input.focus(); return false; }
        input.value = val;
    } else if (type === 'email') {
        if (!/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(val)) { alert('올바른 이메일 주소를 입력해주세요.'); input.focus(); return false; }
    }
    return true;
}
if (document.getElementById('contactType')) updateContactPlaceholder();

document.querySelector('form').addEventListener('submit', function(e) {
    $('#summernote').summernote('triggerEvent', 'change');
    if ($('#summernote').summernote('isEmpty')) {
        e.preventDefault();
        alert('내용을 입력해주세요.');
        return false;
    }
    if (!validateContact()) { e.preventDefault(); return false; }
});
</script>

<?php include 'footer.php'; ?>
