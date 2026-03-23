<?php
// 푸터 설정 로드
$_footerCompany = getSiteSetting($pdo, 'footer', 'company_name', 'SUNO Community');
$_footerCeo = getSiteSetting($pdo, 'footer', 'ceo_name', '김수노');
$_footerBizNum = getSiteSetting($pdo, 'footer', 'business_number', '485-12-01987');
$_footerTelecom = getSiteSetting($pdo, 'footer', 'telecom_number', '2025-서울마포-03821');
$_footerAddress = getSiteSetting($pdo, 'footer', 'address', '서울특별시 마포구 양화로 127, 7층 701호');
$_footerPhone = getSiteSetting($pdo, 'footer', 'phone', '02-6247-7203');
$_footerEmail = getSiteSetting($pdo, 'footer', 'email', 'admin@sunocommunity.kr');
$_footerKakao = getSiteSetting($pdo, 'footer', 'kakao_url', '');
$_footerDesc = getSiteSetting($pdo, 'footer', 'description', '');
$_footerCopyright = getSiteSetting($pdo, 'footer', 'copyright', '© 2026 SUNO Community. All rights reserved.');

// 활성 페이지 목록 로드
$_footerPages = [];
try {
    $tableCheck = $pdo->query("SELECT name FROM sqlite_master WHERE type='table' AND name='site_pages'")->fetchColumn();
    if ($tableCheck) {
        $_footerPages = $pdo->query("SELECT slug, title FROM site_pages WHERE is_active = 1 ORDER BY id")->fetchAll();
    }
} catch (Exception $e) {
    $_footerPages = [];
}
?>
<!-- Footer -->
<footer class="border-t border-suno-border bg-suno-surface/30">
    <div class="max-w-7xl mx-auto px-6">

        <!-- 상단 링크 -->
        <?php if (!empty($_footerPages)): ?>
        <div class="flex flex-wrap items-center gap-x-1 gap-y-1 py-4 border-b border-suno-border/50">
            <?php foreach ($_footerPages as $i => $fp): ?>
            <?php if ($i > 0): ?><span class="text-zinc-500 text-xs">|</span><?php endif; ?>
            <a href="page.php?slug=<?= htmlspecialchars($fp['slug']) ?>" class="text-xs text-white hover:text-suno-accent2 transition-colors <?= $fp['slug'] === 'privacy' ? 'font-bold' : 'font-medium' ?>"><?= htmlspecialchars($fp['title']) ?></a>
            <?php endforeach; ?>
        </div>
        <?php endif; ?>

        <!-- 안내 문구 -->
        <?php if ($_footerDesc): ?>
        <div class="py-4 border-b border-suno-border/50">
            <p class="text-[11px] text-zinc-300 leading-relaxed"><?= nl2br(htmlspecialchars($_footerDesc)) ?></p>
        </div>
        <?php endif; ?>

        <!-- 사업자 정보 -->
        <div class="py-4 border-b border-suno-border/50">
            <p class="text-[11px] text-zinc-300 leading-loose">
                상호: <?= htmlspecialchars($_footerCompany) ?> &nbsp;&middot;&nbsp; 대표자: <?= htmlspecialchars($_footerCeo) ?> &nbsp;&middot;&nbsp; 사업자번호: <?= htmlspecialchars($_footerBizNum) ?> &nbsp;&middot;&nbsp; 통신판매업신고번호: <?= htmlspecialchars($_footerTelecom) ?><br>
                소재지: <?= htmlspecialchars($_footerAddress) ?>
            </p>
        </div>

        <!-- 연락처 + 하단 -->
        <div class="flex flex-col sm:flex-row sm:items-center sm:justify-between gap-3 py-4">
            <p class="text-[11px] text-zinc-300 leading-loose">
                문의: <?= htmlspecialchars($_footerPhone) ?> &nbsp;&middot;&nbsp; 이메일: <span class="text-white"><?= htmlspecialchars($_footerEmail) ?></span>
                <?php if ($_footerKakao): ?>
                &nbsp;&middot;&nbsp; 고객지원/문의: <a href="<?= htmlspecialchars($_footerKakao) ?>" target="_blank" class="text-white hover:text-suno-accent2 transition-colors underline underline-offset-2">카카오톡 플러스친구</a>
                <?php endif; ?>
            </p>
            <p class="text-[11px] text-zinc-400"><?= htmlspecialchars($_footerCopyright) ?></p>
        </div>

    </div>
</footer>
</body>
</html>
