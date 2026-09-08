"""
Cliente WSAA (Web Service de Autenticación y Autorización) de ARCA/AFIP.

Flujo:
1. Arma un TRA (Ticket de Requerimiento de Acceso), un XML chiquito que
   pide acceso al servicio "wsfe" con una ventana de validez corta.
2. Lo firma en formato CMS/PKCS#7 con el certificado + clave privada
   (usando el "openssl smime -sign" ya instalado en el paso 1).
3. Manda ese CMS al método loginCms de WSAA.
4. ARCA devuelve un Token + Sign que valen 12hs. Se cachean en un JSON
   local para no pedir uno nuevo en cada factura.
"""
from __future__ import annotations

import base64
import json
import os
import subprocess
import tempfile
import uuid
from datetime import datetime, timedelta, timezone

import requests

from .config import ArcaConfig, WSAA_SERVICE

# Margen de seguridad: si al token cacheado le quedan menos de esto,
# se pide uno nuevo en vez de arriesgarse a que venza a mitad de la llamada.
_MARGEN_SEGURIDAD = timedelta(minutes=10)

_SOAP_ENVELOPE = """<?xml version="1.0" encoding="utf-8"?>
<soapenv:Envelope xmlns:soapenv="http://schemas.xmlsoap.org/soap/envelope/"
                   xmlns:wsaa="http://wsaa.view.sua.dvadac.desarrollosisi.com.ar">
  <soapenv:Header/>
  <soapenv:Body>
    <wsaa:loginCms>
      <wsaa:in0>{cms_b64}</wsaa:in0>
    </wsaa:loginCms>
  </soapenv:Body>
</soapenv:Envelope>"""


class WSAAError(RuntimeError):
    pass


def _generar_tra() -> str:
    ahora = datetime.now(timezone.utc)
    generation_time = ahora - timedelta(minutes=1)
    expiration_time = ahora + timedelta(minutes=10)
    unique_id = str(int(ahora.timestamp()))

    return f"""<?xml version="1.0" encoding="UTF-8"?>
<loginTicketRequest version="1.0">
  <header>
    <uniqueId>{unique_id}</uniqueId>
    <generationTime>{generation_time.strftime('%Y-%m-%dT%H:%M:%S%z')}</generationTime>
    <expirationTime>{expiration_time.strftime('%Y-%m-%dT%H:%M:%S%z')}</expirationTime>
  </header>
  <service>{WSAA_SERVICE}</service>
</loginTicketRequest>"""


def _firmar_tra_cms(tra_xml: str, cert_path: str, key_path: str, openssl_path: str) -> bytes:
    """
    Firma el TRA con openssl smime, devuelve el CMS/PKCS#7 en DER (bytes).
    Requiere el certificado (.crt) y la clave privada (.key) del ambiente
    correspondiente. La clave privada nunca sale de esta máquina.
    """
    for label, path in (("certificado", cert_path), ("clave privada", key_path)):
        if not os.path.exists(path):
            raise WSAAError(
                f"No encontré el archivo de {label} en '{path}'. "
                "Revisá config/config.*.ini."
            )

    with tempfile.TemporaryDirectory() as tmp:
        tra_path = os.path.join(tmp, "tra.xml")
        cms_path = os.path.join(tmp, "tra.tra")
        with open(tra_path, "w", encoding="utf-8") as f:
            f.write(tra_xml)

        cmd = [
            openssl_path, "smime", "-sign",
            "-signer", cert_path,
            "-inkey", key_path,
            "-outform", "DER",
            "-nodetach",
            "-in", tra_path,
            "-out", cms_path,
        ]
        proc = subprocess.run(cmd, capture_output=True, text=True)
        if proc.returncode != 0:
            raise WSAAError(
                "Falló la firma del TRA con openssl. Salida de openssl:\n"
                f"{proc.stderr}"
            )

        with open(cms_path, "rb") as f:
            return f.read()


def _login_cms(cms_der: bytes, wsaa_url: str) -> str:
    cms_b64 = base64.b64encode(cms_der).decode("ascii")
    body = _SOAP_ENVELOPE.format(cms_b64=cms_b64)

    headers = {
        "Content-Type": "text/xml; charset=utf-8",
        "SOAPAction": "http://wsaa.view.sua.dvadac.desarrollosisi.com.ar/loginCms",
    }
    resp = requests.post(wsaa_url, data=body.encode("utf-8"), headers=headers, timeout=30)

    # WSAA devuelve HTTP 500 (no 200) cuando el login falla, pero el
    # motivo real viene en el cuerpo como un SOAP Fault. Miramos el
    # cuerpo ANTES de reventar por el status code, si no nunca veríamos
    # el motivo real del rechazo.
    if "<faultstring>" in resp.text:
        inicio = resp.text.index("<faultstring>") + len("<faultstring>")
        fin = resp.text.index("</faultstring>")
        raise WSAAError(f"WSAA rechazó el login: {resp.text[inicio:fin]}")

    resp.raise_for_status()

    # La respuesta trae el loginTicketResponse (otro XML) escapado adentro
    # del <loginCmsReturn>. Lo desescapamos con un import local mínimo.
    import html
    import re

    m = re.search(r"<loginCmsReturn>(.*?)</loginCmsReturn>", resp.text, re.S)
    if not m:
        raise WSAAError(f"No pude parsear la respuesta de WSAA:\n{resp.text}")

    return html.unescape(m.group(1))


def _extraer_credenciales(login_ticket_response_xml: str) -> dict:
    import re

    token = re.search(r"<token>(.*?)</token>", login_ticket_response_xml, re.S)
    sign = re.search(r"<sign>(.*?)</sign>", login_ticket_response_xml, re.S)
    expiration = re.search(
        r"<expirationTime>(.*?)</expirationTime>", login_ticket_response_xml
    )
    if not (token and sign and expiration):
        raise WSAAError(
            f"La respuesta de WSAA no tiene token/sign:\n{login_ticket_response_xml}"
        )
    return {
        "token": token.group(1),
        "sign": sign.group(1),
        "expirationTime": expiration.group(1),
    }


def _leer_cache(cache_path: str) -> dict | None:
    if not os.path.exists(cache_path):
        return None
    try:
        with open(cache_path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    try:
        vencimiento = datetime.fromisoformat(data["expirationTime"])
    except (KeyError, ValueError):
        return None

    if vencimiento - _MARGEN_SEGURIDAD <= datetime.now(timezone.utc):
        return None  # vencido o por vencer
    return data


def _guardar_cache(cache_path: str, credenciales: dict) -> None:
    os.makedirs(os.path.dirname(cache_path), exist_ok=True)
    with open(cache_path, "w", encoding="utf-8") as f:
        json.dump(credenciales, f, indent=2)


def obtener_credenciales(config: ArcaConfig, forzar_renovacion: bool = False) -> dict:
    """
    Devuelve {"token": ..., "sign": ..., "expirationTime": ...}, usando el
    caché en disco si todavía es válido (dura ~12hs) o pidiendo uno nuevo
    a WSAA si no.
    """
    if not forzar_renovacion:
        cacheado = _leer_cache(config.cache_token_path)
        if cacheado:
            return cacheado

    tra_xml = _generar_tra()
    cms_der = _firmar_tra_cms(tra_xml, config.cert_path, config.key_path, config.openssl_path)
    login_ticket_response_xml = _login_cms(cms_der, config.wsaa_url)
    credenciales = _extraer_credenciales(login_ticket_response_xml)

    _guardar_cache(config.cache_token_path, credenciales)
    return credenciales
