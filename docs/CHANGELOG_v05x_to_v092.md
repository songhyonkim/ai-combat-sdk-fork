# v0.5.x → v0.9.2 변경 사항 정리

커밋 기준: `v0.5.5.9` (eaf8aef) → `v0.9.2` (aff7a54), 3개 릴리즈(v0.9.0 → v0.9.1 → v0.9.2) 포함.

---

## ⚠️ Breaking Changes

### 1. 각도 관측값 단위 변경

| 키 | v0.5.x | v0.9.x |
|---|---|---|
| `ata_deg`, `aa_deg`, `hca_deg` | 0 ~ 1 (정규화, `/180.0`) | **0° ~ 180°** (실제 도) |
| `tau_deg`, `relative_bearing_deg` | -1 ~ 1 (정규화) | **-180° ~ 180°** (실제 도) |

```python
# v0.5.x (잘못된 결과)
ata = obs.get("ata_deg", 0.0) * 180.0

# v0.9.x (변환 불필요)
ata = obs.get("ata_deg", 0.0)
```

### 2. 관측값 키 이름 변경 (단위 접미사 명시화)

| 폐기 키 (v0.5.x) | 새 키 (v0.9.x) | 단위 |
|---|---|---|
| `distance` | `distance_ft` | ft |
| `alt_gap` | `alt_gap_ft` | ft |
| `ego_altitude` | `ego_altitude_ft` | ft |
| `ego_vc` | `ego_vc_kts` | kts |
| `closure_rate` | `closure_rate_kts` | kts |
| `energy_diff` | `energy_diff_ft` | ft |

---

## 🆕 신규 노드 — 고급 3차원 기동

### `TimedAction` 베이스 클래스 (신규 API)

`BaseAction`(단일 tick SUCCESS) 외에 **N tick 동안 RUNNING → 완료 시 SUCCESS**를 자동 처리하는 새 베이스 클래스 추가. `memory: true` Sequence 내에서 사용 필수.

```python
from src.behavior_tree.nodes.actions import TimedAction

class MyManeuver(TimedAction):
    def on_start(self): ...          # 1회 초기화 (선택)
    def execute(self, step, total):  # 매 tick, set_action() 필수
        self.set_action(4, 4, 1)
    def on_finish(self, status): ... # 완료/중단 시 (선택)
```

### 완결형 기동 (RUNNING → SUCCESS, `TimedAction` 기반)

| 노드 | 기본 ticks | 설명 |
|---|---|---|
| `Loop` | 15 | 수직 원형 기동. 급상승 → 최고점 → 급하강 |
| `ImmelmannTurn` | 12 | 루프 상반부 + 180° 롤아웃. 방향 전환, 고도↑, 속도↓ |
| `SplitS` | 10 | 배면 + 급하강. 방향 전환, 고도↓, 속도↑ |
| `HammerHead` | 15 | 수직 상승 → 실속 직전 요잉 → 급하강 |

### 반응형 연속 기동 (SUCCESS 반환, `BaseAction` 기반)

| 노드 | 설명 |
|---|---|
| `SliceTurn` | 얕은 하강 뱅크턴. 에너지 손실 최소화 |
| `SpiralDive` | 나선형 급강하. 속도 회복, 추격 이탈 |
| `SpiralClimb` | 나선형 상승. 에너지 우위 유지하며 고도↑ |

### 기존 노드 동작 변경

| 노드 | v0.5.x | v0.9.x |
|---|---|---|
| `HighYoYo`, `LowYoYo`, `BarrelRoll` | SUCCESS | **RUNNING 반환** (phase 상태 유지) |
| `GunAttack` | 기본 조준 | 초정밀 ±2° 목표 + `lead_factor` 파라미터 추가 |
| `OvershootAvoidance` | 단순 Lag/HighYoYo | 접근속도 > 155.6 kts + 거리 < 3281 ft → 즉시 Lag 분기 추가 |

---

## 🆕 신규 관측값 키

| 키 | 단위 | 설명 |
|---|---|---|
| `specific_energy_ft` | ft | 비에너지 He = h + v²/2g |
| `ps_fts` | ft/s | Specific Excess Power (dHe/dt) |
| `roll_deg` | ° | 내 롤 각도 |
| `pitch_deg` | ° | 내 피치 각도 |
| `ata_lead_deg` | ° | 1초 후 예측 ATA |
| `tau_lead_deg` | ° | 1초 후 예측 TAU |

---

## 🆕 신규 문서

- **`docs/BLACKBOARD_REFERENCE.md`** (신규): 모든 Blackboard 키의 단위·범위·부호 규약을 정의하는 Single Source of Truth 문서 추가.

---

## 🆕 신규 예제 에이전트

| 파일 | 내용 |
|---|---|
| `examples/aerobatic.yaml` | 고급 3차원 기동 시연 |
| `examples/immelmann_demo.yaml` | `ImmelmannTurn` 사용 예제 |
| `examples/eagle2.yaml` | 신규 예제 에이전트 |
| `examples/red_agent/easy.yaml` | 레드팀 에이전트 (쉬움) |
| `examples/red_agent/normal.yaml` | 레드팀 에이전트 (보통) |
| `examples/red_agent/hard.yaml` | 레드팀 에이전트 (어려움) |

---

## 🔧 엔진/인프라 변경

### Hard Deck 위반 실시간 감지 (`runner_core.py`)

- **v0.5.x**: `MatchJudge` 객체가 생성되었으나 미사용 버그 (`_ = MatchJudge(...)`)
- **v0.9.x**: 매 스텝 Hard Deck 고도 위반을 실시간으로 감지하고 즉시 게임 종료. ACMI 리플레이에 북마크 자동 기록.

### Human vs BT 모드 추가

- `runner_human_vs_bt.cp314-win_amd64.pyd` 신규 추가
- `src/match/__init__.py`에 `HumanVsBTMatchCore` export
- `configs/1v1/NoWeapon/human_vs_bt.yaml` 신규

### 에이전트 탐색 경로 확장 (`scripts/run_match.py`)

| 우선순위 | v0.5.x | v0.9.x |
|---|---|---|
| 0 | - | 직접 경로 (경로 구분자 포함 시) |
| 1 | `submissions/{name}/{name}.yaml` | `submissions/{name}/{name}.yaml` |
| 2 | `examples/{name}.yaml` | `submissions/{name}.yaml` (flat, **신규**) |
| 3 | 직접 경로 | `examples/{name}.yaml` |
| 4 | - | `examples/{name}/{name}.yaml` (**신규**) |

### CSV 로깅 수정 (`runner.py`)

- 각도 값 `* 180.0` 변환 제거 (이미 도 단위이므로)

---

## 📝 커스텀 노드 마이그레이션 체크리스트

기존 v0.5.x 커스텀 노드가 있다면 아래를 수정:

1. `obs.get("ata_deg") * 180.0` → `obs.get("ata_deg")` (5개 각도 키 전체)
2. `obs.get("distance")` → `obs.get("distance_ft")`
3. `obs.get("alt_gap")` → `obs.get("alt_gap_ft")`
4. `obs.get("ego_vc")` → `obs.get("ego_vc_kts")`
5. `obs.get("ego_altitude")` → `obs.get("ego_altitude_ft")`
6. `obs.get("energy_diff")` → `obs.get("energy_diff_ft")`
7. `HighYoYo`, `LowYoYo`, `BarrelRoll`를 자식으로 쓰는 Sequence에 `memory: true` 추가 필요
