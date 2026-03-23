<?php
require_once 'db.php';

if (!$currentUser) {
    header('Location: login.php');
    exit;
}

$pageTitle = '쪽지';

// 대화 상대별 그룹핑: 각 상대방과의 최신 메시지 + 읽지 않은 수
// 1) 나와 관련된 모든 메시지에서 상대방 ID를 추출
$stmt = $pdo->prepare('
    SELECT
        CASE WHEN sender_id = ? THEN receiver_id ELSE sender_id END as partner_id,
        MAX(id) as last_message_id,
        MAX(created_at) as last_time
    FROM messages
    WHERE (sender_id = ? AND sender_deleted = 0)
       OR (receiver_id = ? AND receiver_deleted = 0)
    GROUP BY partner_id
    ORDER BY last_time DESC
');
$stmt->execute([$currentUser['id'], $currentUser['id'], $currentUser['id']]);
$conversations = $stmt->fetchAll();

// 페이지네이션
$totalConversations = count($conversations);
$perPage = 20;
$page = max(1, (int)($_GET['page'] ?? 1));
$totalPages = max(1, ceil($totalConversations / $perPage));
if ($page > $totalPages) $page = $totalPages;
$offset = ($page - 1) * $perPage;
$pageConversations = array_slice($conversations, $offset, $perPage);

// 각 대화의 상세 정보 가져오기
$chatList = [];
foreach ($pageConversations as $conv) {
    $partnerId = $conv['partner_id'];
    $lastMsgId = $conv['last_message_id'];

    // 상대방 정보
    $uStmt = $pdo->prepare('SELECT id, nickname, avatar_color FROM users WHERE id = ?');
    $uStmt->execute([$partnerId]);
    $partner = $uStmt->fetch();
    if (!$partner) continue;

    // 최신 메시지
    $mStmt = $pdo->prepare('SELECT id, sender_id, title, content, created_at, is_read FROM messages WHERE id = ?');
    $mStmt->execute([$lastMsgId]);
    $lastMsg = $mStmt->fetch();

    // 읽지 않은 메시지 수 (상대방이 보낸 + 내가 수신자 + 읽지 않음)
    $unreadStmt = $pdo->prepare('SELECT COUNT(*) FROM messages WHERE sender_id = ? AND receiver_id = ? AND is_read = 0');
    $unreadStmt->execute([$partnerId, $currentUser['id']]);
    $unreadCount = (int)$unreadStmt->fetchColumn();

    $chatList[] = [
        'partner_id' => $partner['id'],
        'partner_name' => $partner['nickname'],
        'partner_avatar' => $partner['avatar_color'] ?: 'from-violet-500 to-purple-500',
        'last_msg_id' => $lastMsg['id'],
        'last_content' => $lastMsg['content'],
        'last_sender_id' => $lastMsg['sender_id'],
        'last_time' => $lastMsg['created_at'],
        'last_is_read' => $lastMsg['is_read'],
        'unread' => $unreadCount,
    ];
}

// 전체 읽지 않은 수
$totalUnread = 0;
foreach ($chatList as $c) $totalUnread += $c['unread'];
?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<style>
    .chat-row { transition: all 0.15s ease; }
    .chat-row:hover { background: rgba(139,92,246,0.04); }
</style>

<div class="pt-20">
    <!-- Header -->
    <section class="border-b border-suno-border">
        <div class="max-w-3xl mx-auto px-6 py-6">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 bg-suno-accent/10 border border-suno-accent/20 rounded-xl flex items-center justify-center">
                        <svg class="w-5 h-5 text-suno-accent" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"/>
                        </svg>
                    </div>
                    <div>
                        <h1 class="text-xl font-bold">쪽지</h1>
                        <?php if($totalUnread > 0): ?>
                        <p class="text-xs text-suno-accent">읽지 않은 쪽지 <?php echo $totalUnread; ?>개</p>
                        <?php else: ?>
                        <p class="text-xs text-suno-muted">대화 목록</p>
                        <?php endif; ?>
                    </div>
                </div>
                <a href="message_write.php" class="inline-flex items-center gap-2 bg-suno-accent hover:bg-suno-accent2 text-white font-semibold px-5 py-2.5 rounded-xl transition-all text-sm">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M16.862 4.487l1.687-1.688a1.875 1.875 0 112.652 2.652L10.582 16.07a4.5 4.5 0 01-1.897 1.13L6 18l.8-2.685a4.5 4.5 0 011.13-1.897l8.932-8.931z"/>
                    </svg>
                    새 쪽지
                </a>
            </div>
        </div>
    </section>

    <!-- Conversation List -->
    <section class="py-0">
        <div class="max-w-3xl mx-auto px-6">
            <?php if(empty($chatList)): ?>
            <div class="py-16 text-center">
                <div class="w-14 h-14 mx-auto mb-4 bg-suno-surface border border-suno-border rounded-xl flex items-center justify-center">
                    <svg class="w-6 h-6 text-suno-muted/40" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="1.5" d="M8.625 12a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H8.25m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0H12m4.125 0a.375.375 0 11-.75 0 .375.375 0 01.75 0zm0 0h-.375M21 12c0 4.556-4.03 8.25-9 8.25a9.764 9.764 0 01-2.555-.337A5.972 5.972 0 015.41 20.97a5.969 5.969 0 01-.474-.065 4.48 4.48 0 00.978-2.025c.09-.457-.133-.901-.467-1.226C3.93 16.178 3 14.189 3 12c0-4.556 4.03-8.25 9-8.25s9 3.694 9 8.25z"/>
                    </svg>
                </div>
                <p class="text-sm text-suno-muted mb-2">아직 쪽지가 없습니다</p>
                <p class="text-xs text-suno-muted/50">다른 크리에이터에게 먼저 쪽지를 보내보세요</p>
            </div>
            <?php else: ?>
            <div class="divide-y divide-suno-border/50">
                <?php foreach($chatList as $chat): ?>
                <a href="message_view.php?user=<?php echo $chat['partner_id']; ?>"
                   class="chat-row flex items-center gap-3 py-4 px-3 rounded-lg">
                    <!-- Avatar (클릭 시 프로필) -->
                    <div class="relative shrink-0" onclick="event.preventDefault(); event.stopPropagation(); window.location.href='profile.php?id=<?php echo $chat['partner_id']; ?>';">
                        <div class="w-12 h-12 rounded-full bg-gradient-to-r <?php echo $chat['partner_avatar']; ?> flex items-center justify-center text-sm font-bold cursor-pointer hover:ring-2 hover:ring-suno-accent/30 transition-all">
                            <?php echo mb_substr($chat['partner_name'], 0, 1); ?>
                        </div>
                        <?php if($chat['unread'] > 0): ?>
                        <span class="absolute -top-0.5 -right-0.5 min-w-[18px] h-[18px] bg-suno-accent text-white text-[10px] font-bold rounded-full flex items-center justify-center px-1"><?php echo $chat['unread']; ?></span>
                        <?php endif; ?>
                    </div>

                    <!-- Content -->
                    <div class="flex-1 min-w-0">
                        <div class="flex items-center justify-between mb-0.5">
                            <span class="text-sm font-semibold <?php echo $chat['unread'] > 0 ? 'text-white' : 'text-zinc-300'; ?>"><?php echo htmlspecialchars($chat['partner_name']); ?></span>
                            <span class="text-[11px] text-suno-muted/50 shrink-0 ml-2"><?php echo timeAgo($chat['last_time']); ?></span>
                        </div>
                        <p class="text-sm truncate <?php echo $chat['unread'] > 0 ? 'text-zinc-300 font-medium' : 'text-suno-muted/70'; ?>">
                            <?php if($chat['last_sender_id'] == $currentUser['id']): ?>
                            <span class="text-suno-muted/50">나: </span>
                            <?php if($chat['last_is_read']): ?><span class="text-suno-accent/50 text-xs">읽음 &middot; </span><?php endif; ?>
                            <?php endif; ?>
                            <?php echo htmlspecialchars(mb_substr($chat['last_content'], 0, 60)); ?>
                        </p>
                    </div>

                    <!-- Arrow -->
                    <svg class="w-4 h-4 text-suno-muted/20 shrink-0" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/>
                    </svg>
                </a>
                <?php endforeach; ?>
            </div>
            <?php endif; ?>

            <!-- Pagination -->
            <?php if($totalPages > 1): ?>
            <div class="flex items-center justify-center gap-1.5 mt-6 mb-8">
                <?php if($page > 1): ?>
                <a href="message_list.php?page=<?php echo $page - 1; ?>" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                </a>
                <?php endif; ?>

                <?php for($i = max(1, $page-2); $i <= min($totalPages, $page+2); $i++): ?>
                <a href="message_list.php?page=<?php echo $i; ?>" class="w-9 h-9 flex items-center justify-center rounded-lg <?php echo $i === $page ? 'bg-suno-accent text-white font-medium' : 'border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors'; ?> text-sm"><?php echo $i; ?></a>
                <?php endfor; ?>

                <?php if($page < $totalPages): ?>
                <a href="message_list.php?page=<?php echo $page + 1; ?>" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:border-suno-accent/30 hover:text-white transition-colors">
                    <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M9 5l7 7-7 7"/></svg>
                </a>
                <?php endif; ?>
            </div>
            <?php else: ?>
            <div class="h-8"></div>
            <?php endif; ?>
        </div>
    </section>
</div>

<?php include 'footer.php'; ?>
