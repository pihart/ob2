import apsw
import json
import logging
from flask import Blueprint, abort, request

import ob2.config as config
from ob2.database import DbCursor
from ob2.database.helpers import create_build
from ob2.dockergrader import dockergrader_queue, Job
from ob2.util.github_api import get_commit_message, get_diff_file_list
from ob2.util.hooks import apply_filters
from ob2.util.job_limiter import rate_limit_fail_build, should_limit_source
from ob2.mailer import create_email, mailer_queue

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
            c.execute("SELECT name, sid, email FROM users WHERE login = ?", [login])
            (name, db_sid,email) = c.fetchone()

            if sid != db_sid:
                return ('Student ID in request does not match database', 400)

            c.execute("INSERT INTO extensions (user, assignment, days) VALUES (?, ?, ?)", [login, assignment, days])
            c.execute("SELECT last_insert_rowid()")
            (extension_id,) = c.fetchone()
            if config.mailer_enabled:
                email_payload = create_email("extension_confirm", email, "[CS 162] Extension Request Reviewed",
                        name=name, days=days, assignment=assignment)
                mailer_job = mailer_queue.create(c, "send", email_payload)
                mailer_queue.enqueue(mailer_job)

        res = {}
        res["status"] = "OK"
        res["id"] = extension_id

        return (res, 201)
    except Exception:
        logging.exception("Error occurred while processing create extension request payload")
        abort(500)
