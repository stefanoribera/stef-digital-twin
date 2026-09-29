from src.knowledge_base import KNOWLEDGE_BASE
from src.schemas import CollisionPayload

class PhysicsOracle:
    """
    Deterministic Expert System for High-Energy Physics.
    Enforces the Standard Model and CMS detector limits via Forward-Chaining logic.
    """

    @staticmethod
    def evaluate_kinematics(payload: CollisionPayload) -> dict:
        """Evaluates raw facts against the theoretical limits of the accelerator."""
        max_pt = KNOWLEDGE_BASE.accelerator.max_single_particle_pt_gev
        max_eta = KNOWLEDGE_BASE.detector.cms_max_pseudorapidity_eta

        # Rule 1: Conservation of Energy / Accelerator Limits
        if payload.pt1 > max_pt or payload.pt2 > max_pt:
            return {
                "status": "HARD_STOP",
                "reason": f"Kinematic Violation: Transverse momentum exceeds theoretical maximum ({max_pt} GeV). Sensor calibration failure inferred."
            }

        # Rule 2: Geometric Detector Limits
        if abs(payload.eta1) > max_eta or abs(payload.eta2) > max_eta:
            return {
                "status": "HARD_STOP",
                "reason": f"Geometric Violation: Particle trajectory exceeds CMS detector acceptance bounds (|eta| > {max_eta})."
            }

        return {"status": "PASS"}

    @staticmethod
    def evaluate_resonance(invariant_mass: float) -> dict:
        """Classifies the calculated mass against known fundamental particles."""
        z_mass = KNOWLEDGE_BASE.particles.z_boson.rest_mass_gev
        tolerance = KNOWLEDGE_BASE.particles.z_boson.mass_tolerance_gev

        # Rule 3: Resonance Window Detection
        if abs(invariant_mass - z_mass) <= tolerance:
            return {
                "status": "OPTIMAL",
                "classification": "Z_BOSON_CANDIDATE",
                "narrative": f"Resonance detected at {invariant_mass:.2f} GeV. Consistent with leptonic decay of a Z-Boson."
            }

        return {
            "status": "IGNORED",
            "classification": "BACKGROUND",
            "narrative": "Standard Model background noise."
        }