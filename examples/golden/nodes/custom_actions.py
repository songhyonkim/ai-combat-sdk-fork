"""
Alpha1 Custom Action Nodes

Callsign: Alpha1
Core: Proportional Navigation + Energy Management + State Memory
       + Adaptive Counter-Strategy (opponent-state-aware)
"""

import csv
import logging
import time
from pathlib import Path

import py_trees

logger = logging.getLogger(__name__)


class BaseAction(py_trees.behaviour.Behaviour):
    """Custom action base class"""

    def __init__(self, name: str):
        super().__init__(name)
        self.blackboard = self.attach_blackboard_client()
        self.blackboard.register_key(key="observation", access=py_trees.common.Access.READ)
        self.blackboard.register_key(key="action", access=py_trees.common.Access.WRITE)

    def set_action(self, delta_altitude_idx: int, delta_heading_idx: int, delta_velocity_idx: int):
        self.blackboard.action = [delta_altitude_idx, delta_heading_idx, delta_velocity_idx]


def _heading_from_tau(tau_deg: float, gain: float = 1.0) -> int:
    """Convert tau angle (degrees) to heading index [0-8] with proportional gain.

    tau_deg: target angle in degrees (-180 to 180)
    gain: proportional gain multiplier
    Returns heading index: 0=hard left(-90) ... 4=straight ... 8=hard right(+90)
    """
    cmd = tau_deg * gain
    idx = int(round(cmd / 22.5)) + 4
    return max(0, min(8, idx))


def _heading_pd(tau_deg: float, tau_rate: float,
                kp: float = 0.8, kd: float = 0.3) -> int:
    """PD controller on tau: proportional + derivative."""
    cmd = kp * tau_deg + kd * tau_rate
    idx = int(round(cmd / 22.5)) + 4
    return max(0, min(8, idx))


class PNPursuit(BaseAction):
    """PN-enhanced pursuit with energy management.

    Heading: PD controller on tau_deg (proportional + derivative).
    Altitude: Situation-aware (closing vs turning fight).
    Speed: ATA-aware — max speed when pointing at enemy, decel in turns.
    """

    def __init__(self, name: str = "PNPursuit",
                 kp: float = 1.0,
                 kd: float = 0.4,
                 close_range: float = 4921.0,
                 wez_max: float = 2999.0,
                 wez_min: float = 499.0,
                 far_range: float = 13123.0):
        super().__init__(name)
        self.kp = kp
        self.kd = kd
        self.close_range = close_range
        self.wez_max = wez_max
        self.wez_min = wez_min
        self.far_range = far_range
        self.prev_tau = None

    def update(self) -> py_trees.common.Status:
        try:
            obs = self.blackboard.observation

            tau = obs.get("tau_deg", 0.0)
            ata = obs.get("ata_deg", 180.0)
            distance_ft = obs.get("distance_ft", 32808.0)
            alt_gap_ft = obs.get("alt_gap_ft", 0.0)
            altitude_ft = obs.get("ego_altitude_ft", 16404.0)
            closure_kts = obs.get("closure_rate_kts", 0.0)

            # --- HEADING: PD on tau ---
            if self.prev_tau is not None:
                tau_rate = (tau - self.prev_tau) / 0.2
                # Increase gains at close range for tighter tracking
                kp = self.kp * (1.5 if distance_ft < self.close_range else 1.0)
                heading_idx = _heading_pd(tau, tau_rate, kp, self.kd)
            else:
                heading_idx = _heading_from_tau(tau, self.kp)
            self.prev_tau = tau

            # --- ALTITUDE: situation-dependent ---
            if altitude_ft < 2625:
                delta_alt = 4  # Emergency climb (Hard Deck ~305m)
            elif ata < 30 and distance_ft > self.wez_max:
                # Pointing at enemy but far: dive slightly for speed, close fast
                delta_alt = 1 if altitude_ft > 6562 else 2
            elif ata > 90:
                # Turning fight (enemy behind): maintain altitude, don't bleed energy climbing
                delta_alt = 2
            elif alt_gap_ft > 656:
                delta_alt = 2  # Have altitude advantage: maintain
            elif alt_gap_ft > -328:
                delta_alt = 2  # Roughly same altitude: maintain (save energy for turns)
            else:
                delta_alt = 3  # Below enemy: climb to reduce disadvantage

            # --- SPEED: ATA-aware ---
            if distance_ft < self.wez_min:
                delta_vel = 0  # Too close: hard brake
            elif distance_ft < self.wez_max and ata < 20:
                delta_vel = 1  # In WEZ + on target: decelerate for stable aim
            elif ata < 30 and distance_ft > self.close_range:
                delta_vel = 4  # Pointing at enemy + far: max speed to close!
            elif ata > 60 and distance_ft < self.close_range:
                delta_vel = 1  # Turning fight + close: decelerate for tighter turn
            elif distance_ft < self.close_range:
                delta_vel = 2  # Close: maintain
            elif distance_ft < self.far_range:
                delta_vel = 3  # Mid: accelerate
            else:
                delta_vel = 4  # Far: max speed

            # Closure rate override: if enemy is opening, push harder
            if closure_kts < -58 and distance_ft > self.wez_max:
                delta_vel = max(delta_vel, 4)

            self.set_action(delta_alt, heading_idx, delta_vel)
            return py_trees.common.Status.SUCCESS

        except Exception as e:
            logger.warning(f"PNPursuit error: {e}")
            self.set_action(2, 4, 2)
            return py_trees.common.Status.FAILURE


class PNAttack(BaseAction):
    """Close-range precision engagement for Gun WEZ.

    Tighter PD gains for precision aiming.
    Speed management for stable gun platform.
    WEZ awareness: ATA < 12deg, 152-914m.
    """

    def __init__(self, name: str = "PNAttack",
                 kp: float = 1.2,
                 kd: float = 0.5):
        super().__init__(name)
        self.kp = kp
        self.kd = kd
        self.prev_tau = None

    def update(self) -> py_trees.common.Status:
        try:
            obs = self.blackboard.observation

            tau = obs.get("tau_deg", 0.0)
            distance_ft = obs.get("distance_ft", 3281.0)
            alt_gap_ft = obs.get("alt_gap_ft", 0.0)
            closure_kts = obs.get("closure_rate_kts", 0.0)

            # --- HEADING: tight PD ---
            if self.prev_tau is not None:
                tau_rate = (tau - self.prev_tau) / 0.2
                heading_idx = _heading_pd(tau, tau_rate, self.kp, self.kd)
            else:
                heading_idx = _heading_from_tau(tau, self.kp)
            self.prev_tau = tau

            # --- ALTITUDE: minimal, keep stable ---
            if alt_gap_ft > 656:
                delta_alt = 2  # We're above: maintain
            elif alt_gap_ft > -328:
                delta_alt = 3  # Slightly below: climb gently
            else:
                delta_alt = 2  # Don't chase vertically during attack

            # --- SPEED: decelerate for stable gun platform ---
            if distance_ft < 499:
                delta_vel = 0  # Too close, hard brake
            elif distance_ft < 1312:
                # Very close: adjust based on closure
                delta_vel = 0 if closure_kts > 58 else 1
            elif distance_ft < 2297:
                delta_vel = 1  # Optimal WEZ range: decelerate
            elif distance_ft < 2999:
                delta_vel = 2  # Edge of WEZ: maintain
            else:
                delta_vel = 3  # Just outside WEZ: close in

            self.set_action(delta_alt, heading_idx, delta_vel)
            return py_trees.common.Status.SUCCESS

        except Exception as e:
            logger.warning(f"PNAttack error: {e}")
            self.set_action(2, 4, 2)
            return py_trees.common.Status.FAILURE


class EnergyRecovery(BaseAction):
    """Energy recovery maneuver when energy state is low.

    Trades altitude for speed or maintains level flight
    while tracking enemy with relaxed heading control.
    """

    def __init__(self, name: str = "EnergyRecovery",
                 min_velocity: float = 389.0,
                 critical_velocity: float = 292.0):
        super().__init__(name)
        self.min_velocity = min_velocity
        self.critical_velocity = critical_velocity

    def update(self) -> py_trees.common.Status:
        try:
            obs = self.blackboard.observation

            tau = obs.get("tau_deg", 0.0)
            velocity_kts = obs.get("ego_vc_kts", 389.0)
            altitude_ft = obs.get("ego_altitude_ft", 16404.0)

            # Heading: relaxed tracking (save energy, don't hard turn)
            heading_idx = _heading_from_tau(tau, 0.5)

            # Altitude/Speed: trade altitude for speed if needed
            if velocity_kts < self.critical_velocity:
                delta_alt = 1  # Dive to gain speed
                delta_vel = 4  # Max accelerate
            elif velocity_kts < self.min_velocity:
                delta_alt = 1 if altitude_ft > 4921 else 2
                delta_vel = 4  # Accelerate
            else:
                delta_alt = 2  # Maintain altitude
                delta_vel = 3  # Accelerate

            # Hard Deck safety
            if altitude_ft < 2625:
                delta_alt = 4
                delta_vel = 3

            self.set_action(delta_alt, heading_idx, delta_vel)
            return py_trees.common.Status.SUCCESS

        except Exception as e:
            logger.warning(f"EnergyRecovery error: {e}")
            self.set_action(2, 4, 3)
            return py_trees.common.Status.FAILURE


# ============================================================
# StepLogger — Per-step obs recorder for analysis
# ============================================================

_OBS_KEYS = [
    'distance_ft', 'ego_altitude_ft', 'ego_vc_kts', 'alt_gap_ft',
    'ata_deg', 'aa_deg', 'hca_deg', 'tau_deg',
    'relative_bearing_deg', 'side_flag',
    'closure_rate_kts', 'turn_rate_degs', 'in_39_line', 'overshoot_risk',
    'tc_type', 'energy_advantage', 'energy_diff_ft',
    'alt_advantage', 'spd_advantage',
]


class StepLogger(BaseAction):
    """Records per-step observation dict to a CSV file.

    Always returns FAILURE so the parent Selector falls through
    to the actual combat logic. Place as the FIRST child of the
    root Selector to capture every BT tick.

    Usage in YAML:
        - type: Action
          name: StepLogger
          params:
            log_dir: logs/alpha1

    Remove from YAML for competition — no overhead when absent.
    """

    def __init__(self, name: str = "StepLogger", log_dir: str = "logs/alpha1"):
        super().__init__(name)
        self._log_dir = Path(log_dir)
        self._log_file = None
        self._writer = None
        self._step = 0

    def _ensure_open(self):
        if self._writer is not None:
            return
        self._log_dir.mkdir(parents=True, exist_ok=True)
        fname = self._log_dir / f"steps_{int(time.time())}.csv"
        self._log_file = open(fname, 'w', newline='', encoding='utf-8')
        self._writer = csv.DictWriter(
            self._log_file,
            fieldnames=['step'] + _OBS_KEYS,
            extrasaction='ignore',
        )
        self._writer.writeheader()

    def update(self) -> py_trees.common.Status:
        try:
            self._ensure_open()
            obs = self.blackboard.observation
            row = {k: obs.get(k, '') for k in _OBS_KEYS}
            row['step'] = self._step
            self._step += 1
            self._writer.writerow(row)
            self._log_file.flush()
        except Exception as e:
            logger.debug(f"StepLogger error: {e}")

        # Write neutral action (overwritten by next Selector child)
        self.set_action(2, 4, 2)
        return py_trees.common.Status.FAILURE  # always fail → Selector continues

    def terminate(self, new_status):
        if self._log_file:
            try:
                self._log_file.close()
            except Exception:
                pass
            self._log_file = None
            self._writer = None


# ============================================================
# AdaptiveAction — Opponent-state-aware counter-strategy
# ============================================================

class AdaptiveAction(BaseAction):
    """Reactive counter-strategy action.

    Reads 19 observation features at each step, classifies
    the current tactical situation, and selects the optimal
    (delta_alt, delta_heading, delta_vel) response.

    Situation hierarchy:
      1. OFFENSIVE  — we're at opp's 6 o'clock (aa < 60°, ata < 60°)
                       → LeadPursuit-style: cut corners, close aggressively
      2. DEFENSIVE  — opp is at our 6 o'clock (aa > 140°)
                       → BreakTurn-style: hard evasive turn
      3. OVERSHOOT  — about to pass the opponent
                       → HighYoYo-style: climb + lag to reset
      4. 1-CIRCLE   — close range, same-direction turn (HCA < 90°)
                       → tight turn, decelerate for turn rate
      5. 2-CIRCLE   — close range, opposing turns (HCA > 90°)
                       → energy preservation, wider arc
      6. DEFAULT    — lag pursuit (energy-efficient, set up WEZ)
    """

    def __init__(self, name: str = "AdaptiveAction"):
        super().__init__(name)
        self._prev_tau = None

    def update(self) -> py_trees.common.Status:
        try:
            obs = self.blackboard.observation

            aa          = obs.get('aa_deg', 90.0)
            ata         = obs.get('ata_deg', 90.0)
            tau         = obs.get('tau_deg', 0.0)
            distance_ft = obs.get('distance_ft', 16404.0)
            tc_type     = obs.get('tc_type', '2-circle')
            overshoot   = obs.get('overshoot_risk', False)
            side_flag   = int(obs.get('side_flag', 0))
            alt_gap_ft  = obs.get('alt_gap_ft', 0.0)
            ego_alt_ft  = obs.get('ego_altitude_ft', 16404.0)
            closure_kts = obs.get('closure_rate_kts', 0.0)
            energy_diff_ft = obs.get('energy_diff_ft', 0.0)

            # Derivative for PD heading control
            if self._prev_tau is not None:
                tau_rate = (tau - self._prev_tau) / 0.2
            else:
                tau_rate = 0.0
            self._prev_tau = tau

            # ── Situation Classification ──

            if aa < 60 and ata < 70:
                # OFFENSIVE: we have rear-aspect position
                da, dh, dv = self._offensive(tau, tau_rate, alt_gap_ft, distance_ft, ata)

            elif aa > 140:
                # DEFENSIVE: opponent has our 6 o'clock
                da, dh, dv = self._defensive(side_flag, ego_alt_ft)

            elif overshoot:
                # OVERSHOOT RISK: too fast, about to pass opponent
                da, dh, dv = self._high_yoyo(tau, side_flag)

            elif distance_ft < 9843:
                if tc_type == '1-circle':
                    # 1-circle: tight turn to cut inside
                    da, dh, dv = self._one_circle(tau, tau_rate)
                else:
                    # 2-circle: energy fight, wider arc
                    da, dh, dv = self._two_circle(tau, energy_diff_ft, alt_gap_ft)

            else:
                # DEFAULT: lag pursuit — energy-efficient, set up WEZ
                da, dh, dv = self._lag_pursuit(tau, tau_rate, alt_gap_ft, distance_ft, closure_kts, ego_alt_ft)

            self.set_action(da, dh, dv)
            return py_trees.common.Status.SUCCESS

        except Exception as e:
            logger.warning(f"AdaptiveAction error: {e}")
            self.set_action(2, 4, 2)
            return py_trees.common.Status.FAILURE

    # ── Sub-maneuver implementations ──

    def _offensive(self, tau, tau_rate, alt_gap_ft, distance_ft, ata):
        """We have rear-aspect advantage: lead pursuit to cut corners."""
        # Lead heading (gain > 1 → head toward where opp will be)
        kp = 1.3 if distance_ft > 6562 else 1.1
        dh = _heading_pd(tau, tau_rate, kp=kp, kd=0.2)

        # Altitude: climb toward opp if they're above, maintain if we're above
        if alt_gap_ft > 492:
            da = 3
        elif alt_gap_ft < -492:
            da = 2
        else:
            da = 2

        # Speed: moderate to avoid overshoot
        if ata < 20 and distance_ft < 4921:
            dv = 2   # about to be in WEZ: stable platform
        elif distance_ft > 9843:
            dv = 4   # far: close fast
        else:
            dv = 3

        return da, dh, dv

    def _defensive(self, side_flag, ego_alt_ft):
        """Opponent has rear-aspect: hard break turn."""
        # Hard turn OPPOSITE to opponent's side
        if side_flag == 1:      # opp on our right → hard left
            dh = 0
        elif side_flag == -1:   # opp on our left → hard right
            dh = 8
        else:
            dh = 0  # default hard left

        da = 1 if ego_alt_ft > 3281 else 2  # slight descent for speed
        dv = 4  # max speed

        return da, dh, dv

    def _high_yoyo(self, tau, side_flag):
        """Overshoot risk: High Yo-Yo — climb and lag to reset."""
        dh = _heading_from_tau(tau, gain=0.5)  # lag behind opp
        da = 4   # climb
        dv = 1   # decelerate (tighter turn, overshoot prevention)
        return da, dh, dv

    def _one_circle(self, tau, tau_rate):
        """1-circle turn fight: tight inside turn."""
        dh = _heading_pd(tau, tau_rate, kp=1.5, kd=0.3)
        da = 2   # maintain altitude for max turn rate
        dv = 1   # decelerate → tighter turn radius
        return da, dh, dv

    def _two_circle(self, tau, energy_diff_ft, alt_gap_ft):
        """2-circle turn fight: energy fight, wider arc."""
        dh = _heading_from_tau(tau, gain=0.9)  # softer turn

        # Climb if we have energy advantage (altitude trade-off)
        if energy_diff_ft > 500:
            da = 3
        elif alt_gap_ft < -656:
            da = 2  # we're above: maintain
        else:
            da = 2

        dv = 3  # maintain speed (energy fight)
        return da, dh, dv

    def _lag_pursuit(self, tau, tau_rate, alt_gap_ft, distance_ft, closure_kts, ego_alt_ft):
        """Default lag pursuit: energy-efficient, follow from behind."""
        dh = _heading_pd(tau, tau_rate, kp=0.8, kd=0.3)

        # Altitude management
        if ego_alt_ft < 2625:
            da = 4  # emergency climb
        elif alt_gap_ft > 656:
            da = 3  # climb to match opp
        elif alt_gap_ft < -656:
            da = 2  # maintain our altitude advantage
        else:
            da = 2

        # Speed: close when far, moderate when near
        if distance_ft > 13123:
            dv = 4
        elif distance_ft > 6562:
            dv = 3
        elif closure_kts < -39:  # distance opening
            dv = 4
        else:
            dv = 2

        return da, dh, dv
