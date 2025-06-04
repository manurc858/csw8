E.md
Nuevo
+53
-0

# Gestor de Proyectos Solares

Esta aplicación web permite crear y administrar proyectos con sus respectivas cartas solares. Se basa en [Flask](https://flask.palletsprojects.com/) y utiliza **pvlib** para los cálculos solares.

## Características

- Autenticación con correo/contraseña y con Google OAuth.
- Gestión de proyectos y cartas solares almacenadas en SQLite.
- Generación de cartas solares en formato PNG usando Matplotlib y pvlib.
- Interfaz web escrita en JavaScript y HTML (templates Jinja2).

## Requisitos

- Python 3.11 o superior.
- Dependencias instalables con `pip`:
  `Flask`, `Flask-Login`, `Flask-SQLAlchemy`, `Authlib`, `pvlib`, `matplotlib`, `numpy`.

## Instalación

1. Crea un entorno virtual (opcional pero recomendado):
   ```bash
   python -m venv venv
   source venv/bin/activate
   ```
2. Instala las dependencias:
   ```bash
   pip install Flask Flask-Login Flask-SQLAlchemy Authlib pvlib matplotlib numpy
   ```
3. Configura las variables de entorno para Google OAuth (opcional):
   `GOOGLE_CLIENT_ID` y `GOOGLE_CLIENT_SECRET`.

## Uso

Ejecuta la aplicación con:
```bash
python app.py
```

El servidor arrancará en `http://localhost:5000`. Accede con un navegador para registrarte o iniciar sesión y empezar a crear proyectos. Para cada proyecto puedes cargar un archivo `.epw` y generar diversas cartas solares.

La base de datos SQLite se guarda en `instance/mi_app.db` y se crea automáticamente al iniciar la aplicación.

## Estructura del repositorio

- `app.py` – Aplicación Flask principal y rutas.
- `models.py` – Modelos SQLAlchemy (usuarios, proyectos y cartas).
- `user.py` – Blueprint de autenticación y registro.
- `templates/` – Plantillas HTML.
- `static/` – Archivos estáticos (CSS, JS, imágenes).
- `instance/` – Base de datos SQLite.

¡Disfruta creando y analizando cartas solares!
