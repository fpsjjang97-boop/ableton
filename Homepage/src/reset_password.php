<?php
require_once 'db.php';
$pageTitle = '비밀번호 재설정';

$token = trim($_GET['token'] ?? $_POST['token'] ?? '');
$errorMsg = '';
$step = 'form'; // form → done

if (empty($token)) {
    $step = 'invalid';
} else {
    $stmt = $pdo->prepare('
        SELECT password_reset_tokens.*, users.nickname
        FROM password_reset_tokens
        JOIN users ON password_reset_tokens.user_id = users.id
        WHERE password_reset_tokens.token = ? AND password_reset_tokens.used = 0
    ');
    $stmt->execute([$token]);
    $resetRecord = $stmt->fetch();

    if (!$resetRecord) {
        $step = 'invalid';
    } elseif (strtotime($resetRecord['expires_at']) < time()) {
        $step = 'expired';
    }
}

if ($_SERVER['REQUEST_METHOD'] === 'POST' && $step === 'form') {
    $newPassword = $_POST['new_password'] ?? '';
    $confirmPassword = $_POST['confirm_password'] ?? '';

    if (empty($newPassword) || empty($confirmPassword)) {
        $errorMsg = '새 비밀번호를 입력해주세요.';
    } elseif (mb_strlen($newPassword) < 8) {
        $errorMsg = '비밀번호는 8자 이상이어야 합니다.';
    } elseif ($newPassword !== $confirmPassword) {
        $errorMsg = '비밀번호가 일치하지 않습니다.';
    } else {
        $hash = password_hash($newPassword, PASSWORD_DEFAULT);
        $pdo->prepare('UPDATE users SET password_hash = ?, updated_at = datetime("now") WHERE id = ?')
            ->execute([$hash, $resetRecord['user_id']]);

        $pdo->prepare('UPDATE password_reset_tokens SET used = 1 WHERE id = ?')
            ->execute([$resetRecord['id']]);

        $step = 'done';
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
                <p class="text-suno-muted text-sm">비밀번호 재설정</p>
            </div>

            <?php if ($errorMsg): ?>
            <div class="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
                <?php echo htmlspecialchars($errorMsg); ?>
            </div>
            <?php endif; ?>

            <?php if ($step === 'invalid'): ?>
            <div class="text-center py-4">
                <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-red-500/10 border border-red-500/20 flex items-center justify-center">
                    <svg class="w-8 h-8 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L3.34 16.5c-.77.833.192 2.5 1.732 2.5z"/>
                    </svg>
                </div>
                <h2 class="text-lg font-bold mb-2">유효하지 않은 링크</h2>
                <p class="text-sm text-suno-muted mb-6">이미 사용되었거나 잘못된 비밀번호 재설정 링크입니다.</p>
                <a href="forgot_password.php" class="inline-block w-full bg-suno-accent hover:bg-suno-accent2 text-white font-bold py-3.5 rounded-xl transition-all text-sm text-center">
                    비밀번호 찾기로 이동
                </a>
            </div>

            <?php elseif ($step === 'expired'): ?>
            <div class="text-center py-4">
                <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-amber-500/10 border border-amber-500/20 flex items-center justify-center">
                    <svg class="w-8 h-8 text-amber-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z"/>
                    </svg>
                </div>
                <h2 class="text-lg font-bold mb-2">링크가 만료되었습니다</h2>
                <p class="text-sm text-suno-muted mb-6">비밀번호 재설정 링크의 유효 시간(1시간)이 지났습니다.<br>다시 요청해주세요.</p>
                <a href="forgot_password.php" class="inline-block w-full bg-suno-accent hover:bg-suno-accent2 text-white font-bold py-3.5 rounded-xl transition-all text-sm text-center">
                    다시 요청하기
                </a>
            </div>

            <?php elseif ($step === 'form'): ?>
            <div class="mb-6">
                <p class="text-sm text-suno-muted text-center">
                    <span class="text-white font-medium"><?php echo htmlspecialchars($resetRecord['nickname']); ?></span>님, 새 비밀번호를 설정해주세요.
                </p>
            </div>
            <form method="POST" class="space-y-4">
                <input type="hidden" name="token" value="<?php echo htmlspecialchars($token); ?>">
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">새 비밀번호</label>
                    <input type="password" name="new_password" placeholder="8자 이상 입력" required
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">새 비밀번호 확인</label>
                    <input type="password" name="confirm_password" placeholder="비밀번호를 다시 입력" required
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>
                <button type="submit" class="w-full bg-suno-accent hover:bg-suno-accent2 text-white font-bold py-3.5 rounded-xl transition-all text-sm">
                    비밀번호 변경
                </button>
            </form>

            <?php elseif ($step === 'done'): ?>
            <div class="text-center py-4">
                <div class="w-16 h-16 mx-auto mb-4 rounded-full bg-emerald-500/10 border border-emerald-500/20 flex items-center justify-center">
                    <svg class="w-8 h-8 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/>
                    </svg>
                </div>
                <h2 class="text-lg font-bold mb-2">비밀번호가 변경되었습니다</h2>
                <p class="text-sm text-suno-muted mb-6">새 비밀번호로 로그인해주세요.</p>
                <a href="login.php" class="inline-block w-full bg-suno-accent hover:bg-suno-accent2 text-white font-bold py-3.5 rounded-xl transition-all text-sm text-center">
                    로그인하기
                </a>
            </div>
            <?php endif; ?>

            <?php if ($step === 'form'): ?>
            <div class="text-center mt-6 pt-4 border-t border-suno-border">
                <a href="login.php" class="text-sm text-suno-muted hover:text-white transition-colors">
                    ← 로그인으로 돌아가기
                </a>
            </div>
            <?php endif; ?>
        </div>
    </div>
</main>

<?php include 'footer.php'; ?>
