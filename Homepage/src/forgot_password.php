<?php
require_once 'db.php';
$pageTitle = '비밀번호 찾기';

$errorMsg = '';
$successMsg = '';

if ($_SERVER['REQUEST_METHOD'] === 'POST') {
    $email = trim($_POST['email'] ?? '');
    $nickname = trim($_POST['nickname'] ?? '');

    if (empty($email) || empty($nickname)) {
        $errorMsg = '이메일과 닉네임을 모두 입력해주세요.';
    } else {
        $stmt = $pdo->prepare('SELECT id, email FROM users WHERE email = ? AND nickname = ?');
        $stmt->execute([$email, $nickname]);
        $user = $stmt->fetch();

        if ($user) {
            $pdo->prepare('UPDATE password_reset_tokens SET used = 1 WHERE user_id = ? AND used = 0')->execute([$user['id']]);

            $token = bin2hex(random_bytes(32));
            $expiresAt = date('Y-m-d H:i:s', strtotime('+1 hour'));

            $stmt = $pdo->prepare('INSERT INTO password_reset_tokens (user_id, token, expires_at) VALUES (?, ?, ?)');
            $stmt->execute([$user['id'], $token, $expiresAt]);

            $protocol = (!empty($_SERVER['HTTPS']) && $_SERVER['HTTPS'] !== 'off') ? 'https' : 'http';
            $host = $_SERVER['HTTP_HOST'] ?? 'localhost';
            $resetUrl = $protocol . '://' . $host . '/reset_password.php?token=' . $token;

            $subject = '=?UTF-8?B?' . base64_encode('[SUNO Community] 비밀번호 재설정') . '?=';
            $body = "안녕하세요,\r\n\r\n"
                  . "비밀번호 재설정을 요청하셨습니다.\r\n"
                  . "아래 링크를 클릭하여 새 비밀번호를 설정해주세요:\r\n\r\n"
                  . $resetUrl . "\r\n\r\n"
                  . "이 링크는 1시간 동안만 유효합니다.\r\n"
                  . "본인이 요청한 것이 아니라면 이 메일을 무시해주세요.\r\n\r\n"
                  . "- SUNO Community";

            $headers = "From: noreply@sunocommunity.kr\r\n"
                     . "Reply-To: noreply@sunocommunity.kr\r\n"
                     . "Content-Type: text/plain; charset=UTF-8\r\n"
                     . "MIME-Version: 1.0\r\n";

            $mailSent = @mail($user['email'], $subject, $body, $headers);

            if ($mailSent) {
                $successMsg = '비밀번호 재설정 링크를 이메일로 발송했습니다.<br/>메일함을 확인해주세요.';
            } else {
                $errorMsg = '메일 발송에 실패했습니다. 잠시 후 다시 시도해주세요.';
            }
        } else {
            $successMsg = '입력하신 정보와 일치하는 계정이 있다면, 비밀번호 재설정 링크를 이메일로 발송했습니다.';
        }
    }
}
?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<main class="pt-20 min-h-screen flex items-center justify-center px-6 py-16">
    <div class="w-full max-w-md">
        <div class="bg-suno-card border border-suno-border rounded-2xl p-8">
            <div class="text-center mb-8">
                <div class="flex items-center justify-center gap-2 mb-3">
                    <div class="flex gap-[2px] items-end h-7">
                        <div class="w-[3px] bg-suno-accent rounded-full h-3 wave-bar"></div>
                        <div class="w-[3px] bg-suno-accent rounded-full h-5 wave-bar" style="animation-delay:0.15s"></div>
                        <div class="w-[3px] bg-suno-accent rounded-full h-4 wave-bar" style="animation-delay:0.3s"></div>
                        <div class="w-[3px] bg-suno-accent rounded-full h-7 wave-bar" style="animation-delay:0.45s"></div>
                        <div class="w-[3px] bg-suno-accent rounded-full h-3 wave-bar" style="animation-delay:0.6s"></div>
                    </div>
                    <span class="text-2xl font-extrabold tracking-tight ml-1">SUNO</span>
                </div>
                <p class="text-suno-muted text-sm">비밀번호 찾기</p>
            </div>

            <?php if ($errorMsg): ?>
            <div class="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
                <?php echo htmlspecialchars($errorMsg); ?>
            </div>
            <?php endif; ?>

            <?php if ($successMsg): ?>
            <div class="text-center py-4">
                <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                    <svg class="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M3 8l7.89 5.26a2 2 0 002.22 0L21 8M5 19h14a2 2 0 002-2V7a2 2 0 00-2-2H5a2 2 0 00-2 2v10a2 2 0 002 2z"/>
                    </svg>
                </div>
                <h2 class="text-lg font-bold mb-2">이메일을 확인해주세요</h2>
                <p class="text-sm text-suno-muted mb-6"><?php echo htmlspecialchars($successMsg); ?></p>
                <p class="text-xs text-suno-muted/60 mb-6">메일이 도착하지 않으면 스팸 폴더를 확인하거나 다시 시도해주세요.</p>
                <a href="forgot_password.php" class="inline-block text-sm text-suno-accent hover:text-suno-accent2 transition-colors">
                    다시 시도하기
                </a>
            </div>
            <?php else: ?>
            <div class="mb-6">
                <p class="text-sm text-suno-muted text-center">가입 시 사용한 이메일과 닉네임을 입력하면<br>비밀번호 재설정 링크를 이메일로 보내드립니다.</p>
            </div>
            <form method="POST" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">이메일</label>
                    <input type="email" name="email" placeholder="가입한 이메일 주소" required
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">닉네임</label>
                    <input type="text" name="nickname" placeholder="가입한 닉네임" required
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>
                <button type="submit" class="w-full bg-suno-accent hover:bg-suno-accent2 text-white font-bold py-3.5 rounded-xl transition-all text-sm">
                    재설정 링크 발송
                </button>
            </form>
            <?php endif; ?>

            <div class="text-center mt-6 pt-4 border-t border-suno-border">
                <a href="login.php" class="text-sm text-suno-muted hover:text-white transition-colors">
                    ← 로그인으로 돌아가기
                </a>
            </div>
        </div>
    </div>
</main>

<?php include 'footer.php'; ?>
