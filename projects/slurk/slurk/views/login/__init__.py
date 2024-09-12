import re

import slurk.views.login.events  # NOQA
from flask import (
    Blueprint,
    current_app,
    flash,
    redirect,
    render_template,
    request,
    url_for,
)
from flask_login import login_user
from slurk.extensions.login import login_manager
from slurk.models import Token, User

from .forms import LoginForm

login = Blueprint("login", __name__, url_prefix="/login")


def register_blueprints(api):
    api.register_blueprint(login)


@login_manager.user_loader
def load_user(id):
    current_app.logger.debug(f"loading user from id {id}")
    return current_app.session.query(User).get(int(id))


@login_manager.request_loader
def load_user_from_request(request):
    token_id = request.headers.get("Authorization") or request.args.get("token")
    user_id = request.args.get("user") or request.headers.get("user")

    if token_id is None or user_id is None:
        return None

    token_id = re.sub(r"bearer\s+", "", token_id, flags=re.IGNORECASE)

    current_app.logger.debug(f"loading user `{user_id}` from token `{token_id}`")

    return (
        current_app.session.query(User)
        .filter_by(token_id=token_id, id=user_id)
        .one_or_none()
    )


@login.route("/", methods=["GET", "POST"])
def index():
    token_id = request.args.get("token")
    name = request.args.get("name")

    form = LoginForm()
    if form.validate_on_submit():
        name = form.name.data
        token_id = form.token.data

    if name and token_id:
        db = current_app.session
        token = db.query(Token).get(token_id)
        current_app.logger.debug(f"Login with token {token_id}")
        print("LOGIN", name, token, token.registrations_left, flush=True)
        if token:
            if token.room is None:
                flash(
                    "The token is an API token, which can not be used for logging in.",
                    "error",
                )
            elif token.registrations_left != 0:
                if token.registrations_left > 0:
                    token.registrations_left -= 1
                user = User(name=name, token=token, rooms=[token.room])
                db.add(user)
                db.commit()
                login_user(user)
                result = redirect(request.args.get("next") or url_for("chat.index"))
                # import time, random
                # time.sleep(random.random())
                print(
                    "REDIRECT",
                    name,
                    token,
                    result.get_data(),
                    result.status,
                    flush=True,
                )
                return result
            else:
                flash(
                    "The token is either expired, was already used, or isn't correct at all.",
                    "error",
                )
        else:
            flash(
                "The token is either expired, was already used, or isn't correct at all.",
                "error",
            )

    form.token.data = token_id
    form.name.data = name
    return render_template("login.html", form=form, title="slurk - Login")
