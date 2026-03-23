<?php
if (session_status() === PHP_SESSION_NONE) session_start();
if (isset($_SESSION['admin_logged_in']) && $_SESSION['admin_logged_in'] === true) {
    header('Location: index.php');
    exit;
}
$error = $_GET['error'] ?? '';
?>
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin Login - SUNO Community</title>
    <script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-gray-900 min-h-screen flex items-center justify-center">
    <div class="w-full max-w-md">
        <div class="bg-gray-800 rounded-2xl shadow-2xl p-8 border border-gray-700">
            <div class="text-center mb-8">
                <div class="inline-flex items-center justify-center w-16 h-16 bg-violet-600 rounded-2xl mb-4">
                    <svg class="w-8 h-8 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 15v2m-6 4h12a2 2 0 002-2v-6a2 2 0 00-2-2H6a2 2 0 00-2 2v6a2 2 0 002 2zm10-10V7a4 4 0 00-8 0v4h8z"/>
                    </svg>
                </div>
                <h1 class="text-2xl font-bold text-white">Admin Panel</h1>
                <p class="text-gray-400 mt-1">SUNO Community 관리자 로그인</p>
            </div>

            <?php if ($error === 'invalid'): ?>
            <div class="bg-red-500/10 border border-red-500/30 text-red-400 px-4 py-3 rounded-lg mb-6 text-sm">
                아이디 또는 비밀번호가 올바르지 않습니다.
            </div>
            <?php endif; ?>

            <form action="login_ok.php" method="POST" class="space-y-5">
                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-2">아이디</label>
                    <input type="text" name="username" required autofocus
                        class="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                        placeholder="관리자 아이디 입력">
                </div>
                <div>
                    <label class="block text-sm font-medium text-gray-300 mb-2">비밀번호</label>
                    <input type="password" name="password" required
                        class="w-full px-4 py-3 bg-gray-700 border border-gray-600 rounded-lg text-white placeholder-gray-400 focus:outline-none focus:ring-2 focus:ring-violet-500 focus:border-transparent"
                        placeholder="비밀번호 입력">
                </div>
                <button type="submit"
                    class="w-full py-3 bg-violet-600 hover:bg-violet-700 text-white font-semibold rounded-lg transition-colors">
                    로그인
                </button>
            </form>

            <div class="mt-6 text-center">
                <a href="../index.php" class="text-sm text-gray-500 hover:text-gray-400 transition-colors">
                    &larr; 사이트로 돌아가기
                </a>
            </div>
        </div>
    </div>
</body>
</html>
