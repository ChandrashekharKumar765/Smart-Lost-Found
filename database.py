import sqlite3
import hashlib
import os


DATABASE_NAME = "lost_found.db"


# =========================================================
# LOAD PRIVATE SETTINGS FROM .env
# =========================================================

def load_env_file():

    env_path = os.path.join(
        os.path.dirname(
            os.path.abspath(__file__)
        ),
        ".env"
    )

    if not os.path.exists(env_path):
        return

    try:

        with open(
            env_path,
            "r",
            encoding="utf-8"
        ) as file:

            for line in file:

                line = line.strip()

                if (
                    not line
                    or line.startswith("#")
                    or "=" not in line
                ):
                    continue

                key, value = line.split(
                    "=",
                    1
                )

                key = key.strip()

                value = (
                    value
                    .strip()
                    .strip('"')
                    .strip("'")
                )

                if key and key not in os.environ:

                    os.environ[key] = value

    except OSError:

        pass


load_env_file()


# =========================================================
# PRIVATE ADMIN SETTINGS
# =========================================================

ADMIN_EMAIL = os.getenv(
    "ADMIN_EMAIL",
    "admin@lostfound.com"
)

ADMIN_PASSWORD = os.getenv(
    "ADMIN_PASSWORD",
    "admin123"
)


# =========================================================
# DATABASE CONNECTION
# =========================================================

def get_connection():

    return sqlite3.connect(
        DATABASE_NAME
    )


# =========================================================
# PASSWORD HASHING
# =========================================================

def hash_password(password):

    return hashlib.sha256(
        password.encode()
    ).hexdigest()


# =========================================================
# CREATE DATABASE
# =========================================================

def create_database():

    conn = get_connection()

    cursor = conn.cursor()


    # -----------------------------------------------------
    # USERS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            email TEXT UNIQUE NOT NULL,
            password TEXT NOT NULL,
            role TEXT DEFAULT 'user'
        )
    """)


    # -----------------------------------------------------
    # ITEMS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS items (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            item_type TEXT NOT NULL,
            item_name TEXT NOT NULL,
            category TEXT NOT NULL,
            description TEXT,
            location TEXT NOT NULL,
            date TEXT NOT NULL,
            image TEXT,
            status TEXT DEFAULT 'Active',

            FOREIGN KEY (user_id)
            REFERENCES users(id)
        )
    """)


    # -----------------------------------------------------
    # CLAIMS
    # -----------------------------------------------------

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS claims (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            item_id INTEGER NOT NULL,
            claimant_id INTEGER NOT NULL,
            message TEXT,
            status TEXT DEFAULT 'Pending',

            FOREIGN KEY (item_id)
            REFERENCES items(id),

            FOREIGN KEY (claimant_id)
            REFERENCES users(id)
        )
    """)


    # -----------------------------------------------------
    # CREATE ADMIN ONLY IF IT DOES NOT EXIST
    # -----------------------------------------------------

    cursor.execute("""
        SELECT id
        FROM users
        WHERE email = ?
    """, (
        ADMIN_EMAIL,
    ))

    existing_admin = cursor.fetchone()


    if existing_admin is None:

        cursor.execute("""
            INSERT INTO users
            (
                name,
                email,
                password,
                role
            )
            VALUES (?, ?, ?, ?)
        """, (
            "System Admin",
            ADMIN_EMAIL,
            hash_password(
                ADMIN_PASSWORD
            ),
            "admin"
        ))

    else:

        # Existing admin account ko overwrite nahi karna.
        # Sirf role ko admin ensure karna hai.

        cursor.execute("""
            UPDATE users
            SET role = 'admin'
            WHERE email = ?
        """, (
            ADMIN_EMAIL,
        ))


    conn.commit()

    conn.close()


# =========================================================
# ADD USER
# =========================================================

def add_user(
    name,
    email,
    password,
    role="user"
):

    conn = get_connection()

    cursor = conn.cursor()

    try:

        cursor.execute("""
            INSERT INTO users
            (
                name,
                email,
                password,
                role
            )
            VALUES (?, ?, ?, ?)
        """, (
            name,
            email,
            password,
            role
        ))

        conn.commit()

        return True

    except sqlite3.IntegrityError:

        return False

    finally:

        conn.close()


# =========================================================
# LOGIN
# =========================================================

def login_user(
    email,
    password
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT *
        FROM users
        WHERE email = ?
        AND password = ?
    """, (
        email,
        password
    ))

    user = cursor.fetchone()

    conn.close()

    return user


# =========================================================
# ADD ITEM
# =========================================================

def add_item(
    user_id,
    item_type,
    item_name,
    category,
    description,
    location,
    date,
    image
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        INSERT INTO items
        (
            user_id,
            item_type,
            item_name,
            category,
            description,
            location,
            date,
            image,
            status
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        user_id,
        item_type,
        item_name,
        category,
        description,
        location,
        date,
        image,
        "Active"
    ))

    conn.commit()

    conn.close()


# =========================================================
# GET ITEMS
# =========================================================

def get_items(
    item_type=None,
    category=None
):

    conn = get_connection()

    cursor = conn.cursor()

    query = """
        SELECT
            id,
            item_type,
            item_name,
            category,
            description,
            location,
            date,
            image,
            status
        FROM items
        WHERE status = 'Active'
    """

    parameters = []


    if item_type:

        query += """
            AND item_type = ?
        """

        parameters.append(
            item_type
        )


    if category and category != "All":

        query += """
            AND category = ?
        """

        parameters.append(
            category
        )


    query += """
        ORDER BY id DESC
    """


    cursor.execute(
        query,
        parameters
    )

    items = cursor.fetchall()

    conn.close()

    return items


# =========================================================
# GET ALL ITEMS FOR ADMIN
# =========================================================

def get_all_items():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            id,
            item_type,
            item_name,
            category,
            description,
            location,
            date,
            image,
            status
        FROM items
        ORDER BY id DESC
    """)

    items = cursor.fetchall()

    conn.close()

    return items


# =========================================================
# ADD CLAIM
# =========================================================

def add_claim(
    item_id,
    claimant_id,
    message
):

    conn = get_connection()

    cursor = conn.cursor()


    # Prevent duplicate pending claims

    cursor.execute("""
        SELECT id
        FROM claims
        WHERE item_id = ?
        AND claimant_id = ?
        AND status = 'Pending'
    """, (
        item_id,
        claimant_id
    ))

    existing_claim = cursor.fetchone()


    if existing_claim:

        conn.close()

        return False


    cursor.execute("""
        INSERT INTO claims
        (
            item_id,
            claimant_id,
            message,
            status
        )
        VALUES (?, ?, ?, ?)
    """, (
        item_id,
        claimant_id,
        message,
        "Pending"
    ))

    conn.commit()

    conn.close()

    return True


# =========================================================
# GET CLAIMS
# =========================================================

def get_claims():

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        SELECT
            claims.id,
            claims.item_id,
            items.item_name,
            items.item_type,
            users.name,
            users.email,
            claims.message,
            claims.status
        FROM claims

        JOIN items
        ON claims.item_id = items.id

        JOIN users
        ON claims.claimant_id = users.id

        ORDER BY claims.id DESC
    """)

    claims = cursor.fetchall()

    conn.close()

    return claims


# =========================================================
# UPDATE CLAIM STATUS
# =========================================================

def update_claim_status(
    claim_id,
    status
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE claims
        SET status = ?
        WHERE id = ?
    """, (
        status,
        claim_id
    ))

    conn.commit()

    conn.close()


# =========================================================
# UPDATE ITEM STATUS
# =========================================================

def update_item_status(
    item_id,
    status
):

    conn = get_connection()

    cursor = conn.cursor()

    cursor.execute("""
        UPDATE items
        SET status = ?
        WHERE id = ?
    """, (
        status,
        item_id
    ))

    conn.commit()

    conn.close()