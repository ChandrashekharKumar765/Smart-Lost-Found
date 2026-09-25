import os
import sqlite3
import uuid
from datetime import date
import streamlit as st

from database import (
    create_database,
    add_item,
    get_items,
    get_all_items,
    update_item_status
)

from auth import show_auth

from matching import (
    calculate_similarity,
    get_match_label
)


# =========================================================
# DATABASE SETUP
# =========================================================

create_database()

os.makedirs("uploads", exist_ok=True)


# =========================================================
# IMAGE UPLOAD HELPER
# =========================================================

def save_uploaded_image(uploaded_file):
    """Save an uploaded image with a unique filename."""

    if uploaded_file is None:
        return ""

    original_name = uploaded_file.name
    base_name, extension = os.path.splitext(original_name)

    safe_base_name = "".join(
        character
        if character.isalnum() or character in "-_"
        else "_"
        for character in base_name
    ).strip("_")

    if not safe_base_name:
        safe_base_name = "item_image"

    unique_name = (
        f"{safe_base_name}_{uuid.uuid4().hex[:10]}{extension.lower()}"
    )

    image_path = os.path.join(
        "uploads",
        unique_name
    )

    with open(
        image_path,
        "wb"
    ) as file:

        file.write(
            uploaded_file.getbuffer()
        )

    return unique_name


def init_message_database():
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            receiver_id INTEGER NOT NULL,
            item_id INTEGER NOT NULL,
            message TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
            is_read INTEGER NOT NULL DEFAULT 0
        )
        """
    )
    conn.commit()
    conn.close()


def init_resolution_database():
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        CREATE TABLE IF NOT EXISTS resolution_requests (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            requester_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'Pending',
            created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
        )
        """
    )
    conn.commit()
    conn.close()


def get_resolution_request(item_id):
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT id, item_id, requester_id, status, created_at
        FROM resolution_requests
        WHERE item_id = ? AND status = 'Pending'
        ORDER BY id DESC
        LIMIT 1
        """,
        (item_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result


def can_request_resolution(item_id, user_id):
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()

    cursor.execute(
        "SELECT user_id FROM items WHERE id = ?",
        (item_id,)
    )
    item = cursor.fetchone()

    if not item:
        conn.close()
        return False

    owner_id = item[0]
    if owner_id == user_id:
        conn.close()
        return True

    cursor.execute(
        """
        SELECT 1
        FROM messages
        WHERE item_id = ?
          AND (sender_id = ? OR receiver_id = ?)
        LIMIT 1
        """,
        (item_id, user_id, user_id)
    )
    contacted = cursor.fetchone() is not None
    conn.close()
    return contacted


def request_resolution(item_id, requester_id):
    if get_resolution_request(item_id):
        return False

    if not can_request_resolution(item_id, requester_id):
        return False

    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO resolution_requests (item_id, requester_id, status)
        VALUES (?, ?, 'Pending')
        """,
        (item_id, requester_id)
    )
    conn.commit()
    conn.close()
    return True


def get_pending_resolution_requests():
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            rr.id,
            rr.item_id,
            rr.requester_id,
            requester.name,
            items.item_name,
            items.item_type,
            items.user_id,
            owner.name,
            rr.status,
            rr.created_at
        FROM resolution_requests AS rr
        JOIN items ON rr.item_id = items.id
        JOIN users AS requester ON rr.requester_id = requester.id
        JOIN users AS owner ON items.user_id = owner.id
        WHERE rr.status = 'Pending'
        ORDER BY rr.id DESC
        """
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def update_resolution_request(request_id, status):
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE resolution_requests SET status = ? WHERE id = ?",
        (status, request_id)
    )
    conn.commit()
    conn.close()


def resolve_case(request_id, item_id):
    update_item_status(item_id, "Resolved")
    update_resolution_request(request_id, "Closed")


def keep_case_active(request_id):
    update_resolution_request(request_id, "Kept Active")


def get_item_contact(item_id):
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT items.user_id, users.name, items.item_name, items.item_type
        FROM items
        JOIN users ON items.user_id = users.id
        WHERE items.id = ?
        """,
        (item_id,)
    )
    result = cursor.fetchone()
    conn.close()
    return result


def send_direct_message(sender_id, receiver_id, item_id, message):
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO messages (sender_id, receiver_id, item_id, message)
        VALUES (?, ?, ?, ?)
        """,
        (sender_id, receiver_id, item_id, message.strip())
    )
    conn.commit()
    conn.close()


def get_user_messages(user_id):
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute(
        """
        SELECT
            messages.id,
            messages.sender_id,
            sender.name,
            messages.receiver_id,
            receiver.name,
            messages.item_id,
            items.item_name,
            items.item_type,
            messages.message,
            messages.created_at,
            messages.is_read
        FROM messages
        JOIN users AS sender ON messages.sender_id = sender.id
        JOIN users AS receiver ON messages.receiver_id = receiver.id
        JOIN items ON messages.item_id = items.id
        WHERE messages.sender_id = ? OR messages.receiver_id = ?
        ORDER BY messages.id DESC
        """,
        (user_id, user_id)
    )
    rows = cursor.fetchall()
    conn.close()
    return rows


def mark_messages_read(user_id):
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE messages SET is_read = 1 WHERE receiver_id = ?",
        (user_id,)
    )
    conn.commit()
    conn.close()


def get_unread_message_count(user_id):
    conn = sqlite3.connect("lost_found.db")
    cursor = conn.cursor()
    cursor.execute(
        "SELECT COUNT(*) FROM messages WHERE receiver_id = ? AND is_read = 0",
        (user_id,)
    )
    count = cursor.fetchone()[0]
    conn.close()
    return count


def open_contact(item_id):
    contact = get_item_contact(item_id)
    if not contact:
        st.error("The person who reported this item could not be found.")
        return

    owner_id, owner_name, item_name, item_type = contact
    current_user_id = st.session_state.get("user_id")

    if owner_id == current_user_id:
        st.info("This is your own report.")
        return

    st.session_state["contact_item_id"] = item_id
    st.session_state["contact_person_name"] = owner_name
    st.session_state["contact_item_name"] = item_name
    st.rerun()


def show_contact_composer():
    item_id = st.session_state.get("contact_item_id")
    if not item_id:
        return

    contact = get_item_contact(item_id)
    if not contact:
        st.session_state.pop("contact_item_id", None)
        st.session_state.pop("contact_receiver_id", None)
        return

    owner_id, owner_name, item_name, item_type = contact
    current_user_id = st.session_state.get("user_id")

    # Normal contact: send to the reporter of the item.
    # Reply: send back to the original message sender.
    receiver_id = st.session_state.get("contact_receiver_id", owner_id)
    receiver_name = owner_name

    if receiver_id == current_user_id:
        st.session_state.pop("contact_item_id", None)
        st.session_state.pop("contact_receiver_id", None)
        return

    if st.session_state.get("reply_message_id"):
        heading = f"↩️ Reply to {receiver_name} — {item_name}"
        help_text = "Your reply will be sent privately to the person who contacted you."
        default_message = ""
    elif item_type == "Found":
        heading = f"📩 Contact Finder — {item_name}"
        help_text = (
            f"Send a private message to {receiver_name}. "
            "Do not share sensitive information unless needed for verification."
        )
        default_message = (
            f"Hi {receiver_name}, I think the found item '{item_name}' may be mine. "
            "I can provide identifying details to verify ownership."
        )
    else:
        heading = f"📩 Contact Owner — {item_name}"
        help_text = (
            f"Send a private message to {receiver_name}. "
            "The finder can ask for identifying details before returning the item."
        )
        default_message = (
            f"Hi {receiver_name}, I found an item matching your lost report '{item_name}'. "
            "Please share a few details so we can verify ownership and arrange its return."
        )

    st.markdown("---")
    st.subheader(heading)
    st.caption(help_text)

    message = st.text_area(
        "Message",
        value=default_message,
        key=f"contact_message_{item_id}_{receiver_id}",
        height=130
    )

    col1, col2 = st.columns(2)
    with col1:
        if st.button(
            "📤 Send Message",
            key=f"send_message_{item_id}_{receiver_id}",
            use_container_width=True
        ):
            if not message.strip():
                st.warning("Please write a message first.")
            else:
                send_direct_message(
                    current_user_id,
                    receiver_id,
                    item_id,
                    message
                )
                for key in ["contact_item_id", "contact_receiver_id", "reply_message_id"]:
                    st.session_state.pop(key, None)
                st.success(f"Message sent to {receiver_name} successfully!")
                st.rerun()

    with col2:
        if st.button(
            "✕ Cancel",
            key=f"cancel_message_{item_id}_{receiver_id}",
            use_container_width=True
        ):
            for key in ["contact_item_id", "contact_receiver_id", "reply_message_id"]:
                st.session_state.pop(key, None)
            st.rerun()


def show_messages_page():
    user_id = st.session_state.get("user_id")
    messages = get_user_messages(user_id)
    unread = get_unread_message_count(user_id)

    st.markdown(
        '<div class="lf-page-head"><div class="lf-kicker">Private communication</div>'
        '<div class="lf-page-title">Messages</div>'
        '<div class="lf-page-sub">Contact owners and finders directly inside the system.</div></div>',
        unsafe_allow_html=True
    )

    if unread:
        st.info(f"📬 You have {unread} unread message(s).")
        mark_messages_read(user_id)

    if not messages:
        st.info("No messages yet. Contact an owner or finder from a report to start a conversation.")
        return

    for msg in messages:
        (
            message_id,
            sender_id,
            sender_name,
            receiver_id,
            receiver_name,
            item_id,
            item_name,
            item_type,
            message_text,
            created_at,
            is_read
        ) = msg

        if sender_id == user_id:
            person = f"To: {receiver_name}"
            icon = "📤"
        else:
            person = f"From: {sender_name}"
            icon = "📥"

        st.markdown(
            f'<div class="lf-card"><div class="lf-card-title">{icon} {person}</div>'
            f'<div style="color:#64748b;font-size:.85rem;margin-bottom:8px;">'
            f'{item_type} • {item_name} • {created_at}</div>'
            f'<div style="color:#1e293b;line-height:1.6;">{message_text}</div></div>',
            unsafe_allow_html=True
        )

        if receiver_id == user_id:
            if st.button(
                "↩️ Reply",
                key=f"reply_{message_id}",
                use_container_width=False
            ):
                st.session_state["contact_item_id"] = item_id
                st.session_state["contact_receiver_id"] = sender_id
                st.session_state["reply_message_id"] = message_id
                st.session_state[f"contact_message_{item_id}_{sender_id}"] = ""
                st.rerun()


init_message_database()
init_resolution_database()


# =========================================================
# PAGE CONFIGURATION
# =========================================================

st.set_page_config(
    page_title="Smart Lost & Found",
    page_icon="🔎",
    layout="wide"
)


# =========================================================
# MODERN APP UI
# =========================================================

st.markdown("""
<style>
:root{
 --sidebar:#111827;
 --sidebar-2:#182235;
 --primary:#2563eb;
 --primary-dark:#1d4ed8;
 --ink:#14213d;
 --muted:#64748b;
 --line:#e5e7eb;
 --surface:#ffffff;
 --page:#f8fafc;
}

.stApp{background:var(--page)}
.block-container{max-width:1320px;padding:1.65rem 2.1rem 3rem}
[data-testid="stHeader"]{background:transparent!important}
[data-testid="stToolbar"]{background:transparent!important}

/* Sidebar */
section[data-testid="stSidebar"]{
 background:linear-gradient(180deg,var(--sidebar) 0%,#0f172a 100%)!important;
 border-right:1px solid #263244!important;
}
section[data-testid="stSidebar"]>div:first-child{padding:1.35rem 1rem}
section[data-testid="stSidebar"] p,
section[data-testid="stSidebar"] label,
section[data-testid="stSidebar"] span{color:#cbd5e1}
section[data-testid="stSidebar"] hr{border-color:#2b3648!important}
section[data-testid="stSidebar"] div[role="radiogroup"]{
 background:transparent!important;border:0!important;box-shadow:none!important;padding:0!important;gap:5px!important
}
section[data-testid="stSidebar"] div[role="radiogroup"]>label{
 margin:0!important;padding:11px 13px!important;border-radius:9px!important;
 background:transparent!important;color:#b9c4d4!important;font-size:.88rem!important;
 font-weight:600!important;transition:all .15s ease
}
section[data-testid="stSidebar"] div[role="radiogroup"]>label:hover{
 background:#1b2638!important;color:#fff!important
}
section[data-testid="stSidebar"] div[role="radiogroup"]>label:has(input:checked){
 background:#2563eb!important;color:#fff!important;box-shadow:0 5px 14px rgba(37,99,235,.20)
}
section[data-testid="stSidebar"] div[role="radiogroup"]>label p,
section[data-testid="stSidebar"] div[role="radiogroup"]>label span{color:inherit!important}

/* Keep sidebar navigation text clearly visible on the dark sidebar. */
section[data-testid="stSidebar"] div[role="radiogroup"]>label,
section[data-testid="stSidebar"] div[role="radiogroup"]>label * {
 color:#f8fafc !important;
 opacity:1 !important;
}
section[data-testid="stSidebar"] div[role="radiogroup"]>label>div:first-child{display:none!important}

/* Typography */
h1{color:var(--ink)!important;font-size:2.25rem!important;font-weight:800!important;letter-spacing:-.75px!important;margin-bottom:.25rem!important}
h2{color:var(--ink)!important;font-size:1.55rem!important;font-weight:780!important;letter-spacing:-.35px!important}
h3,h4{color:#1e293b!important;font-weight:750!important}
p{color:#53657d}

/* Sidebar brand */
.lf-brand{padding:8px 8px 18px}
.lf-brand-name{color:#f8fafc!important;font-size:1.18rem;font-weight:800;letter-spacing:-.2px}
.lf-brand-sub{color:#94a3b8!important;font-size:.76rem;margin-top:4px}
.lf-user{display:flex;align-items:center;gap:10px;padding:13px 8px;margin:10px 0 16px;border-top:1px solid #293548;border-bottom:1px solid #293548}
.lf-avatar{width:34px;height:34px;border-radius:50%;background:#e2e8f0;color:#334155!important;display:flex;align-items:center;justify-content:center;font-weight:800}
.lf-user-name{color:#f8fafc!important;font-weight:750}
.lf-user-role{color:#94a3b8!important;font-size:.72rem}

/* Page heading */
.lf-page-head{margin:2px 0 24px}
.lf-kicker{color:#2563eb!important;font-size:.69rem;font-weight:800;text-transform:uppercase;letter-spacing:1.25px;margin-bottom:7px}
.lf-page-title{color:var(--ink)!important;font-size:2.08rem;font-weight:800;letter-spacing:-.7px}
.lf-page-sub{color:#64748b!important;font-size:.94rem;margin-top:6px}

/* Hero - restrained, no flashy gradient */
.lf-hero{
 background:#14213d;border:1px solid #203352;border-radius:14px;
 padding:25px 28px;margin-bottom:22px;box-shadow:0 8px 24px rgba(15,23,42,.08)
}
.lf-hero-title{color:#fff!important;font-size:1.42rem;font-weight:800;letter-spacing:-.25px}
.lf-hero-text{color:#c4cfdd!important;font-size:.91rem;margin:6px 0 0}

/* Cards */
.lf-card{background:var(--surface);border:1px solid var(--line);border-radius:12px;padding:21px;box-shadow:0 2px 10px rgba(15,23,42,.035)}
div[data-testid="stMetric"]{background:#fff;border:1px solid var(--line);border-radius:12px;padding:17px 18px;box-shadow:0 2px 10px rgba(15,23,42,.035)}
div[data-testid="stMetricLabel"]{color:#64748b!important;font-size:.77rem!important;font-weight:650!important}
div[data-testid="stMetricValue"]{color:var(--ink)!important;font-weight:800!important}

/* Inputs */
div[data-baseweb="input"]>div,
div[data-baseweb="select"]>div,
div[data-baseweb="textarea"]{
 background:#fff!important;border:1px solid #cbd5e1!important;border-radius:8px!important;
 box-shadow:none!important;min-height:42px
}
div[data-baseweb="input"]>div:focus-within,
div[data-baseweb="select"]>div:focus-within,
div[data-baseweb="textarea"]:focus-within{
 border-color:#2563eb!important;box-shadow:0 0 0 3px rgba(37,99,235,.08)!important
}
input,textarea{color:#172033!important;background:#fff!important;-webkit-text-fill-color:#172033!important}
label{color:#334155!important;font-weight:650!important}

/* Date input - force ONLY the closed input box to light mode.
   The calendar popup is intentionally left unchanged. */
div[data-testid="stDateInput"]{
 background:#fff!important;
}
div[data-testid="stDateInput"] [data-baseweb="input"],
div[data-testid="stDateInput"] [data-baseweb="base-input"]{
 background:#fff!important;
 background-color:#fff!important;
 border:1px solid #cbd5e1!important;
 border-radius:8px!important;
 box-shadow:none!important;
 color:#172033!important;
}
div[data-testid="stDateInput"] [data-baseweb="input"] > div,
div[data-testid="stDateInput"] [data-baseweb="base-input"] > div{
 background:#fff!important;
 background-color:#fff!important;
}
div[data-testid="stDateInput"] [data-baseweb="input"] > div > div,
div[data-testid="stDateInput"] [data-baseweb="base-input"] > div > div{
 background:#fff!important;
 background-color:#fff!important;
}
div[data-testid="stDateInput"] input{
 background:#fff!important;
 background-color:#fff!important;
 color:#172033!important;
 -webkit-text-fill-color:#172033!important;
 color-scheme:light!important;
}
div[data-testid="stDateInput"] button{
 background:#fff!important;
 background-color:#fff!important;
 color:#172033!important;
}

/* Select popup */
div[data-baseweb="popover"],div[data-baseweb="menu"],ul[role="listbox"]{
 background:#fff!important;border:1px solid #dbe3ee!important;border-radius:9px!important;box-shadow:0 12px 30px rgba(15,23,42,.12)!important
}
div[data-baseweb="menu"] *,ul[role="listbox"] *,li[role="option"],div[role="option"]{color:#172033!important}
li[role="option"],div[role="option"]{background:#fff!important}
li[role="option"]:hover,div[role="option"]:hover{background:#eff6ff!important;color:#1d4ed8!important}
li[role="option"][aria-selected="true"],div[role="option"][aria-selected="true"]{background:#eaf2ff!important;color:#1d4ed8!important;font-weight:650!important}

/* Buttons */
.stButton>button{
 background:#2563eb!important;color:#fff!important;border:1px solid #2563eb!important;
 border-radius:8px!important;min-height:42px;font-weight:700!important;box-shadow:none!important;transition:.15s ease
}
.stButton>button:hover{background:#1d4ed8!important;border-color:#1d4ed8!important;transform:translateY(-1px);box-shadow:0 5px 12px rgba(37,99,235,.16)!important}
.stButton>button p,.stButton>button span{color:#fff!important}

/* Upload */
section[data-testid="stFileUploaderDropzone"]{
 background:#fbfdff!important;border:1px dashed #b8c4d4!important;border-radius:9px!important;padding:15px!important
}
section[data-testid="stFileUploaderDropzone"] button{
 background:#fff!important;color:#2563eb!important;border:1px solid #b8c4d4!important;border-radius:7px!important;font-weight:700!important
}
section[data-testid="stFileUploaderDropzone"] button *{color:#2563eb!important}
section[data-testid="stFileUploaderDropzone"] small,section[data-testid="stFileUploaderDropzone"] span{color:#64748b!important}

/* Expanders / separators */
details{background:#fff!important;border:1px solid var(--line)!important;border-radius:9px!important}
details summary,details summary span{color:#334155!important;font-weight:700!important}
hr{border-color:#e8edf4!important}

/* Alerts */
div[data-testid="stAlert"]{border-radius:9px!important;border-width:1px!important}

.lf-footer{text-align:center;color:#94a3b8!important;font-size:.74rem;padding:28px 0 4px}

/* =========================================================
   MOBILE SIDEBAR TOGGLE
   IMPORTANT: target ONLY Streamlit's sidebar controls.
   Do NOT style generic header buttons, because those are
   Streamlit's own developer/menu controls.
   ========================================================= */
@media (max-width: 768px) {
    [data-testid="stSidebarCollapseButton"],
    [data-testid="stSidebarCollapsedControl"] {
        display: flex !important;
        visibility: visible !important;
        opacity: 1 !important;
        pointer-events: auto !important;
        position: fixed !important;
        left: 8px !important;
        top: 8px !important;
        z-index: 999999 !important;
        width: 46px !important;
        height: 46px !important;
        min-width: 46px !important;
        min-height: 46px !important;
        align-items: center !important;
        justify-content: center !important;
        background: #2563eb !important;
        background-color: #2563eb !important;
        border: 2px solid #1d4ed8 !important;
        border-radius: 10px !important;
        box-shadow: 0 4px 14px rgba(15, 23, 42, .28) !important;
        color: #ffffff !important;
        fill: #ffffff !important;
        filter: none !important;
        mix-blend-mode: normal !important;
    }

    [data-testid="stSidebarCollapseButton"] *,
    [data-testid="stSidebarCollapsedControl"] * {
        color: #ffffff !important;
        fill: #ffffff !important;
        stroke: #ffffff !important;
        opacity: 1 !important;
        filter: none !important;
    }

    [data-testid="stSidebarCollapseButton"] button,
    [data-testid="stSidebarCollapsedControl"] button {
        width: 46px !important;
        height: 46px !important;
        min-width: 46px !important;
        min-height: 46px !important;
        background: #2563eb !important;
        background-color: #2563eb !important;
        color: #ffffff !important;
        border: 0 !important;
        box-shadow: none !important;
    }

    [data-testid="stSidebarCollapseButton"] svg,
    [data-testid="stSidebarCollapsedControl"] svg {
        width: 24px !important;
        height: 24px !important;
        color: #ffffff !important;
        fill: #ffffff !important;
        stroke: #ffffff !important;
        opacity: 1 !important;
    }
}

/* =========================================================
   DATE INPUT — CLOSED FIELD ONLY
   The calendar popup is intentionally untouched.
   ========================================================= */
div[data-testid="stDateInput"] {
    background: #ffffff !important;
    background-color: #ffffff !important;
}

div[data-testid="stDateInput"] [data-baseweb="input"],
div[data-testid="stDateInput"] [data-baseweb="base-input"],
div[data-testid="stDateInput"] [data-baseweb="input"] > div,
div[data-testid="stDateInput"] [data-baseweb="base-input"] > div,
div[data-testid="stDateInput"] [data-baseweb="input"] > div > div,
div[data-testid="stDateInput"] [data-baseweb="base-input"] > div > div {
    background: #ffffff !important;
    background-color: #ffffff !important;
    border-color: #cbd5e1 !important;
    box-shadow: none !important;
}

div[data-testid="stDateInput"] input {
    background: #ffffff !important;
    background-color: #ffffff !important;
    color: #172033 !important;
    -webkit-text-fill-color: #172033 !important;
    color-scheme: light !important;
}

div[data-testid="stDateInput"] button {
    background: #ffffff !important;
    background-color: #ffffff !important;
    color: #172033 !important;
}

</style>
""", unsafe_allow_html=True)


# =========================================================
# SESSION STATE
# =========================================================

if "logged_in" not in st.session_state:
    st.session_state["logged_in"] = False

if "contact_item_id" not in st.session_state:
    st.session_state["contact_item_id"] = None


# =========================================================
# LOGIN PAGE
# =========================================================

if not st.session_state["logged_in"]:

    show_auth()


# =========================================================
# MAIN APPLICATION
# =========================================================

else:

    user_name = st.session_state.get("user_name", "User")
    user_role = st.session_state.get("user_role", "user")

    # Normalize role
    user_role = str(user_role).strip().lower()


    # =====================================================
    # ADMIN APPLICATION
    # =====================================================

    if user_role == "admin":

        st.title("🛡️ Smart Lost & Found - Admin Panel")

        st.success(
            f"Welcome, {user_name}! 👋"
        )

        st.write(
            "Manage lost & found reports, resolution requests, "
            "and system activities."
        )

        st.divider()


        # =================================================
        # ADMIN MENU
        # =================================================

        # Live resolution-request count for the admin notification bell.
        pending_resolution_requests = get_pending_resolution_requests()
        pending_resolution_count = len(pending_resolution_requests)

        if "admin_navigation" not in st.session_state:
            st.session_state["admin_navigation"] = "🏠 Admin Dashboard"

        st.sidebar.markdown(
            '<div style="font-size:1.35rem;font-weight:800;">🛡️ Admin Panel</div>',
            unsafe_allow_html=True
        )
        st.sidebar.caption("Smart Lost & Found")

        st.sidebar.markdown(
            f'''<div style="margin:8px 0 14px;padding:10px 12px;border-radius:12px;
                        background:rgba(37,99,235,.12);border:1px solid rgba(96,165,250,.22);
                        color:#dbeafe;font-size:.86rem;font-weight:700;">
                🔔 {pending_resolution_count} Pending Resolution Request(s)
            </div>''',
            unsafe_allow_html=True
        )

        st.sidebar.markdown('<div style="font-size:.67rem;text-transform:uppercase;letter-spacing:1px;font-weight:800;color:#7f93af!important;margin:4px 8px 7px;">Navigation</div>', unsafe_allow_html=True)
        admin_option = st.sidebar.radio(
            "",
            [
                "🏠 Admin Dashboard",
                "📦 Manage Items",
                "🔔 Resolution Requests"
            ],
            key="admin_navigation"
        )

        # Notification bell stays visible at the top of every admin page.
        top_col1, top_col2 = st.columns([7, 1])
        with top_col2:
            bell_label = f"🔔 {pending_resolution_count}" if pending_resolution_count else "🔔"
            if st.button(
                bell_label,
                key="admin_notification_bell",
                use_container_width=True,
                help="Open pending resolution requests"
            ):
                st.session_state["admin_navigation"] = "🔔 Resolution Requests"
                st.rerun()


        # =================================================
        # ADMIN DASHBOARD
        # =================================================

        if admin_option == "🏠 Admin Dashboard":

            st.markdown("""
            <div class="lf-hero">
                <div class="lf-hero-title">Campus Recovery Control Center 🛡️</div>
                <p class="lf-hero-text">
                    Monitor reports, review claims, and manage the Lost & Found system.
                </p>
            </div>
            """, unsafe_allow_html=True)

            st.header("🏠 Admin Dashboard")

            all_items = get_all_items()
            pending_resolution_requests = get_pending_resolution_requests()


            lost_count = sum(
                1 for item in all_items
                if item[1] == "Lost"
            )

            found_count = sum(
                1 for item in all_items
                if item[1] == "Found"
            )

            active_count = sum(
                1 for item in all_items
                if item[8] == "Active"
            )

            resolved_count = sum(
                1 for item in all_items
                if item[8] == "Resolved"
            )

            # =============================================
            # STATISTICS
            # =============================================

            col1, col2, col3 = st.columns(3)

            with col1:
                st.metric(
                    "📢 Lost Items",
                    lost_count
                )

            with col2:
                st.metric(
                    "📦 Found Items",
                    found_count
                )

            with col3:
                st.metric(
                    "📊 Total Items",
                    len(all_items)
                )


            col4, col5, col6 = st.columns(3)

            with col4:
                st.metric(
                    "🟢 Active",
                    active_count
                )

            with col5:
                st.metric(
                    "✅ Resolved",
                    resolved_count
                )

            with col6:
                st.metric(
                    "🔔 Resolution Requests",
                    len(pending_resolution_requests)
                )


            st.divider()

            st.subheader("🔔 Pending Resolution Requests")

            if pending_resolution_requests:
                st.info(
                    f"There are {len(pending_resolution_requests)} case(s) waiting for admin review."
                )
                for request in pending_resolution_requests:
                    (
                        request_id,
                        item_id,
                        requester_id,
                        requester_name,
                        item_name,
                        item_type,
                        owner_id,
                        owner_name,
                        request_status,
                        created_at
                    ) = request

                    st.write(
                        f"🔔 **{item_name}** ({item_type}) — "
                        f"{requester_name} reported that the case is solved."
                    )
                    st.caption(f"Request #{request_id} • {created_at}")
                    st.write(
                        f"Reporter: **{owner_name}** • Item ID: **{item_id}**"
                    )
            else:
                st.success("✅ No pending resolution requests.")


            st.divider()


            st.subheader("ℹ️ System Information")

            st.write(
                "🛡️ Administrator can manage reported items."
            )

            st.write(
                "🔔 Administrator can review resolution requests from users."
            )

            st.write(
                "📊 Administrator can monitor system statistics."
            )

            st.write(
                "🤖 AI Match Finder uses NLP-based text similarity."
            )


        # =================================================
        # MANAGE ITEMS
        # =================================================

        elif admin_option == "📦 Manage Items":

            st.header("📦 Manage Items")

            all_items = get_all_items()

            st.write(
                f"Total Reports: **{len(all_items)}**"
            )

            st.divider()


            if not all_items:

                st.info(
                    "No items have been reported yet."
                )

            else:

                for item in all_items:

                    st.divider()

                    if item[1] == "Lost":
                        icon = "📢"
                    else:
                        icon = "📦"


                    st.subheader(
                        f"{icon} {item[2]}"
                    )


                    col1, col2 = st.columns(2)

                    with col1:

                        st.write(
                            f"**Item ID:** {item[0]}"
                        )

                        st.write(
                            f"**Type:** {item[1]}"
                        )

                        st.write(
                            f"**Category:** {item[3]}"
                        )

                        st.write(
                            f"**Location:** {item[5]}"
                        )


                    with col2:

                        st.write(
                            f"**Date:** {item[6]}"
                        )

                        st.write(
                            f"**Status:** {item[8]}"
                        )


                    st.write(
                        f"**Description:** {item[4]}"
                    )


                    if item[7]:

                        image_path = os.path.join(
                            "uploads",
                            item[7]
                        )

                        if os.path.exists(image_path):

                            st.image(
                                image_path,
                                width=250
                            )


                    pending_request = get_resolution_request(item[0])

                    if pending_request:
                        st.warning(
                            "🔔 Resolution requested: a user says this case has been solved. "
                            "Please review and close it if appropriate."
                        )

                        request_id = pending_request[0]

                        review_col1, review_col2 = st.columns(2)

                        with review_col1:
                            if st.button(
                                "✅ Close Case",
                                key=f"close_case_{request_id}",
                                use_container_width=True
                            ):
                                resolve_case(request_id, item[0])
                                st.success("✅ Case closed and item marked Resolved.")
                                st.rerun()

                        with review_col2:
                            if st.button(
                                "↩️ Keep Active",
                                key=f"keep_active_{request_id}",
                                use_container_width=True
                            ):
                                keep_case_active(request_id)
                                st.info("The case will remain Active.")
                                st.rerun()

                    st.write("### 🔄 Update Item Status")


                    current_status = item[8]

                    status_options = [
                        "Active",
                        "Resolved"
                    ]

                    selected_status = st.selectbox(
                        "Select Status",
                        status_options,
                        index=status_options.index(
                            current_status
                        )
                        if current_status in status_options
                        else 0,
                        key=f"item_status_{item[0]}"
                    )


                    if st.button(
                        "Update Status",
                        key=f"update_item_{item[0]}",
                        use_container_width=True
                    ):

                        update_item_status(
                            item[0],
                            selected_status
                        )

                        st.success(
                            "✅ Item status updated successfully!"
                        )

                        st.rerun()


        # =================================================
        # RESOLUTION REQUESTS
        # =================================================

        elif admin_option == "🔔 Resolution Requests":

            st.header("🔔 Resolution Requests")

            requests = get_pending_resolution_requests()

            if not requests:
                st.success("✅ No pending resolution requests.")
                st.caption("When a user reports that an item has been recovered, the request will appear here.")

            else:
                st.info(f"{len(requests)} case(s) are waiting for your review.")

                for request in requests:
                    (
                        request_id,
                        item_id,
                        requester_id,
                        requester_name,
                        item_name,
                        item_type,
                        owner_id,
                        owner_name,
                        request_status,
                        created_at
                    ) = request

                    st.markdown(f"### 🔔 {item_name} · {item_type}")
                    st.write(f"**Request:** #{request_id} &nbsp; | &nbsp; **Item ID:** {item_id}")
                    st.write(f"**Reported solved by:** {requester_name}")
                    st.write(f"**Original reporter:** {owner_name}")
                    st.caption(f"Requested on: {created_at}")

                    review_col1, review_col2 = st.columns(2)

                    with review_col1:
                        if st.button(
                            "✅ Close Case",
                            key=f"notification_close_{request_id}",
                            use_container_width=True
                        ):
                            resolve_case(request_id, item_id)
                            st.success("✅ Case closed and item marked Resolved.")
                            st.rerun()

                    with review_col2:
                        if st.button(
                            "↩️ Keep Active",
                            key=f"notification_keep_{request_id}",
                            use_container_width=True
                        ):
                            keep_case_active(request_id)
                            st.info("The case will remain Active.")
                            st.rerun()

                    st.divider()


    # =====================================================
    # NORMAL USER APPLICATION
    # =====================================================

    else:



        # =================================================
        # USER MENU
        # =================================================

        st.sidebar.markdown('<div class="lf-brand"><div class="lf-brand-name">Smart Lost &amp; Found</div><div class="lf-brand-sub">Campus Recovery System</div></div>', unsafe_allow_html=True)
        st.sidebar.markdown(f'<div class="lf-user"><div class="lf-avatar">{str(user_name)[:1].upper()}</div><div><div class="lf-user-name">{user_name}</div><div class="lf-user-role">Student / User</div></div></div>', unsafe_allow_html=True)

        st.sidebar.markdown('<div style="font-size:.67rem;text-transform:uppercase;letter-spacing:1px;font-weight:800;color:#7f93af!important;margin:4px 8px 7px;">Navigation</div>', unsafe_allow_html=True)
        option = st.sidebar.radio(
            "",
            [
                "🏠 Dashboard",
                "📢 Report Lost Item",
                "📦 Report Found Item",
                "🔍 Search Items",
                "🤖 AI Match Finder",
                "💬 Messages"
            ]
        )

        unread_count = get_unread_message_count(st.session_state.get("user_id"))
        if unread_count:
            st.sidebar.info(f"📬 {unread_count} unread message(s)")


        # =================================================
        # USER DASHBOARD
        # =================================================

        if option == "🏠 Dashboard":

            st.markdown("""
            <div class="lf-hero">
                <div class="lf-hero-title">Find it. Report it. Return it. 🔎</div>
                <p class="lf-hero-text">
                    A smart campus Lost & Found platform that connects lost reports
                    with found items using AI-powered text matching.
                </p>
            </div>
            """, unsafe_allow_html=True)

            st.header("🏠 Dashboard")

            all_items = get_items()


            lost_count = sum(
                1 for item in all_items
                if item[1] == "Lost"
            )

            found_count = sum(
                1 for item in all_items
                if item[1] == "Found"
            )


            col1, col2, col3 = st.columns(3)


            with col1:

                st.metric(
                    "📢 Lost Items",
                    lost_count
                )


            with col2:

                st.metric(
                    "📦 Found Items",
                    found_count
                )


            with col3:

                st.metric(
                    "📊 Total Reports",
                    len(all_items)
                )


            st.divider()


            st.subheader(
                "✨ How It Works"
            )


            st.write(
                "1️⃣ Report a lost item"
            )

            st.write(
                "2️⃣ Report a found item"
            )

            st.write(
                "3️⃣ Search reported items"
            )

            st.write(
                "4️⃣ Use AI Match Finder"
            )

            st.write(
                "5️⃣ Contact the owner or finder directly"
            )

            st.write(
                "6️⃣ Verify ownership and arrange its return"
            )


        # =================================================
        # REPORT LOST ITEM
        # =================================================

        elif option == "📢 Report Lost Item":

            st.markdown('<div class="lf-page-head"><div class="lf-kicker">New report</div><div class="lf-page-title">Report a Lost Item</div><div class="lf-page-sub">Provide accurate details so the system can identify potential matches.</div></div>', unsafe_allow_html=True)


            item_name = st.text_input(
                "Item Name",
                placeholder="Example: Black Samsung Wallet",
                key="lost_item_name"
            )


            category = st.selectbox(
                "Category",
                [
                    "ID Card",
                    "Wallet",
                    "Mobile Phone",
                    "Laptop",
                    "Bag",
                    "Books",
                    "Keys",
                    "Documents",
                    "Earphones",
                    "Other"
                ],
                key="lost_category"
            )


            description = st.text_area(
                "Description",
                placeholder=(
                    "Describe color, brand, "
                    "unique marks, etc."
                ),
                key="lost_description"
            )


            location = st.text_input(
                "Where did you lose it?",
                placeholder="Example: Central Library",
                key="lost_location"
            )


            lost_date = st.date_input(
                "Date Lost",
                value=date.today(),
                key="lost_date"
            )


            image = st.file_uploader(
                "Upload Item Image",
                type=["jpg", "jpeg", "png"],
                key="lost_image"
            )


            if st.button(
                "Submit Lost Item",
                use_container_width=True
            ):

                if not item_name:

                    st.warning(
                        "⚠️ Please enter the item name."
                    )

                elif not location:

                    st.warning(
                        "⚠️ Please enter the location."
                    )

                else:

                    image_name = save_uploaded_image(image)


                    add_item(
                        st.session_state["user_id"],
                        "Lost",
                        item_name,
                        category,
                        description,
                        location,
                        str(lost_date),
                        image_name
                    )


                    st.success(
                        "✅ Lost item reported successfully!"
                    )


        # =================================================
        # REPORT FOUND ITEM
        # =================================================

        elif option == "📦 Report Found Item":

            st.markdown('<div class="lf-page-head"><div class="lf-kicker">New report</div><div class="lf-page-title">Report a Found Item</div><div class="lf-page-sub">Help return an item by recording where and when you found it.</div></div>', unsafe_allow_html=True)


            item_name = st.text_input(
                "Item Name",
                placeholder="Example: Black Samsung Wallet",
                key="found_item_name"
            )


            category = st.selectbox(
                "Category",
                [
                    "ID Card",
                    "Wallet",
                    "Mobile Phone",
                    "Laptop",
                    "Bag",
                    "Books",
                    "Keys",
                    "Documents",
                    "Earphones",
                    "Other"
                ],
                key="found_category"
            )


            description = st.text_area(
                "Description",
                placeholder="Describe the item you found.",
                key="found_description"
            )


            location = st.text_input(
                "Where did you find it?",
                placeholder="Example: Central Library",
                key="found_location"
            )


            found_date = st.date_input(
                "Date Found",
                value=date.today(),
                key="found_date"
            )


            image = st.file_uploader(
                "Upload Item Image",
                type=["jpg", "jpeg", "png"],
                key="found_image"
            )


            if st.button(
                "Submit Found Item",
                use_container_width=True
            ):

                if not item_name:

                    st.warning(
                        "⚠️ Please enter the item name."
                    )

                elif not location:

                    st.warning(
                        "⚠️ Please enter the location."
                    )

                else:

                    image_name = save_uploaded_image(image)


                    add_item(
                        st.session_state["user_id"],
                        "Found",
                        item_name,
                        category,
                        description,
                        location,
                        str(found_date),
                        image_name
                    )


                    st.success(
                        "✅ Found item reported successfully!"
                    )


        # =================================================
        # SEARCH ITEMS
        # =================================================

        elif option == "🔍 Search Items":

            st.markdown('<div class="lf-page-head"><div class="lf-kicker">Browse reports</div><div class="lf-page-title">Search Items</div><div class="lf-page-sub">Find lost and found reports across the campus system.</div></div>', unsafe_allow_html=True)


            show_contact_composer()


            item_type = st.selectbox(
                "What are you looking for?",
                [
                    "All",
                    "Lost",
                    "Found"
                ],
                key="search_type"
            )


            category = st.selectbox(
                "Select Category",
                [
                    "All",
                    "ID Card",
                    "Wallet",
                    "Mobile Phone",
                    "Laptop",
                    "Bag",
                    "Books",
                    "Keys",
                    "Documents",
                    "Earphones",
                    "Other"
                ],
                key="search_category"
            )


            if item_type == "All":

                selected_type = None

            else:

                selected_type = item_type


            items = get_items(
                selected_type,
                category
            )


            st.divider()


            st.subheader(
                f"📊 {len(items)} Item(s) Found"
            )


            if not items:

                st.info(
                    "No matching items found."
                )

            else:

                for item in items:

                    st.divider()


                    if item[1] == "Lost":

                        icon = "📢"

                    else:

                        icon = "📦"


                    st.subheader(
                        f"{icon} {item[2]}"
                    )


                    col1, col2 = st.columns(2)


                    with col1:

                        st.write(
                            f"**Type:** {item[1]}"
                        )

                        st.write(
                            f"**Category:** {item[3]}"
                        )

                        st.write(
                            f"**Location:** {item[5]}"
                        )


                    with col2:

                        st.write(
                            f"**Date:** {item[6]}"
                        )

                        st.write(
                            f"**Status:** {item[8]}"
                        )


                    st.write(
                        f"**Description:** {item[4]}"
                    )


                    if item[7]:

                        image_path = os.path.join(
                            "uploads",
                            item[7]
                        )


                        if os.path.exists(image_path):

                            st.image(
                                image_path,
                                width=250
                            )


                    # =====================================
                    # DIRECT IN-APP CONTACT
                    # =====================================

                    if item[0] != st.session_state.get("user_id"):
                        contact_label = (
                            "📩 Contact Finder"
                            if item[1] == "Found"
                            else "📩 Contact Owner"
                        )

                        if st.button(
                            contact_label,
                            key=f"contact_item_{item[0]}",
                            use_container_width=True
                        ):
                            open_contact(item[0])
                    else:
                        st.caption("This is your own report.")

                    # =====================================
                    # CASE RESOLUTION REQUEST
                    # =====================================
                    if item[8] == "Active" and can_request_resolution(
                        item[0],
                        st.session_state.get("user_id")
                    ):
                        pending_request = get_resolution_request(item[0])

                        if pending_request:
                            st.info(
                                "🔔 Resolution request sent. Waiting for admin review."
                            )
                        else:
                            if st.button(
                                "✅ Item Recovered / Case Solved",
                                key=f"request_resolution_{item[0]}",
                                use_container_width=True
                            ):
                                if request_resolution(
                                    item[0],
                                    st.session_state.get("user_id")
                                ):
                                    st.success(
                                        "✅ Resolution request sent to admin. "
                                        "The item will remain Active until admin closes the case."
                                    )
                                    st.rerun()
                                else:
                                    st.warning(
                                        "A resolution request is already waiting for admin review."
                                    )


        # =================================================
        # MESSAGES
        # =================================================

        elif option == "💬 Messages":

            show_contact_composer()
            show_messages_page()


        # =================================================
        # AI MATCH FINDER
        # =================================================

        elif option == "🤖 AI Match Finder":

            st.markdown('<div class="lf-page-head"><div class="lf-kicker">AI assistance</div><div class="lf-page-title">AI Match Finder</div><div class="lf-page-sub">Compare a lost report against found reports using NLP-based text similarity.</div></div>', unsafe_allow_html=True)


            st.write(
                "The system compares lost and found item "
                "descriptions using NLP-based text similarity."
            )


            all_items = get_items()


            lost_items = [
                item
                for item in all_items
                if item[1] == "Lost"
            ]


            found_items = [
                item
                for item in all_items
                if item[1] == "Found"
            ]


            if not lost_items:

                st.info(
                    "No lost items are available for matching."
                )


            elif not found_items:

                st.info(
                    "No found items are available for matching."
                )


            else:

                lost_options = {
                    f"{item[2]} | {item[5]} | {item[6]}":
                    item
                    for item in lost_items
                }


                selected_lost_label = st.selectbox(
                    "Select a Lost Item",
                    list(lost_options.keys())
                )


                selected_lost = lost_options[
                    selected_lost_label
                ]


                if st.button(
                    "🤖 Find Possible Matches",
                    use_container_width=True
                ):

                    matches = []


                    for found_item in found_items:

                        lost_data = {
                            "item_name": selected_lost[2],
                            "category": selected_lost[3],
                            "description": selected_lost[4],
                            "location": selected_lost[5]
                        }


                        found_data = {
                            "item_name": found_item[2],
                            "category": found_item[3],
                            "description": found_item[4],
                            "location": found_item[5]
                        }


                        score = calculate_similarity(
                            lost_data,
                            found_data
                        )


                        label = get_match_label(
                            score
                        )


                        matches.append(
                            (
                                score,
                                label,
                                found_item
                            )
                        )


                    matches.sort(
                        key=lambda x: x[0],
                        reverse=True
                    )


                    st.subheader(
                        "🔎 Possible Matches"
                    )


                    for score, label, found_item in matches:

                        if score >= 20:

                            st.divider()


                            st.write(
                                f"### 📦 {found_item[2]}"
                            )


                            st.write(
                                f"**Similarity:** {score}%"
                            )


                            st.write(
                                f"**Match Level:** {label}"
                            )


                            st.write(
                                f"**Category:** {found_item[3]}"
                            )


                            st.write(
                                f"**Location:** {found_item[5]}"
                            )


                            st.write(
                                f"**Date:** {found_item[6]}"
                            )


                            st.write(
                                f"**Description:** {found_item[4]}"
                            )


                            if found_item[0] != st.session_state.get("user_id"):
                                if st.button(
                                    "📩 Contact Finder",
                                    key=f"ai_contact_{selected_lost[0]}_{found_item[0]}",
                                    use_container_width=True
                                ):
                                    open_contact(found_item[0])

                            if found_item[8] == "Active" and can_request_resolution(
                                found_item[0],
                                st.session_state.get("user_id")
                            ):
                                pending_request = get_resolution_request(found_item[0])
                                if pending_request:
                                    st.info(
                                        "🔔 Resolution request sent. Waiting for admin review."
                                    )
                                else:
                                    if st.button(
                                        "✅ Item Recovered / Case Solved",
                                        key=f"ai_request_resolution_{selected_lost[0]}_{found_item[0]}",
                                        use_container_width=True
                                    ):
                                        if request_resolution(
                                            found_item[0],
                                            st.session_state.get("user_id")
                                        ):
                                            st.success(
                                                "✅ Resolution request sent to admin."
                                            )
                                            st.rerun()


                            if score >= 80:

                                st.success(
                                    "🟢 High Match"
                                )

                            elif score >= 60:

                                st.info(
                                    "🟡 Possible Match"
                                )

                            else:

                                st.warning(
                                    "🟠 Low Match"
                                )


                    if not any(
                        score >= 20
                        for score, _, _ in matches
                    ):

                        st.info(
                            "No strong matches were found."
                        )


    st.markdown(
        '<div class="lf-footer">Smart Lost & Found Management System • AI/ML Powered</div>',
        unsafe_allow_html=True
    )

    # =====================================================
    # LOGOUT
    # =====================================================

    st.divider()


    if st.button(
        "🚪 Logout",
        use_container_width=True
    ):

        # Clear complete login session
        for key in [
            "logged_in",
            "user_id",
            "user_name",
            "user_role",
            "user_email"
        ]:

            st.session_state.pop(
                key,
                None
            )


        st.session_state["logged_in"] = False

        st.rerun()