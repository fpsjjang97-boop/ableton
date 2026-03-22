#!/bin/bash
# MIDI => 음악 프로젝트 멀티 에이전트 Tmux 세션
# 3개 역할: 작곡자(Composer), 관리자(Manager), 리뷰어(Reviewer)

SESSION="midi-music"
PROJECT_DIR="$HOME/ableton"

# 기존 세션 종료
tmux kill-session -t "$SESSION" 2>/dev/null

# 새 세션 생성 (첫 윈도우: Manager)
tmux new-session -d -s "$SESSION" -n "Manager" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Manager" "python3 agents/manager.py" Enter

# Composer 윈도우
tmux new-window -t "$SESSION" -n "Composer" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Composer" "python3 agents/composer.py" Enter

# Reviewer 윈도우
tmux new-window -t "$SESSION" -n "Reviewer" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Reviewer" "python3 agents/reviewer.py" Enter

# Manager 윈도우로 돌아가기
tmux select-window -t "$SESSION:Manager"

echo "✓ Tmux 세션 '$SESSION' 시작됨"
echo "  접속: tmux attach -t $SESSION"
echo ""
echo "  윈도우:"
echo "    0: Manager  (관리자) - 설정/조율"
echo "    1: Composer (작곡자) - MIDI 생성"
echo "    2: Reviewer (리뷰어) - 결과 검증"
echo ""
echo "  단축키:"
echo "    Ctrl+b 0/1/2 - 윈도우 전환"
echo "    Ctrl+b d     - 세션 분리"
