"""Pre-built mock tool handlers for common testing scenarios."""

from __future__ import annotations

from typing import Any

from .registry import MockToolRegistry


def register_hotel_booking_mocks(registry: MockToolRegistry) -> None:
    """Register a set of mock tools for the hotel booking scenario."""

    registry.register(
        "check_availability",
        handler=lambda args: {
            "available": True,
            "rooms": [
                {"type": "Standard Room", "price": 399},
                {"type": "King Room", "price": 499},
                {"type": "Suite", "price": 899},
            ],
        },
        latency_ms=(200, 800),
    )

    registry.register(
        "create_booking",
        handler=lambda args: {
            "booking_id": "BK20240115001",
            "status": "confirmed",
            "checkin": args.get("checkin", ""),
            "nights": args.get("nights", 1),
        },
        latency_ms=(500, 2000),
        failure_rate=0.1,
    )

    registry.register(
        "cancel_booking",
        handler=lambda args: {
            "booking_id": args.get("booking_id", ""),
            "status": "cancelled",
            "refund": True,
        },
        latency_ms=(300, 1000),
    )

    registry.register(
        "get_booking_details",
        handler=lambda args: {
            "booking_id": args.get("booking_id", "BK20240115001"),
            "status": "confirmed",
            "room_type": "King Room",
            "checkin": "2024-01-19",
            "nights": 2,
            "price_total": 998,
        },
        latency_ms=(100, 400),
    )

    registry.register(
        "long_running_search",
        handler=lambda args: {
            "results": [
                {"hotel": "Grand Hotel", "distance": "0.5km", "price": 599},
                {"hotel": "City Inn", "distance": "1.2km", "price": 299},
            ],
        },
        latency_ms=(3000, 8000),  # deliberately slow
    )


def register_general_mocks(registry: MockToolRegistry) -> None:
    """Register general-purpose mock tools."""

    registry.register(
        "get_weather",
        handler=lambda args: {
            "location": args.get("location", "Beijing"),
            "temperature": 22,
            "condition": "sunny",
            "humidity": 45,
        },
        latency_ms=(100, 300),
    )

    registry.register(
        "search_web",
        handler=lambda args: {
            "query": args.get("query", ""),
            "results": [
                {"title": "Result 1", "snippet": "Some information..."},
                {"title": "Result 2", "snippet": "More information..."},
            ],
        },
        latency_ms=(500, 1500),
    )

    registry.register(
        "send_email",
        handler=lambda args: {
            "status": "sent",
            "to": args.get("to", ""),
            "subject": args.get("subject", ""),
        },
        latency_ms=(200, 600),
        failure_rate=0.05,
    )

    registry.register(
        "set_reminder",
        handler=lambda args: {
            "reminder_id": "REM001",
            "time": args.get("time", ""),
            "message": args.get("message", ""),
            "status": "set",
        },
        latency_ms=(50, 200),
    )

    registry.register(
        "get_calendar",
        handler=lambda args: {
            "date": args.get("date", "today"),
            "events": [
                {"time": "09:00", "title": "Team standup"},
                {"time": "14:00", "title": "Project review"},
            ],
        },
        latency_ms=(100, 400),
    )
