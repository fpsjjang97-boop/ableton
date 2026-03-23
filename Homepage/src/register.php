<?php
require_once 'db.php';
$pageTitle = '회원가입';

// 에러 메시지 매핑
$errorMessages = [
    'empty' => '모든 항목을 입력해주세요.',
    'email_format' => '올바른 이메일 형식이 아닙니다.',
    'nickname_length' => '닉네임은 2~50자로 입력해주세요.',
    'password_mismatch' => '비밀번호가 일치하지 않습니다.',
    'password_short' => '비밀번호는 8자 이상이어야 합니다.',
    'terms' => '이용약관에 동의해주세요.',
    'email_exists' => '이미 사용 중인 이메일입니다.',
    'nickname_exists' => '이미 사용 중인 닉네임입니다.',
];
$error = isset($_GET['error']) ? ($_GET['error']) : '';
$errorMsg = isset($errorMessages[$error]) ? $errorMessages[$error] : '';
?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<main class="pt-20 min-h-screen flex items-center justify-center px-6 py-16">
    <div class="w-full max-w-md">
        <!-- Card -->
        <div class="bg-suno-card border border-suno-border rounded-2xl p-8">
            <!-- Logo -->
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
                <p class="text-suno-muted text-sm">AI 음악 크리에이터가 되어보세요</p>
            </div>

            <?php if ($errorMsg): ?>
            <div class="mb-4 p-3 rounded-xl bg-red-500/10 border border-red-500/20 text-red-400 text-sm text-center">
                <?php echo htmlspecialchars($errorMsg); ?>
            </div>
            <?php endif; ?>

            <!-- Register Form -->
            <form action="register_ok.php" method="POST" class="space-y-4">
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">닉네임</label>
                    <input type="text" name="nickname" placeholder="커뮤니티에서 사용할 닉네임"
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">이메일</label>
                    <input type="email" name="email" placeholder="example@email.com"
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">비밀번호</label>
                    <input type="password" name="password" placeholder="8자 이상 영문, 숫자, 특수문자 조합"
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>
                <div>
                    <label class="block text-sm font-medium text-suno-muted mb-1.5">비밀번호 확인</label>
                    <input type="password" name="password_confirm" placeholder="비밀번호를 다시 입력하세요"
                        class="w-full bg-suno-surface border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50 transition-colors">
                </div>

                <!-- Terms -->
                <div class="pt-2">
                    <label class="flex items-start gap-2.5 cursor-pointer">
                        <input type="checkbox" name="terms" value="1" class="w-4 h-4 rounded border-suno-border bg-suno-surface text-suno-accent focus:ring-suno-accent/50 mt-0.5">
                        <span class="text-xs text-suno-muted leading-relaxed">
                            <a href="#" class="text-suno-accent hover:text-suno-accent2 transition-colors">이용약관</a> 및
                            <a href="#" class="text-suno-accent hover:text-suno-accent2 transition-colors">개인정보처리방침</a>에 동의합니다.
                        </span>
                    </label>
                </div>

                <button type="submit" class="w-full bg-suno-accent hover:bg-suno-accent2 text-white font-bold py-3.5 rounded-xl transition-all text-sm mt-2">
                    회원가입
                </button>
            </form>

            <!-- Divider -->
            <div class="flex items-center gap-4 my-6">
                <div class="flex-1 h-px bg-suno-border"></div>
                <span class="text-xs text-suno-muted">또는</span>
                <div class="flex-1 h-px bg-suno-border"></div>
            </div>

            <!-- Social Signup -->
            <div class="space-y-3">
                <!-- Google -->
                <button class="w-full flex items-center justify-center gap-3 bg-white hover:bg-gray-100 text-gray-800 font-medium py-3 rounded-xl transition-all text-sm">
                    <svg class="w-5 h-5" viewBox="0 0 24 24">
                        <path fill="#4285F4" d="M22.56 12.25c0-.78-.07-1.53-.2-2.25H12v4.26h5.92a5.06 5.06 0 01-2.2 3.32v2.77h3.57c2.08-1.92 3.28-4.74 3.28-8.1z"/>
                        <path fill="#34A853" d="M12 23c2.97 0 5.46-.98 7.28-2.66l-3.57-2.77c-.98.66-2.23 1.06-3.71 1.06-2.86 0-5.29-1.93-6.16-4.53H2.18v2.84C3.99 20.53 7.7 23 12 23z"/>
                        <path fill="#FBBC05" d="M5.84 14.09c-.22-.66-.35-1.36-.35-2.09s.13-1.43.35-2.09V7.07H2.18C1.43 8.55 1 10.22 1 12s.43 3.45 1.18 4.93l2.85-2.22.81-.62z"/>
                        <path fill="#EA4335" d="M12 5.38c1.62 0 3.06.56 4.21 1.64l3.15-3.15C17.45 2.09 14.97 1 12 1 7.7 1 3.99 3.47 2.18 7.07l3.66 2.84c.87-2.6 3.3-4.53 6.16-4.53z"/>
                    </svg>
                    Google로 가입하기
                </button>

                <!-- Kakao -->
                <button class="w-full flex items-center justify-center gap-3 bg-[#FEE500] hover:bg-[#FDD800] text-[#3C1E1E] font-medium py-3 rounded-xl transition-all text-sm">
                    <svg class="w-5 h-5" viewBox="0 0 24 24" fill="#3C1E1E">
                        <path d="M12 3C6.48 3 2 6.58 2 10.94c0 2.8 1.87 5.27 4.68 6.67-.15.56-.96 3.6-.99 3.83 0 0-.02.17.09.23.11.07.24.02.24.02.32-.04 3.7-2.44 4.28-2.85.55.08 1.11.12 1.7.12 5.52 0 10-3.58 10-7.94S17.52 3 12 3z"/>
                    </svg>
                    카카오로 가입하기
                </button>
            </div>

            <!-- Login Link -->
            <div class="text-center mt-8 pt-6 border-t border-suno-border">
                <p class="text-sm text-suno-muted">
                    이미 계정이 있으신가요?
                    <a href="login.php" class="text-suno-accent hover:text-suno-accent2 font-medium transition-colors">로그인</a>
                </p>
            </div>
        </div>
    </div>
</main>

<?php include 'footer.php'; ?>
