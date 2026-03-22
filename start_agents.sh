#!/bin/bash
# MIDI => 음악 프로젝트 멀티 에이전트 Tmux 세션
# 5개 역할: Manager, Composer, Transformer, Ableton Bridge, Reviewer

SESSION="midi-music"
PROJECT_DIR="$HOME/ableton"

# 기존 세션 종료
tmux kill-session -t "$SESSION" 2>/dev/null

# 새 세션 생성 (0: Manager)
tmux new-session -d -s "$SESSION" -n "Manager" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Manager" "python3 agents/manager.py" Enter

# 1: Composer — 작곡자
tmux new-window -t "$SESSION" -n "Composer" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Composer" "python3 agents/composer.py" Enter

# 2: Transformer — Music Transformer (패턴/연속생성/변형)
tmux new-window -t "$SESSION" -n "Transformer" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Transformer" "python3 agents/music_transformer.py" Enter

# 3: Ableton — MCP 브릿지
tmux new-window -t "$SESSION" -n "Ableton" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Ableton" "python3 agents/ableton_bridge.py" Enter

# 4: Reviewer — 결과 검증
tmux new-window -t "$SESSION" -n "Reviewer" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Reviewer" "python3 agents/reviewer.py" Enter

# Manager 윈도우로 돌아가기
tmux select-window -t "$SESSION:Manager"

echo "✓ Tmux 세션 '$SESSION' 시작됨 (5 에이전트)"
echo ""
echo "  접속: tmux attach -t $SESSION"
echo ""
echo "  윈도우:"
echo "    Ctrl+b 0 → Manager     (관리자)     - 설정/조율"
echo "    Ctrl+b 1 → Composer    (작곡자)     - MIDI 생성"
echo "    Ctrl+b 2 → Transformer (변환기)     - 패턴분석/연속생성/스타일변환"
echo "    Ctrl+b 3 → Ableton     (MCP 브릿지) - Ableton Live 제어"
echo "    Ctrl+b 4 → Reviewer    (리뷰어)     - 결과 검증"
echo ""
echo "  워크플로우:"
echo "    Manager(설정) → Composer(작곡) → Transformer(변형)"
echo "                  → Ableton(전송) → Reviewer(검증)"
