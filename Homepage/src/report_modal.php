<!-- 신고 모달 -->
<div id="reportModal" class="fixed inset-0 z-[9999] flex items-center justify-center hidden">
    <div class="absolute inset-0 bg-black/60 backdrop-blur-sm" onclick="closeReportModal()"></div>
    <div class="relative bg-suno-card border border-suno-border rounded-2xl shadow-2xl shadow-black/50 w-full max-w-md mx-4 p-6">
        <div class="flex items-center justify-between mb-5">
            <h3 class="text-lg font-bold flex items-center gap-2">
                <svg class="w-5 h-5 text-red-400" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M12 9v3.75m-9.303 3.376c-.866 1.5.217 3.374 1.948 3.374h14.71c1.73 0 2.813-1.874 1.948-3.374L13.949 3.378c-.866-1.5-3.032-1.5-3.898 0L2.697 16.126zM12 15.75h.007v.008H12v-.008z"/>
                </svg>
                신고하기
            </h3>
            <button onclick="closeReportModal()" class="text-suno-muted hover:text-white transition-colors">
                <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"/>
                </svg>
            </button>
        </div>

        <form id="reportForm" onsubmit="submitReport(event)">
            <input type="hidden" name="target_type" id="reportTargetType">
            <input type="hidden" name="target_id" id="reportTargetId">

            <p class="text-sm text-suno-muted mb-4">신고 사유를 선택해주세요.</p>

            <div class="space-y-2 mb-4">
                <label class="flex items-center gap-3 p-3 rounded-xl border border-suno-border hover:border-suno-accent/30 cursor-pointer transition-colors has-[:checked]:border-suno-accent/50 has-[:checked]:bg-suno-accent/5">
                    <input type="radio" name="reason" value="스팸/광고" class="accent-violet-500" required>
                    <span class="text-sm">스팸/광고</span>
                </label>
                <label class="flex items-center gap-3 p-3 rounded-xl border border-suno-border hover:border-suno-accent/30 cursor-pointer transition-colors has-[:checked]:border-suno-accent/50 has-[:checked]:bg-suno-accent/5">
                    <input type="radio" name="reason" value="욕설/혐오">
                    <span class="text-sm">욕설/혐오 표현</span>
                </label>
                <label class="flex items-center gap-3 p-3 rounded-xl border border-suno-border hover:border-suno-accent/30 cursor-pointer transition-colors has-[:checked]:border-suno-accent/50 has-[:checked]:bg-suno-accent/5">
                    <input type="radio" name="reason" value="저작권 침해">
                    <span class="text-sm">저작권 침해</span>
                </label>
                <label class="flex items-center gap-3 p-3 rounded-xl border border-suno-border hover:border-suno-accent/30 cursor-pointer transition-colors has-[:checked]:border-suno-accent/50 has-[:checked]:bg-suno-accent/5">
                    <input type="radio" name="reason" value="허위 정보">
                    <span class="text-sm">허위 정보</span>
                </label>
                <label class="flex items-center gap-3 p-3 rounded-xl border border-suno-border hover:border-suno-accent/30 cursor-pointer transition-colors has-[:checked]:border-suno-accent/50 has-[:checked]:bg-suno-accent/5">
                    <input type="radio" name="reason" value="기타" id="reportReasonOther">
                    <span class="text-sm">기타</span>
                </label>
            </div>

            <div id="reportCustomReasonWrap" class="hidden mb-4">
                <textarea id="reportCustomReason" placeholder="신고 사유를 직접 입력해주세요..." rows="3"
                    class="w-full bg-suno-dark border border-suno-border rounded-xl px-4 py-3 text-sm text-white placeholder-suno-muted/40 focus:outline-none focus:border-suno-accent/50 resize-none transition-colors"></textarea>
            </div>

            <div class="flex items-center gap-3 justify-end">
                <button type="button" onclick="closeReportModal()" class="px-4 py-2.5 text-sm text-suno-muted hover:text-white transition-colors rounded-xl">취소</button>
                <button type="submit" id="reportSubmitBtn" class="bg-red-500 hover:bg-red-600 text-white text-sm font-semibold px-5 py-2.5 rounded-xl transition-colors">신고 제출</button>
            </div>
        </form>
    </div>
</div>

<script>
function openReportModal(targetType, targetId) {
    document.getElementById('reportTargetType').value = targetType;
    document.getElementById('reportTargetId').value = targetId;
    document.getElementById('reportModal').classList.remove('hidden');
    document.body.style.overflow = 'hidden';
    // 폼 초기화
    document.getElementById('reportForm').reset();
    document.getElementById('reportCustomReasonWrap').classList.add('hidden');
    document.getElementById('reportSubmitBtn').disabled = false;
    document.getElementById('reportSubmitBtn').textContent = '신고 제출';
}

function closeReportModal() {
    document.getElementById('reportModal').classList.add('hidden');
    document.body.style.overflow = '';
}

// 기타 선택 시 직접 입력란 표시
document.querySelectorAll('#reportForm input[name="reason"]').forEach(function(radio) {
    radio.addEventListener('change', function() {
        var customWrap = document.getElementById('reportCustomReasonWrap');
        if (this.value === '기타') {
            customWrap.classList.remove('hidden');
            document.getElementById('reportCustomReason').focus();
        } else {
            customWrap.classList.add('hidden');
        }
    });
});

function submitReport(e) {
    e.preventDefault();
    var form = document.getElementById('reportForm');
    var selected = form.querySelector('input[name="reason"]:checked');
    if (!selected) {
        alert('신고 사유를 선택해주세요.');
        return;
    }

    var reason = selected.value;
    if (reason === '기타') {
        var custom = document.getElementById('reportCustomReason').value.trim();
        if (!custom) {
            alert('신고 사유를 입력해주세요.');
            return;
        }
        reason = '기타: ' + custom;
    }

    var btn = document.getElementById('reportSubmitBtn');
    btn.disabled = true;
    btn.textContent = '제출 중...';

    var fd = new FormData();
    fd.append('target_type', document.getElementById('reportTargetType').value);
    fd.append('target_id', document.getElementById('reportTargetId').value);
    fd.append('reason', reason);

    fetch('report_ok.php', { method: 'POST', body: fd })
        .then(function(r) { return r.json(); })
        .then(function(data) {
            if (data.success) {
                alert(data.message);
                closeReportModal();
            } else {
                alert(data.message || '오류가 발생했습니다.');
                btn.disabled = false;
                btn.textContent = '신고 제출';
            }
        })
        .catch(function() {
            alert('서버 오류가 발생했습니다.');
            btn.disabled = false;
            btn.textContent = '신고 제출';
        });
}
</script>
