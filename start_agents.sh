#!/bin/bash
# MIDI => 음악 프로젝트 멀티 에이전트 Tmux 세션
# 6개 역할: Orchestrator, Manager, Composer, Transformer, Ableton Bridge, Reviewer

SESSION="midi-music"
PROJECT_DIR="$HOME/ableton"

# 기존 세션 종료
tmux kill-session -t "$SESSION" 2>/dev/null

# 0: Orchestrator — 전체 파이프라인 통합
tmux new-session -d -s "$SESSION" -n "Orch" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Orch" "python3 agents/orchestrator.py" Enter

# 1: Manager — 설정 관리
tmux new-window -t "$SESSION" -n "Manager" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Manager" "python3 agents/manager.py" Enter

# 2: Composer — 작곡
tmux new-window -t "$SESSION" -n "Composer" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Composer" "python3 agents/composer.py" Enter

# 3: Transformer — 패턴분석/변형
tmux new-window -t "$SESSION" -n "Trans" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Trans" "python3 agents/music_transformer.py" Enter

# 4: Ableton — MCP 브릿지
tmux new-window -t "$SESSION" -n "Ableton" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Ableton" "python3 agents/ableton_bridge.py" Enter

# 5: Reviewer — 결과 검증
tmux new-window -t "$SESSION" -n "Review" -c "$PROJECT_DIR"
tmux send-keys -t "$SESSION:Review" "python3 agents/reviewer.py" Enter

# Orchestrator로 돌아가기
tmux select-window -t "$SESSION:Orch"

echo "✓ Tmux 세션 '$SESSION' 시작됨 (6 에이전트)"
echo ""
echo "  접속: tmux attach -t $SESSION"
echo ""
echo "  윈도우:"
echo "    Ctrl+b 0 → Orchestrator (통합 파이프라인)"
echo "    Ctrl+b 1 → Manager      (설정/조율)"
echo "    Ctrl+b 2 → Composer     (MIDI 생성)"
echo "    Ctrl+b 3 → Transformer  (패턴/변형)"
echo "    Ctrl+b 4 → Ableton      (MCP 브릿지)"
echo "    Ctrl+b 5 → Reviewer     (품질 검증)"
echo ""
echo "  전체 파이프라인 (Orchestrator에서):"
echo "    audio <mp3/wav>       → Demucs분리→MIDI변환→분석→변형→리뷰"
echo "    compose               → 설정기반 작곡→하모니→리뷰"
echo "    remix <mid> <style>   → 스타일변환→하모니→리뷰"
