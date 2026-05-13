"""
에이전트 로컬 테스트 도구

사용법:
    python tools/test_agent.py my_agent
    python tools/test_agent.py my_agent --opponent ace --rounds 3
    python tools/test_agent.py my_agent --all-opponents --rounds 3
    python tools/test_agent.py my_agent --all-opponents --rounds 3 --log-csv
"""

import sys

# Python 3.14 필수 (SDK 내부 .pyd 바이너리가 cp314 전용)
if sys.version_info[:2] != (3, 14):
    print("❌ 오류: 본 SDK는 Python 3.14 가 필요합니다.")
    print(f"   현재 버전: Python {sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}")
    sys.exit(1)

# Windows PowerShell 기본 코드페이지(cp949)에서도 한글이 깨지지 않도록 처리
try:
    if sys.platform == "win32":
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
except (AttributeError, LookupError):
    pass

import argparse
import os
from datetime import datetime, timezone, timedelta
from pathlib import Path

# 프로젝트 루트를 path에 추가
# SDK 배포판(tools/): parent.parent = SDK 루트
# 개발 환경(sdk/tools/): parent.parent = sdk/, parent.parent.parent = 프로젝트 루트
_candidate = Path(__file__).parent.parent
if not (_candidate / "src").exists() and (_candidate.parent / "src").exists():
    project_root = _candidate.parent
else:
    project_root = _candidate
sys.path.insert(0, str(project_root))

KST = timezone(timedelta(hours=9))

# `--all-opponents` 가 자동 대전할 기본 상대 목록
DEFAULT_OPPONENTS = ["simple", "aggressive", "defensive", "ace", "eagle1", "viper1"]


def get_agent_path(name: str) -> Path:
    """에이전트 파일 경로 찾기

    탐색 순서:
        1. submissions/{name}/{name}.yaml
        2. examples/{name}.yaml (flat)
        3. examples/{name}/{name}.yaml (sub-dir)
        4. 직접 경로
    """
    # 직접 경로인 경우 (플랫폼 독립적 처리)
    if os.sep in name or "/" in name or "\\" in name:
        direct_path = Path(name)
        if not direct_path.is_absolute():
            direct_path = project_root / name
        if direct_path.exists():
            return direct_path
        raise FileNotFoundError(f"파일을 찾을 수 없습니다: {name}")

    # submissions 폴더 확인
    submission_path = project_root / "submissions" / name / f"{name}.yaml"
    if submission_path.exists():
        return submission_path

    # examples 폴더 확인 (flat: examples/{name}.yaml)
    example_path = project_root / "examples" / f"{name}.yaml"
    if example_path.exists():
        return example_path

    # examples 폴더 확인 (sub-dir: examples/{name}/{name}.yaml)
    example_subdir_path = project_root / "examples" / name / f"{name}.yaml"
    if example_subdir_path.exists():
        return example_subdir_path

    raise FileNotFoundError(f"에이전트를 찾을 수 없습니다: {name}")


def run_vs_opponent(agent_path: Path, opponent_path: Path, rounds: int, verbose: bool, log_dir: Path | None):
    """단일 상대와 rounds 라운드 대전 후 (W, D, L) 반환"""
    from src.match.runner import BehaviorTreeMatch

    wins = draws = losses = 0
    agent_name = agent_path.stem
    opp_name = opponent_path.stem

    for i in range(rounds):
        print(f"--- Round {i + 1}/{rounds} ---")

        csv_path = None
        if log_dir is not None:
            log_dir.mkdir(parents=True, exist_ok=True)
            ts = datetime.now(KST).strftime("%Y%m%d_%H%M%S")
            if rounds > 1:
                csv_path = str(log_dir / f"{ts}_{agent_name}_vs_{opp_name}_round{i + 1}.csv")
            else:
                csv_path = str(log_dir / f"{ts}_{agent_name}_vs_{opp_name}.csv")

        match = BehaviorTreeMatch(
            tree1_file=str(agent_path),
            tree2_file=str(opponent_path),
            config_name="1v1/NoWeapon/bt_vs_bt",
            tree1_name=agent_name,
            tree2_name=opp_name,
            log_csv=csv_path,
        )

        result = match.run(verbose=verbose)

        if result.winner == "tree1":
            wins += 1
            print("✅ 승리!")
        elif result.winner == "tree2":
            losses += 1
            print("❌ 패배")
        else:
            draws += 1
            print("➖ 무승부")
        print()

    return wins, draws, losses


def main():
    parser = argparse.ArgumentParser(description="에이전트 로컬 테스트")
    parser.add_argument("agent", help="테스트할 에이전트 이름 또는 파일 경로")
    parser.add_argument("--opponent", default="simple", help="단일 상대 에이전트 (--all-opponents 미사용 시)")
    parser.add_argument("--all-opponents", action="store_true",
                        help=f"기본 상대 {len(DEFAULT_OPPONENTS)}종과 차례로 대전 ({', '.join(DEFAULT_OPPONENTS)})")
    parser.add_argument("--rounds", type=int, default=1, help="상대별 라운드 수")
    parser.add_argument("--verbose", action="store_true", help="상세 출력")
    parser.add_argument("--log-csv", type=str, nargs="?", const="logs", default=None,
                        help="CSV 로그 저장 폴더 (기본값: logs) - 파일명은 자동 생성")

    args = parser.parse_args()

    # 에이전트 경로 확인
    try:
        agent_path = get_agent_path(args.agent)
    except FileNotFoundError as e:
        print(f"❌ {e}")
        sys.exit(1)

    log_dir = Path(args.log_csv) if args.log_csv else None

    print("🎮 에이전트 테스트 시작")
    print(f"   에이전트: {agent_path.stem}")
    print(f"   라운드(상대별): {args.rounds}")
    if log_dir is not None:
        print(f"   CSV 로그: {log_dir}/")
    print()

    if args.all_opponents:
        opponents = DEFAULT_OPPONENTS
    else:
        opponents = [args.opponent]

    summary = {}
    for opp in opponents:
        try:
            opp_path = get_agent_path(opp)
        except FileNotFoundError as e:
            print(f"⚠️  상대 '{opp}' 를 찾을 수 없어 건너뜁니다: {e}")
            continue

        print("=" * 60)
        print(f"🎯 vs {opp_path.stem}")
        print("=" * 60)

        w, d, l = run_vs_opponent(agent_path, opp_path, args.rounds, args.verbose, log_dir)
        summary[opp_path.stem] = (w, d, l)
        print(f"📊 vs {opp_path.stem}: {w}W / {d}D / {l}L")
        print()

    # 최종 요약
    print("=" * 60)
    print("🏆 최종 결과")
    print("=" * 60)
    print()
    print(f"에이전트: {agent_path.stem}")
    print()
    total_w = total_d = total_l = 0
    for name, (w, d, l) in summary.items():
        print(f"vs {name:<12}: {w}W / {d}D / {l}L")
        total_w += w
        total_d += d
        total_l += l
    total = total_w + total_d + total_l
    if total > 0:
        winrate = total_w / total * 100
        print()
        print(f"📊 전체: {total_w}W / {total_d}D / {total_l}L (승률: {winrate:.1f}%)")
    print("=" * 60)


if __name__ == "__main__":
    main()
