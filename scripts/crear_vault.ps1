# Crea la estructura inicial del vault de Obsidian en la Lenovo
# Ejecutar en la Lenovo una sola vez

$VAULT = "C:\Users\chsan\hermes-vault"

Write-Host "Creando vault de Hermes en: $VAULT" -ForegroundColor Cyan

$carpetas = @(
    "$VAULT",
    "$VAULT\inbox",
    "$VAULT\conocimiento",
    "$VAULT\conocimiento\debates",
    "$VAULT\conocimiento\programacion",
    "$VAULT\conocimiento\ia",
    "$VAULT\conocimiento\trading",
    "$VAULT\conocimiento\diseno",
    "$VAULT\conversaciones"
)

foreach ($c in $carpetas) {
    New-Item -ItemType Directory -Force -Path $c | Out-Null
}

# Nota de bienvenida
$bienvenida = @"
# Vault de Hermes

Este vault es la memoria personal de Hermes, tu asistente de IA.

## Estructura

- **inbox/**: Nuevas notas sin clasificar
- **conocimiento/debates/**: Debates sintéticos generados automáticamente de noche
- **conocimiento/programacion/**: Aprendizajes sobre programación y software
- **conocimiento/ia/**: Aprendizajes sobre inteligencia artificial
- **conocimiento/trading/**: Aprendizajes sobre trading y mercados
- **conocimiento/diseno/**: Aprendizajes sobre diseño e interiorismo
- **conversaciones/**: Resúmenes de conversaciones importantes

## Cómo funciona

Hermes lee estas notas antes de responder tus preguntas.
Cada noche genera debates internos y guarda lo aprendido aquí.
Podés instalar Obsidian y abrir esta carpeta para leer y editar las notas.

*Vault creado el $(Get-Date -Format 'dd/MM/yyyy HH:mm')*
"@

$bienvenida | Out-File -FilePath "$VAULT\README.md" -Encoding UTF8

Write-Host "Vault creado correctamente." -ForegroundColor Green
Write-Host "Para verlo en Obsidian: instala Obsidian y abre la carpeta $VAULT" -ForegroundColor Yellow
