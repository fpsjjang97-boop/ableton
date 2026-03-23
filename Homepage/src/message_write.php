<?php
require_once 'db.php';

if (!$currentUser) {
    header('Location: login.php');
    exit;
}

$toUser = '';
if (isset($_GET['to']) && $_GET['to'] !== '') {
    $stmt = $pdo->prepare('SELECT nickname FROM users WHERE nickname = ?');
    $stmt->execute([$_GET['to']]);
    $foundUser = $stmt->fetch();
    if ($foundUser) {
        $toUser = $foundUser['nickname'];
    }
}

$pageTitle = '쪽지 보내기';

// 에러 메시지
$error = $_GET['error'] ?? '';
$errorMessages = [
    'empty' => '받는 사람과 메시지를 모두 입력해주세요.',
    'user_not_found' => '존재하지 않는 사용자입니다.',
    'self_message' => '자기 자신에게는 쪽지를 보낼 수 없습니다.',
];
$errorMsg = $errorMessages[$error] ?? '';
?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<style>
    .form-input { transition: all 0.2s ease; }
    .form-input:focus {
        border-color: rgba(139,92,246,0.5);
        box-shadow: 0 0 0 3px rgba(139,92,246,0.1);
    }
    .send-btn {
        transition: all 0.3s ease;
        background: linear-gradient(135deg, #8b5cf6, #7c3aed);
    }
    .send-btn:hover {
        background: linear-gradient(135deg, #a78bfa, #8b5cf6);
        box-shadow: 0 8px 30px rgba(139,92,246,0.3);
        transform: translateY(-1px);
    }
</style>

<div class="pt-20">
    <!-- Header -->
    <section class="border-b border-suno-border">
        <div class="max-w-3xl mx-auto px-6 py-8">
            <div class="flex items-center gap-3">
                <a href="message_list.php" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                </a>
                <div class="flex items-center gap-2.5">
                    <div class="w-9 h-9 bg-suno-accent/10 border border-suno-accent/20 rounded-lg flex items-center justify-center">
                        <svg class="w-4.5 h-4.5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z"/>
                        </svg>
                    </div>
                    <div>
                        <h1 class="text-lg font-bold">새 쪽지</h1>
                        <p class="text-xs text-suno-muted">쪽지 작성</p>
                    </div>
                </div>
            </div>
        </div>
    </section>

    <!-- Form -->
    <section class="py-8">
        <div class="max-w-3xl mx-auto px-6">
            <?php if($errorMsg): ?>
            <div class="mb-5 p-4 bg-red-500/10 border border-red-500/20 rounded-xl text-sm text-red-400">
                <?php echo $errorMsg; ?>
            </div>
            <?php endif; ?>

            <form action="message_write_ok.php" method="POST">

                <!-- 받는 사람 -->
                <div class="mb-5">
                    <label class="block text-sm font-bold mb-2">받는 사람</label>
                    <div class="relative">
                        <svg class="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M15.75 6a3.75 3.75 0 11-7.5 0 3.75 3.75 0 017.5 0zM4.501 20.118a7.5 7.5 0 0114.998 0A17.933 17.933 0 0112 21.75c-2.676 0-5.216-.584-7.499-1.632z"/>
                        </svg>
                        <input type="text" name="to" required placeholder="유저 이름을 입력하세요" value="<?php echo htmlspecialchars($toUser); ?>"
                            class="form-input w-full bg-suno-card border border-suno-border rounded-xl pl-11 pr-4 py-3.5 text-sm text-white placeholder-suno-muted/40 focus:outline-none"
                            id="toInput" autocomplete="off">
                    </div>
                </div>

                <input type="hidden" name="title" value="DM">

                <!-- 메시지 내용 -->
                <div class="mb-6">
                    <div class="flex items-center justify-between mb-2">
                        <label class="block text-sm font-bold">메시지</label>
                        <span class="text-xs text-suno-muted/50" id="charCount">0 / 2,000</span>
                    </div>
                    <textarea name="content" required rows="6" placeholder="메시지를 입력하세요..." maxlength="2000"
                        oninput="updateCount(this)"
                        class="form-input w-full bg-suno-card border border-suno-border rounded-xl px-4 py-3.5 text-sm text-white placeholder-suno-muted/40 focus:outline-none resize-none leading-relaxed"></textarea>
                </div>

                <!-- 버튼 -->
                <div class="flex items-center justify-end gap-3 pt-4 border-t border-suno-border">
                    <a href="message_list.php" class="px-6 py-3 border border-suno-border rounded-xl text-sm text-suno-muted font-medium hover:bg-white/5 hover:border-white/20 transition-all">
                        취소
                    </a>
                    <button type="submit" class="send-btn inline-flex items-center gap-2 px-8 py-3 rounded-xl text-sm text-white font-semibold">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"/>
                        </svg>
                        보내기
                    </button>
                </div>
            </form>
        </div>
    </section>
</div>

<script>
function updateCount(el) {
    const count = el.value.length;
    const span = document.getElementById('charCount');
    span.textContent = count.toLocaleString() + ' / 2,000';
    span.style.color = count > 1800 ? '#f87171' : '';
}
</script>

<?php include 'footer.php'; ?>
