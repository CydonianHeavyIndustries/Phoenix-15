import os
from datetime import datetime, timedelta


def _format_time(dt: datetime) -> str:
    return dt.strftime("%I:%M %p").lstrip("0")


def _today_tasks():
    try:
        from systems import tasks

        items = tasks.get_all_tasks()
        out = []
        today = datetime.now().date()
        for t in items:
            try:
                when = t.get("time")
                if not when:
                    continue
                dt = datetime.fromisoformat(when)
                if dt.date() == today and not t.get("done"):
                    out.append((dt, t.get("message") or t.get("name")))
            except Exception:
                continue
        out.sort(key=lambda x: x[0])
        return out
    except Exception:
        return []


def _overdue_tasks():
    try:
        from systems import tasks

        items = tasks.get_all_tasks()
        now = datetime.now()
        out = []
        for t in items:
            try:
                when = t.get("time")
                if not when:
                    continue
                dt = datetime.fromisoformat(when)
                if dt < now and not t.get("done"):
                    out.append((dt, t.get("message") or t.get("name")))
            except Exception:
                continue
        out.sort(key=lambda x: x[0])
        return out
    except Exception:
        return []


def _weather_snippet() -> str:
    """Fetch local weather via OpenWeather, but keep location private in output.
    Output example: "Weather: 12°C, Clear sky." (no city name)
    """
    key = os.getenv("OPENWEATHER_API_KEY", "").strip()
    city = os.getenv("WEATHER_CITY", "").strip()
    zip_code = os.getenv("WEATHER_ZIP", "").replace(" ", "").strip()
    country = (os.getenv("WEATHER_COUNTRY", "CA") or "CA").strip()
    if not key or (not city and not zip_code):
        return "Weather: offline."
    try:
        import json
        import urllib.parse
        import urllib.request

        if zip_code:
            q = urllib.parse.quote(f"{zip_code},{country}")
            url = f"https://api.openweathermap.org/data/2.5/weather?zip={q}&appid={key}&units=metric"
        else:
            q = urllib.parse.quote(city)
            url = f"https://api.openweathermap.org/data/2.5/weather?q={q}&appid={key}&units=metric"
        with urllib.request.urlopen(url, timeout=5) as resp:
            d = json.loads(resp.read().decode("utf-8"))
        temp = round(float(d.get("main", {}).get("temp", 0)))
        desc = (
            str(d.get("weather", [{}])[0].get("description", "")).capitalize() or "--"
        )
        return f"Weather: {temp}°C, {desc}."
    except Exception:
        return "Weather: offline."


FACTS = [
    "Honey never spoils — edible for thousands of years.",
    "Octopuses have three hearts.",
    "Bananas are berries; strawberries are not.",
    "Sharks existed before trees.",
    "A day on Venus is longer than its year.",
]


def daily_brief() -> str:
    now = datetime.now()
    head = now.strftime("Good morning — %A, %B %d, %Y at %I:%M %p").lstrip("0")
    # Today’s tasks
    todays = _today_tasks()
    if todays:
        lines = [f"• {name} at {_format_time(dt)}" for dt, name in todays[:6]]
        today_str = "Today: \n" + "\n".join(lines)
    else:
        today_str = "Today: no scheduled events."
    # Overdue
    overdue = _overdue_tasks()
    overdue_str = f"Overdue: {len(overdue)}" if overdue else "Overdue: 0"
    # Weather (optional)
    weather = _weather_snippet()
    # Fun fact
    import random

    fact = random.choice(FACTS)
    brief = f"{head}\n{today_str}\n{overdue_str}\n{weather}\nFun fact: {fact}"
    return brief
