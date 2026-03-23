<?php require_once 'db.php'; ?>
<?php
if (!$currentUser) {
    header('Location: login.php');
    exit;
}
?>
<?php $pageTitle = '내 음원 공유하기'; ?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<?php
// Genre and mood tags for selection
// DB에서 태그 로드 (tag_options 테이블이 없으면 기본값 사용)
$genreTags = ['K-Pop', 'Lo-fi', 'Hip-Hop', 'R&B', 'Rock', 'Jazz', 'Classical', 'EDM', 'Ambient', 'Synthwave', 'City Pop', 'Ballad', 'Folk', 'Funk', 'Cinematic', 'Country', 'Reggae', 'Metal'];
$moodTags = ['신나는', '잔잔한', '슬픈', '몽환적', '에너지틱', '로맨틱', '다크', '밝은', '레트로', '모던', '감성적', '파워풀', '힐링', '드라마틱', '그루비'];
try {
    $__tagTable = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name='tag_options'")->fetchColumn();
    if ($__tagTable) {
        $__g = $pdo->query("SELECT tag_name FROM tag_options WHERE tag_type='track_genre' AND is_active=1 ORDER BY sort_order, id")->fetchAll(PDO::FETCH_COLUMN);
        $__m = $pdo->query("SELECT tag_name FROM tag_options WHERE tag_type='track_mood' AND is_active=1 ORDER BY sort_order, id")->fetchAll(PDO::FETCH_COLUMN);
        if (!empty($__g)) $genreTags = $__g;
        if (!empty($__m)) $moodTags = $__m;
    }
} catch (Exception $e) {}

$uploadError = $_GET['error'] ?? '';
$phpMaxUpload = ini_get('upload_max_filesize');
$errorMessages = [
    'no_source' => 'Suno 공유 링크를 입력하거나, 음원 파일을 업로드해주세요. (최소 하나 필수)',
    'empty_title' => '곡 제목을 입력해주세요.',
    'audio_size' => '현재 서버의 업로드 제한이 ' . $phpMaxUpload . '입니다. 서버를 php -S localhost:8000 -c php.ini 로 재시작해주세요.',
    'audio_type' => 'MP3, WAV, OGG, FLAC 파일만 업로드할 수 있습니다.',
    'audio_upload_failed' => '음원 파일 업로드에 실패했습니다. 다시 시도해주세요.',
    'image_size' => '커버 이미지는 5MB 이하만 가능합니다.',
    'image_type' => '이미지 형식(JPG, PNG, WEBP, GIF)만 업로드할 수 있습니다.',
    'db' => '저장 중 오류가 발생했습니다. 다시 시도해주세요.',
];

// 이전 입력값 복원 (에러 시 세션에서 가져오기)
$savedData = $_SESSION['music_upload_data'] ?? [];
unset($_SESSION['music_upload_data']);
$oldTitle       = htmlspecialchars($savedData['title'] ?? '', ENT_QUOTES);
$oldDescription = htmlspecialchars($savedData['description'] ?? '', ENT_QUOTES);
$oldSunoLink    = htmlspecialchars($savedData['suno_link'] ?? '', ENT_QUOTES);
$oldGenres      = $savedData['genres'] ?? '';
$oldMoods       = $savedData['moods'] ?? '';
?>

<style>
    .tag-selectable {
        transition: all 0.2s ease;
        cursor: pointer;
    }
    .tag-selectable:hover {
        border-color: rgba(139, 92, 246, 0.4);
        color: #a78bfa;
    }
    .tag-selectable.selected {
        background: rgba(139, 92, 246, 0.15);
        border-color: rgba(139, 92, 246, 0.5);
        color: #a78bfa;
    }
    .upload-panel {
        max-height: 0;
        overflow: hidden;
        opacity: 0;
        transition: max-height 0.35s ease, opacity 0.25s ease, margin 0.35s ease;
        margin-bottom: 0;
    }
    .upload-panel.open {
        max-height: 500px;
        opacity: 1;
        margin-bottom: 1.5rem;
    }
    .check-option {
        transition: all 0.2s ease;
        cursor: pointer;
    }
    .check-option:hover {
        border-color: rgba(139, 92, 246, 0.3);
    }
    .check-option.checked {
        background: rgba(139, 92, 246, 0.08);
        border-color: rgba(139, 92, 246, 0.4);
    }
    .custom-check {
        appearance: none;
        -webkit-appearance: none;
        width: 18px;
        height: 18px;
        border: 2px solid #333;
        border-radius: 4px;
        background: #0d0d0d;
        cursor: pointer;
        position: relative;
        flex-shrink: 0;
        transition: all 0.15s ease;
    }
    .custom-check:checked {
        background: #8b5cf6;
        border-color: #8b5cf6;
    }
    .custom-check:checked::after {
        content: '';
        position: absolute;
        top: 2px;
        left: 5px;
        width: 5px;
        height: 9px;
        border: solid white;
        border-width: 0 2px 2px 0;
        transform: rotate(45deg);
    }
    .drop-zone {
        transition: all 0.3s ease;
    }
    .drop-zone.dragover {
        border-color: #8b5cf6;
        background: rgba(139, 92, 246, 0.05);
    }
    .audio-drop-zone {
        transition: all 0.3s ease;
    }
    .audio-drop-zone.dragover {
        border-color: #8b5cf6;
        background: rgba(139, 92, 246, 0.05);
    }
    .form-input {
        transition: border-color 0.2s ease;
    }
    .form-input:focus {
        border-color: rgba(139, 92, 246, 0.5);
        outline: none;
    }
</style>

<!-- Page Content -->
<main class="pt-20 min-h-screen">

    <!-- Page Header -->
    <section class="py-8 border-b border-suno-border bg-suno-surface/30">
        <div class="max-w-7xl mx-auto px-6">
            <div class="flex items-center gap-3 mb-2">
                <a href="music_list.php" class="text-suno-muted hover:text-white transition-colors">
                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/>
                    </svg>
                </a>
                <h1 class="text-2xl font-extrabold">내 음원 공유하기</h1>
            </div>
            <p class="text-suno-muted text-sm ml-8">Suno AI로 만든 음악을 커뮤니티에 공유해보세요</p>
        </div>
    </section>

    <!-- Upload Form -->
    <section class="py-10">
        <div class="max-w-3xl mx-auto px-6">
            <?php if ($uploadError && isset($errorMessages[$uploadError])): ?>
            <div class="mb-6 p-4 bg-red-500/10 border border-red-500/30 rounded-xl text-sm text-red-400 flex items-center gap-2">
                <svg class="w-5 h-5 flex-shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 8v4m0 4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/></svg>
                <?php echo htmlspecialchars($errorMessages[$uploadError]); ?>
            </div>
            <?php endif; ?>

            <form action="music_upload_ok.php" method="POST" enctype="multipart/form-data" id="uploadForm">
                <input type="hidden" name="genres" id="genresInput">
                <input type="hidden" name="moods" id="moodsInput">

                <!-- Step Indicator -->
                <div class="flex items-center gap-3 mb-10">
                    <div class="flex items-center gap-2">
                        <div class="w-7 h-7 rounded-full bg-suno-accent text-white text-xs font-bold flex items-center justify-center">1</div>
                        <span class="text-sm font-medium">기본 정보</span>
                    </div>
                    <div class="flex-1 h-px bg-suno-border"></div>
                    <div class="flex items-center gap-2">
                        <div class="w-7 h-7 rounded-full bg-suno-surface border border-suno-border text-suno-muted text-xs font-bold flex items-center justify-center">2</div>
                        <span class="text-sm text-suno-muted">상세 정보</span>
                    </div>
                    <div class="flex-1 h-px bg-suno-border"></div>
                    <div class="flex items-center gap-2">
                        <div class="w-7 h-7 rounded-full bg-suno-surface border border-suno-border text-suno-muted text-xs font-bold flex items-center justify-center">3</div>
                        <span class="text-sm text-suno-muted">완료</span>
                    </div>
                </div>

                <!-- 음원 등록 방식 선택 -->
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6 mb-6">
                    <label class="block text-sm font-bold mb-1">음원 등록 방식</label>
                    <p class="text-xs text-suno-muted mb-4">하나 이상 선택해주세요. 둘 다 등록할 수도 있습니다.</p>

                    <div class="space-y-3">
                        <!-- Suno 링크 체크 -->
                        <label class="check-option flex items-center gap-3 border border-suno-border bg-suno-surface rounded-xl px-4 py-3.5" id="opt-suno" onclick="toggleOption('suno')">
                            <input type="checkbox" id="check-suno" class="custom-check" onchange="togglePanel('suno')">
                            <div class="w-7 h-7 bg-suno-accent/10 border border-suno-accent/20 rounded-lg flex items-center justify-center flex-shrink-0">
                                <svg class="w-3.5 h-3.5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244"/>
                                </svg>
                            </div>
                            <div>
                                <p class="text-sm font-semibold">Suno 공유 링크</p>
                                <p class="text-[11px] text-suno-muted">링크를 붙여넣으면 Suno에서 재생됩니다</p>
                            </div>
                        </label>

                        <!-- 직접 업로드 체크 -->
                        <label class="check-option flex items-center gap-3 border border-suno-border bg-suno-surface rounded-xl px-4 py-3.5" id="opt-direct" onclick="toggleOption('direct')">
                            <input type="checkbox" id="check-direct" class="custom-check" onchange="togglePanel('direct')">
                            <div class="w-7 h-7 bg-suno-accent/10 border border-suno-accent/20 rounded-lg flex items-center justify-center flex-shrink-0">
                                <svg class="w-3.5 h-3.5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                                </svg>
                            </div>
                            <div>
                                <p class="text-sm font-semibold">음원 파일 직접 업로드</p>
                                <p class="text-[11px] text-suno-muted">파일을 올리면 사이트에서 바로 재생됩니다</p>
                            </div>
                        </label>
                    </div>

                    <!-- Validation message -->
                    <p id="uploadValidationMsg" class="text-[11px] text-suno-accent mt-3 flex items-center gap-1.5">
                        <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                        </svg>
                        최소 하나를 선택해주세요
                    </p>
                </div>

                <!-- Suno 링크 패널 (동적) -->
                <div id="panel-suno" class="upload-panel">
                    <div class="bg-suno-card border border-suno-border rounded-2xl p-6">
                        <div class="flex items-center gap-2 mb-4">
                            <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m13.35-.622l1.757-1.757a4.5 4.5 0 00-6.364-6.364l-4.5 4.5a4.5 4.5 0 001.242 7.244"/>
                            </svg>
                            <h3 class="text-sm font-bold">Suno 공유 링크</h3>
                        </div>
                        <div class="relative">
                            <div class="absolute left-4 top-1/2 -translate-y-1/2 text-suno-muted/40">
                                <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.5 6H5.25A2.25 2.25 0 003 8.25v10.5A2.25 2.25 0 005.25 21h10.5A2.25 2.25 0 0018 18.75V10.5m-10.5 6L21 3m0 0h-5.25M21 3v5.25"/>
                                </svg>
                            </div>
                            <input type="url" name="suno_link" id="sunoLinkInput" placeholder="https://suno.com/song/..." value="<?php echo $oldSunoLink; ?>"
                                class="form-input w-full bg-suno-dark border border-suno-border rounded-xl pl-11 pr-4 py-3.5 text-sm text-white placeholder-suno-muted/40 focus:border-suno-accent/50">
                        </div>
                        <p class="text-[11px] text-suno-muted/50 mt-2 flex items-center gap-1">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                            </svg>
                            Suno 앱 > 곡 페이지 > 공유 버튼 > 링크 복사
                        </p>
                    </div>
                </div>

                <!-- 직접 업로드 패널 (동적) -->
                <div id="panel-direct" class="upload-panel">
                    <div class="bg-suno-card border border-suno-border rounded-2xl p-6">
                        <div class="flex items-center gap-2 mb-4">
                            <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                            </svg>
                            <h3 class="text-sm font-bold">음원 파일 업로드</h3>
                        </div>

                        <div id="audioDropZone" class="audio-drop-zone border-2 border-dashed border-suno-border rounded-xl p-8 text-center cursor-pointer hover:border-suno-accent/40"
                             ondragover="handleAudioDragOver(event)" ondragleave="handleAudioDragLeave(event)" ondrop="handleAudioDrop(event)" onclick="document.getElementById('audioFileInput').click()">
                            <input type="file" id="audioFileInput" name="audio_file" accept=".mp3,.wav,.ogg,.flac" class="hidden" onchange="handleAudioFileSelect(event)">

                            <div id="audioUploadPlaceholder">
                                <div class="w-14 h-14 mx-auto mb-4 bg-suno-surface border border-suno-border rounded-xl flex items-center justify-center">
                                    <svg class="w-6 h-6 text-suno-muted/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/>
                                    </svg>
                                </div>
                                <p class="text-sm text-suno-muted mb-1">음원 파일을 드래그하거나 클릭해서 업로드</p>
                                <p class="text-xs text-suno-muted/40">MP3, WAV, OGG, FLAC (최대 50MB)</p>
                            </div>

                            <div id="audioUploadPreview" class="hidden">
                                <div class="w-14 h-14 mx-auto mb-3 bg-suno-accent/10 border border-suno-accent/20 rounded-xl flex items-center justify-center">
                                    <svg class="w-6 h-6 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/>
                                    </svg>
                                </div>
                                <p id="audioFileName" class="text-sm text-white font-medium"></p>
                                <p id="audioFileSize" class="text-xs text-suno-muted mt-0.5"></p>
                                <button type="button" onclick="removeAudioFile(event)" class="text-xs text-red-400 hover:text-red-300 mt-2 transition-colors">
                                    삭제
                                </button>
                            </div>
                        </div>
                        <p class="text-[11px] text-suno-muted/50 mt-2 flex items-center gap-1">
                            <svg class="w-3 h-3" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13 16h-1v-4h-1m1-4h.01M21 12a9 9 0 11-18 0 9 9 0 0118 0z"/>
                            </svg>
                            직접 업로드하면 사이트 내에서 바로 재생할 수 있습니다
                        </p>
                    </div>
                </div>

                <!-- Song Title -->
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6 mb-6">
                    <label class="block text-sm font-bold mb-3">
                        곡 제목
                        <span class="text-suno-accent text-xs ml-1">*</span>
                    </label>
                    <input type="text" name="title" placeholder="곡 제목을 입력하세요" value="<?php echo $oldTitle; ?>"
                        class="form-input w-full bg-suno-dark border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/40 focus:border-suno-accent/50" required>
                </div>

                <!-- Description -->
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6 mb-6">
                    <label class="block text-sm font-bold mb-3">
                        설명
                        <span class="text-xs text-suno-muted font-normal ml-1">(선택)</span>
                    </label>
                    <textarea name="description" rows="4" placeholder="이 곡에 대한 설명, 제작 의도, 특징 등을 자유롭게 작성해주세요..."
                        class="form-input w-full bg-suno-dark border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/40 focus:border-suno-accent/50 resize-none"><?php echo $oldDescription; ?></textarea>
                    <p class="text-right text-[11px] text-suno-muted/40 mt-1">0 / 500</p>
                </div>

                <!-- Genre Tags -->
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6 mb-6">
                    <label class="block text-sm font-bold mb-1">장르</label>
                    <p class="text-xs text-suno-muted mb-4">해당하는 장르를 선택하세요 (최대 3개)</p>
                    <div class="flex flex-wrap gap-2">
                        <?php foreach ($genreTags as $genre): ?>
                        <button type="button" class="tag-selectable border border-suno-border bg-suno-surface px-3.5 py-1.5 rounded-full text-xs text-suno-muted" onclick="toggleTag(this, 'genre')">
                            <?php echo $genre; ?>
                        </button>
                        <?php endforeach; ?>
                    </div>
                </div>

                <!-- Mood Tags -->
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6 mb-6">
                    <label class="block text-sm font-bold mb-1">분위기</label>
                    <p class="text-xs text-suno-muted mb-4">곡의 분위기를 선택하세요 (최대 3개)</p>
                    <div class="flex flex-wrap gap-2">
                        <?php foreach ($moodTags as $mood): ?>
                        <button type="button" class="tag-selectable border border-suno-border bg-suno-surface px-3.5 py-1.5 rounded-full text-xs text-suno-muted" onclick="toggleTag(this, 'mood')">
                            <?php echo $mood; ?>
                        </button>
                        <?php endforeach; ?>
                    </div>
                </div>

                <!-- Prompt 연결 -->
                <input type="hidden" name="linked_prompt_id" id="linkedPromptIdInput" value="">
                <div class="bg-suno-card border border-suno-accent/15 rounded-2xl p-6 mb-6">
                    <div class="flex items-center gap-2 mb-3">
                        <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/>
                        </svg>
                        <h3 class="text-sm font-bold">프롬프트 연결</h3>
                        <span class="text-xs text-suno-muted font-normal">(선택사항)</span>
                    </div>
                    <p class="text-xs text-suno-muted mb-4">이 음원을 만든 프롬프트가 있다면 연결할 수 있습니다.</p>

                    <!-- 연결된 프롬프트 미리보기 -->
                    <div id="linkedPromptPreview" class="hidden bg-suno-dark border border-suno-border rounded-xl p-4 mb-3">
                        <div class="flex items-center gap-3">
                            <div class="w-9 h-9 bg-suno-accent/10 border border-suno-accent/20 rounded-lg flex items-center justify-center flex-shrink-0">
                                <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/>
                                </svg>
                            </div>
                            <div class="flex-1 min-w-0">
                                <p id="linkedPromptTitle" class="text-sm font-bold truncate"></p>
                                <p id="linkedPromptMeta" class="text-[10px] text-suno-muted mt-0.5"></p>
                            </div>
                            <button type="button" onclick="removeLinkedPrompt()" class="text-suno-muted hover:text-red-400 transition-colors shrink-0">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                            </button>
                        </div>
                    </div>

                    <!-- 프롬프트 선택 버튼 -->
                    <button type="button" id="selectPromptBtn" onclick="openPromptSelector()" class="w-full bg-suno-dark border-2 border-dashed border-suno-border rounded-xl py-5 flex flex-col items-center gap-2 hover:border-suno-accent/40 hover:bg-suno-accent/5 transition-all cursor-pointer">
                        <svg class="w-6 h-6 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.86-2.502a4.5 4.5 0 00-6.364-6.364L4.5 8.625"/>
                        </svg>
                        <span class="text-xs text-suno-muted font-medium">내 프롬프트에서 선택하기</span>
                    </button>

                    <!-- 프롬프트 선택 모달 -->
                    <div id="promptSelectorModal" class="fixed inset-0 z-[100] hidden">
                        <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" onclick="closePromptSelector()"></div>
                        <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg bg-suno-card border border-suno-border rounded-2xl overflow-hidden shadow-2xl">
                            <div class="flex items-center justify-between px-6 py-4 border-b border-suno-border">
                                <h3 class="font-bold text-base">내 프롬프트에서 선택</h3>
                                <button type="button" onclick="closePromptSelector()" class="text-suno-muted hover:text-white transition-colors">
                                    <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                                </button>
                            </div>
                            <div class="max-h-80 overflow-y-auto px-3 py-3 space-y-1">
                                <?php
                                $myPrompts = [];
                                if ($currentUser) {
                                    $mpStmt = $pdo->prepare('SELECT id, title, like_count, created_at FROM prompts WHERE user_id = ? ORDER BY created_at DESC');
                                    $mpStmt->execute([$currentUser['id']]);
                                    $myPrompts = $mpStmt->fetchAll();
                                }
                                if (empty($myPrompts)): ?>
                                <div class="text-center py-8 text-suno-muted/40 text-sm">
                                    <?php if (!$currentUser): ?>
                                    로그인 후 이용 가능합니다.
                                    <?php else: ?>
                                    등록된 프롬프트가 없습니다.
                                    <?php endif; ?>
                                </div>
                                <?php else: ?>
                                <?php foreach($myPrompts as $mp):
                                    $mpDate = date('Y.m.d', strtotime($mp['created_at']));
                                ?>
                                <button type="button" onclick="selectPrompt(<?php echo $mp['id']; ?>, '<?php echo htmlspecialchars(addslashes($mp['title']), ENT_QUOTES); ?>', '<?php echo $mpDate; ?>')" class="w-full flex items-center gap-3 p-3 rounded-xl hover:bg-suno-hover transition-all text-left group">
                                    <div class="w-9 h-9 bg-suno-accent/10 border border-suno-accent/20 rounded-lg flex items-center justify-center flex-shrink-0">
                                        <svg class="w-4 h-4 text-suno-accent/60" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9.813 15.904L9 18.75l-.813-2.846a4.5 4.5 0 00-3.09-3.09L2.25 12l2.846-.813a4.5 4.5 0 003.09-3.09L9 5.25l.813 2.846a4.5 4.5 0 003.09 3.09L15.75 12l-2.846.813a4.5 4.5 0 00-3.09 3.09z"/>
                                        </svg>
                                    </div>
                                    <div class="flex-1 min-w-0">
                                        <p class="text-sm font-medium truncate group-hover:text-suno-accent2 transition-colors"><?php echo htmlspecialchars($mp['title']); ?></p>
                                        <p class="text-[10px] text-suno-muted"><?php echo $mpDate; ?> &middot; 좋아요 <?php echo $mp['like_count']; ?></p>
                                    </div>
                                    <svg class="w-4 h-4 text-suno-muted/30 group-hover:text-suno-accent2 transition-colors shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                                </button>
                                <?php endforeach; ?>
                                <?php endif; ?>
                            </div>
                        </div>
                    </div>
                </div>

                <!-- Cover Image Upload -->
                <div class="bg-suno-card border border-suno-border rounded-2xl p-6 mb-8">
                    <label class="block text-sm font-bold mb-1">
                        커버 이미지
                        <span class="text-xs text-suno-muted font-normal ml-1">(선택)</span>
                    </label>
                    <p class="text-xs text-suno-muted mb-4">곡을 대표할 커버 이미지를 업로드하세요</p>

                    <div id="dropZone" class="drop-zone border-2 border-dashed border-suno-border rounded-xl p-10 text-center cursor-pointer hover:border-suno-accent/40"
                         ondragover="handleDragOver(event)" ondragleave="handleDragLeave(event)" ondrop="handleDrop(event)" onclick="document.getElementById('fileInput').click()">
                        <input type="file" id="fileInput" name="cover_image" accept="image/*" class="hidden" onchange="handleFileSelect(event)">

                        <div id="uploadPlaceholder">
                            <div class="w-14 h-14 mx-auto mb-4 bg-suno-surface border border-suno-border rounded-xl flex items-center justify-center">
                                <svg class="w-6 h-6 text-suno-muted/50" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M2.25 15.75l5.159-5.159a2.25 2.25 0 013.182 0l5.159 5.159m-1.5-1.5l1.409-1.409a2.25 2.25 0 013.182 0l2.909 2.909M3.75 21h16.5A2.25 2.25 0 0022.5 18.75V5.25A2.25 2.25 0 0020.25 3H3.75A2.25 2.25 0 001.5 5.25v13.5A2.25 2.25 0 003.75 21z"/>
                                </svg>
                            </div>
                            <p class="text-sm text-suno-muted mb-1">이미지를 드래그하거나 클릭해서 업로드</p>
                            <p class="text-xs text-suno-muted/40">PNG, JPG, WEBP (최대 5MB)</p>
                        </div>

                        <div id="uploadPreview" class="hidden">
                            <div class="w-32 h-32 mx-auto mb-3 bg-suno-surface rounded-xl overflow-hidden">
                                <img id="previewImage" src="" alt="Preview" class="w-full h-full object-cover">
                            </div>
                            <p id="fileName" class="text-sm text-white font-medium"></p>
                            <button type="button" onclick="removeFile(event)" class="text-xs text-red-400 hover:text-red-300 mt-2 transition-colors">
                                삭제
                            </button>
                        </div>
                    </div>
                </div>

                <!-- Submit / Cancel -->
                <div class="flex items-center justify-end gap-3 pb-16">
                    <a href="music_list.php" class="border border-suno-border hover:border-suno-accent/30 bg-suno-card text-suno-muted hover:text-white font-medium px-6 py-3 rounded-xl transition-all text-sm">
                        취소
                    </a>
                    <button type="submit" class="bg-suno-accent hover:bg-suno-accent2 text-white font-semibold px-8 py-3 rounded-xl transition-all text-sm flex items-center gap-2">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M7 16a4 4 0 01-.88-7.903A5 5 0 1115.9 6L16 6a5 5 0 011 9.9M15 13l-3-3m0 0l-3 3m3-3v12"/>
                        </svg>
                        음원 공유하기
                    </button>
                </div>
            </form>
        </div>
    </section>

</main>

<script>
// Panel toggle via checkbox
function toggleOption(type) {
    // Let the checkbox change event handle it naturally
}

function togglePanel(type) {
    const panel = document.getElementById(type === 'suno' ? 'panel-suno' : 'panel-direct');
    const checkbox = document.getElementById(type === 'suno' ? 'check-suno' : 'check-direct');
    const opt = document.getElementById(type === 'suno' ? 'opt-suno' : 'opt-direct');

    if (checkbox.checked) {
        panel.classList.add('open');
        opt.classList.add('checked');
    } else {
        panel.classList.remove('open');
        opt.classList.remove('checked');
        // Clear content when unchecking
        if (type === 'suno') {
            document.getElementById('sunoLinkInput').value = '';
        } else {
            removeAudioFileQuiet();
        }
    }
    updateValidationMsg();
}

function updateValidationMsg() {
    const sunoChecked = document.getElementById('check-suno').checked;
    const directChecked = document.getElementById('check-direct').checked;
    const msg = document.getElementById('uploadValidationMsg');
    if (sunoChecked || directChecked) {
        msg.classList.add('hidden');
    } else {
        msg.classList.remove('hidden');
    }
}

function checkUploadValidation() {
    const sunoChecked = document.getElementById('check-suno').checked;
    const directChecked = document.getElementById('check-direct').checked;
    if (!sunoChecked && !directChecked) return false;
    if (sunoChecked) {
        const link = document.getElementById('sunoLinkInput').value.trim();
        if (!link) {
            alert('Suno 공유 링크를 입력해주세요.');
            return false;
        }
    }
    if (directChecked && !hasAudioFile) {
        alert('음원 파일을 업로드해주세요.');
        return false;
    }
    return true;
}

// Audio file upload
let hasAudioFile = false;
function handleAudioDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('audioDropZone').classList.add('dragover');
}

function handleAudioDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('audioDropZone').classList.remove('dragover');
}

function handleAudioDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('audioDropZone').classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        // 파일 인풋에 드래그한 파일 설정 (폼 제출 시 전송되도록)
        document.getElementById('audioFileInput').files = files;
        showAudioPreview(files[0]);
    }
}

function handleAudioFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) showAudioPreview(files[0]);
}

function showAudioPreview(file) {
    const validTypes = ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/flac', 'audio/x-wav'];
    if (!validTypes.includes(file.type) && !file.name.match(/\.(mp3|wav|ogg|flac)$/i)) {
        alert('MP3, WAV, OGG, FLAC 파일만 업로드할 수 있습니다.');
        return;
    }
    if (file.size > 50 * 1024 * 1024) {
        alert('파일 크기는 50MB를 초과할 수 없습니다.');
        return;
    }
    document.getElementById('audioFileName').textContent = file.name;
    document.getElementById('audioFileSize').textContent = formatFileSizeUpload(file.size);
    document.getElementById('audioUploadPlaceholder').classList.add('hidden');
    document.getElementById('audioUploadPreview').classList.remove('hidden');
    hasAudioFile = true;
}

function removeAudioFile(e) {
    e.stopPropagation();
    removeAudioFileQuiet();
}

function removeAudioFileQuiet() {
    document.getElementById('audioFileInput').value = '';
    document.getElementById('audioUploadPlaceholder').classList.remove('hidden');
    document.getElementById('audioUploadPreview').classList.add('hidden');
    hasAudioFile = false;
}

function formatFileSizeUpload(bytes) {
    if (bytes === 0) return '0 Bytes';
    const k = 1024;
    const sizes = ['Bytes', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
}

// Tag selection
const selectedGenres = new Set();
const selectedMoods = new Set();

function toggleTag(el, type) {
    const set = type === 'genre' ? selectedGenres : selectedMoods;
    const tagText = el.textContent.trim();

    if (el.classList.contains('selected')) {
        el.classList.remove('selected');
        set.delete(tagText);
    } else {
        if (set.size >= 3) {
            alert('최대 3개까지 선택할 수 있습니다.');
            return;
        }
        el.classList.add('selected');
        set.add(tagText);
    }
}

// Drag and drop
function handleDragOver(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('dropZone').classList.add('dragover');
}

function handleDragLeave(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('dropZone').classList.remove('dragover');
}

function handleDrop(e) {
    e.preventDefault();
    e.stopPropagation();
    document.getElementById('dropZone').classList.remove('dragover');
    const files = e.dataTransfer.files;
    if (files.length > 0) {
        document.getElementById('fileInput').files = files;
        showPreview(files[0]);
    }
}

function handleFileSelect(e) {
    const files = e.target.files;
    if (files.length > 0) {
        showPreview(files[0]);
    }
}

function showPreview(file) {
    if (!file.type.startsWith('image/')) {
        alert('이미지 파일만 업로드할 수 있습니다.');
        return;
    }
    if (file.size > 5 * 1024 * 1024) {
        alert('파일 크기는 5MB를 초과할 수 없습니다.');
        return;
    }

    const reader = new FileReader();
    reader.onload = function(e) {
        document.getElementById('previewImage').src = e.target.result;
        document.getElementById('fileName').textContent = file.name;
        document.getElementById('uploadPlaceholder').classList.add('hidden');
        document.getElementById('uploadPreview').classList.remove('hidden');
    };
    reader.readAsDataURL(file);
}

function removeFile(e) {
    e.stopPropagation();
    document.getElementById('fileInput').value = '';
    document.getElementById('uploadPlaceholder').classList.remove('hidden');
    document.getElementById('uploadPreview').classList.add('hidden');
}

// Form submit
document.getElementById('uploadForm').addEventListener('submit', function(e) {
    e.preventDefault();

    const sunoChecked = document.getElementById('check-suno').checked;
    const directChecked = document.getElementById('check-direct').checked;

    if (!sunoChecked && !directChecked) {
        alert('음원 등록 방식을 최소 하나 선택해주세요.');
        return;
    }
    if (!checkUploadValidation()) {
        return;
    }

    // Populate hidden fields with selected genres and moods
    document.getElementById('genresInput').value = Array.from(selectedGenres).join(',');
    document.getElementById('moodsInput').value = Array.from(selectedMoods).join(',');

    // Submit the form
    this.submit();
});

// ── 프롬프트 연결 ──
function openPromptSelector() {
    document.getElementById('promptSelectorModal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
}
function closePromptSelector() {
    document.getElementById('promptSelectorModal').classList.add('hidden');
    document.body.style.overflow = '';
}
function selectPrompt(id, title, date) {
    document.getElementById('linkedPromptIdInput').value = id;
    document.getElementById('linkedPromptTitle').textContent = title;
    document.getElementById('linkedPromptMeta').textContent = date;
    document.getElementById('linkedPromptPreview').classList.remove('hidden');
    document.getElementById('selectPromptBtn').classList.add('hidden');
    closePromptSelector();
}
function removeLinkedPrompt() {
    document.getElementById('linkedPromptIdInput').value = '';
    document.getElementById('linkedPromptPreview').classList.add('hidden');
    document.getElementById('selectPromptBtn').classList.remove('hidden');
}
document.addEventListener('keydown', function(e) {
    if (e.key === 'Escape') closePromptSelector();
});

// Character count for description
const descTextarea = document.querySelector('textarea[name="description"]');
if (descTextarea) {
    descTextarea.addEventListener('input', function() {
        const count = this.value.length;
        const counter = this.parentElement.querySelector('p:last-child');
        if (counter) {
            counter.textContent = count + ' / 500';
            if (count > 500) {
                counter.classList.add('text-red-400');
            } else {
                counter.classList.remove('text-red-400');
            }
        }
    });
    // 초기 글자수 표시
    if (descTextarea.value.length > 0) {
        const counter = descTextarea.parentElement.querySelector('p:last-child');
        if (counter) counter.textContent = descTextarea.value.length + ' / 500';
    }
}

// ── 이전 입력값 복원 (에러 후 돌아왔을 때) ──
(function restoreSavedData() {
    const savedGenres = <?php echo json_encode($oldGenres); ?>;
    const savedMoods = <?php echo json_encode($oldMoods); ?>;
    const savedSunoLink = <?php echo json_encode($savedData['suno_link'] ?? ''); ?>;

    // Suno 링크가 있으면 패널 열기
    if (savedSunoLink) {
        const checkSuno = document.getElementById('check-suno');
        checkSuno.checked = true;
        togglePanel('suno');
    }

    // 장르 태그 복원
    if (savedGenres) {
        const genreList = savedGenres.split(',').map(s => s.trim()).filter(Boolean);
        document.querySelectorAll('.tag-selectable').forEach(function(el) {
            const tagText = el.textContent.trim();
            if (el.closest('.bg-suno-card') && el.closest('.bg-suno-card').querySelector('.text-sm.font-bold')?.textContent.includes('장르')) {
                if (genreList.includes(tagText)) {
                    el.classList.add('selected');
                    selectedGenres.add(tagText);
                }
            }
        });
    }

    // 분위기 태그 복원
    if (savedMoods) {
        const moodList = savedMoods.split(',').map(s => s.trim()).filter(Boolean);
        document.querySelectorAll('.tag-selectable').forEach(function(el) {
            const tagText = el.textContent.trim();
            if (el.closest('.bg-suno-card') && el.closest('.bg-suno-card').querySelector('.text-sm.font-bold')?.textContent.includes('분위기')) {
                if (moodList.includes(tagText)) {
                    el.classList.add('selected');
                    selectedMoods.add(tagText);
                }
            }
        });
    }
})();
</script>

<?php include 'footer.php'; ?>
