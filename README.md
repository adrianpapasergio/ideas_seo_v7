# Generador de Ideas SEO Profesional – SciData

## Requisitos
- Python 3.8+
- pip

## Instalación
```bash
cd generador_ideas_seo_mac
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# Editar .env con tus credenciales y OpenAI API Key
python app.py
```
## 🛠 Scripts locales (no incluidos en el repo)

Algunos scripts, como `project_start.sh` o `project_start.ps1`, son **exclusivos para uso local** y están listados en `.gitignore` para evitar que se suban a GitHub.  

Estos scripts pueden contener:
- Configuraciones personalizadas
- Alias para iniciar el proyecto
- Comandos de prueba y depuración

> 🔒 **Importante**: Nunca modifiques estos scripts pensando que afectarán el repositorio remoto. Cualquier cambio es solo para tu entorno local.

### Ejecución rápida con alias
Podés configurar un alias de shell para iniciar el proyecto con un solo comando:

#### macOS / Linux (`.zshrc` o `.bashrc`):
```bash
alias startp="bash /ruta/a/tu/project_start.sh"

Abre tu navegador en http://127.0.0.1:5000

## Arranque rápido (alias `startp`)

Para simplificar el inicio del proyecto en entornos locales, creá un alias en tu terminal que ejecute todos los pasos necesarios:

**En macOS/Linux (bash/zsh)**  
Agregá esto a tu `~/.zshrc` o `~/.bashrc`:

```bash
alias startp="cd /ruta/a/ideas_seo_v7 && source venv/bin/activate && flask run"
```

**En Windows PowerShell**  
Agregá esto a tu perfil de PowerShell (`$PROFILE`):

```powershell
function startp {
    Set-Location "C:\ruta\a\ideas_seo_v7"
    .\venv\Scripts\activate
    flask run
}
```

De esta manera, podés iniciar el entorno virtual y la app con un solo comando:

```bash
startp
```