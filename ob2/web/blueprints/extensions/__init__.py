import apsw
import json
import logging
from flask import Blueprint, abort, request

from ob2.database import DbCursor
from ob2.database.helpers import create_build
from ob2.dockergrader import dockergrader_queue, Job
from ob2.util.github_api import get_commit_message, get_diff_file_list
from ob2.util.hooks import apply_filters
from ob2.util.job_limiter import rate_limit_fail_build, should_limit_source

blueprint = Blueprint("extensions", __name__, template_folder="templates")

@blueprint.route("/extensions/create", methods=["POST"])
def extensions():
    payload_bytes = request.get_data()
    if request.form.get("_csrf_token"):
        # You should not be able to use a CSRF token for this
        abort(400)
    try:
        payload = json.loads(payload_bytes)
        assert isinstance(payload, dict)

        sid = payload["sid"]
        days = int(payload["days"])
        login = payload["login"]
        assignment = payload["assignment"]

        assert isinstance(sid, str)
        assert isinstance(days, int)
        assert isinstance(login, str)
        assert isinstance(assignment, str)

        with DbCursor() as c:
            c.execute("SELECT sid FROM users WHERE login = ?")
            (db_sid,) = c.fetchone()

            if sid != db_sid:
                return ('Student ID in request does not match database', 400)

            c.execute("INSERT INTO extensions (user, assignment, days) VALUES (?, ?, ?)", [login, assignment, days])
            c.execute("SELECT last_insert_rowid()")
            (extension_id,) = c.fetchone()

        return ('', 201)
    except Exception:
        logging.exception("Error occurred while processing create extension request payload")
        abort(500)
