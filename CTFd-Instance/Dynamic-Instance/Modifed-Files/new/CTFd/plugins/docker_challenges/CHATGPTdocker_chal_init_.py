import traceback
from CTFd.plugins.challenges import BaseChallenge, CHALLENGE_CLASSES, get_chal_class
from CTFd.plugins.flags import get_flag_class
from CTFd.utils.user import get_ip
from CTFd.utils.uploads import delete_file
from CTFd.plugins import register_plugin_assets_directory, bypass_csrf_protection
from CTFd.schemas.tags import TagSchema
from CTFd.models import db, ma, Challenges, Teams, Users, Solves, Fails, Flags, Files, Hints, Tags, ChallengeFiles, HintUnlocks # HintUnlocks for fixing hint abuse in network console browser
from CTFd.utils.decorators import admins_only, authed_only, during_ctf_time_only, require_verified_emails
from CTFd.utils.decorators.visibility import check_challenge_visibility, check_score_visibility
from CTFd.utils.user import get_current_team
from CTFd.utils.user import get_current_user
from CTFd.utils.user import is_admin, authed
from CTFd.utils.config import is_teams_mode
from CTFd.api import CTFd_API_v1
from CTFd.api.v1.scoreboard import ScoreboardDetail
import CTFd.utils.scores
from CTFd.api.v1.challenges import ChallengeList, Challenge
from flask_restx import Namespace, Resource
from flask import request, Blueprint, jsonify, abort, render_template, url_for, redirect, session
# from flask_wtf import FlaskForm
from wtforms import (
    FileField,
    HiddenField,
    PasswordField,
    RadioField,
    SelectField,
    StringField,
    TextAreaField,
    SelectMultipleField,
    BooleanField,
)
# from wtforms import TextField, SubmitField, BooleanField, HiddenField, FileField, SelectMultipleField
from wtforms.validators import DataRequired, ValidationError, InputRequired
from werkzeug.utils import secure_filename
import requests
import tempfile
from CTFd.utils.dates import unix_time
from datetime import datetime
import json
import hashlib
import random
from CTFd.plugins import register_admin_plugin_menu_bar

from CTFd.forms import BaseForm
from CTFd.forms.fields import SubmitField
from CTFd.utils.config import get_themes

from pathlib import Path


class DockerConfig(db.Model):
    """
        Docker Config Model. This model stores the config for docker API connections.
        """
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column("hostname", db.String(64), index=True)
    tls_enabled = db.Column("tls_enabled", db.Boolean, default=False, index=True)
    ca_cert = db.Column("ca_cert", db.String(2400), index=True)
    client_cert = db.Column("client_cert", db.String(2200), index=True)
    client_key = db.Column("client_key", db.String(3300), index=True)
    repositories = db.Column("repositories", db.String(1024), index=True)


class DockerChallengeTracker(db.Model):
    """
        Docker Container Tracker. This model stores the users/teams active docker containers.
        """
    id = db.Column(db.Integer, primary_key=True)
    team_id = db.Column("team_id", db.String(64), index=True)
    user_id = db.Column("user_id", db.String(64), index=True)
    docker_image = db.Column("docker_image", db.String(64), index=True)
    timestamp = db.Column("timestamp", db.Integer, index=True)
    revert_time = db.Column("revert_time", db.Integer, index=True)
    instance_id = db.Column("instance_id", db.String(128), index=True)
    ports = db.Column('ports', db.String(128), index=True)
    host = db.Column('host', db.String(128), index=True)
    challenge = db.Column('challenge', db.String(256), index=True)

class DockerConfigForm(BaseForm):
    id = HiddenField()
    hostname = StringField(
        "Docker Hostname", description="The Hostname/IP and Port of your Docker Server"
    )
    tls_enabled = RadioField('TLS Enabled?')
    ca_cert = FileField('CA Cert')
    client_cert = FileField('Client Cert')
    client_key = FileField('Client Key')
    repositories = SelectMultipleField('Repositories')
    submit = SubmitField('Submit')


def define_docker_admin(app):
    admin_docker_config = Blueprint('admin_docker_config', __name__, template_folder='templates',
                                    static_folder='assets')

    @admin_docker_config.route("/admin/docker_config", methods=["GET", "POST"])
    @admins_only
    def docker_config():
        docker = DockerConfig.query.filter_by(id=1).first()
        form = DockerConfigForm()
        if request.method == "POST":
            if docker:
                b = docker
            else:
                b = DockerConfig()
            try:
                ca_cert = request.files['ca_cert'].stream.read()
            except:
                traceback.print_exc()
                ca_cert = ''
            try:
                client_cert = request.files['client_cert'].stream.read()
            except:
                traceback.print_exc()
                client_cert = ''
            try:
                client_key = request.files['client_key'].stream.read()
            except:
                traceback.print_exc()
                client_key = ''
            if len(ca_cert) != 0: b.ca_cert = ca_cert
            if len(client_cert) != 0: b.client_cert = client_cert
            if len(client_key) != 0: b.client_key = client_key
            b.hostname = request.form['hostname']
            b.tls_enabled = request.form['tls_enabled']
            if b.tls_enabled == "True":
                b.tls_enabled = True
            else:
                b.tls_enabled = False
            if not b.tls_enabled:
                b.ca_cert = None
                b.client_cert = None
                b.client_key = None
            try:
                b.repositories = ','.join(request.form.to_dict(flat=False)['repositories'])
            except:
                traceback.print_exc()
                b.repositories = None
            db.session.add(b)
            db.session.commit()
            docker = DockerConfig.query.filter_by(id=1).first()
        try:
            repos = get_repositories(docker)
        except:
            traceback.print_exc()
            repos = list()
        if len(repos) == 0:
            form.repositories.choices = [("ERROR", "Failed to Connect to Docker")]
        else:
            form.repositories.choices = [(d, d) for d in repos]
        dconfig = DockerConfig.query.first()
        try:
            selected_repos = dconfig.repositories
            if selected_repos == None:
                selected_repos = list()
        # selected_repos = dconfig.repositories.split(',')
        except:
            traceback.print_exc()
            selected_repos = []
        return render_template("docker_config.html", config=dconfig, form=form, repos=selected_repos)

    app.register_blueprint(admin_docker_config)


def define_docker_status(app):
    admin_docker_status = Blueprint('admin_docker_status', __name__, template_folder='templates',
                                    static_folder='assets')

    @admin_docker_status.route("/admin/docker_status", methods=["GET", "POST"])
    @admins_only
    def docker_admin():
        docker_config = DockerConfig.query.filter_by(id=1).first()
        docker_tracker = DockerChallengeTracker.query.all()
        for i in docker_tracker:
            if is_teams_mode():
                name = Teams.query.filter_by(id=i.team_id).first()
                i.team_id = name.name
            else:
                name = Users.query.filter_by(id=i.user_id).first()
                i.user_id = name.name
        return render_template("admin_docker_status.html", dockers=docker_tracker)

    app.register_blueprint(admin_docker_status)


kill_container = Namespace("nuke", description='Endpoint to nuke containers')


@kill_container.route("", methods=['POST', 'GET'])
class KillContainerAPI(Resource):
    @admins_only
    def get(self):
        container = request.args.get('container')
        full = request.args.get('all')
        docker_config = DockerConfig.query.filter_by(id=1).first()
        docker_tracker = DockerChallengeTracker.query.all()
        if full == "true":
            for c in docker_tracker:
                delete_container(docker_config, c.instance_id)
                DockerChallengeTracker.query.filter_by(instance_id=c.instance_id).delete()
                db.session.commit()

        elif container != 'null' and container in [c.instance_id for c in docker_tracker]:
            delete_container(docker_config, container)
            DockerChallengeTracker.query.filter_by(instance_id=container).delete()
            db.session.commit()

        else:
            return False
        return True


def do_request(docker, url, headers=None, method='GET'):
    tls = docker.tls_enabled
    prefix = 'https' if tls else 'http'
    host = docker.hostname
    URL_TEMPLATE = '%s://%s' % (prefix, host)
    try:
        if tls:
            cert, verify = get_client_cert(docker)
            if (method == 'GET'):
                r = requests.get(url=f"%s{url}" % URL_TEMPLATE, cert=cert, verify=verify, headers=headers)
            elif (method == 'DELETE'):
                r = requests.delete(url=f"%s{url}" % URL_TEMPLATE, cert=cert, verify=verify, headers=headers)
            # Clean up the cert files:
            for file_path in [*cert, verify]:
                if file_path:
                    Path(file_path).unlink(missing_ok=True)
        else:
            if (method == 'GET'):
                r = requests.get(url=f"%s{url}" % URL_TEMPLATE, headers=headers)
            elif (method == 'DELETE'):
                r = requests.delete(url=f"%s{url}" % URL_TEMPLATE, headers=headers)
    except:
        traceback.print_exc()
        r = []
    return r


def get_client_cert(docker):
    # this can be done more efficiently, but works for now.
    try:
        ca = docker.ca_cert
        client = docker.client_cert
        ckey = docker.client_key
        ca_file = tempfile.NamedTemporaryFile(delete=False)
        ca_file.write(ca.encode())
        ca_file.seek(0)
        client_file = tempfile.NamedTemporaryFile(delete=False)
        client_file.write(client.encode())
        client_file.seek(0)
        key_file = tempfile.NamedTemporaryFile(delete=False)
        key_file.write(ckey.encode())
        key_file.seek(0)
        CERT = (client_file.name, key_file.name)
    except:
        traceback.print_exc()
        CERT = None
    return CERT, ca_file.name


# For the Docker Config Page. Gets the Current Repositories available on the Docker Server.
def get_repositories(docker, tags=False, repos=False):
    r = do_request(docker, '/images/json?all=1')
    result = list()
    for i in r.json():
        if not i['RepoTags'] == []:
            if not i['RepoTags'][0].split(':')[0] == '<none>':
                if repos:
                    if not i['RepoTags'][0].split(':')[0] in repos:
                        continue
                if not tags:
                    result.append(i['RepoTags'][0].split(':')[0])
                else:
                    result.append(i['RepoTags'][0])
    return list(set(result))


def get_unavailable_ports(docker):
    r = do_request(docker, '/containers/json?all=1')
    result = list()
    for i in r.json():
        if not i['Ports'] == []:
            for p in i['Ports']:
                result.append(p['PublicPort'])
    return result


def get_required_ports(docker, image):
    r = do_request(docker, f'/images/{image}/json?all=1')
    result = r.json()['Config']['ExposedPorts'].keys()
    return result


def create_container(docker, image, team, portbl):
    tls = docker.tls_enabled
    CERT = None
    if not tls:
        prefix = 'http'
    else:
        prefix = 'https'
    host = docker.hostname
    URL_TEMPLATE = '%s://%s' % (prefix, host)
    needed_ports = get_required_ports(docker, image)
    team = hashlib.md5(team.encode("utf-8")).hexdigest()[:10]
    container_name = "%s_%s" % (image.split(':')[1], team)
    assigned_ports = dict()
    for i in needed_ports:
        while True:
            assigned_port = random.choice(range(30000, 60000))
            if assigned_port not in portbl:
                assigned_ports['%s/tcp' % assigned_port] = {}
                break
    ports = dict()
    bindings = dict()
    tmp_ports = list(assigned_ports.keys())
    for i in needed_ports:
        ports[i] = {}
        bindings[i] = [{"HostPort": tmp_ports.pop()}]
    headers = {'Content-Type': "application/json"}
    data = json.dumps({"Image": image, "ExposedPorts": ports, "HostConfig": {"PortBindings": bindings}})
    if tls:
        cert, verify = get_client_cert(docker)
        r = requests.post(url="%s/containers/create?name=%s" % (URL_TEMPLATE, container_name), cert=cert,
                      verify=verify, data=data, headers=headers)
        result = r.json()
        s = requests.post(url="%s/containers/%s/start" % (URL_TEMPLATE, result['Id']), cert=cert, verify=verify,
                          headers=headers)
        # Clean up the cert files:
        for file_path in [*cert, verify]:
            if file_path:
                Path(file_path).unlink(missing_ok=True)

    else:
        r = requests.post(url="%s/containers/create?name=%s" % (URL_TEMPLATE, container_name),
                          data=data, headers=headers)
        print(r.request.method, r.request.url, r.request.body)
        result = r.json()
        print(result)
        # name conflicts are not handled properly
        s = requests.post(url="%s/containers/%s/start" % (URL_TEMPLATE, result['Id']), headers=headers)
    return result, data


def delete_container(docker, instance_id):
    headers = {'Content-Type': "application/json"}
    do_request(docker, f'/containers/{instance_id}?force=true', headers=headers, method='DELETE')
    return True


class DockerChallengeType(BaseChallenge):
    id = "docker"
    name = "docker"
    templates = {
        'create': '/plugins/docker_challenges/assets/create.html',
        'update': '/plugins/docker_challenges/assets/update.html',
        'view': '/plugins/docker_challenges/assets/view.html',
    }
    scripts = {
        'create': '/plugins/docker_challenges/assets/create.js',
        'update': '/plugins/docker_challenges/assets/update.js',
        'view': '/plugins/docker_challenges/assets/view.js',
    }
    route = '/plugins/docker_challenges/assets'
    blueprint = Blueprint('docker_challenges', __name__, template_folder='templates', static_folder='assets')

    @staticmethod
    def update(challenge, request):
        """
                This method is used to update the information associated with a challenge. This should be kept strictly to the
                Challenges table and any child tables.

                :param challenge:
                :param request:
                :return:
                """
        data = request.form or request.get_json()
        for attr, value in data.items():
            setattr(challenge, attr, value)

        db.session.commit()
        return challenge

    @staticmethod
    def delete(challenge):
        """
                This method is used to delete the resources used by a challenge.
                NOTE: Will need to kill all containers here

                :param challenge:
                :return:
                """
        Fails.query.filter_by(challenge_id=challenge.id).delete()
        Solves.query.filter_by(challenge_id=challenge.id).delete()
        Flags.query.filter_by(challenge_id=challenge.id).delete()
        files = ChallengeFiles.query.filter_by(challenge_id=challenge.id).all()
        for f in files:
            delete_file(f.id)
        ChallengeFiles.query.filter_by(challenge_id=challenge.id).delete()
        Tags.query.filter_by(challenge_id=challenge.id).delete()
        Hints.query.filter_by(challenge_id=challenge.id).delete()
        DockerChallenge.query.filter_by(id=challenge.id).delete()
        Challenges.query.filter_by(id=challenge.id).delete()
        db.session.commit()

# ============================================================
# UPDATED: SECURE CHALLENGE READ METHOD
# ============================================================
# FIXES:
# - Prevents users from viewing locked hint content
# - Protects against browser Network tab leaks
# - Supports BOTH Teams Mode and User Mode
# - Admins can still see all hints
# - Free hints (cost == 0) still show content
# ============================================================

@staticmethod
def read(challenge):
    """
    SECURE READ METHOD

    This method is used when challenges are viewed by users.
    We sanitize the hints BEFORE sending them to the frontend.

    SECURITY FIX:
    We NEVER expose paid hint content unless:
        - User unlocked the hint
        - OR user is admin
        - OR hint cost == 0
    """

    challenge = DockerChallenge.query.filter_by(id=challenge.id).first()

    # --------------------------------------------------------
    # NEW: Get current user/team context
    # --------------------------------------------------------
    user = get_current_user()
    team = get_current_team()

    # --------------------------------------------------------
    # NEW: Build SECURE hints list manually
    # --------------------------------------------------------
    secure_hints = []

    for hint in challenge.hints:

        # ----------------------------------------------------
        # FREE HINTS
        # ----------------------------------------------------
        if hint.cost == 0:
            secure_hints.append({
                "id": hint.id,
                "content": hint.content,
                "cost": hint.cost,
            })
            continue

        # ----------------------------------------------------
        # ADMINS ALWAYS SEE HINTS
        # ----------------------------------------------------
        if is_admin():
            secure_hints.append({
                "id": hint.id,
                "content": hint.content,
                "cost": hint.cost,
            })
            continue

        # ----------------------------------------------------
        # TEAMS MODE
        # ----------------------------------------------------
        if is_teams_mode():

            unlocked = HintUnlocks.query.filter_by(
                team_id=team.id,
                hint_id=hint.id
            ).first()

        # ----------------------------------------------------
        # USER MODE
        # ----------------------------------------------------
        else:

            unlocked = HintUnlocks.query.filter_by(
                user_id=user.id,
                hint_id=hint.id
            ).first()

        # ----------------------------------------------------
        # IF USER PURCHASED THE HINT
        # ----------------------------------------------------
        if unlocked:
            secure_hints.append({
                "id": hint.id,
                "content": hint.content,
                "cost": hint.cost,
            })

        # ----------------------------------------------------
        # LOCKED HINT
        # ----------------------------------------------------
        else:
            # IMPORTANT:
            # We intentionally REMOVE the content field.
            # Browser network console can no longer see it.
            secure_hints.append({
                "id": hint.id,
                "cost": hint.cost,
            })

    # --------------------------------------------------------
    # RETURN SECURE DATA
    # --------------------------------------------------------
    data = {
        'id': challenge.id,
        'name': challenge.name,
        'value': challenge.value,

        # SECURITY:
        # Never expose backend docker image name
        'docker_image': None,

        'description': challenge.description,
        'category': challenge.category,
        'state': challenge.state,
        'max_attempts': challenge.max_attempts,
        'type': challenge.type,

        # IMPORTANT:
        # Use SECURE hints list
        'hints': secure_hints,

        'type_data': {
            'id': DockerChallengeType.id,
            'name': DockerChallengeType.name,
            'templates': DockerChallengeType.templates,
            'scripts': DockerChallengeType.scripts,
        }
    }

    return data

    @staticmethod
    def create(request):
        """
                This method is used to process the challenge creation request.

                :param request:
                :return:
                """
        data = request.form or request.get_json()
        challenge = DockerChallenge(**data)
        db.session.add(challenge)
        db.session.commit()
        return challenge

    @staticmethod
    def attempt(challenge, request):
        """
                This method is used to check whether a given input is right or wrong. It does not make any changes and should
                return a boolean for correctness and a string to be shown to the user. It is also in charge of parsing the
                user's input from the request itself.

                :param challenge: The Challenge object from the database
                :param request: The request the user submitted
                :return: (boolean, string)
                """

        data = request.form or request.get_json()
        submission = data["submission"].strip()
        flags = Flags.query.filter_by(challenge_id=challenge.id).all()
        for flag in flags:
            if get_flag_class(flag.type).compare(flag, submission):
                return True, "Correct"
        return False, "Incorrect"

    @staticmethod
    def solve(user, team, challenge, request):
        """
                This method is used to insert Solves into the database in order to mark a challenge as solved.

                :param team: The Team object from the database
                :param chal: The Challenge object from the database
                :param request: The request the user submitted
                :return:
                """
        data = request.form or request.get_json()
        submission = data["submission"].strip()
        docker = DockerConfig.query.filter_by(id=1).first()
        try:
            if is_teams_mode():
                docker_containers = DockerChallengeTracker.query.filter_by(
                    docker_image=challenge.docker_image_backend).filter_by(team_id=team.id).first()
            else:
                docker_containers = DockerChallengeTracker.query.filter_by(
                    docker_image=challenge.docker_image_backend).filter_by(user_id=user.id).first()
            
            if docker_containers:
                delete_container(docker, docker_containers.instance_id)
                DockerChallengeTracker.query.filter_by(instance_id=docker_containers.instance_id).delete()
        except Exception:
            traceback.print_exc() 

        solve = Solves(
            user_id=user.id,
            team_id=team.id if team else None,
            challenge_id=challenge.id,
            ip=get_ip(req=request),
            provided=submission,
        )
        db.session.add(solve)
        db.session.commit()

    @staticmethod
    def fail(user, team, challenge, request):
        """
                This method is used to insert Fails into the database in order to mark an answer incorrect.

                :param team: The Team object from the database
                :param chal: The Challenge object from the database
                :param request: The request the user submitted
                :return:
                """
        data = request.form or request.get_json()
        submission = data["submission"].strip()
        wrong = Fails(
            user_id=user.id,
            team_id=team.id if team else None,
            challenge_id=challenge.id,
            ip=get_ip(request),
            provided=submission,
        )
        db.session.add(wrong)
        db.session.commit()


# ============================================================
# UPDATED: SECURE DATABASE MODEL
# ============================================================
# This ALSO protects against leaks from:
# - Core CTFd API
# - /api/v1/challenges
# - Internal serialization
# ============================================================

class DockerChallenge(Challenges):
    __mapper_args__ = {'polymorphic_identity': 'docker'}

    id = db.Column(None, db.ForeignKey('challenges.id'), primary_key=True)

    docker_image_backend = db.Column(
        "docker_image",
        db.String(128),
        index=True
    )

    @property
    def docker_image(self):
        """
        SECURITY:
        Never expose actual docker image name
        to users/frontend.
        """
        return None

    @docker_image.setter
    def docker_image(self, value):
        self.docker_image_backend = value

    # ========================================================
    # UPDATED: SECURE JSON SERIALIZATION
    # ========================================================
    def to_json(self):

        # ----------------------------------------------------
        # Get default CTFd JSON
        # ----------------------------------------------------
        data = super(DockerChallenge, self).to_json()

        # ----------------------------------------------------
        # SECURITY:
        # Never expose docker backend image
        # ----------------------------------------------------
        data["docker_image"] = None

        # ----------------------------------------------------
        # ADMINS CAN SEE EVERYTHING
        # ----------------------------------------------------
        if is_admin():
            return data

        # ----------------------------------------------------
        # Get current user/team
        # ----------------------------------------------------
        user = get_current_user()
        team = get_current_team()

        # ----------------------------------------------------
        # Build SECURE hints manually
        # ----------------------------------------------------
        secure_hints = []

        for hint in self.hints:

            # ------------------------------------------------
            # FREE HINTS
            # ------------------------------------------------
            if hint.cost == 0:
                secure_hints.append({
                    "id": hint.id,
                    "content": hint.content,
                    "cost": hint.cost,
                })
                continue

            # ------------------------------------------------
            # TEAMS MODE
            # ------------------------------------------------
            if is_teams_mode():

                unlocked = HintUnlocks.query.filter_by(
                    team_id=team.id,
                    hint_id=hint.id
                ).first()

            # ------------------------------------------------
            # USER MODE
            # ------------------------------------------------
            else:

                unlocked = HintUnlocks.query.filter_by(
                    user_id=user.id,
                    hint_id=hint.id
                ).first()

            # ------------------------------------------------
            # USER HAS UNLOCKED HINT
            # ------------------------------------------------
            if unlocked:
                secure_hints.append({
                    "id": hint.id,
                    "content": hint.content,
                    "cost": hint.cost,
                })

            # ------------------------------------------------
            # LOCKED HINT
            # ------------------------------------------------
            else:
                # IMPORTANT:
                # DO NOT INCLUDE CONTENT FIELD
                secure_hints.append({
                    "id": hint.id,
                    "cost": hint.cost,
                })

        # ----------------------------------------------------
        # Replace original hints with SECURE version
        # ----------------------------------------------------
        data["hints"] = secure_hints

        return data


# API
container_namespace = Namespace("container", description='Endpoint to interact with containers')

@container_namespace.route("", methods=['POST', 'GET'])
class ContainerAPI(Resource):
    @authed_only
    def get(self):
        container = request.args.get('name')
        if not container:
            return abort(403, "No container specified")
        challenge = request.args.get('challenge')
        if not challenge:
            return abort(403, "No challenge name specified")
        
        docker = DockerConfig.query.filter_by(id=1).first()
        containers = DockerChallengeTracker.query.all()
        if container not in get_repositories(docker, tags=True):
            return abort(403,f"Container {container} not present in the repository.")
        if is_teams_mode():
            session = get_current_team()
            for i in containers:
                if int(session.id) == int(i.team_id) and (unix_time(datetime.utcnow()) - int(i.timestamp)) >= 7200:
                    delete_container(docker, i.instance_id)
                    DockerChallengeTracker.query.filter_by(instance_id=i.instance_id).delete()
                    db.session.commit()
            check = DockerChallengeTracker.query.filter_by(team_id=session.id).filter_by(docker_image=container).first()
        else:
            session = get_current_user()
            for i in containers:
                if int(session.id) == int(i.user_id) and (unix_time(datetime.utcnow()) - int(i.timestamp)) >= 7200:
                    delete_container(docker, i.instance_id)
                    DockerChallengeTracker.query.filter_by(instance_id=i.instance_id).delete()
                    db.session.commit()
            check = DockerChallengeTracker.query.filter_by(user_id=session.id).filter_by(docker_image=container).first()
        
        is_stop_request = request.args.get('stopcontainer')

        if check != None and not is_stop_request and (unix_time(datetime.utcnow()) - int(check.timestamp)) < 300:
            return abort(403,"To prevent abuse, your challenge instance can only be reverted after 5 minutes of creation.")

        elif check != None and request.args.get('stopcontainer'):
            delete_container(docker, check.instance_id)
            if is_teams_mode():
                DockerChallengeTracker.query.filter_by(team_id=session.id).filter_by(docker_image=container).delete()
            else:
                DockerChallengeTracker.query.filter_by(user_id=session.id).filter_by(docker_image=container).delete()
            db.session.commit()
            return {"result": "Container stopped"}
        
        elif check != None:
            delete_container(docker, check.instance_id)
            if is_teams_mode():
                DockerChallengeTracker.query.filter_by(team_id=session.id).filter_by(docker_image=container).delete()
            else:
                DockerChallengeTracker.query.filter_by(user_id=session.id).filter_by(docker_image=container).delete()
            db.session.commit()
       
        containers = DockerChallengeTracker.query.all()
        for i in containers:
            if int(session.id) == int(i.user_id):
                return abort(403,f"Another challenge instance is currently running for challenge:<br><i><b>{i.challenge}</b></i>.<br>Please stop this first.<br>You can only run one challenge instance at a time.")

        portsbl = get_unavailable_ports(docker)
        create = create_container(docker, container, session.name, portsbl)
        ports = json.loads(create[1])['HostConfig']['PortBindings'].values()
        entry = DockerChallengeTracker(
            team_id=session.id if is_teams_mode() else None,
            user_id=session.id if not is_teams_mode() else None,
            docker_image=container,
            timestamp=unix_time(datetime.utcnow()),
            revert_time=unix_time(datetime.utcnow()) + 300,
            instance_id=create[0]['Id'],
            ports=','.join([p[0]['HostPort'] for p in ports]),
            host=str(docker.hostname).split(':')[0],
            challenge=challenge
        )
        db.session.add(entry)
        db.session.commit()
        return


active_docker_namespace = Namespace("docker", description='Endpoint to retrieve User Docker Image Status')

@active_docker_namespace.route("", methods=['POST', 'GET'])
class DockerStatus(Resource):
    @authed_only
    def get(self):
        docker = DockerConfig.query.filter_by(id=1).first()
        if is_teams_mode():
            session = get_current_team()
            tracker = DockerChallengeTracker.query.filter_by(team_id=session.id)
        else:
            session = get_current_user()
            tracker = DockerChallengeTracker.query.filter_by(user_id=session.id)
        data = list()
        for i in tracker:
            data.append({
                'id': i.id,
                'team_id': i.team_id,
                'user_id': i.user_id,
                'docker_image': i.docker_image if is_admin() else "Active",
                'timestamp': i.timestamp,
                'revert_time': i.revert_time,
                'instance_id': i.instance_id,
                'ports': i.ports.split(','),
                'host': str(docker.hostname).split(':')[0]
            })
        return {
            'success': True,
            'data': data
        }


docker_namespace = Namespace("docker", description='Endpoint to retrieve dockerstuff')

@docker_namespace.route("", methods=['POST', 'GET'])
class DockerAPI(Resource):
    @admins_only
    def get(self):
        docker = DockerConfig.query.filter_by(id=1).first()
        images = get_repositories(docker, tags=True, repos=docker.repositories)
        if images:
            return images

# =========================================================
# --- MANDATORY PLUGIN LOAD FUNCTION ---
# =========================================================
# FIXED VERSION
#
# WHY THIS WAS MODIFIED:
# - Your previous version used:
#       app.db.create_all()
#
#   In modern CTFd versions, `app.db` usually does NOT exist.
#   This causes module initialization to crash BEFORE Python
#   fully registers the module-level `load()` function.
#
# - When a Python module crashes during import,
#   Flask/CTFd sees a PARTIALLY LOADED MODULE.
#
# - Result:
#       AttributeError:
#       module 'CTFd.plugins.docker_challenges'
#       has no attribute 'load'
#
# EVEN THOUGH THE FUNCTION EXISTS IN SOURCE CODE.
#
# =========================================================

def load(app):
    """
    Main plugin loader for CTFd.

    This function is REQUIRED by CTFd plugin discovery.
    CTFd imports the plugin module and explicitly calls:
    
        plugin.load(app)

    If this function is missing OR the module crashes
    before reaching this definition, CTFd throws:

        AttributeError:
        module has no attribute 'load'
    """

    print("[docker_challenges] Plugin load() called")

    # =====================================================
    # REGISTER CHALLENGE TYPE
    # =====================================================
    # Registers the custom challenge type:
    #
    # type = "docker"
    #
    # This enables DockerChallengeType to appear
    # in the CTFd challenge creation UI.
    # =====================================================

    CHALLENGE_CLASSES["docker"] = DockerChallengeType

    print("[docker_challenges] Registered challenge type")

    # =====================================================
    # REGISTER STATIC ASSETS
    # =====================================================
    # Exposes:
    #
    # /plugins/docker_challenges/assets/
    #
    # for JS/CSS/templates.
    # =====================================================

    register_plugin_assets_directory(
        app,
        base_path="/plugins/docker_challenges/assets/"
    )

    print("[docker_challenges] Registered assets")

    # =====================================================
    # REGISTER ADMIN BLUEPRINTS
    # =====================================================
    # These create:
    #
    # /admin/docker_config
    # /admin/docker_status
    # =====================================================

    define_docker_admin(app)
    define_docker_status(app)

    print("[docker_challenges] Registered admin blueprints")

    # =====================================================
    # REGISTER ADMIN MENU ITEMS
    # =====================================================

    register_admin_plugin_menu_bar(
        "Docker Config",
        "/admin/docker_config"
    )

    register_admin_plugin_menu_bar(
        "Docker Status",
        "/admin/docker_status"
    )

    print("[docker_challenges] Registered admin menu")

    # =====================================================
    # REGISTER API NAMESPACES
    # =====================================================

    CTFd_API_v1.add_namespace(
        container_namespace,
        "/container"
    )

    CTFd_API_v1.add_namespace(
        active_docker_namespace,
        "/docker_status"
    )

    CTFd_API_v1.add_namespace(
        kill_container,
        "/nuke"
    )

    CTFd_API_v1.add_namespace(
        docker_namespace,
        "/docker"
    )

    print("[docker_challenges] Registered API namespaces")

    # =====================================================
    # CREATE DATABASE TABLES
    # =====================================================
    # IMPORTANT FIX:
    #
    # OLD (BROKEN):
    #     app.db.create_all()
    #
    # NEW:
    #     db.create_all()
    #
    # =====================================================

    with app.app_context():
        db.create_all()

    print("[docker_challenges] Database tables ensured")

    print("[docker_challenges] Plugin fully loaded")
