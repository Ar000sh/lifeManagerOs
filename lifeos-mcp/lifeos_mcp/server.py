from datetime import datetime
from zoneinfo import ZoneInfo
from mcp.server.fastmcp import FastMCP
from .config import Settings, load_settings, load_map, save_map
from .errors import WorkspaceUnavailable
from .notion_client import HttpxNotionClient
from .calendar_client import GoogleCalendarClient
from .tools.get_today import get_today
from .tools.get_week import get_week
from .tools.query_records import query_records
from .tools.add_record import add_record
from .tools.create_event import create_event


def build_app(settings: Settings, notion=None, calendar=None) -> FastMCP:
    app = FastMCP("lifeos")

    def _notion():
        return notion or HttpxNotionClient(settings.notion_token)

    def _calendar():
        return calendar or GoogleCalendarClient(
            settings.google_credentials, settings.google_token_path, settings.tz
        )

    def _today():
        return datetime.now(ZoneInfo(settings.tz)).date()

    @app.tool(name="get_today")
    def get_today_tool() -> dict:
        """Today's tasks, key dates, work shift, and calendar events across all areas."""
        m = load_map(settings.map_path)
        try:
            payload = get_today(m, _notion(), _calendar(), _today(), settings.tz)
        except WorkspaceUnavailable:
            return {"error": "reconnect_notion"}
        save_map(m, settings.map_path)
        return payload.to_dict()

    @app.tool(name="get_week")
    def get_week_tool() -> dict:
        """This week's tasks, deadlines, shifts, and events (Mon-Sun)."""
        m = load_map(settings.map_path)
        try:
            payload = get_week(m, _notion(), _calendar(), _today(), settings.tz)
        except WorkspaceUnavailable:
            return {"error": "reconnect_notion"}
        save_map(m, settings.map_path)
        return payload.to_dict()

    @app.tool(name="query_records")
    def query_records_tool(role: str, filters: dict | None = None) -> list:
        """Query records of a function role (tasks/schedule/catalog) with optional filters."""
        m = load_map(settings.map_path)
        res = query_records(m, _notion(), role, filters)
        save_map(m, settings.map_path)
        return res

    @app.tool(name="add_record")
    def add_record_tool(role: str, fields: dict, area: str | None = None) -> dict:
        """Create a record (row) of a role into its resolved destination. Records only."""
        m = load_map(settings.map_path)
        res = add_record(m, _notion(), role, fields, area)
        save_map(m, settings.map_path)
        return res

    @app.tool(name="create_event")
    def create_event_tool(title: str, start: str, end: str | None = None, notes: str | None = None) -> dict:
        """Create a Google Calendar event (Europe/Berlin, default 1h)."""
        return create_event(_calendar(), title, start, end, notes)

    return app


def main():
    build_app(load_settings()).run()


if __name__ == "__main__":
    main()
