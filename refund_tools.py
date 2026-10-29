from pathlib import Path
from datetime import datetime, timezone
import json
import sqlite3

from policy_retrieval import PolicyRetriever


# ==================================================
# PROJECT PATHS
# ==================================================
ROOT = Path(__file__).resolve().parent
DB_FILE = ROOT / "data" / "instamart.db"
LEDGER_FILE = ROOT / "outputs" / "refund_ledger.jsonl"

AUTO_REFUND_LIMIT = 1000.00
REFUND_ELIGIBLE_AFTER_MINUTES = 45

# Reuse the Task 2 policy retriever.
_policy_retriever = PolicyRetriever()


# ==================================================
# TOOL 1: GET ORDER DETAILS
# ==================================================
def get_order(order_id):
    """Return order details from SQLite or an error."""

    if not DB_FILE.exists():
        return {"error": "order not found"}

    try:
        with sqlite3.connect(DB_FILE) as conn:
            conn.row_factory = sqlite3.Row

            tables = conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()

            for table_row in tables:
                table_name = table_row["name"]

                columns = conn.execute(
                    f'PRAGMA table_info("{table_name}")'
                ).fetchall()

                column_map = {
                    col["name"].lower(): col["name"]
                    for col in columns
                }

                required = {
                    "order_id",
                    "status",
                    "order_amount",
                    "delivery_minutes",
                }

                if not required.issubset(column_map):
                    continue

                quoted_table = (
                    '"' + table_name.replace('"', '""') + '"'
                )
                quoted_order_id = (
                    '"'
                    + column_map["order_id"].replace('"', '""')
                    + '"'
                )

                row = conn.execute(
                    f"SELECT * FROM {quoted_table} "
                    f"WHERE {quoted_order_id} = ? LIMIT 1",
                    (str(order_id),),
                ).fetchone()

                if row is not None:
                    return {
                        "order_id": str(row[column_map["order_id"]]),
                        "status": row[column_map["status"]],
                        "order_amount": row[column_map["order_amount"]],
                        "delivery_minutes": row[
                            column_map["delivery_minutes"]
                        ],
                    }

    except sqlite3.Error:
        return {"error": "order not found"}

    return {"error": "order not found"}


# ==================================================
# TOOL 2: SEARCH POLICY DOCUMENTS
# ==================================================
def search_policy(query):
    """Retrieve the three most relevant policy chunks."""

    return {
        "results": _policy_retriever.retrieve(query, k=3)
    }


# ==================================================
# TOOL 3: CALCULATE REFUND
# ==================================================
def calculate_refund(order_amount, delivery_minutes):
    """
    More than 45 minutes: full refund.
    45 minutes or less: no refund.
    """

    try:
        amount = float(order_amount)
        minutes = float(delivery_minutes)
    except (TypeError, ValueError):
        return {
            "error": "invalid order amount or delivery time"
        }

    if amount < 0 or minutes < 0:
        return {
            "error": "order amount and delivery time must be non-negative"
        }

    refund = amount if minutes > REFUND_ELIGIBLE_AFTER_MINUTES else 0.0

    return {"refund_inr": round(refund, 2)}


# ==================================================
# SHARED VALIDATION
# ==================================================
def _validate_eligible_order(order_id):
    """
    Check that an order exists, is completed, and qualifies
    for a delivery-delay refund.
    """

    order = get_order(order_id)

    if "error" in order:
        return {"error": "order not found"}

    if str(order["status"]).strip().lower() != "completed":
        return {
            "error": (
                f"Order is {order['status']}; "
                "refund actions are not allowed."
            )
        }

    try:
        amount = float(order["order_amount"])
        minutes = float(order["delivery_minutes"])
    except (TypeError, ValueError):
        return {"error": "invalid order amount or delivery time"}

    if amount < 0 or minutes < 0:
        return {"error": "invalid order amount or delivery time"}

    if minutes <= REFUND_ELIGIBLE_AFTER_MINUTES:
        return {
            "error": "delivery time does not qualify for a refund"
        }

    return {
        "order": order,
        "order_amount": round(amount, 2),
        "delivery_minutes": minutes,
    }


def _validate_full_refund_amount(order_id, refund_inr):
    """Require the refund to equal the full eligible order amount."""

    try:
        refund = float(refund_inr)
    except (TypeError, ValueError):
        return {"error": "invalid refund amount"}

    if refund <= 0:
        return {"error": "refund amount must be greater than zero"}

    eligible = _validate_eligible_order(order_id)

    if "error" in eligible:
        return eligible

    expected_amount = eligible["order_amount"]

    if round(refund, 2) != expected_amount:
        return {
            "error": (
                "refund must equal the full eligible order amount "
                f"(₹{expected_amount:.2f})"
            )
        }

    return {
        "refund_inr": round(refund, 2),
        "order": eligible["order"],
    }


# ==================================================
# LEDGER HELPER
# ==================================================
def _append_ledger(tool_name, order_id, refund_inr):
    """
    Append a simulated action as one JSON object per line.
    No real payment or refund is processed.
    """

    LEDGER_FILE.parent.mkdir(parents=True, exist_ok=True)

    record = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "tool_name": tool_name,
        "order_id": str(order_id),
        "refund_inr": round(float(refund_inr), 2),
    }

    with open(LEDGER_FILE, "a", encoding="utf-8") as file:
        file.write(json.dumps(record) + "\n")

    return {
        "success": True,
        "simulated": True,
        "tool_name": tool_name,
        "order_id": str(order_id),
        "refund_inr": record["refund_inr"],
        "ledger_file": str(LEDGER_FILE),
    }


# ==================================================
# TOOL 4: ISSUE REFUND
# ==================================================
def issue_refund(order_id, refund_inr):
    """
    Record a simulated refund only when:
    - the order is completed;
    - delivery took more than 45 minutes;
    - the amount equals the full order amount;
    - the amount is no more than ₹1,000.
    """

    validated = _validate_full_refund_amount(
        order_id, refund_inr
    )

    if "error" in validated:
        return validated

    amount = validated["refund_inr"]

    if amount > AUTO_REFUND_LIMIT:
        return {
            "error": (
                "refund exceeds ₹1,000; "
                "escalate to human review instead"
            )
        }

    return _append_ledger("issue_refund", order_id, amount)


# ==================================================
# TOOL 5: ESCALATE TO HUMAN
# ==================================================
def escalate_to_human(order_id, refund_inr):
    """
    Record a simulated human-review escalation for an
    eligible full refund above ₹1,000.
    """

    validated = _validate_full_refund_amount(
        order_id, refund_inr
    )

    if "error" in validated:
        return validated

    amount = validated["refund_inr"]

    if amount <= AUTO_REFUND_LIMIT:
        return {
            "error": (
                "human escalation is required only for "
                "refunds above ₹1,000"
            )
        }

    return _append_ledger(
        "escalate_to_human",
        order_id,
        amount,
    )


# ==================================================
# AGENT WORKFLOW
# ==================================================
def process_refund_request(order_id):
    """
    Apply the refund rules in the correct order.

    1. Look up the order.
    2. Reject missing or non-completed orders.
    3. Calculate refund eligibility.
    4. Escalate amounts above ₹1,000.
    5. Otherwise record the simulated refund.
    """

    order = get_order(order_id)

    if "error" in order:
        return {
            "status": "rejected",
            "message": "Order not found. No refund issued.",
        }

    if str(order["status"]).strip().lower() != "completed":
        return {
            "status": "rejected",
            "message": (
                f"Order status is {order['status']}. "
                "Only completed orders can receive a refund."
            ),
        }

    calculation = calculate_refund(
        order["order_amount"],
        order["delivery_minutes"],
    )

    if "error" in calculation:
        return {
            "status": "rejected",
            "message": calculation["error"],
        }

    amount = calculation["refund_inr"]

    if amount == 0:
        return {
            "status": "not_eligible",
            "refund_inr": 0.0,
            "message": (
                "Delivery took 45 minutes or less. "
                "No refund is due."
            ),
        }

    if amount > AUTO_REFUND_LIMIT:
        result = escalate_to_human(order_id, amount)

        if "error" in result:
            return {
                "status": "error",
                "message": result["error"],
            }

        return {
            "status": "escalated",
            "refund_inr": amount,
            "message": (
                "Refund exceeds ₹1,000. "
                "Escalated for human review; no refund issued."
            ),
            "ledger": result,
        }

    result = issue_refund(order_id, amount)

    if "error" in result:
        return {
            "status": "error",
            "message": result["error"],
        }

    return {
        "status": "simulated_refund_recorded",
        "refund_inr": amount,
        "message": (
            f"Simulated refund of ₹{amount:.2f} recorded."
        ),
        "ledger": result,
    }


# ==================================================
# TOOL SPECIFICATIONS
# ==================================================
TOOLS_SPEC = [
    {
        "name": "get_order",
        "description": (
            "Read an order's status, amount, and delivery time "
            "from the database."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"}
            },
            "required": ["order_id"],
        },
    },
    {
        "name": "search_policy",
        "description": (
            "Retrieve the three most relevant policy chunks."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {"type": "string"}
            },
            "required": ["query"],
        },
    },
    {
        "name": "calculate_refund",
        "description": (
            "Calculate the full refund for a delivery taking "
            "more than 45 minutes; otherwise return zero."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_amount": {"type": "number"},
                "delivery_minutes": {"type": "number"},
            },
            "required": ["order_amount", "delivery_minutes"],
        },
    },
    {
        "name": "issue_refund",
        "description": (
            "Record a simulated full refund for an eligible "
            "completed order when the amount is at most ₹1,000."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "refund_inr": {"type": "number"},
            },
            "required": ["order_id", "refund_inr"],
        },
    },
    {
        "name": "escalate_to_human",
        "description": (
            "Record a human-review escalation for an eligible "
            "completed order when the refund exceeds ₹1,000."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "order_id": {"type": "string"},
                "refund_inr": {"type": "number"},
            },
            "required": ["order_id", "refund_inr"],
        },
    },
]


# Map tool names to Python functions.
TOOL_MAP = {
    "get_order": get_order,
    "search_policy": search_policy,
    "calculate_refund": calculate_refund,
    "issue_refund": issue_refund,
    "escalate_to_human": escalate_to_human,
}


# ==================================================
# GENERIC TOOL DISPATCHER
# ==================================================
def call_tool(name, arguments):
    """Call a registered tool using its name and arguments."""

    function = TOOL_MAP.get(name)

    if function is None:
        return {"error": f"unknown tool: {name}"}

    if not isinstance(arguments, dict):
        return {"error": "arguments must be a dictionary"}

    try:
        return function(**arguments)
    except TypeError as exc:
        return {"error": f"invalid arguments for {name}: {exc}"}


# ==================================================
# BASIC TESTS
# ==================================================
if __name__ == "__main__":
    print("Available tools:")
    for tool in TOOLS_SPEC:
        print("-", tool["name"], ":", tool["description"])

    print("\nTest 1: Refund calculation")
    print("60 minutes:", calculate_refund(500, 60))
    # Expected: {'refund_inr': 500.0}

    print("Exactly 45 minutes:", calculate_refund(500, 45))
    # Expected: {'refund_inr': 0.0}

    print("\nTest 2: Order lookup")
    print(get_order("ORD-100001"))

    print("\nTest 3: Cancelled order ORD-100020")
    cancelled_order = get_order("ORD-100020")
    print("Order details:", cancelled_order)

    if "error" not in cancelled_order:
        if str(cancelled_order["status"]).strip().lower() != "completed":
            print("Agent result:", process_refund_request("ORD-100020"))
        else:
            print(
                "ORD-100020 is completed in the database; "
                "choose a confirmed cancelled order to test this rule."
            )

    print("\nTest 4: Full agent workflow")
    # Replace this ID with a confirmed completed order that took
    # more than 45 minutes. The workflow checks the amount and status.
    test_order_id = "ORD-100001"
    print(process_refund_request(test_order_id))

    print("\nTest 5: Direct attempt to issue more than ₹1,000")
    print(
        issue_refund(
            order_id="ORD-100001",
            refund_inr=1500,
        )
    )
    # Expected: an error; no refund issuance entry is appended.

    print("\nTest 6: Ledger verification")
    print("Ledger path:", LEDGER_FILE)
    print("Ledger exists:", LEDGER_FILE.exists())

    if LEDGER_FILE.exists():
        with open(LEDGER_FILE, "r", encoding="utf-8") as file:
            records = [
                line.strip()
                for line in file
                if line.strip()
            ]

        print("Total ledger records:", len(records))

        for line in records[-5:]:
            try:
                print(json.loads(line))
            except json.JSONDecodeError:
                print("Warning: invalid JSONL record:", line)
    
    print("\nTEST 4: Find eligible completed orders")

    with sqlite3.connect(DB_FILE) as conn:
        eligible_orders = conn.execute("""
            SELECT order_id, status, order_amount, delivery_minutes
            FROM orders
            WHERE LOWER(status) = 'completed'
              AND delivery_minutes > 45
            LIMIT 10
        """).fetchall()

    for item in eligible_orders:
        print(item)

    if not eligible_orders:
        print("No eligible completed orders found.")

    print("\nTEST 5: Test the agent workflow")

    if eligible_orders:
        # Use an actual eligible order from the database.
        test_id, status, amount, minutes = eligible_orders[0]

        print("Testing order:", test_id)
        print("Amount:", amount)
        print("Delivery minutes:", minutes)

        result = process_refund_request(test_id)
        print("Agent result:", result)

        if float(amount) > 1000:
            assert result["status"] == "escalated", (
                "Expected human escalation for refund above ₹1,000"
            )
            print("PASS: Large refund escalated.")
        else:
            assert result["status"] == "simulated_refund_recorded", (
                "Expected simulated refund for eligible order up to ₹1,000"
            )
            print("PASS: Eligible refund recorded.")

    print("\nTEST 6: Check cancelled-order protection")

    cancelled_result = process_refund_request("ORD-100020")
    print(cancelled_result)

    assert cancelled_result["status"] == "rejected"
    print("PASS: Cancelled order rejected.")

    print("\nTEST 7: Check ledger")

    print("Ledger path:", LEDGER_FILE)
    print("Ledger exists:", LEDGER_FILE.exists())

    if LEDGER_FILE.exists():
        with open(LEDGER_FILE, "r", encoding="utf-8") as file:
            for line in file:
                if line.strip():
                    print(json.loads(line))
    else:
        print("No action has been recorded yet.")
