"""
Tools exposed to the LLM + their server-side executors.

SECURITY: identity is never trusted to the model. Tools that read or modify a
patient's appointments take NO phone argument in their schema - the executor
injects the phone from the conversation state. The model literally cannot ask
for another phone number's data because the parameter does not exist. Likewise
book_appointment takes no name/phone; both come from state.

`provide_identity` is how the model records the name + phone it collected
conversationally (or that the web client supplied at init).
"""
from datetime import date, datetime, time
from typing import Any, Awaitable, Callable, Dict

import google.generativeai as genai

from app.clinic_api import ClinicApiClient, ClinicApiError
from app.state import ConversationState

# --------------------------------------------------------------------------
# Function declarations (the schema the model sees)
# --------------------------------------------------------------------------
_S = genai.protos.Schema
_T = genai.protos.Type


def _obj(props: Dict[str, Any], required: list[str] | None = None) -> genai.protos.Schema:
    return _S(type=_T.OBJECT, properties=props, required=required or [])


FUNCTION_DECLARATIONS = [
    genai.protos.FunctionDeclaration(
        name="provide_identity",
        description=(
            "Record the patient's full name and phone number once you have collected "
            "them. Call this before booking, listing, cancelling or rescheduling if the "
            "patient's identity is not already known."
        ),
        parameters=_obj(
            {
                "full_name": _S(type=_T.STRING, description="Patient full name"),
                "phone": _S(type=_T.STRING, description="Patient phone number, digits and optional +"),
            },
            required=["full_name", "phone"],
        ),
    ),
    genai.protos.FunctionDeclaration(
        name="list_departments",
        description="List the clinic's medical departments.",
        parameters=_obj({}),
    ),
    genai.protos.FunctionDeclaration(
        name="list_doctors",
        description="List doctors, optionally filtered by department_id.",
        parameters=_obj(
            {"department_id": _S(type=_T.INTEGER, description="Optional department id to filter by")}
        ),
    ),
    genai.protos.FunctionDeclaration(
        name="get_available_slots",
        description="Get available appointment start times for a doctor on a date (YYYY-MM-DD).",
        parameters=_obj(
            {
                "doctor_id": _S(type=_T.INTEGER),
                "date": _S(type=_T.STRING, description="Date in YYYY-MM-DD format"),
            },
            required=["doctor_id", "date"],
        ),
    ),
    genai.protos.FunctionDeclaration(
        name="book_appointment",
        description=(
            "Book an appointment for the identified patient. Requires identity to be "
            "recorded first. Use a start_time returned by get_available_slots."
        ),
        parameters=_obj(
            {
                "doctor_id": _S(type=_T.INTEGER),
                "department_id": _S(type=_T.INTEGER),
                "date": _S(type=_T.STRING, description="Date in YYYY-MM-DD format"),
                "start_time": _S(type=_T.STRING, description="Start time in HH:MM (24h)"),
                "notes": _S(type=_T.STRING, description="Optional short note"),
            },
            required=["doctor_id", "department_id", "date", "start_time"],
        ),
    ),
    genai.protos.FunctionDeclaration(
        name="list_my_appointments",
        description="List the identified patient's own appointments. Requires identity.",
        parameters=_obj({}),
    ),
    genai.protos.FunctionDeclaration(
        name="cancel_appointment",
        description="Cancel one of the identified patient's appointments by its id. Requires identity.",
        parameters=_obj({"appointment_id": _S(type=_T.INTEGER)}, required=["appointment_id"]),
    ),
    genai.protos.FunctionDeclaration(
        name="reschedule_appointment",
        description="Move one of the identified patient's appointments to a new date/time. Requires identity.",
        parameters=_obj(
            {
                "appointment_id": _S(type=_T.INTEGER),
                "date": _S(type=_T.STRING, description="New date in YYYY-MM-DD format"),
                "start_time": _S(type=_T.STRING, description="New start time in HH:MM (24h)"),
            },
            required=["appointment_id", "date", "start_time"],
        ),
    ),
]

GEMINI_TOOLS = genai.protos.Tool(function_declarations=FUNCTION_DECLARATIONS)


# --------------------------------------------------------------------------
# Executors - each returns a JSON-serializable dict sent back to the model
# --------------------------------------------------------------------------
def _parse_date(s: str) -> date:
    return datetime.strptime(s.strip(), "%Y-%m-%d").date()


def _parse_time(s: str) -> time:
    s = s.strip()
    for fmt in ("%H:%M:%S", "%H:%M"):
        try:
            return datetime.strptime(s, fmt).time()
        except ValueError:
            continue
    raise ValueError("time must be HH:MM")


def _need_identity(state: ConversationState) -> dict | None:
    if not state.has_identity:
        return {"error": "identity_required", "message": "Ask the patient for their full name and phone number first, then call provide_identity."}
    return None


async def _provide_identity(client, state, args) -> dict:
    name = str(args.get("full_name", "")).strip()
    phone = str(args.get("phone", "")).strip()
    if len(name) < 2 or len(phone) < 5:
        return {"error": "invalid_identity", "message": "Need a valid full name and phone number."}
    state.patient_name = name
    state.patient_phone = phone
    return {"ok": True, "message": "Identity recorded."}


async def _list_departments(client: ClinicApiClient, state, args) -> dict:
    return {"departments": await client.list_departments()}


async def _list_doctors(client: ClinicApiClient, state, args) -> dict:
    dept = args.get("department_id")
    return {"doctors": await client.list_doctors(int(dept) if dept is not None else None)}


async def _get_available_slots(client: ClinicApiClient, state, args) -> dict:
    slots = await client.get_available_slots(int(args["doctor_id"]), _parse_date(args["date"]))
    available = [s for s in slots if s.get("is_available")]
    return {"available_slots": available, "count": len(available)}


async def _book_appointment(client: ClinicApiClient, state, args) -> dict:
    guard = _need_identity(state)
    if guard:
        return guard
    appt = await client.book_appointment(
        doctor_id=int(args["doctor_id"]),
        department_id=int(args["department_id"]),
        appointment_date=_parse_date(args["date"]),
        start_time=_parse_time(args["start_time"]),
        patient_full_name=state.patient_name,   # from state, never the model
        patient_phone=state.patient_phone,       # from state, never the model
        notes=(str(args["notes"]) if args.get("notes") else None),
    )
    return {"booked": True, "appointment": appt}


async def _list_my_appointments(client: ClinicApiClient, state, args) -> dict:
    guard = _need_identity(state)
    if guard:
        return guard
    appts = await client.list_appointments(state.patient_phone)  # phone from state
    return {"appointments": appts, "count": len(appts)}


async def _cancel_appointment(client: ClinicApiClient, state, args) -> dict:
    guard = _need_identity(state)
    if guard:
        return guard
    appt = await client.cancel_appointment(int(args["appointment_id"]), state.patient_phone)
    return {"cancelled": True, "appointment": appt}


async def _reschedule_appointment(client: ClinicApiClient, state, args) -> dict:
    guard = _need_identity(state)
    if guard:
        return guard
    appt = await client.reschedule_appointment(
        int(args["appointment_id"]),
        state.patient_phone,  # phone from state
        _parse_date(args["date"]),
        _parse_time(args["start_time"]),
    )
    return {"rescheduled": True, "appointment": appt}


Executor = Callable[[ClinicApiClient, ConversationState, dict], Awaitable[dict]]

EXECUTORS: Dict[str, Executor] = {
    "provide_identity": _provide_identity,
    "list_departments": _list_departments,
    "list_doctors": _list_doctors,
    "get_available_slots": _get_available_slots,
    "book_appointment": _book_appointment,
    "list_my_appointments": _list_my_appointments,
    "cancel_appointment": _cancel_appointment,
    "reschedule_appointment": _reschedule_appointment,
}


async def execute_tool(name: str, args: dict, client: ClinicApiClient, state: ConversationState) -> dict:
    executor = EXECUTORS.get(name)
    if executor is None:
        return {"error": "unknown_tool", "message": f"No such tool: {name}"}
    try:
        return await executor(client, state, args)
    except ClinicApiError as exc:
        # Surface the backend's own validation message (safe, tenant-scoped).
        return {"error": "api_error", "status": exc.status_code, "message": exc.detail}
    except (ValueError, KeyError) as exc:
        return {"error": "bad_arguments", "message": str(exc)}
