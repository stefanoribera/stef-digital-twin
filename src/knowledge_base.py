import yaml
from pydantic import BaseModel

class AcceleratorConfig(BaseModel):
    max_single_particle_pt_gev: float

class DetectorConfig(BaseModel):
    cms_max_pseudorapidity_eta: float

class ZBosonConfig(BaseModel):
    rest_mass_gev: float
    mass_tolerance_gev: float

class ParticlesConfig(BaseModel):
    z_boson: ZBosonConfig

class PhysicsRules(BaseModel):
    accelerator: AcceleratorConfig
    detector: DetectorConfig
    particles: ParticlesConfig

def load_knowledge_base(filepath: str = "physics_rules.yaml") -> PhysicsRules:
    """Parses the YAML Knowledge Base into a strongly-typed, immutable Pydantic object."""
    with open(filepath, "r") as f:
        raw_data = yaml.safe_load(f)
    return PhysicsRules(**raw_data)

KNOWLEDGE_BASE = load_knowledge_base()