# =====================================
# GOD HAND BERSERK - Launcher
# =====================================

param(
    [switch]$SkipDeps = $false,
    [switch]$FemtoOnly = $false,
    [switch]$VoidOnly = $false
)

# Configuration
$FEMTO_PORT = 8000
$VOID_PORT = 5000
$PROJECT_NAME = "God Hand Berserk"
$PYTHON_MIN_VERSION = "3.8"

# Couleurs
$RED = "Red"
$GREEN = "Green" 
$YELLOW = "Yellow"
$MAGENTA = "Magenta"
$CYAN = "Cyan"

function Write-GodHandMessage {
    param([string]$Message, [string]$Color = "White", [string]$Symbol = "[*]")
    Write-Host "$Symbol $Message" -ForegroundColor $Color
}

function Test-PythonInstallation {
    Write-GodHandMessage "Verification de Python..." $CYAN "[CHECK]"
    
    try {
        $pythonVersion = python --version 2>$null
        if ($pythonVersion -match "Python (\d+\.\d+)") {
            $version = [version]$matches[1]
            $minVersion = [version]$PYTHON_MIN_VERSION
            
            if ($version -ge $minVersion) {
                Write-GodHandMessage "Python $($matches[1]) detecte [OK]" $GREEN "[PYTHON]"
                return $true
            } else {
                Write-GodHandMessage "Python $($matches[1]) trop ancien (min: $PYTHON_MIN_VERSION)" $RED "[ERROR]"
                return $false
            }
        }
    } catch {
        Write-GodHandMessage "Python non trouve!" $RED "[ERROR]"
        Write-GodHandMessage "Telechargez Python sur: https://python.org" $YELLOW "[INFO]"
        return $false
    }
}

function Test-PortAvailability {
    param([int]$Port)
    
    try {
        $connection = New-Object System.Net.Sockets.TcpClient
        $connection.Connect("127.0.0.1", $Port)
        $connection.Close()
        return $false
    } catch {
        return $true
    }
}

function Install-Dependencies {
    Write-GodHandMessage "Installation des dependances..." $MAGENTA "[INSTALL]"
    
    python -m pip install --upgrade pip
    
    if (Test-Path "requirements.txt") {
        python -m pip install -r requirements.txt
    }
    
    $godHandDeps = @(
        "streamlit",
        "flask", 
        "pandas",
        "numpy",
        "plotly",
        "anthropic",
        "openai"
    )
    
    foreach ($dep in $godHandDeps) {
        Write-GodHandMessage "Installation: $dep" $CYAN "[DEPS]"
        python -m pip install $dep --quiet
    }
    
    Write-GodHandMessage "Dependances installees!" $GREEN "[OK]"
}

function Start-Femto {
    Write-GodHandMessage "FEMTO - The Fallen Angel s'eveille..." $RED "[FEMTO]"
    
    if (-not (Test-PortAvailability $FEMTO_PORT)) {
        Write-GodHandMessage "Port $FEMTO_PORT occupe!" $RED "[ERROR]"
        return $false
    }
    
    $femtoProcess = Start-Process python -ArgumentList "ubik\start_solana_api.py" -PassThru -WindowStyle Hidden
    Start-Sleep -Seconds 3
    
    if ($femtoProcess -and -not $femtoProcess.HasExited) {
        Write-GodHandMessage "FEMTO operationnel sur port $FEMTO_PORT" $GREEN "[ACTIVE]"
        Write-GodHandMessage "Swagger UI: http://localhost:$FEMTO_PORT/docs" $CYAN "[API]"
        return $femtoProcess
    } else {
        Write-GodHandMessage "Echec du demarrage FEMTO!" $RED "[ERROR]"
        return $false
    }
}

function Start-Void {
    Write-GodHandMessage "VOID - The All-Seeing s'eveille..." $MAGENTA "[VOID]"
    
    if (-not (Test-PortAvailability $VOID_PORT)) {
        Write-GodHandMessage "Port $VOID_PORT occupe!" $RED "[ERROR]"
        return $false
    }
    
    $voidProcess = Start-Process streamlit -ArgumentList @(
        "run", "void\main_analytics.py",
        "--server.port", $VOID_PORT,
        "--server.address", "0.0.0.0"
    ) -PassThru -WindowStyle Hidden
    
    Start-Sleep -Seconds 5
    
    if ($voidProcess -and -not $voidProcess.HasExited) {
        Write-GodHandMessage "VOID operationnel sur port $VOID_PORT" $GREEN "[ACTIVE]"
        Write-GodHandMessage "Interface: http://localhost:$VOID_PORT" $CYAN "[WEB]"
        return $voidProcess
    } else {
        Write-GodHandMessage "Echec du demarrage VOID!" $RED "[ERROR]"
        return $false
    }
}

function Open-Browsers {
    Write-GodHandMessage "Ouverture des portails..." $CYAN "[BROWSER]"
    
    if (-not $VoidOnly) {
        Start-Process "http://localhost:$FEMTO_PORT/docs"
    }
    if (-not $FemtoOnly) {
        Start-Process "http://localhost:$VOID_PORT"
    }
}

function Show-GodHandBanner {
    Write-Host ""
    Write-Host "==========================================" -ForegroundColor $MAGENTA
    Write-Host "        GOD HAND BERSERK LAUNCHER        " -ForegroundColor $MAGENTA  
    Write-Host "==========================================" -ForegroundColor $MAGENTA
    Write-Host "  FEMTO - The Fallen Angel              " -ForegroundColor $RED
    Write-Host "  VOID  - The All-Seeing                " -ForegroundColor $MAGENTA
    Write-Host "==========================================" -ForegroundColor $MAGENTA
    Write-Host ""
}

function Wait-ForExit {
    param($femtoProcess, $voidProcess)
    
    Write-GodHandMessage "Systeme actif. Appuyez sur Ctrl+C pour arreter..." $GREEN "[RUNNING]"
    
    try {
        while ($true) {
            Start-Sleep -Seconds 1
            
            if ($femtoProcess -and $femtoProcess.HasExited) {
                Write-GodHandMessage "FEMTO s'est arrete!" $RED "[DIED]"
            }
            if ($voidProcess -and $voidProcess.HasExited) {
                Write-GodHandMessage "VOID s'est arrete!" $RED "[DIED]"
            }
        }
    } finally {
        Write-GodHandMessage "Arret du systeme God Hand..." $YELLOW "[STOP]"
        
        if ($femtoProcess -and -not $femtoProcess.HasExited) {
            $femtoProcess.Kill()
        }
        if ($voidProcess -and -not $voidProcess.HasExited) {
            $voidProcess.Kill()
        }
    }
}

# =====================================
# EXECUTION PRINCIPALE
# =====================================

Show-GodHandBanner

if (-not (Test-PythonInstallation)) {
    exit 1
}

if (-not $SkipDeps) {
    Install-Dependencies
}

$femtoProcess = $null
$voidProcess = $null

if (-not $VoidOnly) {
    $femtoProcess = Start-Femto
}

if (-not $FemtoOnly) {
    $voidProcess = Start-Void
}

Start-Sleep -Seconds 2
Open-Browsers

Write-Host ""
Write-GodHandMessage "SYSTEME GOD HAND OPERATIONNEL" $GREEN "[SUCCESS]"
Write-Host ""

if ($femtoProcess) {
    Write-Host "FEMTO (API Solana)    : http://localhost:$FEMTO_PORT/docs" -ForegroundColor $RED
}
if ($voidProcess) {
    Write-Host "VOID (Analytics IA)   : http://localhost:$VOID_PORT" -ForegroundColor $MAGENTA
}

Write-Host ""

Wait-ForExit $femtoProcess $voidProcess