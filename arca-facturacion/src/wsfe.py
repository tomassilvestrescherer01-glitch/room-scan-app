"""
Cliente WSFEv1 (Facturación Electrónica) de ARCA/AFIP.

Antes de confiar en los códigos que usa este módulo (CbteTipo, Concepto,
DocTipo, CondicionIVAReceptorId), corré consultar_parametros.py: ese
script le pregunta al propio web service de homologación cuáles son los
valores válidos, en vez de confiar de memoria en esta documentación.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from zeep import Client
from zeep.transports import Transport

from .config import ArcaConfig


class WSFEError(RuntimeError):
    pass


def _cliente(config: ArcaConfig) -> Client:
    transport = Transport(timeout=30)
    return Client(config.wsfe_wsdl, transport=transport)


def _auth(config: ArcaConfig, credenciales: dict) -> dict:
    return {
        "Token": credenciales["token"],
        "Sign": credenciales["sign"],
        "Cuit": config.cuit,
    }


def _chequear_errores(resultado) -> None:
    errores = getattr(resultado, "Errors", None)
    if errores and errores.Err:
        detalle = "; ".join(
            f"[{e.Code}] {e.Msg}" for e in errores.Err
        )
        raise WSFEError(f"ARCA devolvió error(es): {detalle}")


def obtener_ultimo_comprobante(config: ArcaConfig, credenciales: dict) -> int:
    cliente = _cliente(config)
    resultado = cliente.service.FECompUltimoAutorizado(
        Auth=_auth(config, credenciales),
        PtoVta=config.punto_venta,
        CbteTipo=config.cbte_tipo,
    )
    _chequear_errores(resultado)
    return resultado.CbteNro


@dataclass
class ResultadoFactura:
    cae: str
    cae_vencimiento: str
    numero_comprobante: int
    observaciones: str | None


def emitir_factura(config: ArcaConfig, credenciales: dict) -> ResultadoFactura:
    """
    Emite UNA factura con los datos fijos de config.*.ini (Factura C,
    mismo monto, a consumidor final) y devuelve el CAE.
    """
    cliente = _cliente(config)
    ultimo = obtener_ultimo_comprobante(config, credenciales)
    numero = ultimo + 1
    hoy = date.today().strftime("%Y%m%d")

    detalle = {
        "Concepto": config.concepto,
        "DocTipo": config.doc_tipo,
        "DocNro": config.doc_nro,
        "CbteDesde": numero,
        "CbteHasta": numero,
        "CbteFch": hoy,
        "ImpTotal": config.importe_total,
        "ImpTotConc": 0,
        "ImpNeto": config.importe_total,
        "ImpOpEx": 0,
        "ImpTrib": 0,
        # Factura C (monotributista) no discrimina IVA: no se manda
        # array de Iva y el importe de IVA es 0.
        "ImpIVA": 0,
        "MonId": config.moneda,
        "MonCotiz": config.cotizacion,
        "CondicionIVAReceptorId": config.condicion_iva_receptor_id,
    }

    # Concepto 2 o 3 (servicios) requiere informar el período del
    # servicio y la fecha de vencimiento de pago.
    if config.concepto in (2, 3):
        detalle["FchServDesde"] = hoy
        detalle["FchServHasta"] = hoy
        detalle["FchVtoPago"] = hoy

    solicitud = {
        "FeCabReq": {
            "CantReg": 1,
            "PtoVta": config.punto_venta,
            "CbteTipo": config.cbte_tipo,
        },
        "FeDetReq": {"FECAEDetRequest": [detalle]},
    }

    resultado = cliente.service.FECAESolicitar(
        Auth=_auth(config, credenciales),
        FeCAEReq=solicitud,
    )
    _chequear_errores(resultado)

    resp_cabecera = resultado.FeCabResp
    resp_detalle = resultado.FeDetResp.FECAEDetResponse[0]

    if resp_cabecera.Resultado != "A":
        observ = getattr(resp_detalle, "Observaciones", None)
        obs_txt = ""
        if observ and observ.Obs:
            obs_txt = "; ".join(f"[{o.Code}] {o.Msg}" for o in observ.Obs)
        raise WSFEError(
            f"ARCA no aprobó el comprobante (Resultado={resp_cabecera.Resultado}). "
            f"Observaciones: {obs_txt or 'ninguna'}"
        )

    observ = getattr(resp_detalle, "Observaciones", None)
    obs_txt = None
    if observ and observ.Obs:
        obs_txt = "; ".join(f"[{o.Code}] {o.Msg}" for o in observ.Obs)

    return ResultadoFactura(
        cae=resp_detalle.CAE,
        cae_vencimiento=resp_detalle.CAEFchVto,
        numero_comprobante=numero,
        observaciones=obs_txt,
    )
