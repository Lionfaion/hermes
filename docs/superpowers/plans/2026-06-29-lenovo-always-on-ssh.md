# Lenovo Always-On SSH + No-Sleep Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Que Claude pueda ejecutar comandos en la Lenovo (192.168.1.100) vía SSH en cualquier momento, sin que el usuario esté presente, y sin que la Lenovo entre en suspensión al cerrar la tapa.

**Architecture:** 
SSH passwordless desde este PC con `hermes_key` (ya existe). La Lenovo corre Windows + WSL2 Ubuntu. El no-sleep se configura en Windows via `powercfg`. El SSH server en WSL2 se auto-inicia via Windows Task Scheduler. El `~/.ssh/config` de Windows define el alias `lenovo` para conexiones sin fricción.

**Tech Stack:** PowerShell (Windows local), SSH (ed25519 key ya existente), WSL2 Ubuntu, systemd, powercfg, Windows Task Scheduler.

## Global Constraints

- IP fija de Lenovo: `192.168.1.100`
- Usuario SSH Lenovo: `cris`
- Clave SSH ya existente: `C:\Users\Cris\.ssh\hermes_key`
- WSL2 distro: Ubuntu (donde corre Ollama y hermes brain)
- NUNCA tocar repos remotos (tick100, 15SMC)
- NUNCA commitear .env ni secretos

---

## Archivos que se crean/modifican

| Archivo | Acción | Responsabilidad |
|---------|--------|-----------------|
| `C:\Users\Cris\.ssh\config` | Crear | Alias SSH `lenovo` con hermes_key |
| `~/wsl2_autostart.ps1` en Lenovo Windows | Crear via SSH | Script que inicia WSL2 + sshd al boot |
| Task Scheduler en Lenovo Windows | Crear via SSH | Ejecuta wsl2_autostart.ps1 al iniciar sesión |
| `/etc/systemd/system/ssh.service` en WSL2 | Verificar/habilitar | Asegura sshd autoinicio en WSL2 |
| `brain/.env` en este PC | Modificar | Variables pendientes (VISION_MODEL, etc.) |

---

## Task 1: Crear `~/.ssh/config` en este PC

**Files:**
- Create: `C:\Users\Cris\.ssh\config`

**Interfaces:**
- Produce: alias `lenovo` usable como `ssh lenovo` en lugar de `ssh -i ~/.ssh/hermes_key cris@192.168.1.100`

- [ ] **Step 1: Crear el archivo config**

```
Host lenovo
    HostName 192.168.1.100
    User cris
    IdentityFile ~/.ssh/hermes_key
    IdentitiesOnly yes
    ServerAliveInterval 30
    ServerAliveCountMax 3
    StrictHostKeyChecking no
```

- [ ] **Step 2: Verificar que hermes_key.pub ya está en Lenovo**

```bash
ssh -i ~/.ssh/hermes_key cris@192.168.1.100 "echo SSH_OK"
```

Esperado: `SSH_OK`

Si falla con "Permission denied" → ir a Task 1b (manual).

---

## Task 1b: (SOLO SI Task 1 falla) — Instalar clave pública en Lenovo

> ⚠️ **Requiere acción manual del usuario UNA SOLA VEZ en la Lenovo**

El usuario debe ejecutar esto en la Lenovo (terminal WSL2 o PowerShell):

```bash
# En WSL2 de la Lenovo:
mkdir -p ~/.ssh && chmod 700 ~/.ssh
echo "ssh-ed25519 AAAAC3NzaC1lZDI1NTE5AAAAIN8xMOKJMlv8g5C4gS0XQwdxiPzc6xSHRWEcNN+zuLnk hermes@main-pc" >> ~/.ssh/authorized_keys
chmod 600 ~/.ssh/authorized_keys
```

Después confirmar con: `ssh lenovo "echo SSH_OK"`

---

## Task 2: Configurar Lenovo para NO dormir al cerrar la tapa

**Files:**
- Modify: Power settings de Windows en la Lenovo (via `powercfg` desde WSL2)

**Interfaces:**
- Consumes: SSH funcional (`ssh lenovo`)
- Produce: Lenovo nunca duerme al cerrar tapa (AC ni batería)

- [ ] **Step 1: Configurar "lid close = do nothing" en Windows de la Lenovo**

```bash
ssh lenovo "powershell.exe -Command \"\
  powercfg /SETACVALUEINDEX SCHEME_CURRENT 4f971e89-eebd-4455-a8de-9e59040e7347 5ca83367-6e45-459f-a27b-476b1d01c936 0;\
  powercfg /SETDCVALUEINDEX SCHEME_CURRENT 4f971e89-eebd-4455-a8de-9e59040e7347 5ca83367-6e45-459f-a27b-476b1d01c936 0;\
  powercfg /SETACTIVE SCHEME_CURRENT\
\""
```

- [ ] **Step 2: Deshabilitar sleep e hibernación completamente**

```bash
ssh lenovo "powershell.exe -Command \"\
  powercfg /CHANGE standby-timeout-ac 0;\
  powercfg /CHANGE standby-timeout-dc 0;\
  powercfg /CHANGE hibernate-timeout-ac 0;\
  powercfg /CHANGE hibernate-timeout-dc 0\
\""
```

- [ ] **Step 3: Verificar que quedó aplicado**

```bash
ssh lenovo "powershell.exe -Command \"powercfg /QUERY SCHEME_CURRENT 4f971e89-eebd-4455-a8de-9e59040e7347 5ca83367-6e45-459f-a27b-476b1d01c936\""
```

Esperado: ver `Current AC Power Setting Index: 0x00000000` (Do nothing)

---

## Task 3: Auto-inicio de WSL2 + SSH al boot de la Lenovo

**Files:**
- Create: `C:\Users\cris\wsl2_autostart.ps1` en la Lenovo (via SSH)
- Create: Windows Task Scheduler task en la Lenovo

**Interfaces:**
- Consumes: SSH funcional
- Produce: WSL2 arranca automáticamente cuando Windows bootea, sshd disponible sin intervención

- [ ] **Step 1: Crear script PowerShell de autostart en la Lenovo**

```bash
ssh lenovo "powershell.exe -Command \"\
  Set-Content -Path 'C:\\Users\\cris\\wsl2_autostart.ps1' -Value @'\
# Auto-inicia WSL2 y SSH server\`n\
wsl -d Ubuntu -e bash -c 'sudo service ssh start >> /tmp/wsl2_ssh_start.log 2>&1'\`n\
'@\
\""
```

- [ ] **Step 2: Registrar tarea en Windows Task Scheduler de la Lenovo**

```bash
ssh lenovo "powershell.exe -Command \"\
  \$action = New-ScheduledTaskAction -Execute 'powershell.exe' -Argument '-WindowStyle Hidden -File C:\\Users\\cris\\wsl2_autostart.ps1';\
  \$trigger = New-ScheduledTaskTrigger -AtLogOn -User 'cris';\
  \$settings = New-ScheduledTaskSettingsSet -ExecutionTimeLimit 0 -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1);\
  Register-ScheduledTask -TaskName 'Hermes-WSL2-Autostart' -Action \$action -Trigger \$trigger -Settings \$settings -RunLevel Highest -Force\
\""
```

- [ ] **Step 3: Asegurar que sshd arranca automáticamente en WSL2**

```bash
ssh lenovo "sudo systemctl enable ssh 2>/dev/null || sudo update-rc.d ssh enable 2>/dev/null; echo 'SSH_AUTOSTART_OK'"
```

- [ ] **Step 4: Verificar tarea creada**

```bash
ssh lenovo "powershell.exe -Command \"Get-ScheduledTask -TaskName 'Hermes-WSL2-Autostart' | Select-Object TaskName, State\""
```

Esperado: `Hermes-WSL2-Autostart   Ready`

---

## Task 4: Completar tareas pendientes de Hermes en Lenovo

**Files:**
- Modify: crontab de usuario `cris` en WSL2 Lenovo
- Create: `~/SadTalker/` en Lenovo

**Interfaces:**
- Consumes: SSH funcional, Ollama corriendo en WSL2
- Produce: modelo `obsidian:3b` disponible, cron jobs de reflexión activos, SadTalker instalado

- [ ] **Step 1: Verificar que Ollama está corriendo en Lenovo**

```bash
ssh lenovo "curl -s http://localhost:11434/api/tags | python3 -c 'import sys,json; print([m[\"name\"] for m in json.load(sys.stdin)[\"models\"]])'"
```

- [ ] **Step 2: Descargar modelo obsidian:3b**

```bash
ssh lenovo "ollama pull obsidian:3b"
```

Tarda varios minutos. Esperado al final: `success`

- [ ] **Step 3: Agregar cron jobs de aprendizaje**

```bash
ssh lenovo "(crontab -l 2>/dev/null; echo '0 3 * * * cd ~/hermes/brain && python3 learning/reflexion_diaria.py >> ~/hermes/logs/reflexion.log 2>&1'; echo '30 3 * * * cd ~/hermes/brain && python3 learning/debate_sintetico.py >> ~/hermes/logs/debate.log 2>&1') | crontab -"
```

- [ ] **Step 4: Verificar cron jobs**

```bash
ssh lenovo "crontab -l"
```

Esperado: ver las 2 líneas de reflexion_diaria y debate_sintetico.

- [ ] **Step 5: Clonar SadTalker**

```bash
ssh lenovo "cd ~ && git clone https://github.com/OpenTalker/SadTalker.git"
```

- [ ] **Step 6: Instalar dependencias SadTalker**

```bash
ssh lenovo "cd ~/SadTalker && pip install -r requirements.txt"
```

- [ ] **Step 7: Descargar modelos SadTalker**

```bash
ssh lenovo "cd ~/SadTalker && bash scripts/download_models.sh"
```

---

## Task 5: Variables pendientes en brain/.env (este PC)

**Files:**
- Modify: `C:\Users\Cris\hermes\brain\.env`

**Interfaces:**
- Consumes: Ruta real de SadTalker en Lenovo (siempre `/home/cris/SadTalker`)
- Produce: Config completa para visión, SadTalker, Whisper

- [ ] **Step 1: Leer .env actual**

```bash
# Claude Code: usar Read tool en C:\Users\Cris\hermes\brain\.env
```

- [ ] **Step 2: Agregar variables faltantes**

Agregar al final de `brain/.env`:
```
VISION_MODEL=obsidian:3b
SADTALKER_PATH=/home/cris/SadTalker
WHISPER_MODEL_SIZE=small
```

- [ ] **Step 3: Verificar que el bot levanta correctamente**

```powershell
C:\Users\Cris\hermes\venv\Scripts\python.exe -c "import sys; sys.path.insert(0, 'C:/Users/Cris/hermes/brain'); import config; print('CONFIG_OK')"
```

---

## Verificación Final

```bash
# Desde este PC, sin contraseña, sin opciones extra:
ssh lenovo "echo 'LENOVO_OK' && ollama list | grep obsidian && crontab -l | wc -l"
```

Esperado:
```
LENOVO_OK
obsidian:3b   ...
2
```
