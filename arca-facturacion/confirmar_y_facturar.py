#!/usr/bin/env python3
"""
Igual que emitir_factura_prueba.py, pero antes de facturar muestra una
ventana preguntando si confirmás. Pensado para el Task Scheduler: así
alguien puede decir que no (o simplemente no contestar) un miércoles
puntual sin tener que tocar nada de la configuración.

Reglas:
- "Sí"            -> factura, como siempre.
- "No"            -> no factura esta semana, no rompe nada.
- Sin respuesta en 30 minutos -> se cierra solo y NO factura (por las
  dudas de que no haya nadie mirando la pantalla).

Para que el cartel se vea, la tarea programada en Windows tiene que
correr con la sesión de Windows iniciada (no "en segundo plano").
"""
import sys
import tkinter as tk
from tkinter import messagebox

from src.config import load_config
from src.wsaa import obtener_credenciales, WSAAError
from src.wsfe import emitir_factura, WSFEError

TIMEOUT_MS = 30 * 60 * 1000  # 30 minutos


def preguntar(config) -> bool:
    """Muestra el cartel de confirmación. Devuelve True solo si tocaste 'Sí'."""
    respuesta = {"confirmado": False}

    root = tk.Tk()
    root.withdraw()  # no mostramos una ventana vacía de fondo

    def on_si():
        respuesta["confirmado"] = True
        root.destroy()

    def on_no():
        respuesta["confirmado"] = False
        root.destroy()

    def on_timeout():
        if root.winfo_exists():
            root.destroy()

    root.after(TIMEOUT_MS, on_timeout)

    mensaje = (
        f"¿Facturar esta semana?\n\n"
        f"Factura C a Consumidor Final\n"
        f"Punto de venta: {config.punto_venta}\n"
        f"Importe: ${config.importe_total:,.2f}\n"
        f"Ambiente: {config.ambiente.upper()}\n\n"
        f"Si no contestás en 30 minutos, se cancela sola (no factura)."
    )

    # askyesno usa su propio loop modal; lo llamamos sobre este root
    # oculto para poder controlar el timeout con root.after().
    root.deiconify()
    root.withdraw()
    confirmado = messagebox.askyesno("Facturación automática", mensaje, parent=root)
    respuesta["confirmado"] = bool(confirmado)

    try:
        root.destroy()
    except tk.TclError:
        pass

    return respuesta["confirmado"]


def main() -> int:
    config = load_config()

    if not preguntar(config):
        print("Cancelado: no se confirmó a tiempo o se eligió 'No'. No se facturó nada.")
        return 0

    try:
        credenciales = obtener_credenciales(config)
        resultado = emitir_factura(config, credenciales)
    except (WSAAError, WSFEError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        try:
            tk.Tk().withdraw()
            messagebox.showerror("Facturación automática", f"Falló la facturación:\n{exc}")
        except tk.TclError:
            pass
        return 1

    print("¡Factura autorizada!")
    print(f"  Número de comprobante: {resultado.numero_comprobante}")
    print(f"  CAE: {resultado.cae}")
    print(f"  CAE vence: {resultado.cae_vencimiento}")

    try:
        tk.Tk().withdraw()
        messagebox.showinfo(
            "Facturación automática",
            f"Factura emitida.\nComprobante N° {resultado.numero_comprobante}\nCAE: {resultado.cae}",
        )
    except tk.TclError:
        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
