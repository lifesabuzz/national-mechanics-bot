# app_chat.py — Minimal FastAPI chatbot API
import os, yaml, json
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse
from pydantic import BaseModel
from typing import Dict, Any, List
from datetime import datetime
from pathlib import Path
from price_quote import price_quote
from openai import OpenAI

OPENAI_MODEL = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
client = OpenAI(api_key=OPENAI_API_KEY)

with open("policies.yaml") as f:
    POLICIES = yaml.safe_load(f)

DATA = {
    "packages_food": {
        "pkg_1": {"name":"Package 1","price_pp":20,"extras_price_pp_starter":5,"extras_price_pp_main":10,"extras_price_pp_dessert":5,"extras_price_pp_special":5},
        "pkg_2": {"name":"Package 2 – Save $5","price_pp":35,"extras_price_pp_starter":5,"extras_price_pp_main":10,"extras_price_pp_dessert":5,"extras_price_pp_special":5},
        "pkg_3": {"name":"Package 3 – Save $10","price_pp":45,"extras_price_pp_starter":5,"extras_price_pp_main":10,"extras_price_pp_dessert":5,"extras_price_pp_special":5},
    },
    "experiences_food": {
        "exp_eats_phl":{"name":"Eats of Philadelphia","price_pp":25},
        "exp_cozy":{"name":"Cozy Company","price_pp":35},
        "exp_game":{"name":"Game Night Classics","price_pp":20},
    },
    "beverages_open_bar": {
        "nonalc":{"tier_name":"Non-alcoholic","base_price_pp_2hr":15,"addl_hour_price_pp":5,"ticket_price":5},
        "beer":{"tier_name":"Beer","base_price_pp_2hr":25,"addl_hour_price_pp":10,"ticket_price":9},
        "house":{"tier_name":"House","base_price_pp_2hr":30,"addl_hour_price_pp":10,"ticket_price":10},
        "call":{"tier_name":"Call","base_price_pp_2hr":40,"addl_hour_price_pp":10,"ticket_price":12},
        "premium":{"tier_name":"Premium","base_price_pp_2hr":50,"addl_hour_price_pp":10,"ticket_price":15},
    },
    "happy_hour_packages": {
        "hh_house":{"tier_name":"House","price_pp_2hr":30,"extra_choice_price_pp":5},
        "hh_call":{"tier_name":"Call","price_pp_2hr":35,"extra_choice_price_pp":5},
        "hh_beer":{"tier_name":"Beer","price_pp_2hr":25,"extra_choice_price_pp":5},
        "hh_nonalc":{"tier_name":"Non-alcoholic","price_pp_2hr":20,"extra_choice_price_pp":5}
    },
    "late_night_open_bar": {
        "ln_house":{"tier_name":"House","price_pp_2hr":30,"ticket_price":10},
        "ln_call":{"tier_name":"Call","price_pp_2hr":40,"ticket_price":12},
        "ln_premium":{"tier_name":"Premium","price_pp_2hr":50,"ticket_price":15}
    },
    "food_extras_lookup": {
        "extra_starter":{"name":"Extra Starter","type":"starter"}
    }
}

SYSTEM_PROMPT = """You are Paul, the events manager at National Mechanics (Old City, Philadelphia).
Tone: professional, measured, clear. One idea per short paragraph. No exclamation points or emojis.
Clarify options; confirm math in plain language; invite questions; never oversell.

Always gather these before quoting:
- date, rough headcount, total on-site hours
- food choice (food package 1/2/3 OR a themed “food experience”)
- beverage choice (open bar tier & hours OR drink tickets OR happy hour window)

If any are missing, ask short follow-ups in Paul’s tone.
When enough info is present, call the tool `price_quote` with clean parameters.
Return a short, readable summary: per-person items, itemized totals, and a closing line:
“Pricing is before tax and 20% gratuity. Food taxed at 8%; beer/wine/liquor at 10%.”
Default close: “Let me know if you have any questions.”
"""

TOOLS = [{
    "type": "function",
    "function": {
        "name": "price_quote",
        "description": "Compute itemized quote for event packages.",
        "parameters": {
            "type": "object",
            "properties": {
                "event_date": {"type":"string"},
                "day_type": {"type":"string","enum":["weekday","weekend"]},
                "start_time": {"type":"string"},
                "duration_minutes": {"type":"integer","minimum":60},
                "guests": {"type":"integer","minimum":1},
                "room": {"type":"string"},
                "package_type": {"type":"string","enum":["food_package","food_experience","a_la_carte"]},
                "food_package_id": {"type":"string"},
                "experience_id": {"type":"string"},
                "food_extras": {"type":"array","items":{"type":"string"}},
                "open_bar_tier_id": {"type":"string"},
                "open_bar_duration_minutes": {"type":"integer","minimum":0},
                "drink_tickets": {"type":"object","properties":{"tier_id":{"type":"string"},"tickets_per_guest":{"type":"integer","minimum":0}}},
                "happy_hour_tier_id":{"type":"string"},
                "happy_hour_food_choices":{"type":"array","items":{"type":"string"}},
                "happy_hour_extra_choices":{"type":"integer","minimum":0},
                "late_night_tier_id":{"type":"string"},
                "waive_private_rental":{"type":"boolean","default":False},
                "notes":{"type":"string"}
            },
            "required": ["event_date","day_type","duration_minutes","guests"]
        }
    }
}]

SESSIONS: Dict[str, List[Dict[str, Any]]] = {}

app = FastAPI()
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_credentials=True, allow_methods=["*"], allow_headers=["*"])

class ChatIn(BaseModel):
    session_id: str
    message: str

@app.get("/", response_class=HTMLResponse)
def root():
    html = Path("index.html")
    return html.read_text(encoding="utf-8") if html.exists() else "OK"

@app.post("/chat")
def chat(inp: ChatIn):
    sid = inp.session_id
    SESSIONS.setdefault(sid, [])
    history = SESSIONS[sid]

    msgs = [{"role":"system","content":SYSTEM_PROMPT}, *history, {"role":"user","content":inp.message}]

    resp = client.chat.completions.create(model=OPENAI_MODEL, messages=msgs, tools=TOOLS, tool_choice="auto", temperature=0.2)
    msg = resp.choices[0].message

    if msg.tool_calls:
        call = msg.tool_calls[0]
        args = json.loads(call.function.arguments or "{}")
        if "day_type" not in args and "event_date" in args:
            dt = datetime.fromisoformat(args["event_date"])
            args["day_type"] = "weekend" if dt.weekday() >= 5 else "weekday"
        quote = price_quote(args, DATA, POLICIES)
        msgs.append({"role":"assistant","tool_calls":[{"id":call.id,"type":"function","function":{"name":call.function.name,"arguments":json.dumps(args)}}]})
        msgs.append({"role":"tool","tool_call_id":call.id,"name":call.function.name,"content":json.dumps(quote)})
        resp2 = client.chat.completions.create(model=OPENAI_MODEL, messages=msgs, temperature=0.2)
        out = resp2.choices[0].message.content
        history.append({"role":"user","content":inp.message})
        history.append({"role":"assistant","content":out})
        return {"reply": out, "quote": quote}

    out = msg.content
    history.append({"role":"user","content":inp.message})
    history.append({"role":"assistant","content":out})
    return {"reply": out}
