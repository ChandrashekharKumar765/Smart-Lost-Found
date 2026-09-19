import streamlit as st
import hashlib

from database import add_user, login_user


# =========================================================
# PASSWORD HASHING
# =========================================================

def hash_password(password):
    return hashlib.sha256(password.encode()).hexdigest()


# =========================================================
# AUTHENTICATION PAGE
# =========================================================

def show_auth():

    st.title("🔐 Smart Lost & Found")

    option = st.radio(
        "Choose an option",
        ["Login", "Register"],
        horizontal=True
    )

    # =====================================================
    # REGISTER
    # =====================================================

    if option == "Register":

        st.subheader("📝 Create Account")

        name = st.text_input("Full Name")
        email = st.text_input("Email")
        password = st.text_input(
            "Password",
            type="password"
        )
        confirm_password = st.text_input(
            "Confirm Password",
            type="password"
        )

        if st.button(
            "Register",
            use_container_width=True
        ):

            if not name or not email or not password:

                st.warning(
                    "⚠️ Please fill all fields."
                )

            elif password != confirm_password:

                st.error(
                    "❌ Passwords do not match."
                )

            else:

                password_hash = hash_password(password)

                success = add_user(
                    name,
                    email,
                    password_hash,
                    "user"
                )

                if success:

                    st.success(
                        "✅ Account created successfully! "
                        "Please login."
                    )

                else:

                    st.error(
                        "❌ This email is already registered."
                    )

    # =====================================================
    # LOGIN
    # =====================================================

    else:

        st.subheader("🔑 Login")

        email = st.text_input(
            "Email",
            key="login_email"
        )

        password = st.text_input(
            "Password",
            type="password",
            key="login_password"
        )

        if st.button(
            "Login",
            use_container_width=True
        ):

            if not email or not password:

                st.warning(
                    "⚠️ Please enter email and password."
                )

            else:

                password_hash = hash_password(password)

                user = login_user(
                    email,
                    password_hash
                )

                # =================================================
                # SUCCESSFUL LOGIN
                # =================================================

                if user:

                    # Clear previous session completely
                    for key in [
                        "logged_in",
                        "user_id",
                        "user_name",
                        "user_role",
                        "user_email"
                    ]:
                        st.session_state.pop(key, None)

                    # Save current user information
                    st.session_state["user_id"] = user[0]
                    st.session_state["user_name"] = user[1]
                    st.session_state["user_email"] = user[2]

                    # IMPORTANT:
                    # user table structure:
                    # id, name, email, password, role

                    role = user[4]

                    # Normalize role
                    if role:
                        role = str(role).strip().lower()
                    else:
                        role = "user"

                    st.session_state["user_role"] = role
                    st.session_state["logged_in"] = True

                    # Debug information in terminal/session
                    print(
                        "LOGIN SUCCESS:",
                        user[1],
                        user[2],
                        "ROLE:",
                        role
                    )

                    st.rerun()

                else:

                    st.error(
                        "❌ Invalid email or password."
                    )