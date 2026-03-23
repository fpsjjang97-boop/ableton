<?php
require_once __DIR__ . '/auth.php';
requireAdmin();

$currentPage = basename($_SERVER['PHP_SELF'], '.php');
$menuItems = [
    ['index', '대시보드', 'fa-solid fa-house'],
    ['users', '회원 관리', 'fa-solid fa-users'],
    ['tracks', '트랙 관리', 'fa-solid fa-music'],
    ['prompts', '프롬프트 관리', 'fa-solid fa-wand-magic-sparkles'],
    ['posts', '게시글 관리', 'fa-solid fa-newspaper'],
    ['boards', '게시판 관리', 'fa-solid fa-table-columns'],
    ['menus', '메뉴 관리', 'fa-solid fa-bars'],
    ['tags', '태그 관리', 'fa-solid fa-tags'],
    ['messages', '쪽지 관리', 'fa-solid fa-envelope'],
    ['reports', '신고 관리', 'fa-solid fa-triangle-exclamation'],
    ['settings', '사이트 설정', 'fa-solid fa-gear'],
    ['footer_settings', '푸터 설정', 'fa-solid fa-shoe-prints'],
    ['pages', '페이지 관리', 'fa-solid fa-file-lines'],
];
?>
<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Admin - SUNO Community</title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <style>
        .sidebar-link.active { background: rgba(139, 92, 246, 0.15); color: #a78bfa; border-left-color: #8b5cf6; }
        .sidebar-link:hover:not(.active) { background: rgba(255,255,255,0.05); }
    </style>
</head>
<body class="bg-gray-900 text-gray-200 min-h-screen">
    <div class="flex min-h-screen">
        <!-- Sidebar -->
        <aside class="w-64 bg-gray-800 border-r border-gray-700 flex flex-col fixed h-full z-10">
            <div class="p-5 border-b border-gray-700">
                <a href="index.php" class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-violet-600 rounded-xl flex items-center justify-center">
                        <svg class="w-5 h-5 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 10V3L4 14h7v7l9-11h-7z"/>
                        </svg>
                    </div>
                    <div>
                        <div class="font-bold text-white text-lg">SUNO Admin</div>
                        <div class="text-xs text-gray-500">관리자 패널</div>
                    </div>
                </a>
            </div>

            <nav class="flex-1 py-4 overflow-y-auto">
                <?php foreach ($menuItems as $item): ?>
                <a href="<?= $item[0] ?>.php"
                   class="sidebar-link flex items-center gap-3 px-5 py-3 text-sm border-l-3 border-transparent transition-all <?= $currentPage === $item[0] ? 'active' : 'text-gray-400' ?>"
                   style="border-left-width: 3px;">
                    <i class="<?= $item[2] ?> w-5 text-center flex-shrink-0"></i>
                    <?= $item[1] ?>
                </a>
                <?php endforeach; ?>
            </nav>

            <div class="p-4 border-t border-gray-700">
                <div class="flex items-center justify-between">
                    <div class="flex items-center gap-2">
                        <div class="w-8 h-8 bg-violet-600 rounded-full flex items-center justify-center text-sm font-bold text-white">A</div>
                        <span class="text-sm text-gray-400"><?= e($_SESSION['admin_username'] ?? 'admin') ?></span>
                    </div>
                    <a href="logout.php" class="text-gray-500 hover:text-red-400 transition-colors" title="로그아웃">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M17 16l4-4m0 0l-4-4m4 4H7m6 4v1a3 3 0 01-3 3H6a3 3 0 01-3-3V7a3 3 0 013-3h4a3 3 0 013 3v1"/>
                        </svg>
                    </a>
                </div>
                <a href="../index.php" class="mt-3 block text-center text-xs text-gray-500 hover:text-gray-400 transition-colors">
                    사이트로 돌아가기 &rarr;
                </a>
            </div>
        </aside>

        <!-- Main Content -->
        <main class="flex-1 ml-64">
            <div class="p-8">
