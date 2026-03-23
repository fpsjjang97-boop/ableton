<?php
require_once __DIR__ . '/db.php';

$slug = $_GET['slug'] ?? '';
$page = null;

if ($slug) {
    $stmt = $pdo->prepare("SELECT * FROM site_pages WHERE slug = ?");
    $stmt->execute([$slug]);
    $page = $stmt->fetch();
}

$pageTitle = $page ? $page['title'] : '페이지를 찾을 수 없습니다';
?>
<?php require_once __DIR__ . '/head.php'; ?>
<?php require_once __DIR__ . '/navbar.php'; ?>

<div class="pt-24 pb-16 min-h-screen">
    <div class="max-w-4xl mx-auto px-6">

        <?php if (!$page || !$page['is_active']): ?>
        <!-- 페이지 없음 / 비활성 -->
        <div class="text-center py-20">
            <div class="w-16 h-16 bg-suno-surface border border-suno-border rounded-2xl flex items-center justify-center mx-auto mb-4">
                <i class="fa-solid fa-file-circle-xmark text-2xl text-suno-muted"></i>
            </div>
            <h1 class="text-xl font-bold text-white mb-2">페이지를 찾을 수 없습니다</h1>
            <p class="text-suno-muted text-sm">요청하신 페이지가 존재하지 않거나 비활성 상태입니다.</p>
            <a href="index.php" class="inline-block mt-6 px-6 py-2 bg-suno-accent hover:bg-suno-accent2 text-white text-sm font-medium rounded-lg transition-colors">메인으로 돌아가기</a>
        </div>

        <?php elseif (!$page['content'] || trim($page['content']) === ''): ?>
        <!-- 내용 없음 (준비 중) -->
        <div class="mb-8">
            <h1 class="text-2xl font-bold text-white"><?= htmlspecialchars($page['title']) ?></h1>
        </div>
        <div class="bg-suno-card border border-suno-border rounded-2xl p-12 text-center">
            <div class="w-16 h-16 bg-suno-surface border border-suno-border rounded-2xl flex items-center justify-center mx-auto mb-4">
                <i class="fa-solid fa-file-pen text-2xl text-suno-muted"></i>
            </div>
            <h2 class="text-lg font-semibold text-white mb-2">준비 중입니다</h2>
            <p class="text-suno-muted text-sm">해당 페이지의 내용이 아직 작성되지 않았습니다.<br>빠른 시일 내에 업데이트하겠습니다.</p>
        </div>

        <?php else: ?>
        <!-- 정상 표시 -->
        <div class="mb-8">
            <h1 class="text-2xl font-bold text-white"><?= htmlspecialchars($page['title']) ?></h1>
            <p class="text-xs text-suno-muted mt-2">최종 수정: <?= date('Y년 m월 d일', strtotime($page['updated_at'])) ?></p>
        </div>
        <div class="bg-suno-card border border-suno-border rounded-2xl p-8">
            <div class="prose prose-invert prose-sm max-w-none text-gray-300 leading-relaxed
                [&_h1]:text-xl [&_h1]:font-bold [&_h1]:text-white [&_h1]:mt-8 [&_h1]:mb-4
                [&_h2]:text-lg [&_h2]:font-semibold [&_h2]:text-white [&_h2]:mt-6 [&_h2]:mb-3
                [&_h3]:text-base [&_h3]:font-semibold [&_h3]:text-white [&_h3]:mt-4 [&_h3]:mb-2
                [&_p]:mb-3 [&_p]:text-sm
                [&_ul]:list-disc [&_ul]:pl-5 [&_ul]:mb-3 [&_ul]:text-sm
                [&_ol]:list-decimal [&_ol]:pl-5 [&_ol]:mb-3 [&_ol]:text-sm
                [&_li]:mb-1
                [&_table]:w-full [&_table]:border-collapse [&_table]:mb-4
                [&_th]:bg-suno-surface [&_th]:border [&_th]:border-suno-border [&_th]:px-3 [&_th]:py-2 [&_th]:text-left [&_th]:text-sm [&_th]:text-white
                [&_td]:border [&_td]:border-suno-border [&_td]:px-3 [&_td]:py-2 [&_td]:text-sm
                [&_a]:text-suno-accent2 [&_a]:underline [&_a]:underline-offset-2 hover:[&_a]:text-suno-accent
                [&_strong]:text-white [&_strong]:font-semibold">
                <?= $page['content'] ?>
            </div>
        </div>
        <?php endif; ?>

    </div>
</div>

<?php require_once __DIR__ . '/footer.php'; ?>
