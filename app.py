"""Census Avalúos · punto de entrada Streamlit. Desarrollado por Adaptiva.com.co."""
from __future__ import annotations

import html
import os
import time

import streamlit as st

st.set_page_config(page_title="Census Avalúos", page_icon="🏛️", layout="wide",
                   initial_sidebar_state="expanded")

# Streamlit Cloud: los secretos se exponen como variables de entorno antes de cargar la configuración.
try:
    for _key, _value in st.secrets.items():
        if isinstance(_value, str):
            os.environ.setdefault(_key, _value)
except Exception:  # sin archivo de secretos (ejecución local)
    pass

from config.settings import settings  # noqa: E402
from core import security  # noqa: E402
from ui import components as C  # noqa: E402
from ui import steps  # noqa: E402


def _logout(message: str | None = None) -> None:
    user = st.session_state.get("auth", {}) or {}
    if user:
        security.audit("logout", user.get("user", "?"))
    st.session_state.auth = None
    steps.reset_draft()
    if message:
        st.session_state["flash"] = message
    st.rerun()


def _login() -> None:
    C.brand()
    st.markdown("#### Acceso seguro")
    if flash := st.session_state.pop("flash", None):
        st.info(flash)

    guard = st.session_state.setdefault("guard", {})
    if security.is_locked(guard, time.time()):
        st.error("Demasiados intentos fallidos. Espere antes de volver a intentarlo.")
        return

    with st.form("login_form"):
        username = st.text_input("Usuario", max_chars=64)
        password = st.text_input("Contraseña", type="password", max_chars=128)
        submit = st.form_submit_button("Ingresar", type="primary")

    if not submit:
        return
    username = username.strip()
    users = security.load_users()
    if not users:
        st.error("El sistema no tiene usuarios configurados (CENSUS_USERS_JSON).")
        return
    record = users.get(username)
    valid = isinstance(record, dict) and security.verify_password(password, record.get("password_hash", ""))
    if valid:
        security.reset_failures(guard)
        st.session_state.auth = {"user": username, "role": record.get("role", "avaluador"), "last": time.time()}
        security.audit("login_ok", username)
        st.rerun()
    security.register_failure(guard, time.time(), settings.max_login_attempts, settings.lockout_minutes)
    security.audit("login_failed", username[:64])
    st.error("Credenciales inválidas.")


def _sidebar(auth: dict) -> None:
    with st.sidebar:
        C.brand()
        st.markdown(
            f"**{html.escape(auth['user'])}**  \nRol: {html.escape(auth['role'])}",
        )
        st.divider()
        step = st.session_state.step
        total = len(steps.WIZARD)
        for i, (title, _, _) in enumerate(steps.WIZARD):
            marker = "✓" if i < step else ("●" if i == step else "○")
            st.markdown(f"{marker}&nbsp; {title}")
        st.divider()
        if st.button("Nuevo avalúo"):
            steps.reset_draft()
            st.rerun()
        if st.button("Cerrar sesión"):
            _logout()
        st.caption(f"{settings.app_name} v{settings.version} · {settings.company}")


def main() -> None:
    C.apply_theme()
    st.session_state.setdefault("draft", {})
    st.session_state.setdefault("step", 0)

    auth = st.session_state.get("auth")
    if not auth:
        _login()
        return
    if time.time() - auth["last"] > settings.session_timeout_min * 60:
        security.audit("session_expired", auth["user"])
        _logout("La sesión se cerró por inactividad.")
        return
    auth["last"] = time.time()

    _sidebar(auth)
    steps.render_wizard()
    C.footer()


main()
