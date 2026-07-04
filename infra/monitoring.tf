# Monitoring stack: where the VM's logs and metrics go, and who gets paged.
#
# Pieces (top to bottom):
#   1. Log Analytics workspace  — the database that stores logs/metrics (CloudWatch Logs).
#   2. Application Insights      — app-level telemetry store; its connection string feeds
#                                  Plan 3 (custom bot metrics). Backed by the workspace above.
#   3. Azure Monitor Agent (AMA) — an extension installed ON the VM that ships data out.
#   4. Data Collection Rule      — tells the agent WHAT to collect and WHERE to send it.
#                                  Without this, AMA is installed but collects nothing.
#   5. Action Group + Alert      — emails you when the VM stops reporting availability.
#   6. Container-logs DCR + table — tails the bot's Docker logs into a queryable table.

# ---------------------------------------------------------------------------
# 1. Log Analytics workspace — the store everything lands in.
# ---------------------------------------------------------------------------
resource "azurerm_log_analytics_workspace" "main" {
  name                = "log-${var.prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  sku                 = "PerGB2018" # pay-per-GB ingested; the standard modern SKU.
  retention_in_days   = 30          # how long logs are kept before auto-deletion.
}

# ---------------------------------------------------------------------------
# 2. Application Insights — app telemetry, wired to the workspace above
#    (workspace-based mode). Plan 3 exports custom bot metrics into this.
# ---------------------------------------------------------------------------
resource "azurerm_application_insights" "main" {
  name                = "appi-${var.prefix}"
  location            = azurerm_resource_group.main.location
  resource_group_name = azurerm_resource_group.main.name
  workspace_id        = azurerm_log_analytics_workspace.main.id
  application_type    = "other" # not a web app; "other" = generic/custom telemetry.
}

# ---------------------------------------------------------------------------
# 3. Azure Monitor Agent (AMA) — installed on the VM as an extension.
#    It is the shipper; the Data Collection Rule below decides what it ships.
# ---------------------------------------------------------------------------
resource "azurerm_virtual_machine_extension" "ama" {
  name                       = "AzureMonitorLinuxAgent"
  virtual_machine_id         = azurerm_linux_virtual_machine.main.id
  publisher                  = "Microsoft.Azure.Monitor"
  type                       = "AzureMonitorLinuxAgent"
  type_handler_version       = "1.0"
  auto_upgrade_minor_version = true
}

# ---------------------------------------------------------------------------
# 4. Data Collection Rule (DCR) + association.
#    The DCR is the "what + where". The association binds it to the VM.
#    This is the piece that makes Heartbeat / Perf / Syslog actually appear
#    in the workspace — AMA alone collects nothing without it.
# ---------------------------------------------------------------------------
resource "azurerm_monitor_data_collection_rule" "main" {
  name                = "dcr-${var.prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location

  # WHERE the collected data is sent.
  destinations {
    log_analytics {
      workspace_resource_id = azurerm_log_analytics_workspace.main.id
      name                  = "law-dest" # local nickname referenced by data_flow below.
    }
  }

  # WHICH streams go to WHICH destination. Heartbeat rides along automatically
  # once any DCR is associated, which is what powers the liveness check.
  data_flow {
    streams      = ["Microsoft-Perf", "Microsoft-Syslog"]
    destinations = ["law-dest"]
  }

  # WHAT to collect.
  data_sources {
    # A couple of basic host metrics → the Perf table.
    performance_counter {
      name                          = "basic-host-metrics"
      streams                       = ["Microsoft-Perf"]
      sampling_frequency_in_seconds = 60
      counter_specifiers = [
        "\\Processor(_Total)\\% Processor Time",
        "\\Memory\\Available Bytes",
      ]
    }
    # System logs at Warning+ → the Syslog table (handy for boot/docker issues).
    syslog {
      name           = "system-syslog"
      streams        = ["Microsoft-Syslog"]
      facility_names = ["*"]
      log_levels     = ["Warning", "Error", "Critical", "Alert", "Emergency"]
    }
  }
}

resource "azurerm_monitor_data_collection_rule_association" "main" {
  name                    = "dcra-${var.prefix}"
  target_resource_id      = azurerm_linux_virtual_machine.main.id
  data_collection_rule_id = azurerm_monitor_data_collection_rule.main.id
}

# ---------------------------------------------------------------------------
# 5. Alert: email the operator when the VM stops being available (i.e. down).
# ---------------------------------------------------------------------------
# An "action group" is the reusable list of who/what to notify when an alert fires.
resource "azurerm_monitor_action_group" "main" {
  name                = "ag-${var.prefix}"
  resource_group_name = azurerm_resource_group.main.name
  short_name          = "lifeos" # <=12 chars; shown as the email/SMS sender label.

  email_receiver {
    name          = "operator"
    email_address = var.alert_email
  }
}

# VmAvailabilityMetric is a platform metric (no agent needed): 1 = up, <1 = unavailable.
resource "azurerm_monitor_metric_alert" "vm_down" {
  name                = "alert-${var.prefix}-vm-availability"
  resource_group_name = azurerm_resource_group.main.name
  scopes              = [azurerm_linux_virtual_machine.main.id]
  description         = "VM availability dropped (likely down)."
  frequency           = "PT5M" # evaluate every 5 minutes.
  window_size         = "PT5M" # over a 5-minute look-back window.

  criteria {
    metric_namespace = "Microsoft.Compute/virtualMachines"
    metric_name      = "VmAvailabilityMetric"
    aggregation      = "Average"
    operator         = "LessThan"
    threshold        = 1
  }

  action {
    action_group_id = azurerm_monitor_action_group.main.id
  }
}

# ---------------------------------------------------------------------------
# 6. Bot container logs → a custom table you can query in the portal.
#    The agent tails Docker's per-container JSON log files on disk, so this
#    does NOT disturb `docker logs lifeos-bot` on the VM — you keep both.
#
#    Flow:  /var/lib/docker/containers/*/*-json.log   (raw JSON lines)
#             -> agent ships them as the "Custom-ContainerLogs" stream
#             -> transform_kql unwraps Docker's JSON ({"log","stream","time"})
#             -> lands in the ContainerLogs_CL table.
# ---------------------------------------------------------------------------

# The destination table. azurerm can't CREATE custom (_CL) tables, so we call
# the ARM API directly via azapi. Must exist before the DCR references it.
resource "azapi_resource" "container_logs_table" {
  type      = "Microsoft.OperationalInsights/workspaces/tables@2022-10-01"
  name      = "ContainerLogs_CL" # custom tables must end in _CL.
  parent_id = azurerm_log_analytics_workspace.main.id

  body = {
    properties = {
      schema = {
        name = "ContainerLogs_CL"
        # TimeGenerated (datetime) is mandatory for any DCR-ingested table.
        columns = [
          { name = "TimeGenerated", type = "datetime" },
          { name = "Level", type = "string" },         # INFO | WARNING | ERROR | DEBUG…
          { name = "Logger", type = "string" },        # lifeos-bot | httpx | telegram…
          { name = "Event", type = "string" },         # optional stable event name
          { name = "Message", type = "string" },       # human-readable message
          { name = "ExceptionType", type = "string" }, # ValueError | NetworkError…
          { name = "Exception", type = "string" },     # complete multiline traceback
          { name = "Stream", type = "string" },        # stdout | stderr
          { name = "ContainerTime", type = "string" }, # Docker's own timestamp
          { name = "RawData", type = "string" },       # original JSON line (fallback)
        ]
      }
      retentionInDays = 14
    }
  }
}

# A Data Collection ENDPOINT — the ingestion URL the agent posts custom logs to.
# Standard streams (Perf/Syslog) don't need one, but custom-log DCRs (log_file →
# a _CL table) are rejected without it. One DCE can serve many custom-log DCRs.
resource "azurerm_monitor_data_collection_endpoint" "main" {
  name                = "dce-${var.prefix}"
  resource_group_name = azurerm_resource_group.main.name
  location            = azurerm_resource_group.main.location
}

resource "azurerm_monitor_data_collection_rule" "container_logs" {
  name                        = "dcr-${var.prefix}-containerlogs"
  resource_group_name         = azurerm_resource_group.main.name
  location                    = azurerm_resource_group.main.location
  data_collection_endpoint_id = azurerm_monitor_data_collection_endpoint.main.id
  depends_on                  = [azapi_resource.container_logs_table] # table must exist first.

  # Shape of what the agent SENDS: each tailed line as RawData + an ingest time.
  stream_declaration {
    stream_name = "Custom-ContainerLogs" # input stream names must start with "Custom-".
    column {
      name = "TimeGenerated"
      type = "datetime"
    }
    column {
      name = "RawData"
      type = "string"
    }
  }

  destinations {
    log_analytics {
      workspace_resource_id = azurerm_log_analytics_workspace.main.id
      name                  = "law-dest"
    }
  }

  # WHAT to read: Docker writes one JSON object per line into these files.
  data_sources {
    log_file {
      name          = "docker-container-logs"
      streams       = ["Custom-ContainerLogs"]
      file_patterns = ["/var/lib/docker/containers/*/*-json.log"]
      format        = "text" # we read raw lines; the transform below parses them.
      settings {
        text {
          # One line = one record (Docker JSON lines are single-line).
          record_start_timestamp_format = "ISO 8601"
        }
      }
    }
  }

  # Unwrap Docker's JSON envelope, pull out the log level, and map to the table.
  #
  # COST KNOB: by default DEBUG lines are dropped *before* ingestion (so they're
  # never billed). Mark any noisy log (e.g. the Telegram getUpdates poll) as DEBUG
  # in the bot and it stops costing you anything, while still showing in
  # `docker logs` locally. Flip var.ingest_debug_logs = true (then apply) when you
  # need those DEBUG lines in the portal to investigate — no bot redeploy needed.
  #
  # Level is parsed from the bot's log format: "<ts> | <LEVEL> | <name> | <msg>".
  # Continuation lines (e.g. tracebacks) have no " | " and get Level "" → kept.
  data_flow {
    streams       = ["Custom-ContainerLogs"]
    destinations  = ["law-dest"]
    output_stream = "Custom-ContainerLogs_CL" # the azapi table above.
    # NOTE: the DCR transform engine is a restricted KQL subset — it rejects
    # multi-assignment `extend` (a = x, b = y). Use one `extend` per column.
    transform_kql = <<-KQL
      source
      | extend d = parse_json(RawData)
      | extend DockerMessage = tostring(d["log"])
      | extend app = parse_json(DockerMessage)
      | extend Stream = tostring(d["stream"])
      | extend ContainerTime = tostring(d["time"])
      | extend StructuredLevel = tostring(app["level"])
      | extend Level = iff(isnotempty(StructuredLevel), StructuredLevel, tostring(split(DockerMessage, " | ")[1]))
      | extend Logger = iff(isnotempty(StructuredLevel), tostring(app["logger"]), tostring(split(DockerMessage, " | ")[2]))
      | extend Event = tostring(app["event"])
      | extend Message = iff(isnotempty(StructuredLevel), tostring(app["message"]), DockerMessage)
      | extend ExceptionType = tostring(app["exception_type"])
      | extend Exception = tostring(app["exception"])
      %{~if !var.ingest_debug_logs~}
      | where Level != "DEBUG"
      %{~endif~}
      | where not(Logger == "httpx" and Level == "INFO" and Message has "/getUpdates")
      | project TimeGenerated, Level, Logger, Event, Message, ExceptionType, Exception, Stream, ContainerTime, RawData
    KQL
  }
}

resource "azurerm_monitor_data_collection_rule_association" "container_logs" {
  name                    = "dcra-${var.prefix}-containerlogs"
  target_resource_id      = azurerm_linux_virtual_machine.main.id
  data_collection_rule_id = azurerm_monitor_data_collection_rule.container_logs.id
}
