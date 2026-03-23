<!DOCTYPE html>
<html lang="ko">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title><?php echo isset($pageTitle) ? $pageTitle . ' - SUNO Community' : 'SUNO Community - AI 음악 커뮤니티'; ?></title>
    <script src="https://cdn.tailwindcss.com"></script>
    <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.5.1/css/all.min.css">
    <link rel="preconnect" href="https://fonts.googleapis.com">
    <link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600;700;800;900&display=swap" rel="stylesheet">
    <script>
        tailwind.config = {
            theme: {
                extend: {
                    fontFamily: {
                        'inter': ['Inter', 'sans-serif'],
                    },
                    colors: {
                        'suno': {
                            'dark': '#0a0a0a',
                            'card': '#141414',
                            'border': '#1e1e1e',
                            'accent': '#8b5cf6',
                            'accent2': '#a78bfa',
                            'hover': '#1a1a2e',
                            'muted': '#71717a',
                            'surface': '#18181b',
                        }
                    }
                }
            }
        }
    </script>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: 'Inter', sans-serif; }

        ::-webkit-scrollbar { width: 6px; }
        ::-webkit-scrollbar-track { background: #0a0a0a; }
        ::-webkit-scrollbar-thumb { background: #333; border-radius: 3px; }

        @keyframes wave {
            0%, 100% { height: 8px; }
            50% { height: 24px; }
        }
        .wave-bar { animation: wave 1.2s ease-in-out infinite; }

        @keyframes pulseGlow {
            0%, 100% { box-shadow: 0 0 20px rgba(139,92,246,0.2); }
            50% { box-shadow: 0 0 40px rgba(139,92,246,0.4); }
        }
        .pulse-glow { animation: pulseGlow 3s ease-in-out infinite; }

        .music-card {
            transition: all 0.3s cubic-bezier(0.4, 0, 0.2, 1);
        }
        .music-card:hover {
            transform: translateY(-4px);
            box-shadow: 0 12px 40px rgba(139,92,246,0.15);
        }
        .music-card:hover .play-overlay { opacity: 1; }
        .play-overlay { opacity: 0; transition: opacity 0.3s ease; }

        .nav-blur {
            backdrop-filter: blur(20px);
            -webkit-backdrop-filter: blur(20px);
        }
        .nav-dropdown {
            opacity: 0; visibility: hidden; transform: translateY(8px); transition: all 0.2s ease;
        }
        .nav-item:hover .nav-dropdown {
            opacity: 1; visibility: visible; transform: translateY(0);
        }
        .nav-dropdown-item { transition: all 0.15s ease; }
        .nav-dropdown-item:hover { background: rgba(139,92,246,0.08); }
        .nav-dropdown-item:hover .dropdown-icon { color: #8b5cf6; }

        .mobile-menu { max-height: 0; overflow: hidden; transition: max-height 0.4s ease; }
        .mobile-menu.open { max-height: 80vh; overflow-y: auto; }

        .genre-tag { transition: all 0.3s ease; }
        .genre-tag:hover {
            background: rgba(139,92,246,0.2);
            border-color: #8b5cf6;
            color: #a78bfa;
        }

        .tab-active {
            color: #8b5cf6;
            border-bottom: 2px solid #8b5cf6;
        }
    </style>
</head>
<body class="bg-suno-dark text-white font-inter">
