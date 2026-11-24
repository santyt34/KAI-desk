# Troko-Desk (KAI) – Asistente Virtual de Escritorio con Isla Superior Animada

<p align="center">
  <img src="https://img.shields.io/badge/Python-3.12-blue?logo=python" />
  <img src="https://img.shields.io/badge/PyQt6-6.7-green?logo=qt" />
  <img src="https://img.shields.io/badge/Llama_3.2_3B-Offline--First-purple" />
  <img src="https://img.shields.io/badge/Windows-10%2F11-blue?logo=windows" />
  <img src="https://img.shields.io/badge/license-MIT-orange" />
</p>

**Troko-Desk** es un asistente virtual de escritorio para Windows 10/11 con interfaz tipo *notch* / isla superior flotante animada a 60 FPS, control por voz offline, inteligencia artificial híbrida (Llama 3.2 3B local por defecto) y automatización segura del sistema.

---

## ✨ Características Principales

### 1. Privacidad y Arquitectura Híbrida (Offline Primero)
- **Ejecución Local por Defecto**: Inferencia con `Llama 3.2 3B` (~2.02 GB) vía `llama.cpp` o `Ollama`, con `ONNX Runtime` y `Kokoro`/`edge-tts` para voz.
- **Descargas Pausables y Reanudables**: Gestor de descarga de modelo con soporte de cabeceras HTTP `Range` para no perder avance si se interrumpe la conexión (`ai/model_manager.py`).
- **Capa Híbrida (`LLMRouter`)**: Ejecución offline por defecto con fallback a APIs online (OpenAI, OpenRouter, Groq) cuando se requiera.
- **Seguridad Estricta**: No borra archivos permanentemente y nunca envía correos sin confirmación explícita del usuario.

### 2. Motor de Animación Procedural a 60 FPS (`ui/animation_engine.py` & `ui/eye_renderer.py`)
- **12 Emociones Paramétricas**:
  1. `contento`: Arcos curvados hacia arriba y estrellas de satisfacción.
  2. `enamorado`: Pupilas en forma de corazón y corazones flotantes.
  3. `sorpresa`: Ojos circulares muy abiertos y pupilas contraídas.
  4. `orgulloso`: Ojos entornados con satisfacción y barbilla alta.
  5. `guiño`: Un ojo guiñado pícaramente en arco y el otro con destello.
  6. `bostezo`: Ojos entrecerrados y boca redonda de bostezo.
  7. `mareado`: Pupilas en espiral rotando con estrellas y balanceo.
  8. `triste`: Ojos caídos en arco inverso.
  9. `enfadado`: Ojos rasgados oblicuos hacia el centro con mirada intensa.
  10. `timido`: Ojos mirando hacia abajo con rubor intenso en las mejillas.
  11. `curioso`: Ojos asimétricos ladeados con destello inquisitivo.
  12. `travieso`: Mirada pícara hacia un lado y chispas.
- **Overlays Dinámicos**: Rubor procedural en las mejillas, corazones palpitantes, estrellas titilantes, gotas de sudor y lluvia de confeti.
- **7 Estados Operativos de la Isla**: `reposo`, `escucha`, `piensa`, `habla`, `alerta`, `notificacion` y `sueno`.
- **Feedback Visual con Check Verde**: Icono de check animado con palabra corta (`Listo`, `Anotado`, `Confirmado`) tras cada acción.

### 3. Escenas Animadas de Hábitos (15 Estilos + Festejo)
1. **Enfoque / Pomodoro**: Troko tecleando en laptop con manos animadas y cuenta atrás visible en la isla notch en tiempo real.
2. **Agua**: Vaso con nivel de agua dinámico azul (`6/8 vasos`), con botón `+1 vaso` y `Deshacer`.
3. **Lectura**: Libro abierto con animación de páginas pasando.
4. **Ejercicio / Pesas**: Levantamiento de mancuernas con esfuerzo y gotas de sudor.
5. **Meditación / Descanso**: Troko bajo un sol zen que se expande y contrae en ciclo de 4 segundos.
6. **Caminar / Pasos**: Animación de pasos rítmicos y medidor de distancia.
7. **Estudio / Aprender**: Bombilla/foco de ideas encendiéndose con rayos.
8. **Dormir temprano**: Luna creciente con cielo nocturno estrellado.
9. **Comida saludable**: Manzana roja con hoja verde y brillo.
10. **Postura**: Troko enderezando la espalda y alineando vértebras.
11. **Pausa visual (20-20-20)**: Parpadeo guiado de descanso ocular.
12. **Agradecimiento / Diario**: Cuaderno y pluma dorada escribiendo.
13. **Respiración guiada (4-4-4)**: Círculo expansivo ("Inhala - Retén - Exhala").
14. **Limpieza / Orden**: Destellos mágicos de orden.
15. **Desconexión digital**: Pantalla apagándose con brote verde floreciendo.
- **Animación de Festejo (`festejo`)**: Explosión de confeti multicolor procedural cuando se completa una meta diaria.

### 4. Automatización y Acciones de Escritorio
- **Voz, Texto y Toque en la Isla**: Activación por palabra clave *"Troko"* o *"KAI"*, entrada por voz, escritura rápida o toque directo en la isla notch.
- **Organizador de Escritorio Seguro**: Escanea archivos sueltos en el Escritorio, muestra vista previa y resumen, pide confirmación explícita (`"Ordenar ahora"` o `"sí, ordénalo"`) antes de mover y permite `Deshacer` en cualquier momento sin borrar datos.
- **Control de Aplicaciones**: Lanzador seguro de aplicaciones permitidas (`ALLOWED_APPS`).
- **Correo (Borradores con Confirmación)**: Redacta borradores a partir de una idea del usuario (ej. *"Responde a Ana diciendo que mañana confirmo"*) y solicita confirmación interactiva en la isla notch antes de enviar.
- **Reporte al Despertar**: Al despertar a Troko tras haber estado dormido, resume automáticamente los recordatorios o tareas que vencieron durante el sueño.

---

## 🗂 Estructura Modular

```
Troko-Desk/
├── main.py                        # Punto de entrada y orquestación
├── KAI.spec                       # Spec de compilación para PyInstaller
├── build.py                       # Script de build a .exe
├── .env.example                   # Variables de entorno y configuración
├── requirements.txt               # Dependencias Python 3.12 en Windows
├── config/
│   ├── settings.py                # Configuración centralizada tipada
│   └── tools_schema.json          # Definición de herramientas para el LLM
├── core/
│   ├── event_bus.py               # Bus de eventos desacoplado pub/sub
│   ├── state_machine.py           # Máquina de estados (12 emociones, 15 hábitos, 7 ops)
│   └── logger.py                  # Logging estructurado con rotación
├── ui/
│   ├── island_window.py           # Ventana superior flotante tipo notch
│   ├── eye_renderer.py            # Renderizado vectorial a 60 FPS
│   ├── animation_engine.py        # Motor procedural, easing y partículas
│   └── tray_menu.py               # Menú de la bandeja del sistema
├── audio/
│   ├── wake_word.py               # Detección continua de palabra clave ("Troko" / "KAI")
│   ├── stt_whisper.py             # Transcripción local faster-whisper + VAD
│   └── tts_speaker.py             # Síntesis Kokoro / edge-tts / piper
├── ai/
│   ├── llm_router.py              # Enrutador híbrido local-first (Llama/Ollama) + online
│   ├── model_manager.py           # Descarga pausable/reanudable de Llama 3.2 3B GGUF
│   ├── prompts.py                 # System prompt y formato JSON estricto
│   └── action_dispatcher.py       # Validador y despachador seguro de herramientas
├── actions/
│   ├── file_organizer.py          # Clasificación con vista previa y deshacer
│   ├── app_launcher.py            # Apertura segura de aplicaciones
│   ├── productivity.py            # Pomodoro con cuenta atrás en notch y reporte al despertar
│   ├── habits_tracker.py          # 15 hábitos con metas diarias, rachas y festejo
│   ├── email_drafts.py            # Borradores de correo con confirmación en la isla
│   └── emotions.py                # Control explícito de emociones
├── storage/
│   ├── db.py                      # Conexión SQLite y migraciones ligeras
│   └── undo_history.json          # Historial de movimientos de archivos
├── scripts/
│   └── generate_assets.py         # Utilidad para exportar fotogramas vectoriales a PNG
└── tests/
    ├── test_file_organizer.py     # Pruebas del organizador y undo
    ├── test_action_dispatcher.py  # Pruebas del despachador
    └── test_email_and_habits.py   # Pruebas de correos, hábitos y reporte al despertar
```

---

## 🚀 Inicio Rápido

### 1. Requisitos
- Windows 10 u 11 con Python 3.12 (ya instalado).
- Ollama corriendo localmente (`ollama pull llama3.2:3b` o `ollama pull qwen2.5:3b`) o modelo GGUF descargado en `models/`.

### 2. Ejecución

```powershell
# Activar entorno virtual
.\.venv\Scripts\Activate.ps1

# Probar auto-verificación completa
python main.py --test

# Iniciar en modo interactivo texto (sin micrófono)
python main.py --text

# Iniciar en modo completo (voz + isla notch + IA)
python main.py

# Generar fotogramas vectoriales estáticos a disco (opcional)
python scripts/generate_assets.py
```

### 3. Comandos de Voz y Texto Frecuentes
- *"Troko, ponme un Pomodoro de 25 minutos"*
- *"Troko, anoté un vaso de agua"*
- *"Troko, organiza mi escritorio"* ➔ Muestra vista previa ➔ Di *"ordenar ahora"* para confirmar.
- *"Troko, deshaz el último movimiento"*
- *"Troko, redacta un correo a Ana diciendo que confirmo la reunión de mañana"*
- *"Troko, ponte contento"* / *"ponte enamorado"* / *"Troko, descansa"*
- *"Troko, ¿cuál es mi reporte al despertar?"*

---

## 🧪 Pruebas Automatizadas

```powershell
.\.venv\Scripts\python.exe -m pytest tests/ -v
```

Todos los 16 tests unitarios pasan exitosamente validando el organizador de escritorio, undo, hábitos, confirmaciones de correo y reporte al despertar.
