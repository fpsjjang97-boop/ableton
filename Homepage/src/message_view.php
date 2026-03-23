<?php
require_once 'db.php';

if (!$currentUser) {
    header('Location: login.php');
    exit;
}

$pageTitle = '쪽지';

// 상대방 결정: ?user= 또는 기존 ?id= 호환
$otherUserId = 0;
if (isset($_GET['user'])) {
    $otherUserId = (int)$_GET['user'];
} elseif (isset($_GET['id'])) {
    // 기존 방식: 메시지 ID로 접근 시 상대방 추출
    $msgId = (int)$_GET['id'];
    $stmt = $pdo->prepare('SELECT sender_id, receiver_id FROM messages WHERE id = ?');
    $stmt->execute([$msgId]);
    $msg = $stmt->fetch();
    if ($msg) {
        $otherUserId = ($msg['sender_id'] == $currentUser['id']) ? $msg['receiver_id'] : $msg['sender_id'];
    }
}

if ($otherUserId <= 0 || $otherUserId == $currentUser['id']) {
    header('Location: message_list.php');
    exit;
}

// 상대방 정보
$stmt = $pdo->prepare('SELECT id, nickname, avatar_color, bio FROM users WHERE id = ?');
$stmt->execute([$otherUserId]);
$otherUser = $stmt->fetch();

if (!$otherUser) {
    header('Location: message_list.php');
    exit;
}

$otherAvatar = $otherUser['avatar_color'] ?: 'from-violet-500 to-purple-500';

// 두 사용자 간의 모든 메시지 (시간순)
$stmt = $pdo->prepare('
    SELECT messages.*, sender.nickname as sender_name, sender.avatar_color as sender_avatar
    FROM messages
    JOIN users as sender ON messages.sender_id = sender.id
    WHERE ((sender_id = ? AND receiver_id = ?) OR (sender_id = ? AND receiver_id = ?))
      AND ((sender_id = ? AND sender_deleted = 0) OR (receiver_id = ? AND receiver_deleted = 0))
    ORDER BY created_at ASC
');
$stmt->execute([
    $currentUser['id'], $otherUserId,
    $otherUserId, $currentUser['id'],
    $currentUser['id'], $currentUser['id']
]);
$threadMessages = $stmt->fetchAll();

// 읽음 처리: 상대방이 보낸 메시지 중 읽지 않은 것
$stmt = $pdo->prepare('UPDATE messages SET is_read = 1 WHERE receiver_id = ? AND sender_id = ? AND is_read = 0');
$stmt->execute([$currentUser['id'], $otherUserId]);

// 날짜별 그룹핑 헬퍼
function formatMessageDate($datetime) {
    $utc = new DateTimeZone('UTC');
    $kst = new DateTimeZone('Asia/Seoul');
    $dt = new DateTime($datetime, $utc);
    $dt->setTimezone($kst);
    $today = new DateTime('now', $kst);
    $yesterday = (clone $today)->modify('-1 day');

    if ($dt->format('Y-m-d') === $today->format('Y-m-d')) {
        return '오늘';
    } elseif ($dt->format('Y-m-d') === $yesterday->format('Y-m-d')) {
        return '어제';
    } elseif ($dt->format('Y') === $today->format('Y')) {
        return $dt->format('n월 j일');
    } else {
        return $dt->format('Y년 n월 j일');
    }
}

function formatMessageTime($datetime) {
    $utc = new DateTimeZone('UTC');
    $kst = new DateTimeZone('Asia/Seoul');
    $dt = new DateTime($datetime, $utc);
    $dt->setTimezone($kst);
    $hour = (int)$dt->format('G');
    $ampm = $hour < 12 ? '오전' : '오후';
    $h = $hour % 12;
    if ($h === 0) $h = 12;
    return $ampm . ' ' . $h . ':' . $dt->format('i');
}
?>
<?php include 'head.php'; ?>
<?php include 'navbar.php'; ?>

<style>
    .msg-bubble { max-width: 75%; word-break: break-word; }
    .msg-bubble.mine { margin-left: auto; }
    .msg-bubble.theirs { margin-right: auto; }
    .chat-area { height: calc(100vh - 200px); min-height: 300px; }
    .chat-area::-webkit-scrollbar { width: 4px; }
    .chat-area::-webkit-scrollbar-thumb { background: #333; border-radius: 2px; }
</style>

<div class="pt-20 flex flex-col" style="height: calc(100vh - 0px);">
    <!-- Header -->
    <section class="border-b border-suno-border shrink-0">
        <div class="max-w-3xl mx-auto px-6 py-4">
            <div class="flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <a href="message_list.php" class="w-9 h-9 flex items-center justify-center rounded-lg border border-suno-border text-suno-muted hover:text-white hover:border-suno-accent/40 transition-all">
                        <svg class="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24"><path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M15 19l-7-7 7-7"/></svg>
                    </a>
                    <a href="profile.php?id=<?php echo $otherUserId; ?>" class="flex items-center gap-2.5 hover:opacity-80 transition-opacity">
                        <div class="w-9 h-9 rounded-full bg-gradient-to-r <?php echo $otherAvatar; ?> flex items-center justify-center text-xs font-bold">
                            <?php echo mb_substr($otherUser['nickname'], 0, 1); ?>
                        </div>
                        <div>
                            <p class="text-sm font-bold"><?php echo htmlspecialchars($otherUser['nickname']); ?></p>
                            <p class="text-[11px] text-suno-muted">프로필 보기</p>
                        </div>
                    </a>
                </div>
            </div>
        </div>
    </section>

    <!-- Messages Thread -->
    <section class="flex-1 overflow-y-auto chat-area" id="chatArea">
        <div class="max-w-3xl mx-auto px-6 py-4">
            <div class="space-y-1">
                <?php
                $prevDate = '';
                foreach($threadMessages as $msg):
                    $isMe = ($msg['sender_id'] == $currentUser['id']);
                    $senderName = $msg['sender_name'];
                    $senderAvatar = $msg['sender_avatar'] ?: 'from-violet-500 to-purple-500';
                    $msgDate = formatMessageDate($msg['created_at']);
                    $msgTime = formatMessageTime($msg['created_at']);

                    // 날짜 구분선
                    if ($msgDate !== $prevDate):
                        $prevDate = $msgDate;
                ?>
                <div class="flex items-center gap-3 py-4">
                    <div class="flex-1 h-px bg-suno-border/50"></div>
                    <span class="text-[11px] text-suno-muted/60 shrink-0"><?php echo $msgDate; ?></span>
                    <div class="flex-1 h-px bg-suno-border/50"></div>
                </div>
                <?php endif; ?>

                <div class="msg-bubble <?php echo $isMe ? 'mine' : 'theirs'; ?> mb-3">
                    <div class="flex items-end gap-2 <?php echo $isMe ? 'flex-row-reverse' : ''; ?>">
                        <?php if (!$isMe): ?>
                        <a href="profile.php?id=<?php echo $otherUserId; ?>" class="shrink-0">
                            <div class="w-7 h-7 rounded-full bg-gradient-to-r <?php echo $senderAvatar; ?> flex items-center justify-center text-[10px] font-bold hover:ring-2 hover:ring-suno-accent/30 transition-all">
                                <?php echo mb_substr($senderName, 0, 1); ?>
                            </div>
                        </a>
                        <?php endif; ?>
                        <div class="<?php echo $isMe ? 'text-right' : ''; ?>">
                            <div class="inline-block text-left rounded-2xl px-4 py-2.5 text-sm leading-relaxed <?php echo $isMe ? 'bg-suno-accent/15 border border-suno-accent/20 text-zinc-200 rounded-br-md' : 'bg-suno-card border border-suno-border text-zinc-300 rounded-bl-md'; ?>">
                                <?php echo nl2br(htmlspecialchars($msg['content'])); ?>
                            </div>
                            <p class="text-[10px] text-suno-muted/40 mt-1 <?php echo $isMe ? 'text-right mr-1' : 'ml-1'; ?>">
                                <?php if ($isMe): ?>
                                    <?php if ($msg['is_read']): ?>
                                        <span class="text-suno-accent/60">읽음</span> &middot;
                                    <?php endif; ?>
                                <?php endif; ?>
                                <?php echo $msgTime; ?>
                            </p>
                        </div>
                    </div>
                </div>
                <?php endforeach; ?>
            </div>
        </div>
    </section>

    <!-- Reply Box (고정 하단) -->
    <section class="border-t border-suno-border bg-suno-dark shrink-0">
        <div class="max-w-3xl mx-auto px-6 py-3">
            <form action="message_write_ok.php" method="POST" class="flex items-end gap-3" id="replyForm">
                <input type="hidden" name="to" value="<?php echo htmlspecialchars($otherUser['nickname']); ?>">
                <input type="hidden" name="title" value="DM">
                <input type="hidden" name="redirect" value="message_view.php?user=<?php echo $otherUserId; ?>">
                <div class="flex-1">
                    <textarea name="content" placeholder="메시지를 입력하세요..." rows="1" required
                        class="w-full bg-suno-card border border-suno-border rounded-xl px-4 py-2.5 text-sm text-white placeholder-suno-muted/40 focus:outline-none focus:border-suno-accent/50 resize-none transition-all"
                        id="msgInput" onkeydown="handleKeyDown(event)"></textarea>
                </div>
                <button type="submit" class="shrink-0 w-10 h-10 bg-suno-accent hover:bg-suno-accent2 rounded-xl flex items-center justify-center transition-all">
                    <svg class="w-4 h-4 text-white" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 12L3.269 3.126A59.768 59.768 0 0121.485 12 59.77 59.77 0 013.27 20.876L5.999 12zm0 0h7.5"/>
                    </svg>
                </button>
            </form>
        </div>
    </section>
</div>

<script>
// 채팅 영역 자동 스크롤 최하단
const chatArea = document.getElementById('chatArea');
if (chatArea) {
    chatArea.scrollTop = chatArea.scrollHeight;
}

// Enter로 전송, Shift+Enter로 줄바꿈
function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        const form = document.getElementById('replyForm');
        const content = document.getElementById('msgInput').value.trim();
        if (content) form.submit();
    }
}

// textarea 자동 높이 조절
const msgInput = document.getElementById('msgInput');
if (msgInput) {
    msgInput.addEventListener('input', function() {
        this.style.height = 'auto';
        this.style.height = Math.min(this.scrollHeight, 120) + 'px';
    });
}
</script>

<?php include 'footer.php'; ?>
