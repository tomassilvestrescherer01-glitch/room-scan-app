#!/usr/bin/env python3
"""
Le pregunta al propio web service de ARCA (homologación o producción,
según el config) cuáles son los códigos válidos de Concepto, Tipo de
Comprobante, Tipo de Documento y Condición frente al IVA del receptor.

Usalo para CONFIRMAR los valores que se usan en config/*.ini y en
src/wsfe.py, en vez de creerle de memoria a un tutorial (incluido este).

Uso:
    python consultar_parametros.py
    ARCA_CONFIG=config/config.produccion.ini python consultar_parametros.py
"""
import sys

from src.config import load_config
from src.wsaa import obtener_credenciales
from src.wsfe import _auth, _cliente  # reutilizamos helpers internos


def main() -> int:
    config = load_config()
    print(f"Ambiente: {config.ambiente}")
    credenciales = obtener_credenciales(config)
    cliente = _cliente(config)
    auth = _auth(config, credenciales)

    print("\n== Tipos de comprobante (CbteTipo) ==")
    for item in cliente.service.FEParamGetTiposCbte(Auth=auth).ResultGet.CbteTipo:
        print(f"  {item.Id:>4}  {item.Desc}")

    print("\n== Conceptos ==")
    for item in cliente.service.FEParamGetTiposConcepto(Auth=auth).ResultGet.ConceptoTipo:
        print(f"  {item.Id:>4}  {item.Desc}")

    print("\n== Tipos de documento (DocTipo) ==")
    for item in cliente.service.FEParamGetTiposDoc(Auth=auth).ResultGet.DocTipo:
        print(f"  {item.Id:>4}  {item.Desc}")

    print("\n== Condición IVA del receptor (por tipo de comprobante) ==")
    try:
        resultado = cliente.service.FEParamGetCondicionIvaReceptor(Auth=auth)
        for item in resultado.ResultGet.CondicionIvaReceptor:
            print(f"  {item.Id:>4}  {item.Desc}")
    except Exception as exc:  # el método puede no existir en versiones viejas del WSDL
        print(f"  (no se pudo consultar: {exc})")

    print(
        "\nRevisá que config.cbte_tipo / concepto / doc_tipo / "
        "condicion_iva_receptor_id coincidan con lo que devolvió ARCA arriba."
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
