# Changelog: v0.9.4 → v0.10.1

**릴리즈 날짜:** 2026-05-13

## 변경사항

- refactor: BaseAction/BaseCondition 중복 제거 및 에너지/거리 단위 표준화
- docs: 실행 모델(Execution Model) 섹션 추가 - 시간 계층 및 20 Hz condition subtick 상세 설명
- refactor: BT 조건 노드 20 Hz 분리 평가 및 TimedAction tick rate 자동 환산 구현
- refactor: BT 10 Hz / RNN 5 Hz 분리 캐싱 구현 - env.step 20 Hz 전환 대응
- docs: BT tick 주기 변경 결정 문서 업데이트 - ADT 벤치마크 정합 및 최종 권고안 추가
- docs: ADT 논문 PDF 추가
- docs: ADT 교전 환경 조건 정리 문서 추가
- docs: BT tick 주기 변경 분석 문서 추가
- refactor: Tacview 실시간 텔레메트리 확장 속성 포맷 개선 및 이벤트 캐싱 추가
- refactor: 늦은 접속 클라이언트를 위한 Tacview 헤더 재전송 로직 추가
- refactor: 리플레이 및 실시간 텔레메트리 프레임 생성 로직 통합
- docs: 조이스틱 아키텍처 문서 추가 및 스로틀 범위 주석 업데이트
- refactor: 스로틀 정규화 범위 0.4~0.9 → 0.2~1.0으로 확장
- refactor: 고속 영역 속도 안전장치 추가 및 NN OOD 방지 로직 구현
- refactor: 매치 런타임 종료 조건 개선 및 max_steps 설정 추가
- ..
- refactor: 확장 로그 HDG/CAS 계산 방식 개선 및 포맷 수정
- refactor: 레거시 RL 학습용 설정 파일 _legacy 디렉토리로 이동 및 SDK 빌드 제외
- feat: 초기 속도 안정화를 위한 IC 재적용 및 검증 스크립트 추가
- fix: Supabase 버전 상한선 2.10.0 미만으로 제한
- refactor: Python 버전 요구사항 3.12 → 3.14로 업데이트
- refactor: crash 발생 시 Tacview 북마크 자동 기록 및 결과 요약에 충돌 원인 표시
- refactor: Tacview 리플레이 기록을 비동기 Writer로 전환 및 프레임 생성 로직 통합
- refactor: Eagle1 → Eagle3 전환 및 위협 판정 로직 개선
- refactor: crash 발생 시 원인 상세 출력 기능 추가
- refactor: 충돌/극한상태 종료 시 승패 판정 로직 추가
- refactor: 항공기 ID 명명 규칙 복원 및 LeadPursuit 전용 행동트리 추가
- refactor: 항공기 ID 명명 규칙 변경 및 초기 속도 조정
- feat: Tacview 설정 대기 기능 추가 및 대기 중 초기 프레임 전송
- feat: 조이스틱 입력 처리 모듈 분리 및 리플레이 Writer 비동기화
- refactor: 인간 조종 응답성 향상을 위해 시뮬레이션 타임스텝 0.2s → 0.05s로 단축
- refactor: 조이스틱 입력 처리를 워커 스레드에서 메인 스레드 폴링 방식으로 전환
- feat: 조이스틱 초기화를 워커 스레드로 이동하여 Windows SDL2 이벤트 처리 개선
- feat: 조이스틱 입력 처리를 메인 스레드로 이동하여 Windows SDL2 호환성 개선
- feat: 조이스틱 스로틀 축 반전 옵션 추가 및 디버그 로깅 강화
- feat: 조이스틱 진단 스크립트 추가
- docs: trees/ 폴더에 AI 행동트리 예제 4종 및 참조 문서 추가

