#!/usr/bin/env python3
"""
Emite UNA factura con los datos de config/config.homologacion.ini y
muestra el CAE. Pensado para correrlo a mano mientras se prueba todo en
homologación, antes de programarlo en el Task Scheduler.

Uso:
    python emitir_factura_prueba.py
    ARCA_CONFIG=config/config.produccion.ini python emitir_factura_prueba.py
"""
import sys

from src.config import load_config
from src.wsaa import obtener_credenciales, WSAAError
from src.wsfe import emitir_factura, WSFEError


def main() -> int:
    config = load_config()

    print(f"Ambiente: {config.ambiente}")
    if config.ambiente == "produccion" and sys.stdin.isatty():
        # Si corre desde una consola interactiva (uso manual), pedimos
        # confirmación explícita. Si corre desde el Task Scheduler (sin
        # consola) no hay stdin: ahí se asume que ya se decidió pasar a
        # producción a propósito y se sigue sin preguntar.
        respuesta = input(
            "¡ATENCIÓN! Estás por emitir una factura REAL en PRODUCCIÓN. "
            "Escribí 'SI' para confirmar: "
        )
        if respuesta.strip().upper() != "SI":
            print("Cancelado.")
            return 1

    try:
        print("Pidiendo Token/Sign a WSAA (o usando el cacheado)...")
        credenciales = obtener_credenciales(config)

        print(
            f"Emitiendo Factura C a Consumidor Final, "
            f"punto de venta {config.punto_venta}, importe ${config.importe_total}..."
        )
        resultado = emitir_factura(config, credenciales)
    except (WSAAError, WSFEError) as exc:
        print(f"\nERROR: {exc}", file=sys.stderr)
        return 1

    print("\n¡Factura autorizada!")
    print(f"  Número de comprobante: {resultado.numero_comprobante}")
    print(f"  CAE: {resultado.cae}")
    print(f"  CAE vence: {resultado.cae_vencimiento}")
    if resultado.observaciones:
        print(f"  Observaciones de ARCA: {resultado.observaciones}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
