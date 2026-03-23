<?php
require_once __DIR__ . '/header.php';

$id = intval($_GET['id'] ?? 0);
if (!$id) { header('Location: users.php'); exit; }

$stmt = $pdo->prepare("SELECT * FROM users WHERE id = ?");
$stmt->execute([$id]);
$user = $stmt->fetch();
if (!$user) { header('Location: users.php'); exit; }

$msg = $_GET['msg'] ?? '';
?>

<div class="flex items-center gap-3 mb-6">
    <a href="users.php" class="text-gray-500 hover:text-gray-300 transition-colors">
        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
    </a>
    <h1 class="text-2xl font-bold text-white">회원 수정</h1>
    <span class="text-sm text-gray-500">#<?= $id ?></span>
</div>

<?php if ($msg === 'saved'): ?>
<div class="bg-green-500/10 border border-green-500/30 text-green-400 px-4 py-3 rounded-lg mb-6 text-sm">
    저장되었습니다.
</div>
<?php endif; ?>

<form action="user_edit_ok.php" method="POST" class="max-w-2xl">
    <input type="hidden" name="id" value="<?= $id ?>">

    <div class="bg-gray-800 rounded-xl border border-gray-700 p-6 space-y-5">
        <div class="grid grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">닉네임</label>
                <input type="text" name="nickname" value="<?= e($user['nickname']) ?>" required
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">이메일</label>
                <input type="email" name="email" value="<?= e($user['email']) ?>" required
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
        </div>

        <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">새 비밀번호 (비워두면 유지)</label>
            <input type="password" name="new_password"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500"
                placeholder="변경할 비밀번호 입력">
        </div>

        <div>
            <label class="block text-sm font-medium text-gray-300 mb-1">자기소개</label>
            <textarea name="bio" rows="3"
                class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500"><?= e($user['bio']) ?></textarea>
        </div>

        <div class="grid grid-cols-2 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">등급</label>
                <select name="badge" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                    <?php foreach (['Bronze','Silver','Gold','Diamond'] as $b): ?>
                    <option value="<?= $b ?>" <?= $user['badge'] === $b ? 'selected' : '' ?>><?= $b ?></option>
                    <?php endforeach; ?>
                </select>
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">관리자 여부</label>
                <select name="is_admin" class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
                    <option value="0" <?= !$user['is_admin'] ? 'selected' : '' ?>>일반 회원</option>
                    <option value="1" <?= $user['is_admin'] ? 'selected' : '' ?>>관리자</option>
                </select>
            </div>
        </div>

        <div class="grid grid-cols-3 gap-4">
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">YouTube URL</label>
                <input type="url" name="youtube_url" value="<?= e($user['youtube_url']) ?>"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">Instagram URL</label>
                <input type="url" name="instagram_url" value="<?= e($user['instagram_url']) ?>"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
            <div>
                <label class="block text-sm font-medium text-gray-300 mb-1">SUNO Profile URL</label>
                <input type="url" name="suno_profile_url" value="<?= e($user['suno_profile_url']) ?>"
                    class="w-full px-3 py-2 bg-gray-700 border border-gray-600 rounded-lg text-white focus:outline-none focus:ring-2 focus:ring-violet-500">
            </div>
        </div>

        <div class="bg-gray-700/50 rounded-lg p-4 text-sm text-gray-400">
            <div class="grid grid-cols-2 gap-2">
                <div>가입일: <?= formatDate($user['created_at']) ?></div>
                <div>수정일: <?= formatDate($user['updated_at']) ?></div>
                <div>약관 동의: <?= $user['terms_agreed'] ? 'Y' : 'N' ?></div>
                <div>아바타 색상: <?= e($user['avatar_color']) ?></div>
            </div>
        </div>
    </div>

    <div class="flex gap-3 mt-6">
        <button type="submit" class="px-6 py-2 bg-violet-600 hover:bg-violet-700 text-white font-medium rounded-lg transition-colors">저장</button>
        <a href="users.php" class="px-6 py-2 bg-gray-700 hover:bg-gray-600 text-gray-300 rounded-lg transition-colors">취소</a>
    </div>
</form>

<?php require_once __DIR__ . '/footer.php'; ?>
