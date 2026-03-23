<?php require_once 'db.php'; ?>
<?php
if (!$currentUser) {
    header('Location: login.php');
    exit;
}

$promptId = isset($_GET['id']) ? intval($_GET['id']) : 0;
if (!$promptId) {
    header('Location: prompt_list.php');
    exit;
}

$stmt = $pdo->prepare('SELECT * FROM prompts WHERE id = ?');
$stmt->execute([$promptId]);
$promptRow = $pdo->prepare('SELECT * FROM prompts WHERE id = ? AND user_id = ?');
$promptRow->execute([$promptId, $currentUser['id']]);
$promptRow = $promptRow->fetch();

if (!$promptRow) {
    header('Location: prompt_list.php');
    exit;
}

$gStmt = $pdo->prepare('SELECT genre FROM prompt_genres WHERE prompt_id = ?');
$gStmt->execute([$promptId]);
$existingGenres = $gStmt->fetchAll(PDO::FETCH_COLUMN);

$sStmt = $pdo->prepare('SELECT style FROM prompt_styles WHERE prompt_id = ?');
$sStmt->execute([$promptId]);
$existingStyles = $sStmt->fetchAll(PDO::FETCH_COLUMN);

$linkedTrack = null;
if (!empty($promptRow['linked_track_id'])) {
    $tStmt = $pdo->prepare('SELECT id, title, cover_image_path, duration, created_at, (SELECT genre FROM track_genres WHERE track_id = tracks.id LIMIT 1) as genre FROM tracks WHERE id = ?');
    $tStmt->execute([$promptRow['linked_track_id']]);
    $linkedTrack = $tStmt->fetch();
}
?>
<?php $pageTitle = '프롬프트 수정'; ?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<style>
    .form-input { transition: all 0.2s ease; }
    .form-input:focus { border-color: rgba(139,92,246,0.5); box-shadow: 0 0 0 3px rgba(139,92,246,0.1); }
    .tag-select { transition: all 0.2s ease; cursor: pointer; }
    .tag-select:hover { background: rgba(139,92,246,0.15); border-color: rgba(139,92,246,0.4); color: #a78bfa; }
    .tag-select.selected { background: rgba(139,92,246,0.2); border-color: #8b5cf6; color: #a78bfa; }
    .submit-btn { transition: all 0.3s ease; background: linear-gradient(135deg, #8b5cf6, #7c3aed); }
    .submit-btn:hover { background: linear-gradient(135deg, #a78bfa, #8b5cf6); box-shadow: 0 8px 30px rgba(139,92,246,0.3); transform: translateY(-1px); }
    .cancel-btn { transition: all 0.2s ease; }
    .cancel-btn:hover { background: rgba(255,255,255,0.05); border-color: rgba(255,255,255,0.2); }
    .char-count { transition: color 0.2s ease; }
    input[type="number"]::-webkit-inner-spin-button, input[type="number"]::-webkit-outer-spin-button { -webkit-appearance: none; margin: 0; }
    input[type="number"] { -moz-appearance: textfield; }
    input[type="range"] { -webkit-appearance: none; appearance: none; height: 6px; border-radius: 3px; outline: none; }
    input[type="range"]::-webkit-slider-thumb { -webkit-appearance: none; appearance: none; width: 16px; height: 16px; border-radius: 50%; background: #e11d48; cursor: pointer; border: 2px solid #1a1a2e; box-shadow: 0 0 6px rgba(225,29,72,0.3); }
    input[type="range"]::-moz-range-thumb { width: 16px; height: 16px; border-radius: 50%; background: #e11d48; cursor: pointer; border: 2px solid #1a1a2e; box-shadow: 0 0 6px rgba(225,29,72,0.3); }
</style>

<?php
$genreOptions = ['K-Pop', 'Lo-fi', 'Hip-Hop', 'R&B', 'Rock', 'Jazz', 'EDM', 'Ambient', 'Cinematic', 'Classical', 'Ballad', 'Folk', 'Reggae', 'Metal', 'Country', 'Latin'];
$styleOptions = ['Dreamy', 'Energetic', 'Chill', 'Dark', 'Uplifting', 'Melancholic', 'Retro', 'Futuristic', 'Acoustic', 'Electronic', 'Orchestral', 'Minimal'];

$myTracks = [];
$tStmt = $pdo->prepare('SELECT id, title, cover_image_path, duration, created_at, (SELECT genre FROM track_genres WHERE track_id = tracks.id LIMIT 1) as genre FROM tracks WHERE user_id = ? ORDER BY created_at DESC');
$tStmt->execute([$currentUser['id']]);
$myTracks = $tStmt->fetchAll();
?>

<main class="pt-20">
    <div class="max-w-4xl mx-auto px-6 py-8">
        <nav class="flex items-center gap-2 text-sm mb-8">
            <a href="index.php" class="text-suno-muted hover:text-white transition-colors">홈</a>
            <svg class="w-3.5 h-3.5 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
            <a href="prompt_list.php" class="text-suno-muted hover:text-white transition-colors">프롬프트</a>
            <svg class="w-3.5 h-3.5 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
            <span class="text-white/80">수정하기</span>
        </nav>

        <div class="mb-8">
            <div class="flex items-center gap-3 mb-2">
                <div class="w-10 h-10 rounded-xl bg-suno-accent/15 flex items-center justify-center">
                    <svg class="w-5 h-5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931zm0 0L19.5 7.125M18 14v4.75A2.25 2.25 0 0115.75 21H5.25A2.25 2.25 0 013 18.75V8.25A2.25 2.25 0 015.25 6H10"/>
                    </svg>
                </div>
                <div>
                    <h1 class="text-2xl font-extrabold tracking-tight">프롬프트 수정</h1>
                    <p class="text-suno-muted text-sm mt-0.5">프롬프트 내용을 수정하세요</p>
                </div>
            </div>
        </div>

        <form action="prompt_edit_ok.php" method="POST" enctype="multipart/form-data" class="space-y-8">
            <input type="hidden" name="id" value="<?php echo $promptId; ?>">
            <input type="hidden" name="genres" id="hiddenGenres" value="">
            <input type="hidden" name="styles" id="hiddenStyles" value="">
            <input type="hidden" name="linked_track_id" id="hiddenLinkedTrackId" value="<?php echo $promptRow['linked_track_id'] ?: ''; ?>">
            <input type="hidden" name="weirdness" id="hiddenWeirdness" value="<?php echo $promptRow['weirdness'] ?? 50; ?>">
            <input type="hidden" name="style_influence" id="hiddenStyleInfluence" value="<?php echo $promptRow['style_influence'] ?? 50; ?>">
            <input type="hidden" name="audio_influence" id="hiddenAudioInfluence" value="<?php echo $promptRow['audio_influence'] ?? 25; ?>">

            <!-- Title -->
            <div>
                <label class="block text-sm font-semibold mb-2">제목 <span class="text-red-400">*</span></label>
                <input type="text" name="title" id="promptTitle" placeholder="프롬프트의 제목을 입력하세요"
                    class="form-input w-full bg-suno-card border border-suno-border rounded-xl px-4 py-3.5 text-sm text-white placeholder-suno-muted/50 focus:outline-none"
                    maxlength="100" value="<?php echo htmlspecialchars($promptRow['title']); ?>"
                    oninput="updateCharCount('titleCount', this, 100);">
                <div class="flex justify-end mt-1">
                    <span id="titleCount" class="char-count text-xs text-suno-muted/50"><?php echo mb_strlen($promptRow['title']); ?>/100</span>
                </div>
            </div>

            <!-- Prompt Content -->
            <div>
                <label class="block text-sm font-semibold mb-2">프롬프트 내용 <span class="text-suno-muted/50 font-normal">(Styles)</span> <span class="text-red-400">*</span></label>
                <p class="text-xs text-suno-muted mb-3">Suno의 Styles 필드에 입력할 프롬프트를 작성하세요.</p>
                <textarea name="prompt_text" id="promptContent" placeholder="예: Dreamy K-pop ballad..."
                    class="form-input w-full bg-suno-card border border-suno-border rounded-xl px-4 py-4 text-sm text-white placeholder-suno-muted/50 focus:outline-none resize-none font-mono leading-relaxed"
                    rows="8" maxlength="2000"
                    oninput="updateCharCount('contentCount', this, 2000);"><?php echo htmlspecialchars($promptRow['prompt_text']); ?></textarea>
                <div class="flex justify-end mt-1">
                    <span id="contentCount" class="char-count text-xs text-suno-muted/50"><?php echo mb_strlen($promptRow['prompt_text']); ?>/2000</span>
                </div>
            </div>

            <!-- Exclude Styles -->
            <div>
                <label class="block text-sm font-semibold mb-2 flex items-center gap-2">Exclude Styles <span class="text-xs text-suno-muted font-normal">(선택사항)</span></label>
                <p class="text-xs text-suno-muted mb-3">제외할 스타일이 있다면 입력하세요</p>
                <input type="text" name="exclude_styles" id="excludeStyles" placeholder="예: autotune, screaming, heavy distortion"
                    class="form-input w-full bg-suno-card border border-suno-border rounded-xl px-4 py-3.5 text-sm text-rose-400/80 placeholder-suno-muted/50 focus:outline-none font-mono"
                    maxlength="500" value="<?php echo htmlspecialchars($promptRow['exclude_styles'] ?? ''); ?>">
            </div>

            <!-- Suno Parameters -->
            <div>
                <label class="block text-sm font-semibold mb-2 flex items-center gap-2">Suno 파라미터 <span class="text-xs text-suno-muted font-normal">(선택사항)</span></label>
                <div class="bg-suno-card border border-suno-border rounded-xl p-5 space-y-5">
                    <?php
                    $paramsList = [
                        ['name' => 'weirdness', 'label' => 'Weirdness', 'value' => $promptRow['weirdness'] ?? 50],
                        ['name' => 'styleInfl', 'label' => 'Style Influence', 'value' => $promptRow['style_influence'] ?? 50],
                        ['name' => 'audioInfl', 'label' => 'Audio Influence', 'value' => $promptRow['audio_influence'] ?? 25],
                    ];
                    foreach ($paramsList as $p): ?>
                    <div>
                        <div class="flex items-center justify-between mb-2">
                            <span class="text-xs font-medium text-suno-muted"><?php echo $p['label']; ?></span>
                            <div class="flex items-center gap-1">
                                <input type="number" id="<?php echo $p['name']; ?>Num" min="0" max="100" value="<?php echo $p['value']; ?>"
                                    class="w-12 bg-suno-dark border border-suno-border rounded px-1.5 py-0.5 text-xs font-mono text-rose-400/80 text-right focus:outline-none focus:border-rose-500/40"
                                    oninput="syncSlider('<?php echo $p['name']; ?>', this.value)">
                                <span class="text-xs text-rose-400/50">%</span>
                            </div>
                        </div>
                        <input type="range" id="<?php echo $p['name']; ?>Slider" min="0" max="100" value="<?php echo $p['value']; ?>" step="1"
                            class="w-full h-1.5 rounded-full appearance-none bg-suno-border/60 cursor-pointer accent-rose-500"
                            oninput="syncInput('<?php echo $p['name']; ?>', this.value)">
                    </div>
                    <?php endforeach; ?>
                </div>
            </div>

            <!-- Lyrics -->
            <div>
                <label class="block text-sm font-semibold mb-2 flex items-center gap-2">가사 <span class="text-suno-muted/50 font-normal">(Lyrics)</span> <span class="text-xs text-suno-muted font-normal">(선택사항)</span></label>
                <textarea name="lyrics" id="lyricsContent" placeholder="[Verse 1]&#10;Here comes the morning light..."
                    class="form-input w-full bg-suno-card border border-suno-border rounded-xl px-4 py-4 text-sm text-white placeholder-suno-muted/50 focus:outline-none resize-none font-mono leading-relaxed"
                    rows="8" maxlength="5000"
                    oninput="updateCharCount('lyricsCount', this, 5000);"><?php echo htmlspecialchars($promptRow['lyrics'] ?? ''); ?></textarea>
                <div class="flex justify-end mt-1">
                    <span id="lyricsCount" class="char-count text-xs text-suno-muted/50"><?php echo mb_strlen($promptRow['lyrics'] ?? ''); ?>/5000</span>
                </div>
            </div>

            <!-- Genre / Style Tags -->
            <div>
                <label class="block text-sm font-semibold mb-2">장르 태그 <span class="text-red-400">*</span></label>
                <p class="text-xs text-suno-muted mb-3">해당하는 장르를 선택하세요 (최대 3개)</p>
                <div class="flex flex-wrap gap-2 mb-6" id="genreTags">
                    <?php foreach($genreOptions as $genre): ?>
                    <button type="button" class="tag-select text-xs px-3.5 py-2 rounded-full border border-suno-border bg-suno-dark text-suno-muted font-medium <?php echo in_array($genre, $existingGenres) ? 'selected' : ''; ?>"
                            onclick="toggleTag(this, 'genre')" data-tag="<?php echo $genre; ?>">
                        <?php echo $genre; ?>
                    </button>
                    <?php endforeach; ?>
                </div>

                <label class="block text-sm font-semibold mb-2">스타일 태그</label>
                <p class="text-xs text-suno-muted mb-3">분위기나 스타일을 선택하세요 (선택사항, 최대 3개)</p>
                <div class="flex flex-wrap gap-2" id="styleTags">
                    <?php foreach($styleOptions as $style): ?>
                    <button type="button" class="tag-select text-xs px-3.5 py-2 rounded-full border border-suno-border bg-suno-dark text-suno-muted font-medium <?php echo in_array($style, $existingStyles) ? 'selected' : ''; ?>"
                            onclick="toggleTag(this, 'style')" data-tag="<?php echo $style; ?>">
                        <?php echo $style; ?>
                    </button>
                    <?php endforeach; ?>
                </div>
            </div>

            <!-- Description -->
            <div>
                <label class="block text-sm font-semibold mb-2">설명</label>
                <textarea name="description" id="promptDesc" placeholder="이 프롬프트의 특징, 사용 팁, 추천 조합 등을 자유롭게 작성해주세요..."
                    class="form-input w-full bg-suno-card border border-suno-border rounded-xl px-4 py-4 text-sm text-white placeholder-suno-muted/50 focus:outline-none resize-none leading-relaxed"
                    rows="4" maxlength="1000"
                    oninput="updateCharCount('descCount', this, 1000);"><?php echo htmlspecialchars($promptRow['description'] ?? ''); ?></textarea>
                <div class="flex justify-end mt-1">
                    <span id="descCount" class="char-count text-xs text-suno-muted/50"><?php echo mb_strlen($promptRow['description'] ?? ''); ?>/1000</span>
                </div>
            </div>

            <!-- 완성본 곡 연결 -->
            <div>
                <label class="block text-sm font-semibold mb-2 flex items-center gap-2">
                    <svg class="w-4 h-4 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M9 9l10.5-3m0 6.553v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 11-.99-3.467l2.31-.66a2.25 2.25 0 001.632-2.163zm0 0V2.25L9 5.25v10.303m0 0v3.75a2.25 2.25 0 01-1.632 2.163l-1.32.377a1.803 1.803 0 01-.99-3.467l2.31-.66A2.25 2.25 0 009 15.553z"/></svg>
                    완성본 곡 연결 <span class="text-xs text-suno-muted font-normal">(선택사항)</span>
                </label>

                <div id="linkedTrackPreview" class="<?php echo $linkedTrack ? '' : 'hidden'; ?> bg-suno-card border border-suno-border rounded-xl p-4 mb-3">
                    <div class="flex items-center gap-3">
                        <div id="linkedTrackThumbWrap" class="w-14 h-14 rounded-lg overflow-hidden flex-shrink-0 bg-suno-dark">
                            <?php if ($linkedTrack): ?>
                                <?php if (!empty($linkedTrack['cover_image_path'])): ?>
                                <img src="<?php echo htmlspecialchars($linkedTrack['cover_image_path']); ?>" alt="" class="w-14 h-14 rounded-lg object-cover">
                                <?php else: ?>
                                <div class="w-14 h-14 rounded-lg bg-gradient-to-br <?php echo getGradient($linkedTrack['id'], $linkedTrack['genre'] ?? null); ?> flex items-center justify-center">
                                    <svg class="w-6 h-6 text-white/25" fill="currentColor" viewBox="0 0 20 20"><path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/></svg>
                                </div>
                                <?php endif; ?>
                            <?php endif; ?>
                        </div>
                        <div class="flex-1 min-w-0">
                            <p id="linkedTrackTitle" class="text-sm font-bold truncate"><?php echo $linkedTrack ? htmlspecialchars($linkedTrack['title']) : ''; ?></p>
                            <p id="linkedTrackMeta" class="text-[10px] text-suno-muted mt-0.5"><?php echo $linkedTrack ? ($linkedTrack['duration'] . ' · ' . date('Y.m.d', strtotime($linkedTrack['created_at']))) : ''; ?></p>
                        </div>
                        <button type="button" onclick="removeLinkedTrack()" class="text-suno-muted hover:text-red-400 transition-colors shrink-0">
                            <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                        </button>
                    </div>
                </div>

                <button type="button" id="selectTrackBtn" onclick="openTrackSelector()" class="<?php echo $linkedTrack ? 'hidden' : ''; ?> w-full bg-suno-dark border-2 border-dashed border-suno-border rounded-xl py-6 flex flex-col items-center gap-2 hover:border-suno-accent/40 hover:bg-suno-accent/5 transition-all cursor-pointer">
                    <svg class="w-7 h-7 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M13.19 8.688a4.5 4.5 0 011.242 7.244l-4.5 4.5a4.5 4.5 0 01-6.364-6.364l1.757-1.757m9.86-2.502a4.5 4.5 0 00-6.364-6.364L4.5 8.625"/></svg>
                    <span class="text-xs text-suno-muted font-medium">내 음원에서 곡 선택하기</span>
                </button>

                <div id="trackSelectorModal" class="fixed inset-0 z-[100] hidden">
                    <div class="absolute inset-0 bg-black/70 backdrop-blur-sm" onclick="closeTrackSelector()"></div>
                    <div class="absolute top-1/2 left-1/2 -translate-x-1/2 -translate-y-1/2 w-full max-w-lg bg-suno-card border border-suno-border rounded-2xl overflow-hidden shadow-2xl">
                        <div class="flex items-center justify-between px-6 py-4 border-b border-suno-border">
                            <h3 class="font-bold text-base">내 음원에서 선택</h3>
                            <button type="button" onclick="closeTrackSelector()" class="text-suno-muted hover:text-white transition-colors">
                                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/></svg>
                            </button>
                        </div>
                        <div class="max-h-80 overflow-y-auto px-3 py-3 space-y-1">
                            <?php if(empty($myTracks)): ?>
                            <div class="text-center py-8 text-suno-muted/40 text-sm">등록된 음원이 없습니다.</div>
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
                                    <svg class="w-5 h-5 text-white/25" fill="currentColor" viewBox="0 0 20 20"><path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/></svg>
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
                    <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z"/></svg>
                    샘플 사운드 첨부 <span class="text-xs text-suno-muted font-normal">(선택사항)</span>
                </label>
                <?php if(!empty($promptRow['sample_file_path'])): ?>
                <div class="bg-suno-card border border-emerald-500/20 rounded-xl p-3 mb-3 flex items-center gap-3">
                    <div class="w-8 h-8 rounded-lg bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
                        <svg class="w-4 h-4 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z"/></svg>
                    </div>
                    <p class="text-xs text-suno-muted flex-1">현재 첨부된 샘플: <?php echo htmlspecialchars(basename($promptRow['sample_file_path'])); ?></p>
                    <label class="flex items-center gap-1.5 text-xs text-red-400 cursor-pointer">
                        <input type="checkbox" name="remove_sample" value="1" class="rounded"> 삭제
                    </label>
                </div>
                <?php endif; ?>
                <p class="text-xs text-suno-muted mb-3">새 파일을 업로드하면 기존 파일이 교체됩니다 (MP3, WAV, OGG / 최대 10MB)</p>
                <label class="flex flex-col items-center justify-center w-full bg-suno-card border-2 border-dashed border-suno-border rounded-xl py-7 cursor-pointer hover:border-emerald-500/40 hover:bg-emerald-500/5 transition-all">
                    <div id="sampleUploadDefault" class="flex flex-col items-center gap-2">
                        <svg class="w-7 h-7 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z"/></svg>
                        <span class="text-xs text-suno-muted font-medium">클릭하거나 파일을 드래그하세요</span>
                        <span class="text-[10px] text-suno-muted/40">MP3, WAV, OGG &bull; 최대 10MB</span>
                    </div>
                    <div id="sampleUploadPreview" class="hidden flex items-center gap-3 w-full px-6">
                        <div class="w-10 h-10 rounded-lg bg-emerald-500/15 flex items-center justify-center flex-shrink-0">
                            <svg class="w-5 h-5 text-emerald-400" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M19.114 5.636a9 9 0 010 12.728M16.463 8.288a5.25 5.25 0 010 7.424M6.75 8.25l4.72-4.72a.75.75 0 011.28.53v15.88a.75.75 0 01-1.28.53l-4.72-4.72H4.51c-.88 0-1.704-.507-1.938-1.354A9.01 9.01 0 012.25 12c0-.83.112-1.633.322-2.396C2.806 8.756 3.63 8.25 4.51 8.25H6.75z"/></svg>
                        </div>
                        <div class="flex-1 min-w-0">
                            <p id="sampleFileName" class="text-sm text-white font-medium truncate"></p>
                            <p id="sampleFileSize" class="text-[10px] text-suno-muted"></p>
                        </div>
                    </div>
                    <input type="file" name="sample_file" id="sampleFileInput" accept=".mp3,.wav,.ogg,audio/mpeg,audio/wav,audio/ogg" class="absolute inset-0 w-full h-full opacity-0 cursor-pointer" onchange="handleSampleFile(this)">
                </label>
                <div class="mt-3">
                    <label class="block text-xs font-medium text-suno-muted mb-1.5">샘플 설명</label>
                    <input type="text" name="sample_label" id="sampleLabel" placeholder="예: 피아노 멜로디 루프, 기타 리프 ..."
                        class="form-input w-full bg-suno-card border border-suno-border rounded-lg px-3.5 py-2.5 text-xs text-white placeholder-suno-muted/50 focus:outline-none"
                        maxlength="50" value="<?php echo htmlspecialchars($promptRow['sample_label'] ?? ''); ?>">
                </div>
            </div>
            <?php endif; ?>

            <!-- Suno Link -->
            <div>
                <label class="block text-sm font-semibold mb-2">Suno 공유 링크 <span class="text-xs text-suno-muted font-normal ml-1">(선택사항)</span></label>
                <div class="relative">
                    <svg class="absolute left-4 top-1/2 -translate-y-1/2 w-4 h-4 text-suno-muted/50" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1"/></svg>
                    <input type="url" name="suno_link" placeholder="https://suno.com/song/..."
                        class="form-input w-full bg-suno-card border border-suno-border rounded-xl pl-11 pr-4 py-3.5 text-sm text-white placeholder-suno-muted/50 focus:outline-none"
                        value="<?php echo htmlspecialchars($promptRow['suno_link'] ?? ''); ?>">
                </div>
            </div>

            <!-- Submit / Cancel -->
            <div class="flex items-center gap-3 pt-4 border-t border-suno-border">
                <button type="submit" onclick="return handleSubmit()" class="submit-btn text-white font-semibold px-8 py-3.5 rounded-xl text-sm flex items-center gap-2">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M5 13l4 4L19 7"/></svg>
                    수정하기
                </button>
                <a href="prompt_detail.php?id=<?php echo $promptId; ?>" class="cancel-btn border border-suno-border bg-suno-card text-suno-muted font-medium px-8 py-3.5 rounded-xl text-sm inline-block text-center">취소</a>
            </div>
        </form>
    </div>
</main>

<script>
function syncInput(name, val) {
    val = Math.max(0, Math.min(100, parseInt(val) || 0));
    document.getElementById(name + 'Num').value = val;
}
function syncSlider(name, val) {
    val = Math.max(0, Math.min(100, parseInt(val) || 0));
    document.getElementById(name + 'Slider').value = val;
    document.getElementById(name + 'Num').value = val;
}

const selectedGenres = <?php echo json_encode(array_values($existingGenres)); ?>;
const selectedStyles = <?php echo json_encode(array_values($existingStyles)); ?>;
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
            const container = type === 'genre' ? document.getElementById('genreTags') : document.getElementById('styleTags');
            const firstTag = arr.shift();
            container.querySelectorAll('.tag-select').forEach(btn => {
                if (btn.dataset.tag === firstTag) btn.classList.remove('selected');
            });
        }
        arr.push(tag);
        el.classList.add('selected');
    }
}

function updateCharCount(elementId, input, max) {
    const el = document.getElementById(elementId);
    const len = input.value.length;
    el.textContent = len + '/' + max;
    if (len > max * 0.9) el.style.color = '#ef4444';
    else if (len > max * 0.7) el.style.color = '#f59e0b';
    else el.style.color = '';
}

let linkedTrackId = <?php echo $promptRow['linked_track_id'] ? $promptRow['linked_track_id'] : 'null'; ?>;

function openTrackSelector() { document.getElementById('trackSelectorModal').classList.remove('hidden'); document.body.style.overflow = 'hidden'; }
function closeTrackSelector() { document.getElementById('trackSelectorModal').classList.add('hidden'); document.body.style.overflow = ''; }

function selectTrack(id, title, thumb, meta, hasCover, gradient) {
    linkedTrackId = id;
    const thumbWrap = document.getElementById('linkedTrackThumbWrap');
    if (hasCover && thumb) {
        thumbWrap.innerHTML = '<img src="' + thumb + '" alt="" class="w-14 h-14 rounded-lg object-cover">';
    } else {
        thumbWrap.innerHTML = '<div class="w-14 h-14 rounded-lg bg-gradient-to-br ' + gradient + ' flex items-center justify-center"><svg class="w-6 h-6 text-white/25" fill="currentColor" viewBox="0 0 20 20"><path d="M18 3a1 1 0 00-1.196-.98l-10 2A1 1 0 006 5v9.114A4.369 4.369 0 005 14c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V7.82l8-1.6v5.894A4.37 4.37 0 0015 12c-1.657 0-3 .895-3 2s1.343 2 3 2 3-.895 3-2V3z"/></svg></div>';
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

document.addEventListener('keydown', e => { if (e.key === 'Escape') closeTrackSelector(); });

function handleSampleFile(input) {
    const file = input.files[0];
    if (!file) return;
    if (file.size > 10 * 1024 * 1024) { alert('파일 크기가 10MB를 초과합니다.'); input.value = ''; return; }
    const validTypes = ['audio/mpeg', 'audio/wav', 'audio/ogg', 'audio/mp3'];
    if (!validTypes.includes(file.type) && !file.name.match(/\.(mp3|wav|ogg)$/i)) { alert('MP3, WAV, OGG 파일만 업로드 가능합니다.'); input.value = ''; return; }
    document.getElementById('sampleUploadDefault').classList.add('hidden');
    document.getElementById('sampleUploadPreview').classList.remove('hidden');
    document.getElementById('sampleUploadPreview').classList.add('flex');
    document.getElementById('sampleFileName').textContent = file.name;
    document.getElementById('sampleFileSize').textContent = (file.size / (1024 * 1024)).toFixed(1) + ' MB';
}

function handleSubmit() {
    const title = document.getElementById('promptTitle').value.trim();
    const content = document.getElementById('promptContent').value.trim();
    if (!title) { alert('제목을 입력해주세요.'); document.getElementById('promptTitle').focus(); return false; }
    if (!content) { alert('프롬프트 내용을 입력해주세요.'); document.getElementById('promptContent').focus(); return false; }
    if (selectedGenres.length === 0) { alert('장르 태그를 최소 1개 선택해주세요.'); return false; }

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
