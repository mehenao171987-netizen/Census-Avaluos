# Census Avalúos

Software para la elaboración de **avalúos comerciales** de inmuebles en Colombia, con asistencia de **Claude (Anthropic)**, búsqueda de mercado en la web y un registro seguro de informes.
Desarrollado por **[Adaptiva.com.co](https://adaptiva.com.co)**.

> Census Avalúos es una herramienta de apoyo. El avalúo debe ser elaborado, revisado y firmado por un perito avaluador inscrito en el **Registro Nacional de Avaluadores (RNA)**, conforme a la Ley 1673 de 2013 y la Resolución 620 de 2008.

## Funcionalidades

- **Asistente paso a paso** (12 pasos) que sigue la estructura de un informe de avalúo comercial.
- **Cálculo valuatorio**: método comparativo de mercado con homologación (forma de pago, época, tamaño, conservación, comercialización de 0 % a 5 %), coeficiente de variación con límite de 7,4 %, y método de reposición con depreciación por edad y estado.
- **Búsqueda de mercado en la web** mediante Claude con la herramienta `web_search`, con fuentes citables de portales inmobiliarios.
- **Geolocalización** de la dirección y visualización en mapa (OpenStreetMap).
- **Claude como asistente técnico**: redacción del entorno, análisis de testigos y revisión del avalúo antes de firmar.
- **Imágenes**: carga, validación, eliminación de metadatos (EXIF/GPS), rotación, recorte, brillo, contraste, nitidez y escala de grises.
- **Informe en Word (.docx)** con la estructura del formato original y anexo fotográfico.
- **Registro seguro** en base de datos cifrada, con búsqueda por cédula mediante índice ciego.

## Pasos del flujo

| # | Paso | Contenido |
|---|------|-----------|
| 1 | Propietario | Nombre completo |
| 2 | Cédula | Número de identificación (cifrado) |
| 3 | Matrícula inmobiliaria | Formato ORIP-consecutivo, ej. 001-400729 |
| 4 | Ubicación | Dirección, municipio, barrio, tipo, estrato y mapa |
| 5 | Características físicas | Áreas de lote, antejardín y construcción, antigüedad, niveles, habitaciones, baños |
| 6 | Acabados y estado | Estado de conservación, estructura y acabados |
| 7 | Servicios, entorno y POT | Servicios públicos, transporte, entorno, tratamiento y densidad |
| 8 | Testigos de mercado | Comparables con factores de homologación |
| 9 | Investigación web e IA | Búsqueda en portales y análisis con Claude |
| 10 | Cálculo del avalúo | Valor comercial, coeficiente de variación y vigencia |
| 11 | Imágenes | Carga y edición de fotografías del anexo |
| 12 | Informe y registro | Descarga del .docx y guardado seguro |

## Niveles de ciberseguridad

| Nivel | Control | Implementación |
|-------|---------|----------------|
| 1 | Autenticación | Contraseñas con PBKDF2-SHA256 (310 000 iteraciones y sal aleatoria) |
| 2 | Anti fuerza bruta | Bloqueo temporal tras intentos fallidos; mensajes genéricos |
| 3 | Sesión | Cierre automático por inactividad (configurable) y limpieza del borrador al salir |
| 4 | Autorización | Roles `admin`, `avaluador` y `revisor` con permisos por acción |
| 5 | Cifrado en reposo | Datos personales cifrados con Fernet (AES-128-CBC + HMAC) |
| 6 | Búsqueda sin exponer datos | Índice ciego HMAC-SHA256 para cédulas |
| 7 | Entradas | Validación y saneamiento; consultas SQL parametrizadas; escape HTML |
| 8 | Archivos | Límite de tamaño, verificación de firma binaria y reconstrucción de píxeles sin metadatos |
| 9 | Secretos | Solo en variables de entorno o en los secretos de la plataforma; nunca en el repositorio |
| 10 | IA | Lista blanca de campos: el nombre, la cédula y la dirección del solicitante no se envían a Claude |
| 11 | Auditoría | Registro de eventos en `logs/audit.log` sin datos personales |
| 12 | Aplicación | Configuración de Streamlit con XSRF activado, sin detalles de error al usuario y sin telemetría |
| 13 | Integración continua | Pruebas automáticas y auditoría de dependencias en GitHub Actions |

## Instalación local

```bash
git clone https://github.com/<su-organizacion>/census-avaluos.git
cd census-avaluos
python -m venv .venv && source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python scripts/generate_secrets.py                  # genera claves y el usuario administrador
cp .env.example .env                                # complete los valores generados y su ANTHROPIC_API_KEY
export $(grep -v '^#' .env | xargs)                 # Windows: cargue las variables en su terminal
streamlit run app.py
```

Pruebas:

```bash
pytest -q
```

## Despliegue

**Streamlit Community Cloud**: conecte el repositorio de GitHub, seleccione `app.py` y configure los secretos en *Settings → Secrets* con el mismo formato de `.env` (por ejemplo `ANTHROPIC_API_KEY = "..."`). La aplicación copia esos valores a variables de entorno al iniciar.

**Servidor propio**: ejecute detrás de un proxy inverso con HTTPS (Nginx o Caddy), limite la tasa de peticiones en el proxy y haga respaldos periódicos de `data/census.db`.

## Limitaciones conocidas

- El bloqueo de intentos fallidos vive en la sesión del navegador. Para un bloqueo global, aplique limitación de tasa en el proxy.
- `logs/` y `data/` son locales. En plataformas efímeras (como Streamlit Community Cloud) use un volumen persistente o una base de datos externa antes de producción.
- La búsqueda web depende de los resultados que devuelva Claude. Verifique cada testigo contra la fuente antes de usarlo; respete los términos de uso de cada portal.
- El costo de reposición por m² y los parámetros de depreciación son supuestos editables. Verifíquelos con la tabla vigente y con su criterio profesional.
- Antes de producción, revise el cumplimiento de la Ley 1581 de 2012 (protección de datos personales) y establezca políticas de retención y acceso.

## Estructura del proyecto

```
app.py                  Punto de entrada: acceso, sesión y navegación
config/settings.py      Parámetros configurables (sin secretos)
core/                   Lógica de negocio y seguridad
  valuation.py          Motor valuatorio (comparativo, reposición, vigencia)
  validators.py         Validación de entradas
  security.py           Autenticación, roles, cifrado y auditoría
  repository.py         Persistencia SQLite cifrada
  numeros.py            Valor en letras (español)
services/               Integraciones
  ai_assistant.py       Claude (asistente técnico)
  market_search.py      Búsqueda web y geocodificación
  image_service.py      Procesamiento seguro de imágenes
  report.py             Informe .docx
ui/                     Interfaz
  components.py         Tema visual y componentes
  steps.py              Pasos del asistente
tests/                  Pruebas automáticas
scripts/generate_secrets.py   Generación de claves y administrador
```

## Licencia

Propiedad de Adaptiva.com.co. Defina la licencia de uso antes de publicar el repositorio.
