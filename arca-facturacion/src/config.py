"""
Carga de configuración desde un .ini. Nada de credenciales ni datos del
contribuyente hardcodeados en el código: todo sale de config/config.*.ini
(que no se sube a git).
"""
from __future__ import annotations

import configparser
import os
from dataclasses import dataclass

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Endpoints oficiales de ARCA (ex AFIP). No se leen del .ini: dependen
# únicamente del ambiente elegido, así que se fijan acá para no permitir
# que un typo en el config mande una factura de prueba a producción
# (o viceversa).
WSAA_WSDL = {
    "homologacion": "https://wsaahomo.afip.gov.ar/ws/services/LoginCms?wsdl",
    "produccion": "https://wsaa.afip.gov.ar/ws/services/LoginCms?wsdl",
}
WSAA_URL = {
    "homologacion": "https://wsaahomo.afip.gov.ar/ws/services/LoginCms",
    "produccion": "https://wsaa.afip.gov.ar/ws/services/LoginCms",
}
WSFE_WSDL = {
    "homologacion": "https://wswhomo.afip.gov.ar/wsfev1/service.asmx?WSDL",
    "produccion": "https://servicios1.afip.gov.ar/wsfev1/service.asmx?WSDL",
}

# Servicio que se pide en el TRA (Ticket de Requerimiento de Acceso) para
# poder usar WSFEv1.
WSAA_SERVICE = "wsfe"


@dataclass
class ArcaConfig:
    ambiente: str
    cuit: str
    punto_venta: int
    cbte_tipo: int
    concepto: int
    doc_tipo: int
    doc_nro: int
    condicion_iva_receptor_id: int
    importe_total: float
    moneda: str
    cotizacion: float
    cert_path: str
    key_path: str
    cache_token_path: str
    openssl_path: str

    @property
    def wsaa_wsdl(self) -> str:
        return WSAA_WSDL[self.ambiente]

    @property
    def wsaa_url(self) -> str:
        return WSAA_URL[self.ambiente]

    @property
    def wsfe_wsdl(self) -> str:
        return WSFE_WSDL[self.ambiente]


def _resolve(path: str) -> str:
    if os.path.isabs(path):
        return path
    return os.path.join(BASE_DIR, path)


def load_config(path: str | None = None) -> ArcaConfig:
    """
    Lee config/config.homologacion.ini por defecto (o la ruta que se pase
    por parámetro / variable de entorno ARCA_CONFIG).
    """
    if path is None:
        path = os.environ.get(
            "ARCA_CONFIG",
            os.path.join(BASE_DIR, "config", "config.homologacion.ini"),
        )

    if not os.path.exists(path):
        raise FileNotFoundError(
            f"No encontré el archivo de configuración '{path}'.\n"
            "Copiá config/config.example.ini a config/config.homologacion.ini "
            "y completá tus datos."
        )

    parser = configparser.ConfigParser()
    parser.read(path, encoding="utf-8")

    arca = parser["arca"]
    certs = parser["certificados"]

    ambiente = arca.get("ambiente", "homologacion").strip()
    if ambiente not in WSAA_WSDL:
        raise ValueError(
            f"ambiente='{ambiente}' inválido. Usá 'homologacion' o 'produccion'."
        )

    return ArcaConfig(
        ambiente=ambiente,
        cuit=arca.get("cuit").strip(),
        punto_venta=arca.getint("punto_venta"),
        cbte_tipo=arca.getint("cbte_tipo"),
        concepto=arca.getint("concepto"),
        doc_tipo=arca.getint("doc_tipo"),
        doc_nro=arca.getint("doc_nro"),
        condicion_iva_receptor_id=arca.getint("condicion_iva_receptor_id"),
        importe_total=arca.getfloat("importe_total"),
        moneda=arca.get("moneda", "PES").strip(),
        cotizacion=arca.getfloat("cotizacion", fallback=1.0),
        cert_path=_resolve(certs.get("cert_path")),
        key_path=_resolve(certs.get("key_path")),
        cache_token_path=_resolve(certs.get("cache_token_path")),
        openssl_path=certs.get("openssl_path", fallback="openssl").strip(),
    )
