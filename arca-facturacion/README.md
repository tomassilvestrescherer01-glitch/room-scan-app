# Facturación electrónica automática (ARCA / ex AFIP) — Monotributista

Automatiza la Factura C semanal a Consumidor Final por el web service
WSFEv1 de ARCA. Pensado para probar TODO en homologación antes de tocar
producción.

Orden recomendado: **1 → 2 → 3/4/5 (ya hechos acá) → 6 (probar) → 7 (programar)**.

---

## 0. Instalar OpenSSL en Windows

Si no lo tenés instalado, cualquiera de estas dos opciones sirve:

- **Git for Windows** (lo más simple si ya usás git): al instalarlo,
  OpenSSL queda disponible en `C:\Program Files\Git\usr\bin\openssl.exe`.
  Descarga: https://git-scm.com/download/win
- **Win64 OpenSSL** de Shining Light Productions:
  https://slproweb.com/products/Win32OpenSSL.html (instalá la versión
  "Win64 OpenSSL vX.X.X" normal, no la "Light" si podés elegir).

Después de instalar, abrí una consola nueva (CMD o PowerShell) y probá:

```
openssl version
```

Si no lo reconoce, o usá la ruta completa al ejecutable, o agregá esa
carpeta al PATH de Windows.

---

## 1. Generar la clave privada y el CSR

Todo esto es local, no toca internet. **La clave privada (`.key`) no se
comparte con nadie, ni se sube a git, ni se manda por mail.**

Parado en la carpeta `arca-facturacion/certs/`, corré (reemplazando el
CUIT y el nombre):

```
cd arca-facturacion\certs

REM 1) clave privada (2048 bits, estándar para esto)
openssl genrsa -out monotributo.key 2048

REM 2) CSR con los datos que pide ARCA
openssl req -new -key monotributo.key -subj "/C=AR/O=Nombre Apellido/CN=facturacion-monotributo/serialNumber=CUIT 20XXXXXXXXX" -out monotributo.csr
```

Notas sobre el `-subj`:

- `O=` va el nombre y apellido del monotributista (o razón social).
- `CN=` es un alias cualquiera, a tu elección (lo vas a volver a ver en
  el paso 2, para identificar el certificado en el listado de ARCA).
- `serialNumber=CUIT 20XXXXXXXXX` — reemplazá por el CUIT real de tu
  viejo, **sin guiones**, con el prefijo literal `CUIT ` (así lo exige
  ARCA en el CSR).

Al terminar vas a tener:

- `monotributo.key` → clave privada. **No se toca de esta carpeta.**
- `monotributo.csr` → esto sí lo subís a ARCA en el paso 2.

Vas a necesitar generar **dos certificados distintos** más adelante: uno
para homologación y, cuando todo funcione, otro para producción. Podés
reusar el mismo par de clave/CSR para pedir ambos, o generar un segundo
par — cualquiera de las dos formas es válida. Este README asume que
vas a tener archivos separados, p. ej. `homologacion.crt` /
`homologacion.key` y (más adelante) `produccion.crt` / `produccion.key`.

---

## 2. Trámites a mano en el sitio de ARCA (con Clave Fiscal)

La interfaz web de ARCA cambia de layout de tanto en tanto; los nombres
de los menúes de abajo son los que estuvieron vigentes al escribir esto.
Si algo no coincide exactamente, buscá el manual oficial vigente (los
mismos pasos, distinto lugar en el menú):

- Manual del desarrollador WSFEv1 (ARCA):
  https://www.afip.gob.ar/ws/documentacion/manuales/manual-desarrollador-ARCA-COMPG-v4-1.pdf
- Portal de webservices: https://www.afip.gob.ar/ws/

Pasos:

1. **Entrar con Clave Fiscal** (la de tu viejo, o la tuya si tenés
   autorización de "Administrador de Relaciones" sobre su CUIT).

2. **Adherir el servicio "Administración de Certificados Digitales"**
   desde el Administrador de Relaciones de Clave Fiscal, si todavía no
   lo tiene habilitado.

3. **Subir el CSR** dentro de "Administración de Certificados
   Digitales" → agregar un alias nuevo → cargar el archivo `.csr`
   generado en el paso 1. ARCA te devuelve un certificado (`.crt`/`.cer`)
   para descargar: guardalo como `certs/produccion.crt` (o el nombre que
   uses en el `.ini`).

4. **Habilitar el mismo certificado para homologación.** Producción y
   homologación son ambientes separados: además de lo anterior, tenés
   que asociar tu certificado (o generar uno de prueba) al ambiente de
   testing. ARCA documenta esto como "acceso al ambiente de
   homologación" / "WSAA homologación" en el mismo portal de
   webservices — seguí la guía vigente del link de arriba para esa
   parte puntual, porque es donde más cambia la pantalla. El resultado
   final que necesitás es un certificado válido contra
   `wsaahomo.afip.gov.ar` (el de testing).

5. **Autorizar el servicio "Facturación Electrónica" (WSFE)** para ese
   alias/certificado, desde el Administrador de Relaciones de Clave
   Fiscal → Nueva Relación → buscar el servicio de Facturación
   Electrónica → asociarlo al certificado del paso 3/4. Hacelo tanto
   para el certificado de homologación como (más adelante) para el de
   producción.

6. **Dar de alta el punto de venta tipo "Web Services".** En el
   administrador de "Puntos de Venta y Domicilios" (dentro del servicio
   de Facturas Electrónicas / RECE), creá un punto de venta nuevo con
   sistema **"Web Services"** (no el de facturación manual/"Comprobantes
   en línea"). Anotá el número: va en `config/config.*.ini` como
   `punto_venta`.

Guardá los certificados así:

```
arca-facturacion/certs/homologacion.crt
arca-facturacion/certs/homologacion.key   (la clave del paso 1)
```

y cuando tengas el de producción:

```
arca-facturacion/certs/produccion.crt
arca-facturacion/certs/produccion.key
```

---

## 3/4/5. El código (ya escrito en este repo)

- `src/wsaa.py` — firma el TRA con openssl y pide Token/Sign a WSAA,
  cacheándolos en `cache/token_*.json` (duran ~12hs; se renuevan solos
  cuando vencen, con 10 minutos de margen).
- `src/wsfe.py` — llama a `FECompUltimoAutorizado` (para saber el
  próximo número de comprobante) y a `FECAESolicitar` (para pedir el
  CAE) de una Factura C a Consumidor Final.
- `src/config.py` — toda la configuración sale de un `.ini`, nada
  hardcodeado. Los endpoints de homologación/producción están fijos en
  el código (no en el `.ini`) para que un typo no mande una prueba a
  producción por accidente.
- `config/config.example.ini` — plantilla parametrizable: CUIT, punto de
  venta, importe, concepto, tipo de comprobante, rutas a los
  certificados.

**Antes de instalar nada**, instalá las dependencias de Python (una sola
vez):

```
cd arca-facturacion
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Después copiá la config de ejemplo y completala:

```
copy config\config.example.ini config\config.homologacion.ini
notepad config\config.homologacion.ini
```

Completá `cuit`, `punto_venta`, `importe_total`, y las rutas de
`cert_path` / `key_path` apuntando a `certs/homologacion.crt` /
`certs/homologacion.key`. Dejá `ambiente = homologacion`.

### Verificá los códigos contra ARCA (no de memoria)

Antes de emitir nada, corré:

```
python consultar_parametros.py
```

Esto le pregunta al web service de homologación cuáles son los valores
válidos de tipo de comprobante, concepto, tipo de documento y condición
de IVA del receptor, y los imprime. Confirmá que:

- El tipo de comprobante "Factura C" tenga el `Id` que pusiste en
  `cbte_tipo` del `.ini`.
- "Consumidor Final" en la condición de IVA del receptor tenga el `Id`
  que pusiste en `condicion_iva_receptor_id`.
- El concepto (Productos/Servicios) coincida con la actividad real del
  monotributo.

Si algo no coincide, corregí el `.ini` antes de seguir.

---

## 6. Emitir la factura de prueba en homologación

```
python emitir_factura_prueba.py
```

Con `ambiente = homologacion` en el `.ini`, esto:

1. Pide (o reusa) el Token/Sign de WSAA.
2. Consulta el último comprobante autorizado para ese punto de venta.
3. Pide el CAE de una Factura C, a Consumidor Final, por el importe
   configurado.
4. Imprime el número de comprobante, el CAE y su vencimiento.

Si ARCA rechaza algo, el error que imprime trae el código y mensaje
tal cual los devuelve el web service — sirve para ajustar el `.ini` o el
`consultar_parametros.py` de nuevo.

**No sigas al paso 7 hasta que esto funcione de punta a punta en
homologación.**

---

## Pasar a producción (después de que homologación funcione)

1. Repetí el trámite del paso 2 pero para producción real (el
   certificado de "Administración de Certificados Digitales" sin pasar
   por el ambiente de testing), y autorizá el servicio WSFE de
   producción para ese certificado.
2. Guardá ese certificado como `certs/produccion.crt` /
   `certs/produccion.key`.
3. Copiá `config/config.example.ini` a `config/config.produccion.ini`,
   poné `ambiente = produccion` y las rutas a los certificados de
   producción. Usá el punto de venta real de producción (puede ser
   distinto número al de homologación).
4. Probá una vez a mano:
   ```
   set ARCA_CONFIG=config\config.produccion.ini
   python emitir_factura_prueba.py
   ```
   Te va a pedir confirmación explícita antes de emitir (porque ahí sí
   es una factura real). Escribí `SI` para confirmar.

---

## 7. Programar en el Task Scheduler de Windows (miércoles a la noche)

Hay dos scripts posibles para programar:

- **`emitir_factura_prueba.py`** — factura directo, sin preguntar nada.
- **`confirmar_y_facturar.py`** — antes de facturar, muestra un cartel en
  pantalla preguntando "¿Facturar esta semana?" (Sí/No). Si no contestás
  en 30 minutos, se cancela sola y no factura. Pensado para cuando algún
  miércoles no querés que salga la factura, sin tener que tocar nada de
  la configuración.

El `.bat` de este repo ya viene armado con `confirmar_y_facturar.py`. Si
preferís que factura directo sin preguntar, cambiá esa línea del `.bat`
por `emitir_factura_prueba.py`.

**Importante si usás `confirmar_y_facturar.py`**: el cartel solo se ve si
hay una sesión de Windows con pantalla iniciada en ese momento. Si la PC
está apagada o sin nadie logueado, la tarea no va a poder mostrar nada
(y por seguridad, tampoco va a facturar).

1. Editá `scheduler/facturar_semanal.bat` y poné la ruta real de
   `PROYECTO_DIR`.
2. Confirmá que `ARCA_CONFIG` dentro del `.bat` apunte al config que
   corresponda (`config.homologacion.ini` mientras prueban,
   `config.produccion.ini` cuando ya esté todo resuelto para pasar a
   producción).
3. Abrí **"Programador de tareas"** (Task Scheduler) → *Crear tarea*
   (no "tarea básica", para tener más control):
   - **General**: nombre "Factura semanal monotributo".
     - Si usás `confirmar_y_facturar.py` (el cartel de confirmación):
       **NO marques** "Ejecutar tanto si el usuario inició sesión como
       si no" — dejala en "Ejecutar solo cuando el usuario haya iniciado
       sesión", para que el cartel se vea en pantalla.
     - Si usás `emitir_factura_prueba.py` (factura directo, sin cartel):
       marcá "Ejecutar tanto si el usuario inició sesión como si no".
   - **Desencadenadores** → Nuevo: Semanal, día **miércoles**, hora que
     prefieras a la noche (p. ej. 22:00).
   - **Acciones** → Nueva → Iniciar un programa → Programa/script:
     la ruta completa a `facturar_semanal.bat`.
   - **Condiciones**: si la PC puede estar apagada/en reposo un
     miércoles a la noche, desmarcá "Iniciar la tarea solo si el equipo
     está conectado a la corriente" y considerá "Reactivar el equipo
     para ejecutar esta tarea" si el equipo se suspende (esto último no
     sirve de mucho si necesitás que alguien esté para confirmar el
     cartel).
4. Guardá y probá con **clic derecho → Ejecutar** una vez, y revisá
   `scheduler/log.txt` para confirmar que salió bien.

De ahí en más corre solo, todos los miércoles a la noche, sin entrar a
la web de ARCA.

---

## Seguridad

- Los archivos `.key`, `.crt`, `.csr` y los `config.homologacion.ini` /
  `config.produccion.ini` están en `.gitignore`: nunca se suben a git.
- El caché de Token/Sign (`cache/*.json`) tampoco se sube: da acceso al
  web service durante ~12hs si alguien lo obtiene.
- Nada de esto usa ni guarda la Clave Fiscal — el web service de ARCA no
  la usa, se autentica solo con el certificado.
