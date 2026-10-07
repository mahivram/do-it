"""Windows system and hardware information plus explicitly confirmed controls."""

import ctypes
import json
import os
import platform
import re
import subprocess
from datetime import datetime, timezone
from typing import Any


_SENSITIVE_ENV_PATTERN = re.compile(
    r"(^|[_-])(?:KEY|AUTH|CREDENTIALS?|PASS(?:WORD|WD)?|SECRET|TOKEN|"
    r"URL|URI|DSN|CONNECTION_STRING)"
    r"(?:[_-]|$)",
    re.IGNORECASE,
)
_UPDATE_ID_PATTERN = re.compile(
    r"^[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-"
    r"[0-9a-fA-F]{4}-[0-9a-fA-F]{12}$"
)


def _run_powershell(script: str, *, timeout: int = 60) -> str:
    """Run a fixed PowerShell script and surface command failures."""
    result = subprocess.run(
        [
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-ExecutionPolicy",
            "Bypass",
            "-Command",
            script,
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=timeout,
    )
    if result.returncode:
        message = result.stderr.strip() or result.stdout.strip()
        raise RuntimeError(message or f"PowerShell exited with code {result.returncode}")
    return result.stdout.strip()


def _run_powershell_json(script: str) -> Any:
    output = _run_powershell(
        "$ErrorActionPreference = 'Stop'; "
        + script
        + " | ConvertTo-Json -Depth 6 -Compress"
    )
    if not output:
        return None
    return json.loads(output)


def _ps_literal(value: str) -> str:
    return "'" + value.replace("'", "''") + "'"


def get_system_info() -> dict[str, str]:
    """Return operating-system version, build, and architecture."""
    return {
        "os": platform.system(),
        "release": platform.release(),
        "version": platform.version(),
        "architecture": platform.machine(),
    }


def get_system_uptime() -> dict[str, str | int]:
    """Return uptime seconds and an ISO-8601 boot time."""
    uptime_seconds = int(ctypes.windll.kernel32.GetTickCount64() // 1000)
    boot_time = datetime.now(timezone.utc).timestamp() - uptime_seconds
    return {
        "uptime_seconds": uptime_seconds,
        "boot_time_utc": datetime.fromtimestamp(boot_time, timezone.utc).isoformat(),
        "last_restart_utc": datetime.fromtimestamp(boot_time, timezone.utc).isoformat(),
    }


def get_hardware_info() -> dict[str, Any]:
    """Return CPU, memory, disk, and display-adapter details."""
    script = """
$cpu = Get-CimInstance Win32_Processor | Select-Object -First 1 Name, NumberOfCores, NumberOfLogicalProcessors
$computer = Get-CimInstance Win32_ComputerSystem
$disks = @(Get-CimInstance Win32_LogicalDisk -Filter "DriveType=3" | ForEach-Object {
    [pscustomobject]@{ device = $_.DeviceID; size_bytes = $_.Size; free_bytes = $_.FreeSpace }
})
$gpus = @(Get-CimInstance Win32_VideoController | ForEach-Object {
    [pscustomobject]@{ name = $_.Name; driver_version = $_.DriverVersion; adapter_ram_bytes = $_.AdapterRAM }
})
[pscustomobject]@{
    cpu = $cpu
    memory_bytes = $computer.TotalPhysicalMemory
    disks = $disks
    gpus = $gpus
}
"""
    result = _run_powershell_json(script)
    if not isinstance(result, dict):
        raise RuntimeError("PowerShell returned invalid hardware information")
    return result


def list_environment_variables() -> dict[str, str]:
    """Return environment variables while redacting likely credentials."""
    values = {}
    for name, value in sorted(os.environ.items(), key=lambda item: item[0].lower()):
        if _SENSITIVE_ENV_PATTERN.search(name):
            values[name] = "<redacted>"
        else:
            values[name] = value
    return values


def _confirm_system_action(action_description: str) -> bool:
    """Require a direct human confirmation in the running terminal."""
    try:
        answer = input(
            f"{action_description}. Type 'yes' to confirm (anything else cancels): "
        )
    except EOFError:
        return False
    return answer.strip().lower() == "yes"


def manage_power(action: str) -> str:
    """Perform a power action only after explicit terminal confirmation."""
    commands = {
        "shutdown": ["shutdown.exe", "/s", "/t", "0"],
        "restart": ["shutdown.exe", "/r", "/t", "0"],
        "hibernate": ["shutdown.exe", "/h"],
        "lock": ["rundll32.exe", "user32.dll,LockWorkStation"],
    }
    if action not in {*commands, "sleep"}:
        raise ValueError(f"Unsupported power action: {action}")
    if not _confirm_system_action(f"Confirm system {action}"):
        return f"Cancelled system {action}"

    if action == "sleep":
        script = (
            "Add-Type -Name PowerControl -Namespace Native "
            "-MemberDefinition '[DllImport(\"powrprof.dll\", SetLastError=true)] "
            "public static extern bool SetSuspendState(bool hibernate, "
            "bool forceCritical, bool disableWakeEvent);'; "
            "[Native.PowerControl]::SetSuspendState($false, $false, $false)"
        )
        _run_powershell(script)
    else:
        result = subprocess.run(
            commands[action], capture_output=True, text=True, check=False, timeout=15
        )
        if result.returncode:
            message = result.stderr.strip() or result.stdout.strip()
            raise RuntimeError(message or f"{action} command failed")
    return f"Started system {action}"


def create_system_restore_point(description: str) -> str:
    """Create a restore point after asking the user to confirm."""
    if not description.strip():
        raise ValueError("Restore point description cannot be empty")
    if not _confirm_system_action(f"Create system restore point {description!r}"):
        return "Cancelled system restore point creation"

    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"Checkpoint-Computer -Description {_ps_literal(description)} "
        "-RestorePointType MODIFY_SETTINGS"
    )
    _run_powershell(script, timeout=300)
    return f"Created system restore point: {description}"


def manage_windows_updates(action: str, update_id: str | None = None) -> Any:
    """List updates or install/hide one update by ID after confirmation."""
    if action not in {"list", "install", "hide"}:
        raise ValueError(f"Unsupported Windows Update action: {action}")
    if action == "list":
        script = r"""
$session = New-Object -ComObject Microsoft.Update.Session
$search = $session.CreateUpdateSearcher()
$result = $search.Search("IsInstalled=0 and IsHidden=0")
$updates = @()
for ($i = 0; $i -lt $result.Updates.Count; $i++) {
    $update = $result.Updates.Item($i)
    $updates += [pscustomobject]@{
        title = $update.Title
        update_id = $update.Identity.UpdateID
        revision = $update.Identity.RevisionNumber
        downloaded = $update.IsDownloaded
    }
}
ConvertTo-Json -InputObject @($updates) -Depth 4 -Compress
"""
        output = _run_powershell(script, timeout=300)
        return json.loads(output) if output else []

    if update_id is None or not _UPDATE_ID_PATTERN.fullmatch(update_id):
        raise ValueError("A valid update_id GUID is required")
    if not _confirm_system_action(f"{action.title()} Windows Update {update_id}"):
        return f"Cancelled Windows Update {action}"

    update_literal = _ps_literal(update_id)
    if action == "hide":
        script = f"""
$ErrorActionPreference = 'Stop'
$session = New-Object -ComObject Microsoft.Update.Session
$search = $session.CreateUpdateSearcher()
$result = $search.Search("IsInstalled=0 and IsHidden=0")
$update = $null
for ($i = 0; $i -lt $result.Updates.Count; $i++) {{
    $candidate = $result.Updates.Item($i)
    if ($candidate.Identity.UpdateID -eq {update_literal}) {{ $update = $candidate; break }}
}}
if ($null -eq $update) {{ throw "Update ID not found" }}
$update.IsHidden = $true
"""
    else:
        script = f"""
$ErrorActionPreference = 'Stop'
$session = New-Object -ComObject Microsoft.Update.Session
$search = $session.CreateUpdateSearcher()
$result = $search.Search("IsInstalled=0 and IsHidden=0")
$update = $null
for ($i = 0; $i -lt $result.Updates.Count; $i++) {{
    $candidate = $result.Updates.Item($i)
    if ($candidate.Identity.UpdateID -eq {update_literal}) {{ $update = $candidate; break }}
}}
if ($null -eq $update) {{ throw "Update ID not found" }}
$collection = New-Object -ComObject Microsoft.Update.UpdateColl
[void]$collection.Add($update)
$downloader = $session.CreateUpdateDownloader()
$downloader.Updates = $collection
[void]$downloader.Download()
if (-not $update.IsDownloaded) {{ throw "Update download failed" }}
$installer = $session.CreateUpdateInstaller()
$installer.Updates = $collection
$installResult = $installer.Install()
if ($installResult.ResultCode -ge 3) {{ throw "Update installation failed" }}
"""
    _run_powershell(script, timeout=1800)
    return f"Windows Update {action} completed for {update_id}"


def manage_windows_features(action: str, feature_name: str | None = None) -> Any:
    """List Windows optional features or enable/disable one with confirmation."""
    if action not in {"list", "enable", "disable"}:
        raise ValueError(f"Unsupported Windows feature action: {action}")
    if action == "list":
        return _run_powershell_json(
            "Get-WindowsOptionalFeature -Online | "
            "Select-Object FeatureName, State"
        )

    if feature_name is None or not feature_name.strip():
        raise ValueError("feature_name is required")
    if not _confirm_system_action(f"{action.title()} Windows feature {feature_name}"):
        return f"Cancelled Windows feature {action}"

    name_literal = _ps_literal(feature_name)
    command = (
        "Enable-WindowsOptionalFeature"
        if action == "enable"
        else "Disable-WindowsOptionalFeature"
    )
    script = (
        "$ErrorActionPreference = 'Stop'; "
        f"{command} -Online -FeatureName {name_literal} -NoRestart | Out-Null"
    )
    _run_powershell(script, timeout=900)
    return f"Windows feature {action} completed: {feature_name}"


def get_power_info() -> dict[str, Any]:
    """Return battery status and available power plans."""
    battery_script = """
$batteries = @(Get-CimInstance Win32_Battery | ForEach-Object {
    [pscustomobject]@{
        name = $_.Name
        status = $_.Status
        estimated_charge_percent = $_.EstimatedChargeRemaining
        battery_status = $_.BatteryStatus
    }
})
ConvertTo-Json -InputObject @($batteries) -Depth 4 -Compress
"""
    battery_output = _run_powershell(battery_script)
    batteries = json.loads(battery_output) if battery_output else []
    plans_output = _run_powershell("powercfg.exe /list")
    return {"batteries": batteries, "power_plans": plans_output.splitlines()}
