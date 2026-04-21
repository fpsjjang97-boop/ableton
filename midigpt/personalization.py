"""
Sprint XXX — 사용자 어댑터 레지스트리 scaffold
=============================================

종합 리뷰 §13 "사용자 복제본 작곡가" + §20-10 "base model + user adapter
구조를 전제로 개인화 방향 설계" 대응.

설계 원칙
---------
1. **Base model 은 공유** — 모든 사용자가 같은 base checkpoint 를 본다.
2. **Task LoRA 는 공유** — drums_from_context / bass_from_chords 등 task
   adapter 는 공용 자산.
3. **User LoRA 는 분리** — 사용자 편향/취향은 `user_<id>_<profile>` 이름의
   LoRA 로만 반영. base 에 섞지 않는다.
4. **2 단 결합** — 생성 시 "task LoRA + user LoRA" 를 선택적으로 블렌드
   (LoRA blending 은 별도 sprint; 여기서는 택일 / 하나만 활성화).

디렉토리 관례
-------------
::

    checkpoints/
      midigpt_best.pt          (base)
      lora/
        task/
          drums_from_context.bin
          bass_from_chords.bin
          …
        user/
          <user_id>/
            default.bin
            profile_dense.bin
            profile_sparse.bin

`MidiGPTInference.register_lora()` 는 이미 name → path 맵을 받으므로,
여기서는 위 관례에 맞는 이름 해석기만 제공하고 나머지는 엔진 API 를
그대로 재사용한다.

사용 예
-------
.. code-block:: python

    from midigpt.personalization import (
        user_lora_path, task_lora_path, register_standard_adapters,
    )
    register_standard_adapters(engine,
                                checkpoints_dir="./checkpoints",
                                user_id="jisu",
                                user_profile="default")
    engine.activate_lora("user:jisu/default")
"""
from __future__ import annotations

from pathlib import Path
from typing import Optional


def task_lora_path(checkpoints_dir: str | Path,
                   task: str) -> Path:
    """공유 task adapter 경로. 존재 확인은 호출측 책임."""
    return Path(checkpoints_dir) / "lora" / "task" / f"{task}.bin"


def user_lora_path(checkpoints_dir: str | Path,
                   user_id: str,
                   profile: str = "default") -> Path:
    """사용자별 adapter 경로.

    profile 은 동일 사용자 안에서도 여러 취향 편향을 저장할 수 있도록
    분기 (예: "dense" / "sparse" / "cinematic")."""
    return (Path(checkpoints_dir) / "lora" / "user"
            / user_id / f"{profile}.bin")


def register_standard_adapters(
    engine,
    checkpoints_dir: str | Path,
    tasks: list[str] | None = None,
    user_id: Optional[str] = None,
    user_profile: str = "default",
    activate: Optional[str] = None,
) -> dict:
    """Register standard task + user adapters with an engine.

    Args:
        engine: MidiGPTInference 인스턴스.
        checkpoints_dir: checkpoints/ 루트.
        tasks: 등록할 task 목록. None 이면 파일 존재하는 모든 *.bin 스캔.
        user_id: 사용자 식별자. None 이면 user adapter 등록 스킵.
        user_profile: user_id 안의 프로파일 이름.
        activate: 등록 후 즉시 활성화할 이름 (task 이름 또는
                  ``"user:<id>/<profile>"``).

    Returns:
        dict with keys ``registered_tasks`` (list[str]),
        ``registered_user`` (str | None), ``active`` (str | None).

    이 함수는 **파일이 없으면 조용히 skip** 하지 않고 경고 로그를 남긴다
    (rule 02-2 의 "경고 없는 skip 금지").
    """
    base = Path(checkpoints_dir)
    registered_tasks: list[str] = []

    if tasks is None:
        task_dir = base / "lora" / "task"
        if task_dir.exists():
            tasks = sorted(p.stem for p in task_dir.glob("*.bin"))
        else:
            tasks = []

    for t in tasks:
        p = task_lora_path(base, t)
        if not p.is_file():
            print(f"[personalization] task LoRA 누락: {p} — skip", flush=True)
            continue
        try:
            engine.register_lora(f"task:{t}", str(p))
            registered_tasks.append(t)
        except Exception as e:
            print(f"[personalization] task {t} 등록 실패: {e}", flush=True)

    registered_user: Optional[str] = None
    if user_id:
        p = user_lora_path(base, user_id, user_profile)
        if p.is_file():
            try:
                name = f"user:{user_id}/{user_profile}"
                engine.register_lora(name, str(p))
                registered_user = name
            except Exception as e:
                print(f"[personalization] user {user_id}/{user_profile} "
                      f"등록 실패: {e}", flush=True)
        else:
            print(f"[personalization] user LoRA 누락: {p} — 첫 학습 전 상태",
                  flush=True)

    active: Optional[str] = None
    if activate:
        try:
            engine.activate_lora(activate)
            active = activate
        except Exception as e:
            print(f"[personalization] activate({activate}) 실패: {e}", flush=True)

    return {
        "registered_tasks": registered_tasks,
        "registered_user":  registered_user,
        "active":           active,
    }


# ---------------------------------------------------------------------------
# Capture I/O — 사용자 edit 로그를 capture_v1.md 스키마로 쓰고 읽는 helper.
# ---------------------------------------------------------------------------
def write_capture(capture: dict, out_dir: str | Path) -> Path:
    """capture_v1.md 스키마의 dict 를 파일로 저장. 파일명은
    ``capture_{session_id}_{captured_at}.json``. 한국어 metadata 가 있어도
    안전하도록 utf-8, ensure_ascii=False."""
    import json as _json
    out_dir_p = Path(out_dir)
    out_dir_p.mkdir(parents=True, exist_ok=True)
    sid = str(capture.get("session_id", "nosid"))
    ts  = str(capture.get("captured_at", "nots")).replace(":", "-")
    fn = out_dir_p / f"capture_{sid}_{ts}.json"
    with open(fn, "w", encoding="utf-8") as f:
        _json.dump(capture, f, ensure_ascii=False, indent=2)
    return fn


def read_capture(path: str | Path) -> dict:
    """반대 방향. schema_version 은 읽은 쪽 책임으로 검증."""
    import json as _json
    with open(path, "r", encoding="utf-8") as f:
        return _json.load(f)
