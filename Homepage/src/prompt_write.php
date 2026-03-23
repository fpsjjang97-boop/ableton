<?php require_once 'db.php'; ?>
<?php
// 로그인 필수
if (!$currentUser) {
    header('Location: login.php');
    exit;
}
?>
<?php $pageTitle = '프롬프트 공유하기'; ?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<style>
    .form-input {
        transition: all 0.2s ease;
    }
    .form-input:focus {
        border-color: rgba(139,92,246,0.5);
        box-shadow: 0 0 0 3px rgba(139,92,246,0.1);
    }
    .tag-select {
        transition: all 0.2s ease;
        cursor: pointer;
    }
    .tag-select:hover {
        background: rgba(139,92,246,0.15);
        border-color: rgba(139,92,246,0.4);
        color: #a78bfa;
    }
    .tag-select.selected {
        background: rgba(139,92,246,0.2);
        border-color: #8b5cf6;
        color: #a78bfa;
    }
    .submit-btn {
        transition: all 0.3s ease;
        background: linear-gradient(135deg, #8b5cf6, #7c3aed);
    }
    .submit-btn:hover {
        background: linear-gradient(135deg, #a78bfa, #8b5cf6);
        box-shadow: 0 8px 30px rgba(139,92,246,0.3);
        transform: translateY(-1px);
    }
    .cancel-btn {
        transition: all 0.2s ease;
    }
    .cancel-btn:hover {
        background: rgba(255,255,255,0.05);
        border-color: rgba(255,255,255,0.2);
    }
    .preview-block {
        font-family: 'SF Mono', 'Fira Code', 'Fira Mono', 'Roboto Mono', monospace;
    }
    .char-count {
        transition: color 0.2s ease;
    }
    /* Number input arrows hide */
    input[type="number"]::-webkit-inner-spin-button,
    input[type="number"]::-webkit-outer-spin-button {
        -webkit-appearance: none;
        margin: 0;
    }
    input[type="number"] {
        -moz-appearance: textfield;
    }
    /* Range slider styling */
    input[type="range"] {
        -webkit-appearance: none;
        appearance: none;
        height: 6px;
        border-radius: 3px;
        outline: none;
    }
    input[type="range"]::-webkit-slider-thumb {
        -webkit-appearance: none;
        appearance: none;
        width: 16px;
        height: 16px;
        border-radius: 50%;
        background: #e11d48;
        cursor: pointer;
        border: 2px solid #1a1a2e;
        box-shadow: 0 0 6px rgba(225,29,72,0.3);
    }
    input[type="range"]::-moz-range-thumb {
        width: 16px;
        height: 16px;
        border-radius: 50%;
        background: #e11d48;
        cursor: pointer;
        border: 2px solid #1a1a2e;
        box-shadow: 0 0 6px rgba(225,29,72,0.3);
    }
</style>

<?php
// DB에서 태그 로드 (tag_options 테이블이 없으면 기본값 사용)
$genreOptions = ['K-Pop', 'Lo-fi', 'Hip-Hop', 'R&B', 'Rock', 'Jazz', 'EDM', 'Ambient', 'Cinematic', 'Classical', 'Ballad', 'Folk', 'Reggae', 'Metal', 'Country', 'Latin'];
$styleOptions = ['Dreamy', 'Energetic', 'Chill', 'Dark', 'Uplifting', 'Melancholic', 'Retro', 'Futuristic', 'Acoustic', 'Electronic', 'Orchestral', 'Minimal'];
try {
    $__tagTable = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name='tag_options'")->fetchColumn();
    if ($__tagTable) {
        $__g = $pdo->query("SELECT tag_name FROM tag_options WHERE tag_type='prompt_genre' AND is_active=1 ORDER BY sort_order, id")->fetchAll(PDO::FETCH_COLUMN);
        $__s = $pdo->query("SELECT tag_name FROM tag_options WHERE tag_type='prompt_style' AND is_active=1 ORDER BY sort_order, id")->fetchAll(PDO::FETCH_COLUMN);
        if (!empty($__g)) $genreOptions = $__g;
        if (!empty($__s)) $styleOptions = $__s;
    }
} catch (Exception $e) {}

// Fetch user's tracks for the modal
$myTracks = [];
if ($currentUser) {
    $tStmt = $pdo->prepare('SELECT id, title, cover_image_path, duration, created_at, (SELECT genre FROM track_genres WHERE track_id = tracks.id LIMIT 1) as genre FROM tracks WHERE user_id = ? ORDER BY created_at DESC');
    $tStmt->execute([$currentUser['id']]);
    $myTracks = $tStmt->fetchAll();
}
?>

<!-- Main Content -->
<main class="pt-20">
    <div class="max-w-4xl mx-auto px-6 py-8">
        <!-- Breadcrumb -->
        <nav class="flex items-center gap-2 text-sm mb-8">
            <a href="index.php" class="text-suno-muted hover:text-white transition-colors">홈</a>
            <svg class="w-3.5 h-3.5 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
            <a href="prompt_list.php" class="text-suno-muted hover:text-white transition-colors">프롬프트</a>
            <svg class="w-3.5 h-3.5 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
            </svg>
            <span class="text-white/80">작성하기</span>
        </nav>

        <!-- Page Header -->
        <div class="mb-8">
            <div class="flex items-center gap-3 mb-2">
                <div class="w-10 h-10 rounded-xl bg-suno-accent/15 flex items-center justify-center">
                    <svg class="w-5 h-5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/>
                    </svg>
                </div>
                <div>
                    <h1 class="text-2xl font-extrabold tracking-tight">프롬프트 공유하기</h1>
                    <p class="text-suno-muted text-sm mt-0.5">나만의 Suno 프롬프트를 커뮤니티와 공유하세요</p>
                </div>
            </div>
        </div>

        <!-- Form -->
        <form action="prompt_write_ok.php" method="POST" enctype="multipart/form-data" class="space-y-8">
            <!-- Hidden fields for JS-populated values -->
            <input type="hidden" name="genres" id="hiddenGenres" value="">
            <input type="hidden" name="styles" id="hiddenStyles" value="">
            <input type="hidden" name="linked_track_id" id="hiddenLinkedTrackId" value="">
            <input type="hidden" name="weirdness" id="hiddenWeirdness" value="50">
            <input type="hidden" name="style_influence" id="hiddenStyleInfluence" value="50">
            <input type="hidden" name="audio_influence" id="hiddenAudioInfluence" value="25">

            <!-- Title -->
            <div>
                <label class="block text-sm font-semibold mb-2">
                    제목 <span class="text-red-400">*</span>
                </label>
                <input type="text" name="title" id="promptTitle" placeholder="프롬프트의 제목을 입력하세요 (예: 몽환적인 K-Pop 발라드)"
                    class="form-input w-full bg-suno-card border border-suno-border rounded-xl px-4 py-3.5 text-sm text-white placeholder-suno-muted/50 focus:outline-none"
                    maxlength="100"
                    oninput="updatePreview(); updateCharCount('titleCount', this, 100);">
                <div class="flex justify-end mt-1">
                    <span id="titleCount" class="char-count text-xs text-suno-muted/50">0/100</span>
                </div>
            </div>

            <!-- Prompt Content (Styles) -->
            <div>
                <label class="block text-sm font-semibold mb-2">
                    프롬프트 내용 <span class="text-suno-muted/50 font-normal">(Styles)</span> <span class="text-red-400">*</span>
                </label>
                <p class="text-xs text-suno-muted mb-3">Suno의 Styles 필드에 입력할 프롬프트를 작성하세요. 장르, 악기, BPM, 분위기 등을 구체적으로 작성할수록 좋은 결과를 얻을 수 있습니다.</p>
                <textarea name="prompt_text" id="promptContent" placeholder="예: Dreamy K-pop ballad, ethereal female vocals, soft piano melody, lush string arrangement, emotional bridge with soaring high notes, 72 BPM, reverb-heavy production..."
                    class="form-input w-full bg-suno-card border border-suno-border rounded-xl px-4 py-4 text-sm text-white placeholder-suno-muted/50 focus:outline-none resize-none font-mono leading-relaxed"
                    rows="8"
                    maxlength="2000"
                    oninput="updatePreview(); updateCharCount('contentCount', this, 2000);"></textarea>
                <div class="flex justify-end mt-1">
                    <span id="contentCount" class="char-count text-xs text-suno-muted/50">0/2000</span>
                </div>
            </div>

            <!-- Exclude Styles -->
            <div>
                <label class="block text-sm font-semibold mb-2 flex items-center gap-2">
                    Exclude Styles
                    <span class="text-xs text-suno-muted font-normal">(선택사항)</span>
                </label>
                <p class="text-xs text-suno-muted mb-3">제외할 스타일이 있다면 입력하세요 (예: autotune, screaming, heavy distortion)</p>
                <input type="text" name="exclude_styles" id="excludeStyles" placeholder="예: autotune, screaming, heavy distortion"
                    class="form-input w-full bg-suno-card border border-suno-border rounded-xl px-4 py-3.5 text-sm text-rose-400/80 placeholder-suno-muted/50 focus:outline-none font-mono"
                    maxlength="500">
            </div>

            <!-- Suno Parameters -->
            <div>
                <label class="block text-sm font-semibold mb-2 flex items-center gap-2">
                    Suno 파라미터
                    <span class="text-xs text-suno-muted font-normal">(선택사항)</span>
                </label>
                <p class="text-xs text-suno-muted mb-4">곡 생성 시 사용한 Suno 파라미터 값을 공유하세요</p>
                <div class="bg-suno-card border border-suno-border rounded-xl p-5 space-y-5">
                    <!-- Weirdness -->
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-xs font-medium text-suno-muted">Weirdness</span>
                            <div class="flex items-center gap-1">
                                <input type="number" id="weirdnessNum" min="0" max="100" value="50"
                                    class="w-12 bg-suno-dark border border-suno-border rounded px-1.5 py-0.5 text-xs font-mono text-rose-400/80 text-right focus:outline-none focus:border-rose-500/40"
                                    oninput="syncSlider('weirdness', this.value)">
                                <span class="text-xs text-rose-400/50">%</span>
                            </div>
                        </div>
                        <input type="range" id="weirdnessSlider" min="0" max="100" value="50" step="1"
                            class="w-full h-1.5 rounded-full appearance-none bg-suno-border/60 cursor-pointer accent-rose-500"
                            oninput="syncInput('weirdness', this.value)">
                    </div>
                    <!-- Style Influence -->
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-xs font-medium text-suno-muted">Style Influence</span>
                            <div class="flex items-center gap-1">
                                <input type="number" id="styleInflNum" min="0" max="100" value="50"
                                    class="w-12 bg-suno-dark border border-suno-border rounded px-1.5 py-0.5 text-xs font-mono text-rose-400/80 text-right focus:outline-none focus:border-rose-500/40"
                                    oninput="syncSlider('styleInfl', this.value)">
                                <span class="text-xs text-rose-400/50">%</span>
                            </div>
                        </div>
                        <input type="range" id="styleInflSlider" min="0" max="100" value="50" step="1"
                            class="w-full h-1.5 rounded-full appearance-none bg-suno-border/60 cursor-pointer accent-rose-500"
                            oninput="syncInput('styleInfl', this.value)">
                    </div>
                    <!-- Audio Influence -->
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-xs font-medium text-suno-muted">Audio Influence</span>
                            <div class="flex items-center gap-1">
                                <input type="number" id="audioInflNum" min="0" max="100" value="25"
                                    class="w-12 bg-suno-dark border border-suno-border rounded px-1.5 py-0.5 text-xs font-mono text-rose-400/80 text-right focus:outline-none focus:border-rose-500/40"
                                    oninput="syncSlider('audioInfl', this.value)">
                                <span class="text-xs text-rose-400/50">%</span>
                            </div>
                        </div>
                        <input type="range" id="audioInflSlider" min="0" max="100" value="25" step="1"
                            class="w-full h-1.5 rounded-full appearance-none bg-suno-border/60 cursor-pointer accent-rose-500"
                            oninput="syncInput('audioInfl', this.value)">
                    </div>
                </div>
            </div>

            <!-- Lyrics (가사) -->
            <div>
                <label class="block text-sm font-semibold mb-2 flex items-center gap-2">
                    가사 <span class="text-suno-muted/50 font-normal">(Lyrics)</span>
                    <span class="text-xs text-suno-muted font-normal">(선택사항)</span>
                </label>
                <p class="text-xs text-suno-muted mb-3">Suno에 입력한 가사가 있다면 공유하세요. 커스텀 가사 없이 생성한 경우 비워두세요.</p>
                <textarea name="lyrics" id="lyricsContent" placeholder="[Verse 1]&#10;Here comes the morning light...&#10;&#10;[Chorus]&#10;We're dancing through the night..."
                    class="form-input w-full bg-suno-card border border-suno-border rounded-xl px-4 py-4 text-sm text-white placeholder-suno-muted/50 focus:outline-none resize-none font-mono leading-relaxed"
                    rows="8"
                    maxlength="5000"
                    oninput="updateCharCount('lyricsCount', this, 5000);"></textarea>
                <div class="flex justify-end mt-1">
                    <span id="lyricsCount" class="char-count text-xs text-suno-muted/50">0/5000</span>
                </div>
            </div>

            <!-- Genre / Style Tags -->
            <div>
                <label class="block text-sm font-semibold mb-2">
                    장르 태그 <span class="text-red-400">*</span>
                </label>
                <p class="text-xs text-suno-muted mb-3">해당하는 장르를 선택하세요 (최대 3개)</p>
                <div class="flex flex-wrap gap-2 mb-6" id="genreTags">
                    <?php foreach($genreOptions as $genre): ?>
                    <button type="button" class="tag-select text-xs px-3.5 py-2 rounded-full border border-suno-border bg-suno-dark text-suno-muted font-medium"
                            onclick="toggleTag(this, 'genre')" data-tag="<?php echo $genre; ?>">
                        <?php echo $genre; ?>
                    </button>
                    <?php endforeach; ?>
                </div>

                <label class="block text-sm font-semibold mb-2">
                    스타일 태그
                </label>
                <p class="text-xs text-suno-muted mb-3">분위기나 스타일을 선택하세요 (선택사항, 최대 3개)</p>
                <div class="flex flex-wrap gap-2" id="styleTags">
                    <?php foreach($styleOptions as $style): ?>
                    <button type="button" class="tag-select text-xs px-3.5 py-2 rounded-full border border-suno-border bg-suno-dark text-suno-muted font-medium"
                            onclick="toggleTag(this, 'style')" data-tag="<?php echo $style; ?>">
                        <?php echo $style; ?>
                    </button>
                    <?php endforeach; ?>
                </div>
            </div>

            <!-- Description -->
            <div>
                <label class="block text-sm font-semibold mb-2">
                    설명
                </label>
                <p class="text-xs text-suno-muted mb-3">프롬프트에 대한 설명이나 사용 팁을 작성하세요 (선택사항)</p>
                <textarea name="description" id="promptDesc" placeholder="이 프롬프트의 특징, 사용 팁, 추천 조합 등을 자유롭게 작성해주세요..."
                    class="form-input w-full bg-suno-card border border-suno-border rounded-xl px-4 py-4 text-sm text-white placeholder-suno-muted/50 focus:outline-none resize-none leading-relaxed"
                    rows="4"
                    maxlength="1000"
                    oninput="updateCharCount('descCount', this, 1000);"></textarea>
                <div class="flex justify-end mt-1">
                    <span id="descCount" class="char-count text-xs text-suno-muted/50">0/1000</span>
                </div>
            </div>

            <!-- 완성본 곡 연결 (음원 게시판) -->
            <div>
                <label class="block text-sm font-semibold mb-2 flex items-center gap-2">
                    <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/>
                    </svg>
                    완성본 곡 연결
                    <span class="text-xs text-suno-muted font-normal">(선택사항)</span>
                </label>
                <p class="text-xs text-suno-muted mb-3">이 프롬프트+샘플로 만든 완성곡이 있다면, 내 음원 게시물에서 가져올 수 있습니다.</p>

                <!-- 연결된 곡 미리보기 (초기: hidden, JS로 표시) -->
                <div id="linkedTrackPreview" class="hidden bg-suno-card border border-suno-border rounded-xl p-4 mb-3">
                    <div class="flex items-center gap-3">
                        <div id="linkedTrackThumbWrap" class="w-14 h-14 rounded-lg overflow-hidden flex-shrink-0 bg-suno-dark"></div>
                        <div class="flex-1 min-w-0">
                            <p id="linkedTrackTitle" class="text-sm font-bold truncate"></p>
                            <p id="linkedTrackMeta" class="text-[10px] text-suno-muted mt-0.5"></p>
                        </div>
                        <button type="button" onclick="removeLinkedTrack()" class="text-suno-muted hover:text-red-400 transition-colors shrink-0">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                        </button>
                    </div>
                </div>

                <!-- 곡 선택 버튼 -->
                <button type="button" id="selectTrackBtn" onclick="openTrackSelector()" class="w-full bg-suno-dark border-2 border-dashed border-suno-border rounded-xl py-6 flex flex-col items-center gap-2 hover:border-suno-accent/40 hover:bg-suno-accent/5 transition-all cursor-pointer">
                    <svg class="w-7 h-7 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.86-2.502a4.5 4.5 0 00-6.364-6.364L4.5 8.625"/>
                    </svg>
                    <span class="text-xs text-suno-muted font-medium">내 음원에서 곡 선택하기</span>
                    <span class="text-[10px] text-suno-muted/40">음원 게시판에 업로드한 곡 목록에서 선택</span>
                </button>

                <!-- 곡 선택 모달 -->
                <div id="trackSelectorModal" class="fixed inset-0 z-[100] hidden">
                    <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" onclick="closeTrackSelector()"></div>
                    <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg bg-suno-card border border-suno-border rounded-2xl overflow-hidden shadow-2xl">
                        <div class="flex items-center justify-between px-6 py-4 border-b border-suno-border">
                            <h3 class="font-bold text-base">내 음원에서 선택</h3>
                            <button type="button" onclick="closeTrackSelector()" class="text-suno-muted hover:text-white transition-colors">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                            </button>
                        </div>
                        <!-- 검색 -->
                        <div class="px-6 py-3 border-b border-suno-border">
                            <div class="relative">
                                <svg class="absolute left-3 top-1/2 -translate-y-1/2 w-4 h-4 text-suno-muted/50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z"/></svg>
                                <input type="text" placeholder="곡 제목으로 검색..." class="w-full bg-suno-dark border border-suno-border rounded-lg pl-10 pr-4 py-2.5 text-sm text-white placeholder-suno-muted/50 focus:outline-none focus:border-suno-accent/50">
                            </div>
                        </div>
                        <!-- 곡 목록 -->
                        <div class="max-h-80 overflow-y-auto px-3 py-3 space-y-1">
                            <?php if(empty($myTracks)): ?>
                            <div class="text-center py-8 text-suno-muted/40 text-sm">
                                <?php if(!$currentUser): ?>
                                로그인 후 이용 가능합니다.
                                <?php else: ?>
                                등록된 음원이 없습니다.
                                <?php endif; ?>
                            </div>
                            <?php else: ?>
                            <?php foreach($myTracks as $t):
                                $hasCover = !empty($t['cover_image_path']);
                                $thumbSrc = $hasCover ? htmlspecialchars($t['cover_image_path']) : '';
                                $gradient = getGradient($t['id'], $t['genre'] ?? null);
                                $trackDate = date('Y.m.d', strtotime($t['created_at']));
                            ?>
                            <button type="button" onclick="selectTrack(<?php echo $t['id']; ?>, '<?php echo htmlspecialchars(addslashes($t['title']), ENT_QUOTES); ?>', '<?php echo $thumbSrc; ?>', '<?php echo $t['duration']; ?> &middot; <?php echo $trackDate; ?>', <?php echo $hasCover ? 'true' : 'false'; ?>, '<?php echo $gradient; ?>')" class="w-full flex items-center gap-3 p-3 rounded-xl hover:bg-suno-hover transition-all text-left group">
                                <?php if ($hasCover): ?>
                                <img src="<?php echo $thumbSrc; ?>" alt="" class="w-11 h-11 rounded-lg object-cover flex-shrink-0">
                                <?php else: ?>
                                <div class="w-11 h-11 rounded-lg bg-gradient-to-br <?php echo $gradient; ?> flex items-center justify-center flex-shrink-0">
                                    <svg class="w-5 h-5 text-white/25" fill="currentColor" viewBox="0 0 20 20">
                                        <path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/>
                                    </svg>
                                </div>
                                <?php endif; ?>
                                <div class="flex-1 min-w-0">
                                    <p class="text-sm font-medium truncate group-hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($t['title']); ?></p>
                                    <p class="text-[10px] text-suno-muted"><?php echo $t['duration']; ?> &middot; <?php echo $trackDate; ?></p>
                                </div>
                                <svg class="w-4 h-4 text-suno-muted/30 group-hover:text-suno-accent2 transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                            </button>
                            <?php endforeach; ?>
                            <?php endif; ?>
                        </div>
                    </div>
                </div>
            </div>

            <!-- 샘플 사운드 업로드 -->
            <?php if($useSampleSound): ?>
            <div>
                <label class="block text-sm font-semibold mb-2 flex items-center gap-2">
                    <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z"/>
                    </svg>
                    샘플 사운드 첨부
                    <span class="text-xs text-suno-muted font-normal">(선택사항)</span>
                </label>
                <p class="text-xs text-suno-muted mb-3">프롬프트와 함께 사용할 수 있는 사운드 샘플을 첨부하세요 (MP3, WAV, OGG / 최대 10MB)</p>
                <div class="relative">
                    <label id="sampleDropzone" class="flex flex-col items-center justify-center w-full bg-suno-card border-2 border-dashed border-suno-border rounded-xl py-7 cursor-pointer hover:border-emerald-500/40 hover:bg-emerald-500/5 transition-all">
                        <div id="sampleUploadDefault" class="flex flex-col items-center gap-2">
                            <svg class="w-7 h-7 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z"/>
                            </svg>
                            <span class="text-xs text-suno-muted font-medium">클릭하거나 파일을 드래그하세요</span>
                            <span class="text-[10px] text-suno-muted/40">MP3, WAV, OGG &bull; 최대 10MB</span>
                        </div>
                        <div id="sampleUploadPreview" class="hidden flex items-center gap-3 w-full px-6">
                            <div class="w-10 h-10 rounded-lg bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
                                <svg class="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z"/>
                                </svg>
                            </div>
                            <div class="flex-1 min-w-0">
                                <p id="sampleFileName" class="text-sm text-white font-medium truncate"></p>
                                <p id="sampleFileSize" class="text-[10px] text-suno-muted"></p>
                            </div>
                            <button type="button" onclick="removeSampleFile(event)" class="text-suno-muted hover:text-red-400 transition-colors flex-shrink-0">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                            </button>
                        </div>
                        <input type="file" name="sample_file" id="sampleFileInput" accept=".mp3,.wav,.ogg,audio/mpeg,audio/wav,audio/ogg" class="absolute inset-0 w-full h-full opacity-0 cursor-pointer" onchange="handleSampleFile(this)">
                    </label>
                </div>
                <div class="mt-3">
                    <label class="block text-xs font-medium text-suno-muted mb-1.5">샘플 설명 <span class="text-suno-muted/40">(첨부 시 표시될 설명)</span></label>
                    <input type="text" name="sample_label" id="sampleLabel" placeholder="예: 피아노 멜로디 루프, 기타 리프, 808 베이스 ..."
                        class="form-input w-full bg-suno-card border border-suno-border rounded-lg px-3.5 py-2.5 text-xs text-white placeholder-suno-muted/50 focus:outline-none"
                        maxlength="50">
                </div>
            </div>
            <?php endif; ?>

            <!-- Suno Link (optional) -->
            <div>
                <label class="block text-sm font-semibold mb-2">
                    Suno 공유 링크
                    <span class="text-xs text-suno-muted font-normal ml-1">(선택사항)</span>
                </label>
                <p class="text-xs text-suno-muted mb-3">이 프롬프트로 만든 곡이 있다면 Suno 링크를 공유해주세요</p>
                <div class="relative">
                    <svg class="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-suno-muted/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/>
                    </svg>
                    <input type="url" name="suno_link" placeholder="https://suno.com/song/..."
                        class="form-input w-full bg-suno-card border border-suno-border rounded-xl pl-11 pr-4 py-3.5 text-sm text-white placeholder-suno-muted/50 focus:outline-none">
                </div>
            </div>

            <!-- Preview Section -->
            <div>
                <div class="flex items-center gap-2 mb-4">
                    <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 12a3 3 0 11-6 0 3 3 0 016 0z"/>
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M2.458 12C3.732 7.943 7.523 5 12 5c4.478 0 8.268 2.943 9.542 7-1.274 4.057-5.064 7-9.542 7-4.477 0-8.268-2.943-9.542-7z"/>
                    </svg>
                    <h3 class="text-sm font-semibold">미리보기</h3>
                </div>
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6" id="previewArea">
                    <!-- Preview Tags -->
                    <div class="flex flex-wrap items-center gap-2 mb-3" id="previewTags">
                        <span class="text-xs text-suno-muted/40 italic">태그를 선택하세요</span>
                    </div>
                    <!-- Preview Title -->
                    <h3 id="previewTitle" class="font-bold text-lg leading-snug mb-3 text-suno-muted/30 italic">제목이 여기에 표시됩니다</h3>
                    <!-- Preview Prompt -->
                    <div class="preview-block bg-suno-dark/80 border border-suno-border/50 rounded-lg p-4 mb-4">
                        <p id="previewPrompt" class="text-xs text-suno-muted/30 leading-relaxed italic whitespace-pre-wrap">프롬프트 내용이 여기에 표시됩니다</p>
                    </div>
                    <!-- Preview Footer -->
                    <div class="flex items-center justify-between pt-3 border-t border-suno-border">
                        <div class="flex items-center gap-2">
                            <div class="w-7 h-7 rounded-full bg-gradient-to-r from-suno-accent to-purple-500 flex items-center justify-center text-[10px] font-bold">
                                <?php echo $currentUser ? mb_substr($currentUser['nickname'], 0, 1) : 'U'; ?>
                            </div>
                            <span class="text-xs text-suno-muted font-medium"><?php echo $currentUser ? htmlspecialchars($currentUser['nickname']) : '사용자'; ?></span>
                        </div>
                        <div class="flex items-center gap-3 text-xs text-suno-muted/40">
                            <span class="flex items-center gap-1">
                                <svg class="w-3.5 h-3.5" fill="currentColor" viewBox="0 0 20 20">
                                    <path fill-rule="evenodd" d="M3.172 5.172a4 4 0 015.656 0L10 6.343l1.172-1.171a4 4 0 115.656 5.656L10 17.657l-6.828-6.829a4 4 0 010-5.656z" clip-rule="evenodd"/>
                                </svg>
                                0
                            </span>
                            <span class="flex items-center gap-1">
                                <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M8 16H6a2 2 0 01-2-2V6a2 2 0 012-2h8a2 2 0 012 2v2m-6 12h8a2 2 0 002-2v-8a2 2 0 00-2-2h-8a2 2 0 00-2 2v8a2 2 0 002 2z"/>
                                </svg>
                                0
                            </span>
                        </div>
                    </div>
                </div>
            </div>

            <!-- Submit / Cancel -->
            <div class="flex items-center gap-3 pt-4 border-t border-suno-border">
                <button type="submit" onclick="return handleSubmit()" class="submit-btn text-white font-semibold px-8 py-3.5 rounded-xl text-sm flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 4v16m8-8H4"/>
                    </svg>
                    공유하기
                </button>
                <a href="prompt_list.php" class="cancel-btn border border-suno-border bg-suno-card text-suno-muted font-medium px-8 py-3.5 rounded-xl text-sm inline-block text-center">
                    취소
                </a>
            </div>
        </form>
    </div>
</main>

<script>
// Slider <-> Number input sync
function syncInput(name, val) {
    val = Math.max(0, Math.min(100, parseInt(val) || 0));
    document.getElementById(name + 'Num').value = val;
}
function syncSlider(name, val) {
    val = Math.max(0, Math.min(100, parseInt(val) || 0));
    document.getElementById(name + 'Slider').value = val;
    document.getElementById(name + 'Num').value = val;
}

// Track selected tags
const selectedGenres = [];
const selectedStyles = [];
const maxTags = 3;

function toggleTag(el, type) {
    const arr = type === 'genre' ? selectedGenres : selectedStyles;
    const tag = el.dataset.tag;
    const idx = arr.indexOf(tag);

    if (idx > -1) {
        arr.splice(idx, 1);
        el.classList.remove('selected');
    } else {
        if (arr.length >= maxTags) {
            // Remove the first selected
            const container = type === 'genre' ? document.getElementById('genreTags') : document.getElementById('styleTags');
            const firstTag = arr.shift();
            container.querySelectorAll('.tag-select').forEach(btn => {
                if (btn.dataset.tag === firstTag) btn.classList.remove('selected');
            });
        }
        arr.push(tag);
        el.classList.add('selected');
    }
    updatePreviewTags();
}

function updatePreviewTags() {
    const container = document.getElementById('previewTags');
    const allTags = [...selectedGenres, ...selectedStyles];

    if (allTags.length === 0) {
        container.innerHTML = '<span class="text-xs text-suno-muted/40 italic">태그를 선택하세요</span>';
    } else {
        container.innerHTML = allTags.map(tag =>
            '<span class="text-xs px-2.5 py-0.5 rounded-full bg-suno-accent/10 text-suno-accent2 border border-suno-accent/20 font-medium">' + tag + '</span>'
        ).join('');
    }
}

function updatePreview() {
    const title = document.getElementById('promptTitle').value;
    const content = document.getElementById('promptContent').value;

    const previewTitle = document.getElementById('previewTitle');
    const previewPrompt = document.getElementById('previewPrompt');

    if (title) {
        previewTitle.textContent = title;
        previewTitle.classList.remove('text-suno-muted/30', 'italic');
        previewTitle.classList.add('text-white');
    } else {
        previewTitle.textContent = '제목이 여기에 표시됩니다';
        previewTitle.classList.add('text-suno-muted/30', 'italic');
        previewTitle.classList.remove('text-white');
    }

    if (content) {
        previewPrompt.textContent = content;
        previewPrompt.classList.remove('text-suno-muted/30', 'italic');
        previewPrompt.classList.add('text-suno-accent2/90');
    } else {
        previewPrompt.textContent = '프롬프트 내용이 여기에 표시됩니다';
        previewPrompt.classList.add('text-suno-muted/30', 'italic');
        previewPrompt.classList.remove('text-suno-accent2/90');
    }
}

function updateCharCount(elementId, input, max) {
    const el = document.getElementById(elementId);
    const len = input.value.length;
    el.textContent = len + '/' + max;

    if (len > max * 0.9) {
        el.style.color = '#ef4444';
    } else if (len > max * 0.7) {
        el.style.color = '#f59e0b';
    } else {
        el.style.color = '';
    }
}

// 완성본 곡 연결
let linkedTrackId = null;

function openTrackSelector() {
    document.getElementById('trackSelectorModal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}

function closeTrackSelector() {
    document.getElementById('trackSelectorModal').classList.add('hidden');
    document.body.style.overflow = '';
}

function selectTrack(id, title, thumb, meta, hasCover, gradient) {
    linkedTrackId = id;
    const thumbWrap = document.getElementById('linkedTrackThumbWrap');
    if (hasCover && thumb) {
        thumbWrap.innerHTML = '<img src="' + thumb + '" alt="" class="w-14 h-14 rounded-lg object-cover">';
    } else {
        thumbWrap.innerHTML = '<div class="w-14 h-14 rounded-lg bg-gradient-to-br ' + gradient + ' flex items-center justify-center">' +
            '<svg class="w-6 h-6 text-white/25" fill="currentColor" viewBox="0 0 20 20">' +
            '<path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/>' +
            '</svg></div>';
    }
    document.getElementById('linkedTrackTitle').textContent = title;
    document.getElementById('linkedTrackMeta').textContent = meta;
    document.getElementById('linkedTrackPreview').classList.remove('hidden');
    document.getElementById('selectTrackBtn').classList.add('hidden');
    closeTrackSelector();
}

function removeLinkedTrack() {
    linkedTrackId = null;
    document.getElementById('linkedTrackPreview').classList.add('hidden');
    document.getElementById('selectTrackBtn').classList.remove('hidden');
}

// ESC로 모달 닫기
document.addEventListener('keydown', e => {
    if (e.key === 'Escape') closeTrackSelector();
});

// 샘플 사운드 업로드
function handleSampleFile(input) {
    const file = input.files[0];
    if (!file) return;

    const maxSize = 10 * 1024 * 1024;
    if (file.size > maxSize) {
        alert('파일 크기가 10MB를 초과합니다.');
        input.value = '';
        return;
    }

    const validTypes = ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp3'];
    if (!validTypes.includes(file.type) && !file.name.match(/\.(mp3|wav|ogg)$/i)) {
        alert('MP3, WAV, OGG 파일만 업로드 가능합니다.');
        input.value = '';
        return;
    }

    document.getElementById('sampleUploadDefault').classList.add('hidden');
    document.getElementById('sampleUploadPreview').classList.remove('hidden');
    document.getElementById('sampleUploadPreview').classList.add('flex');
    document.getElementById('sampleFileName').textContent = file.name;
    document.getElementById('sampleFileSize').textContent = formatFileSize(file.size);
}

function removeSampleFile(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('sampleFileInput').value = '';
    document.getElementById('sampleUploadDefault').classList.remove('hidden');
    document.getElementById('sampleUploadPreview').classList.add('hidden');
    document.getElementById('sampleUploadPreview').classList.remove('flex');
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1024 * 1024) return (bytes / 1024).toFixed(1) + ' KB';
    return (bytes / (1024 * 1024)).toFixed(1) + ' MB';
}

// Drag and drop for sample
const sampleDropzone = document.getElementById('sampleDropzone');
if (sampleDropzone) {
    ['dragenter','dragover'].forEach(evt => {
        sampleDropzone.addEventListener(evt, e => {
            e.preventDefault();
            sampleDropzone.classList.add('border-emerald-500/50', 'bg-emerald-500/5');
        });
    });
    ['dragleave','drop'].forEach(evt => {
        sampleDropzone.addEventListener(evt, e => {
            e.preventDefault();
            sampleDropzone.classList.remove('border-emerald-500/50', 'bg-emerald-500/5');
        });
    });
    sampleDropzone.addEventListener('drop', e => {
        const files = e.dataTransfer.files;
        if (files.length) {
            document.getElementById('sampleFileInput').files = files;
            handleSampleFile(document.getElementById('sampleFileInput'));
        }
    });
}

function handleSubmit() {
    const title = document.getElementById('promptTitle').value.trim();
    const content = document.getElementById('promptContent').value.trim();

    if (!title) {
        alert('제목을 입력해주세요.');
        document.getElementById('promptTitle').focus();
        return false;
    }
    if (!content) {
        alert('프롬프트 내용을 입력해주세요.');
        document.getElementById('promptContent').focus();
        return false;
    }
    if (selectedGenres.length === 0) {
        alert('장르 태그를 최소 1개 선택해주세요.');
        return false;
    }

    // Populate hidden fields
    document.getElementById('hiddenGenres').value = selectedGenres.join(',');
    document.getElementById('hiddenStyles').value = selectedStyles.join(',');
    document.getElementById('hiddenLinkedTrackId').value = linkedTrackId || '';
    document.getElementById('hiddenWeirdness').value = document.getElementById('weirdnessNum').value;
    document.getElementById('hiddenStyleInfluence').value = document.getElementById('styleInflNum').value;
    document.getElementById('hiddenAudioInfluence').value = document.getElementById('audioInflNum').value;

    return true;
}
</script>

<?php include 'footer.php'; ?>
