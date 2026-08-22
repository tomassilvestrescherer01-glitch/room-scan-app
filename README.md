# Escaneo de Habitación

App estática (un solo `index.html`, sin frameworks ni dependencias) que
guía a la persona a recorrer una habitación con la cámara del teléfono y
capturar 12 vistas. Flujo: Inicio → Instrucciones → Cámara → 12 capturas →
Procesamiento → Resultado.

## Build

```bash
npm run build
```

Genera el sitio final en `dist/` (solo copia y valida `index.html`, no hay
bundler porque no hace falta: todo el CSS y JS está inline en un único
archivo).

## Probar localmente

```bash
npm start
```

Sirve `dist/` en `http://localhost:4173`. La cámara solo se activa en un
contexto seguro (HTTPS o `localhost`), así que en local funciona porque
`localhost` cuenta como seguro.

## Despliegue en Vercel

`vercel.json` ya define `buildCommand` (`npm run build`) y
`outputDirectory` (`dist`), así que Vercel no necesita configuración
manual adicional: solo hay que importar este repo/carpeta como proyecto.
