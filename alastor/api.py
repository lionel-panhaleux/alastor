import itertools
import babel
import contextlib
import datetime
import flask
import json
import logging
import os
import os.path
import PIL.Image
import PIL.ImageDraw
import PIL.ImageOps
import pkg_resources
import psycopg2.extras
import psycopg2.pool
import re
import requests
import shutil
import urllib
import werkzeug.security

from . import decorators

logger = logging.getLogger()
logging.basicConfig(level=logging.INFO, format="[%(levelname)7s] %(message)s")
base = flask.Blueprint("base", "alastor")
KRCG_STATIC_SERVER = "https://static.krcg.org"
ANONYMOUS_AVATAR = "anonymous.png"
VEKN_LOGIN = os.getenv("VEKN_LOGIN")
VEKN_PASSWORD = os.getenv("VEKN_PASSWORD")
CACHE = {"ranking": [], "ranking_timestamp": datetime.datetime(1, 1, 1), "admins": []}
# babel = flask_babel.Babel()


class _Geography:
    def __init__(self):
        self.countries = {}
        self.cities = {}
        self._countries_rev = {}

    def get_country_name(self, code):
        return self.countries.get(code)

    def get_country_code(self, name):
        return self._countries_rev.get(name)

    def get_country_flag(self, code):
        base = 127397
        if not code:
            return
        return "".join(chr(base + ord(c)) for c in code)

    def load(self):
        logger.info("loading geographical data...")
        local_filename, _headers = urllib.request.urlretrieve(
            KRCG_STATIC_SERVER + "/data/countries.json"
        )
        with open(local_filename) as fp:
            self.countries = {c["iso"]: c["country"] for c in json.load(fp)}
            self.cities = {k: [] for k in self.countries.keys()}
        local_filename, _headers = urllib.request.urlretrieve(
            KRCG_STATIC_SERVER + "/data/cities.json"
        )
        with open(local_filename) as fp:
            for city in sorted(json.load(fp), key=lambda c: c["name"]):
                # ignore cities sub-divisions and destroyed/abandonned places
                if city["feature_code"] in {"PPLA5", "PPLX", "PPLL", "PPLQ", "PPLW"}:
                    continue
                if city["country_code"] == "US":
                    name = f'{city["name"]}, {city["admin1_code"]}'
                else:
                    name = city["name"]
                self.cities[city["country_code"]].append(
                    {
                        "name": name,
                        "geoname_id": city["geoname_id"],
                        "timezone": city["timezone"],
                    }
                )
        urllib.request.urlcleanup()
        self._countries_rev = {v: k for k, v in self.countries.items()}


GEOGRAPHY = _Geography()


class AlastorApp(flask.Flask):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.connection_pool = psycopg2.pool.ThreadedConnectionPool(
            1,
            50,
            "dbname=alastor user=alastor",
            cursor_factory=psycopg2.extras.NamedTupleCursor,
        )

    @contextlib.contextmanager
    def connection(self):
        conn = self.connection_pool.getconn()
        try:
            yield conn
            conn.commit()
        except:  # noqa: E722
            conn.rollback()
            raise
        finally:
            self.connection_pool.putconn(conn)

    @contextlib.contextmanager
    def cursor(self):
        with self.connection() as con:
            with con.cursor() as cur:
                yield cur

    def _apply_migrations(self):
        try:
            with self.cursor() as cur:
                cur.execute("select id from migrations")
                ids = set(row.id for row in cur)
        except psycopg2.errors.UndefinedTable:
            ids = set()

        with self.cursor() as cur:
            for path in sorted(pkg_resources.resource_listdir("alastor", "db")):
                try:
                    migration_id = int(path.split(".")[0])
                except ValueError:
                    continue
                if migration_id in ids:
                    continue
                cur.execute(pkg_resources.resource_string("alastor.db", path))
                cur.execute("insert into migrations values (%s)", [migration_id])

    def _setup_avatar(self):
        os.makedirs(os.path.join(self.root_path, "app_files/avatar"), exist_ok=True)
        static_folder = pkg_resources.resource_filename("alastor", "static")
        shutil.copyfile(
            os.path.join(static_folder, "img", ANONYMOUS_AVATAR),
            os.path.join(self.root_path, "app_files/avatar", ANONYMOUS_AVATAR),
        )


def create_app():
    GEOGRAPHY.load()
    logger.info("launching app")
    app = AlastorApp("alastor")
    app._apply_migrations()
    app._setup_avatar()
    app.register_blueprint(base)
    app.config.update(
        FLASK_ENV=os.getenv("FLASK_ENV") or "production",
        SECRET_KEY=os.getenv("FLASK_SECRET_KEY"),
        UPLOAD_FOLDER="private",
        ALLOWED_EXTENSIONS=["png"],
        MAX_CONTENT_LENGTH=100 * 1024,
        SESSION_COOKIE_SECURE=not os.getenv("DEBUG"),
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
        PERMANENT_SESSION_LIFETIME=datetime.timedelta(days=7),
    )
    # babel.init_app(app)
    return app


@base.route("/")
@base.route("/index.html")
def index():
    return flask.render_template("index.html")


@base.route("/organise.html")
@decorators.ranked(1)
def tournament():
    return flask.render_template("organise.html")


def _get_vekn_token():
    result = requests.post(
        "https://www.vekn.net/api/vekn/login",
        data={"username": VEKN_LOGIN, "password": VEKN_PASSWORD},
    )
    result.raise_for_status()
    result = result.json()
    return result["data"]["auth"]


@base.route("/profile.html", methods=["GET", "POST"])
@decorators.logged
def profile():
    with flask.current_app.cursor() as cur:
        if not CACHE["admins"]:
            cur.execute("select id from users where obj -> level = 3")
            CACHE["admins"] = cur.fetchall()
        cur.execute(
            "select email, obj from users where id=%s",
            [flask.session["user"]],
        )
        user = cur.fetchone()
        email = user.email
        if flask.request.method == "POST":
            data = dict(flask.request.form)
            email = data.pop("email", None) or email
            password = data.pop("password", None)
            if password:
                password = werkzeug.generate_password_hash(password)
            user.obj.update(data)
        if user.obj.get("vekn"):
            try:
                user.obj.pop("vekn_name", None)
                user.obj.pop("vekn_country", None)
                token = _get_vekn_token()
                result = requests.get(
                    f"https://www.vekn.net/api/vekn/registry?filter={user.obj['vekn']}",
                    headers={"Authorization": f"Bearer {token}"},
                )
                result.raise_for_status()
                result = result.json()["data"]["players"]
                if len(result) != 1:
                    raise ValueError("Invalid VEKN number")
                result = result[0]
                logger.info(result)
                vekn_name = result["firstname"] + " " + result["lastname"]
                vekn_country = result["countryname"]
                if vekn_name != user.obj.get("name", vekn_name):
                    user.obj["vekn_name"] = vekn_name
                if user.obj.get("country") != GEOGRAPHY.get_country_code(vekn_country):
                    user.obj["vekn_country"] = vekn_country
            except:  # noqa: E722
                logger.exception("invalid VEKN")
                user.obj["vekn"] = ""
        if flask.request.method == "POST":
            cur.execute(
                "update users set email=%s, obj=%s where id=%s",
                [email, psycopg2.extras.Json(user.obj), flask.session["user"]],
            )
            if password:
                cur.execute(
                    "update users set pwd=%s where id=%s",
                    [password, flask.session["user"]],
                )

        return flask.render_template(
            "profile.html",
            email=email,
            **user.obj,
        )


@base.route("/player.html")
@decorators.ranked(1)
def player():
    return flask.render_template("player.html")


@base.route("/ranking.html")
def ranking():
    if CACHE["ranking_expiration"] > datetime.datetime.now():
        return flask.render_template("ranking.html", CACHE["ranking"])
    try:
        token = _get_vekn_token()
        result = requests.get(
            "https://www.vekn.net/api/vekn/ranking",
            headers={"Authorization": f"Bearer {token}"},
        )
        result.raise_for_status()
        ranking = result.json()["data"]["players"][:1000]
    except:  # noqa: E722
        logger.exception("Ranking unavailable")
        ranking = []

    for player in ranking:
        player["vekn"] = player.pop("veknid")
        player["name"] = " ".join([player.pop("firstname"), player.pop("lastname")])
        player["constructed"] = int(player.pop("rtp_constructed"))
        player.pop("rtp_limited")
        code = player.get("country")
        name = GEOGRAPHY.get_country_name(code)
        if not name:
            continue
        player["country"] = name
        flag = GEOGRAPHY.get_country_flag(code)
        if not flag:
            continue
        player["country"] = " ".join([flag, name])
    ranking = list(itertools.takewhile(lambda p: p["constructed"] > 9, ranking))
    CACHE["ranking_expiration"] = datetime.datetime.now() + datetime.timedelta(hours=1)
    CACHE["ranking"] = ranking
    return flask.render_template("ranking.html", ranking=ranking)


@base.route("/api/login", methods=["POST"])
def login():
    data = flask.request.form or flask.request.get_json()
    try:
        with flask.current_app.cursor() as cur:
            cur.execute(
                "select id, pwd, obj from users where email=%s",
                [data["email"]],
            )
            row = cur.fetchone()
        if werkzeug.security.check_password_hash(row.pwd, data["password"]):
            flask.session["user"] = row.id
            flask.session["rank"] = row.obj.get("rank", 0)
            return flask.redirect(flask.request.args.get("next"))
    except KeyError:
        return "Missing field", 400
    except (psycopg2.ProgrammingError, AttributeError):
        pass
    return "Invalid", 403


@base.route("/api/signup", methods=["POST"])
def signup():
    # TODO check redirect adress points to our website.
    data = flask.request.form or flask.request.get_json()
    try:
        if not re.match(r"^[^@]+@[^@]+\.[^@]+$", data["email"]):
            return "Invalid email address", 400
        with flask.current_app.cursor() as cur:
            cur.execute(
                "insert into users (email, pwd) values (%s, %s) returning id",
                [
                    data["email"],
                    werkzeug.security.generate_password_hash(data["password"]),
                ],
            )
            row = cur.fetchone()
    except (psycopg2.ProgrammingError, psycopg2.IntegrityError):
        return "Login already exists", 403
    flask.session["user"] = row.id
    flask.session["rank"] = 0
    flask.session.permanent = True
    return flask.redirect(flask.request.args.get("next", flask.url_for("base.index")))


@base.route("/api/logout")
def logout():
    flask.session.pop("user", None)
    flask.session.pop("rank", None)
    return flask.redirect(flask.request.args.get("next", flask.url_for("base.index")))


@base.route("/avatar", methods=["GET", "POST"])
@decorators.logged
def avatar():
    user = flask.session["user"]
    if flask.request.method == "GET":
        filename = f"app_files/avatar/{user}.png"
        if not os.path.isfile(os.path.join(flask.current_app.root_path, filename)):
            filename = f"app_files/avatar/{ANONYMOUS_AVATAR}"
        if flask.current_app.config["FLASK_ENV"] == "production":
            response = flask.make_response()
            response.headers["Content-Type"] = "image/png"
            response.headers["X-Accel-Redirect"] = filename
            return response
        return flask.send_file(filename, mimetype="image/png")
    # POST
    image = PIL.Image.open(flask.request.files["avatar"].stream)
    size = (512, 512)
    mask = PIL.Image.new("L", size, 0)
    draw = PIL.ImageDraw.Draw(mask)
    draw.ellipse((0, 0) + size, fill=255)
    output = PIL.ImageOps.fit(image, mask.size, centering=(0.5, 0.5))
    output.putalpha(mask)
    output.save(
        os.path.join(flask.current_app.root_path, f"app_files/avatar/{user}.png")
    )
    return flask.redirect(flask.url_for("base.profile"))


@base.route("/api/countries")
def countries():
    countries = GEOGRAPHY.countries
    lang = flask.request.accept_languages.values()
    if lang:
        lang = babel.Locale.parse(next(lang)[:2])
        countries = sorted(
            [[k, lang.territories.get(k, v)] for k, v in countries.items()],
            key=lambda a: a[1],
        )
    return flask.jsonify(countries)


@base.route("/api/cities/<country_code>")
def cities(country_code):
    if not country_code:
        return "Bad Request", 400
    country_code = country_code.upper()
    if country_code not in GEOGRAPHY.cities:
        return "Not Found", 404
    return flask.jsonify(GEOGRAPHY.cities[country_code])
