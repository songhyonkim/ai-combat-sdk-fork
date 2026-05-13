"""
Viper1 커스텀 조건 노드

Callsign: Viper1
"""

import logging
import py_trees
from src.behavior_tree.nodes.conditions import BaseCondition

logger = logging.getLogger(__name__)


class HighEnergyState(BaseCondition):
    """고에너지 상태 확인

    specific_energy_ft (ft) = ego_altitude_ft + ego_vc_fts² / (2 × g_ft)
    threshold 기본값 30000 ft ≈ 순항 에너지 + 여유
    """

    def __init__(self, name: str = "HighEnergyState", threshold: float = 30000.0):
        super().__init__(name)
        self.threshold = threshold
        self.blackboard = self.attach_blackboard_client()
        self.blackboard.register_key(key="observation", access=py_trees.common.Access.READ)

    def update(self) -> py_trees.common.Status:
        try:
            obs = self.blackboard.observation
            energy = obs.get("specific_energy_ft", 22000.0)

            if energy > self.threshold:
                return py_trees.common.Status.SUCCESS
            else:
                return py_trees.common.Status.FAILURE
        except (KeyError, AttributeError, TypeError) as e:
            logger.warning(f"HighEnergyState 실행 실패: {e}")
            return py_trees.common.Status.FAILURE


class LowEnergyState(BaseCondition):
    """저에너지 상태 확인

    specific_energy_ft (ft) 기준. threshold 기본값 20000 ft ≈ 에너지 부족 판단선
    """

    def __init__(self, name: str = "LowEnergyState", threshold: float = 20000.0):
        super().__init__(name)
        self.threshold = threshold
        self.blackboard = self.attach_blackboard_client()
        self.blackboard.register_key(key="observation", access=py_trees.common.Access.READ)

    def update(self) -> py_trees.common.Status:
        try:
            obs = self.blackboard.observation
            energy = obs.get("specific_energy_ft", 22000.0)

            if energy < self.threshold:
                return py_trees.common.Status.SUCCESS
            else:
                return py_trees.common.Status.FAILURE
        except (KeyError, AttributeError, TypeError) as e:
            logger.warning(f"LowEnergyState 실행 실패: {e}")
            return py_trees.common.Status.FAILURE


class OptimalAttackPosition(BaseCondition):
    """최적 공격 위치 확인

    조건:
    - 거리: 2625 ft ~ 8202 ft (800 m ~ 2500 m, WEZ 범위)
    - ATA: < 30도 (조준 가능)
    - 고도 우위: > 0 ft
    """

    def __init__(self, name: str = "OptimalAttackPosition"):
        super().__init__(name)
        self.blackboard = self.attach_blackboard_client()
        self.blackboard.register_key(key="observation", access=py_trees.common.Access.READ)

    def update(self) -> py_trees.common.Status:
        try:
            obs = self.blackboard.observation
            distance_ft = obs.get("distance_ft", 10000.0)
            ata_deg = obs.get("ata_deg", 180.0)
            alt_gap_ft = obs.get("alt_gap_ft", 0.0)

            # 최적 거리 (ft)
            if distance_ft < 2625 or distance_ft > 8202:
                return py_trees.common.Status.FAILURE

            # 조준 가능 각도
            if abs(ata_deg) > 30:
                return py_trees.common.Status.FAILURE

            # 고도 우위
            if alt_gap_ft < 0:
                return py_trees.common.Status.FAILURE

            return py_trees.common.Status.SUCCESS
        except (KeyError, AttributeError, TypeError) as e:
            logger.warning(f"OptimalAttackPosition 실행 실패: {e}")
            return py_trees.common.Status.FAILURE
