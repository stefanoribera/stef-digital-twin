"""Esquemas compartidos entre la API y el worker.

El worker DEBE validar con el mismo esquema que la API: la cola de Redis es
una frontera de confianza, no un canal interno de confianza implicita.
"""
import math

from pydantic import BaseModel, ConfigDict, Field


class TelemetryPayload(BaseModel):
    model_config = ConfigDict(extra="forbid")

    sensor_id: int = Field(ge=1, le=100)
    radiation_level: float = Field(ge=0.0, le=1.0e6, allow_inf_nan=False)


class CollisionPayload(BaseModel):
    """Cinematica de un par de muones, acotada al dominio fisico real del CMS.

    allow_inf_nan=False es obligatorio: json.loads() de la stdlib acepta los
    literales no estandar Infinity y NaN, y Pydantic los admite por defecto.
    """

    model_config = ConfigDict(extra="forbid")

    # pt > 0 GeV (un momento transverso negativo o nulo no existe)
    pt1: float = Field(gt=0.0, le=1.0e4, allow_inf_nan=False)
    pt2: float = Field(gt=0.0, le=1.0e4, allow_inf_nan=False)
    # |eta| <= 5 cubre de sobra la aceptancia del detector CMS (~2.4 para muones)
    eta1: float = Field(ge=-5.0, le=5.0, allow_inf_nan=False)
    eta2: float = Field(ge=-5.0, le=5.0, allow_inf_nan=False)
    # phi es un angulo azimutal: [-pi, pi]
    phi1: float = Field(ge=-math.pi, le=math.pi, allow_inf_nan=False)
    phi2: float = Field(ge=-math.pi, le=math.pi, allow_inf_nan=False)
