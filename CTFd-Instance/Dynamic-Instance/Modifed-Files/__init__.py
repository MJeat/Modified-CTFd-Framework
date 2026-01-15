import traceback
import requests
import tempfile
import json
import hashlib
import random
from datetime import datetime
from pathlib import Path

from flask import request, Blueprint, jsonify, abort, render_template, url_for, redirect, session
from flask_restx import Namespace, Resource
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
from wtforms.validators import DataRequired, ValidationError, InputRequired

from CTFd.plugins.challenges import BaseChallenge, CHALLENGE_CLASSES, get_chal_class
from CTFd.plugins.flags import get_flag_class
from CTFd.utils.user import get_ip, get_current_team, get_current_user, is_admin, authed
from CTFd.utils.uploads import delete_file
from CTFd.plugins import register_plugin_assets_directory, bypass_csrf_protection, register_admin_plugin_menu_bar
from CTFd.schemas.tags import TagSchema
from CTFd.models import db, ma, Challenges, Teams, Users, Solves, Fails, Flags, Files, Hints, Tags, ChallengeFiles
from CTFd.utils.decorators import admins_only, authed_only, during_ctf_time_only, require_verified_emails
from CTFd.utils.config import is_teams_mode, get_themes
from CTFd.api import CTFd_API_v1
from CTFd.utils.dates import unix_time
from CTFd.forms import BaseForm
from CTFd.forms.fields import SubmitField

# --- Models ---

class DockerConfig(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    hostname = db.Column("hostname", db.String(64), index=True)
    tls_enabled = db.Column("tls_enabled", db.Boolean, default=False, index=True)
    ca_cert = db.Column("ca_cert", db.String(2200), index=True)
    client_cert = db.Column("client_cert", db.String(2000), index=True)
    client_key = db.Column("client_key", db.String(3300), index=True)
    repositories = db.Column("repositories", db.String(1024), index=True)

class DockerChallengeTracker(db.Model):
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

class DockerChallenge(Challenges):
    __mapper_args__ = {'polymorphic_identity': 'docker'}
    id = db.Column(None, db.ForeignKey('challenges.id'), primary_key=True)
    docker_image = db.Column(db.String(128), index=True)

class DockerConfigForm(BaseForm):
    id = HiddenField()
    hostname = StringField("Docker Hostname", description="The Hostname/IP and Port of your Docker Server")
    tls_enabled = RadioField('TLS Enabled?', choices=[(True, 'Yes'), (False, 'No')])
    ca_cert = FileField('CA Cert')
    client_cert = FileField('Client Cert')
    client_key = FileField('Client Key')
    repositories = SelectMultipleField('Repositories')
    submit = SubmitField('Submit')

# --- Helper Functions ---

def get_client_cert(docker):
    try:
        ca_file = tempfile.NamedTemporaryFile(delete=False)
        ca_file.write(docker.ca_cert.encode())
        ca_file.close()

        client_file = tempfile.NamedTemporaryFile(delete=False)
        client_file.write(docker.client_cert.encode())
        client_file.close()

        key_file = tempfile.NamedTemporaryFile(delete=False)
        key_file.write(docker.client_key.encode())
        key_file.close()

        return (client_file.name, key_file.name), ca_file.name
    except Exception:
        traceback.print_exc()
        return None, None

def do_request(docker, url, headers=None, method='GET', data=None):
    tls = docker.tls_enabled
    prefix = 'https' if tls else 'http'
    URL_TEMPLATE = f"{prefix}://{docker.hostname}{url}"
    
    r = None
    cert_paths = None
    ca_path = None

    try:
        kwargs = {"headers": headers, "timeout": 10, "data": data}
        if tls:
            cert_paths, ca_path = get_client_cert(docker)
            kwargs["cert"] = cert_paths
            kwargs["verify"] = ca_path

        if method == 'GET':
            r = requests.get(URL_TEMPLATE, **kwargs)
        elif method == 'DELETE':
            r = requests.delete(URL_TEMPLATE, **kwargs)
        elif method == 'POST':
            r = requests.post(URL_TEMPLATE, **kwargs)

        # Immediate Cleanup of Temp Files
        if tls and cert_paths:
            for f in [*cert_paths, ca_path]:
                Path(f).unlink(missing_ok=True)

    except Exception:
        traceback.print_exc()
        class MockResponse:
            def json(self): return {}
            @property
            def status_code(self): return 500
        return MockResponse()
        
    return r

def get_repositories(docker, tags=False, repos=None):
    r = do_request(docker, '/images/json?all=1')
    result = []
    try:
        for i in r.json():
            if i.get('RepoTags'):
                tag = i['RepoTags'][0]
                if tag == '<none>': continue
                name = tag if tags else tag.split(':')[0]
                if repos and name not in repos: continue
                result.append(name)
    except: pass
    return list(set(result))

def get_unavailable_ports(docker):
    r = do_request(docker, '/containers/json?all=1')
    ports = []
    try:
        for i in r.json():
            for p in i.get('Ports', []):
                if 'PublicPort' in p: ports.append(p['PublicPort'])
    except: pass
    return ports

def get_required_ports(docker, image):
    r = do_request(docker, f'/images/{image}/json')
    try:
        return r.json()['Config']['ExposedPorts'].keys()
    except: return []

def create_container(docker, image, team_name, portbl):
    needed_ports = get_required_ports(docker, image)
    team_hash = hashlib.md5(team_name.encode("utf-8")).hexdigest()[:10]
    container_name = f"{image.split(':')[0].replace('/', '-')}_{team_hash}"
    
    bindings = {}
    exposed_ports = {}
    for port in needed_ports:
        while True:
            p = random.randint(30000, 60000)
            if p not in portbl:
                bindings[port] = [{"HostPort": str(p)}]
                exposed_ports[port] = {}
                portbl.append(p)
                break

    data = json.dumps({"Image": image, "ExposedPorts": exposed_ports, "HostConfig": {"PortBindings": bindings}})
    headers = {'Content-Type': "application/json"}
    
    # Create
    r_create = do_request(docker, f"/containers/create?name={container_name}", method='POST', headers=headers, data=data)
    res_json = r_create.json()
    
    # Start
    if 'Id' in res_json:
        do_request(docker, f"/containers/{res_json['Id']}/start", method='POST', headers=headers)
    
    return res_json, data

def delete_container(docker, instance_id):
    return do_request(docker, f'/containers/{instance_id}?force=true', method='DELETE')

# --- Admin Blueprints ---

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
            
            # Certificate handling
            try:
                ca_cert = request.files['ca_cert'].stream.read().decode('utf-8')
            except: ca_cert = ''
            try:
                client_cert = request.files['client_cert'].stream.read().decode('utf-8')
            except: client_cert = ''
            try:
                client_key = request.files['client_key'].stream.read().decode('utf-8')
            except: client_key = ''

            if ca_cert: b.ca_cert = ca_cert
            if client_cert: b.client_cert = client_cert
            if client_key: b.client_key = client_key
            
            b.hostname = request.form.get('hostname')
            b.tls_enabled = request.form.get('tls_enabled') == "True"

            if not b.tls_enabled:
                b.ca_cert = None
                b.client_cert = None
                b.client_key = None

            # FIXED: Safely handle missing repositories key
            try:
                repos_list = request.form.getlist('repositories')
                b.repositories = ','.join(repos_list) if repos_list else None
            except Exception:
                traceback.print_exc()
                b.repositories = None

            db.session.add(b)
            db.session.commit()
            docker = DockerConfig.query.filter_by(id=1).first()

        # Fetch repos for the selection list
        try:
            repos = get_repositories(docker)
        except Exception:
            traceback.print_exc()
            repos = []

        if not repos:
            form.repositories.choices = [("ERROR", "Failed to Connect to Docker")]
        else:
            form.repositories.choices = [(d, d) for d in repos]

        selected_repos = docker.repositories.split(',') if (docker and docker.repositories) else []
        
        return render_template("docker_config.html", config=docker, form=form, repos=selected_repos)

    app.register_blueprint(admin_docker_config)

def define_docker_status(app):
    admin_docker_status = Blueprint('admin_docker_status', __name__, template_folder='templates', static_folder='assets')

    @admin_docker_status.route("/admin/docker_status", methods=["GET", "POST"])
    @admins_only
    def docker_admin():
        trackers = DockerChallengeTracker.query.all()
        return render_template("admin_docker_status.html", dockers=trackers)

    app.register_blueprint(admin_docker_status)

# --- API Namespaces ---

container_namespace = Namespace("container", description='Interaction with Docker containers')

@authed_only
    def get(self):
        image = request.args.get('name')
        challenge_name = request.args.get('challenge')
        
        docker = DockerConfig.query.filter_by(id=1).first()
        user = get_current_user()
        team = get_current_team()
        
        user_id = user.id
        team_id = team.id if team else None
        filter_args = {'team_id': team_id} if is_teams_mode() else {'user_id': user_id}

        # --- LOGGING START ---
        print(f"DEBUG: Container GET request for User {user_id}")

        # 1. Fail-Safe Cleanup
        existing = DockerChallengeTracker.query.filter_by(**filter_args).all()
        now = unix_time(datetime.utcnow())
        
        for c in existing:
            elapsed = now - int(c.timestamp)
            print(f"DEBUG: Found existing container {c.instance_id}. Age: {elapsed}s")
            
            if elapsed >= 300:
                print(f"DEBUG: EXPIRED! Attempting to delete {c.instance_id}...")
                try:
                    delete_container(docker, c.instance_id)
                    print(f"DEBUG: Successfully deleted on Machine B")
                except Exception as e:
                    print(f"DEBUG: Delete failed or container already gone: {e}")
                finally:
                    DockerChallengeTracker.query.filter_by(id=c.id).delete()
                    db.session.commit()
                    print(f"DEBUG: Database record cleared.")
                    return {"success": True, "message": "Instance expired and cleaned up"}

        # 2. Check current status
        tracker = DockerChallengeTracker.query.filter_by(**filter_args).first()
        if tracker:
            return {
                "success": True,
                "status": "already_running",
                "ip": tracker.ip,
                "port": tracker.port
            }
        
        return {"success": True, "status": "no_instance"}

        # 2. Check current status
        check = DockerChallengeTracker.query.filter_by(**filter_args).filter_by(docker_image=image).first()
        
        if check:
            if request.args.get('stopcontainer'):
                delete_container(docker, check.instance_id)
                DockerChallengeTracker.query.filter_by(id=check.id).delete()
                db.session.commit()
                return {"success": True, "message": "Stopped"}
            return abort(403, "Container is already running.")

        # 3. Prevent multiple different containers
        if DockerChallengeTracker.query.filter_by(**filter_args).first():
            return abort(403, "Please stop your other running container first.")

        # 4. Create New
        portsbl = get_unavailable_ports(docker)
        res, create_data = create_container(docker, image, (team.name if team else user.name), portsbl)
        
        if 'Id' not in res: return abort(500, f"Docker Error: {res}")

        bindings = json.loads(create_data)['HostConfig']['PortBindings']
        port_str = ','.join([v[0]['HostPort'] for v in bindings.values()])

        new_entry = DockerChallengeTracker(
            team_id=team_id,
            user_id=user_id,
            docker_image=image,
            timestamp=now,
            revert_time=now + 300,
            instance_id=res['Id'],
            ports=port_str,
            host=docker.hostname.split(':')[0],
            challenge=challenge_name
        )
        db.session.add(new_entry)
        db.session.commit()
        return {"success": True}

# --- Challenge Type ---

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
    def create(request):
        data = request.form or request.get_json()
        challenge = DockerChallenge(**data)
        db.session.add(challenge)
        db.session.commit()
        return challenge

    @staticmethod
    def read(challenge):
        challenge = DockerChallenge.query.filter_by(id=challenge.id).first()
        data = {
            'id': challenge.id,
            'name': challenge.name,
            'value': challenge.value,
            'docker_image': challenge.docker_image,
            'description': challenge.description,
            'category': challenge.category,
            'state': challenge.state,
            'max_attempts': challenge.max_attempts,
            'type': challenge.type,
            'type_data': {
                'id': DockerChallengeType.id,
                'name': DockerChallengeType.name,
                'templates': DockerChallengeType.templates,
                'scripts': DockerChallengeType.scripts,
            }
        }
        return data

    @staticmethod
    def update(challenge, request):
        data = request.form or request.get_json()
        for attr, value in data.items():
            setattr(challenge, attr, value)
        db.session.commit()
        return challenge

    @staticmethod
    def delete(challenge):
        # Implementation omitted for brevity, logic remains same as provided
        Fails.query.filter_by(challenge_id=challenge.id).delete()
        Solves.query.filter_by(challenge_id=challenge.id).delete()
        Flags.query.filter_by(challenge_id=challenge.id).delete()
        DockerChallenge.query.filter_by(id=challenge.id).delete()
        Challenges.query.filter_by(id=challenge.id).delete()
        db.session.commit()

    @staticmethod
    def attempt(challenge, request):
        data = request.form or request.get_json()
        submission = data["submission"].strip()
        flags = Flags.query.filter_by(challenge_id=challenge.id).all()
        for flag in flags:
            if get_flag_class(flag.type).compare(flag, submission):
                return True, "Correct"
        return False, "Incorrect"

    @staticmethod
    def solve(user, team, challenge, request):
        data = request.form or request.get_json()
        submission = data["submission"].strip()
        
        # Auto-stop container on solve
        docker = DockerConfig.query.filter_by(id=1).first()
        filter_args = {'team_id': team.id} if is_teams_mode() and team else {'user_id': user.id}
        tracker = DockerChallengeTracker.query.filter_by(docker_image=challenge.docker_image, **filter_args).first()
        if tracker:
            delete_container(docker, tracker.instance_id)
            DockerChallengeTracker.query.filter_by(id=tracker.id).delete()

        solve = Solves(user_id=user.id, team_id=team.id if team else None, challenge_id=challenge.id,
                       ip=get_ip(req=request), provided=submission)
        db.session.add(solve)
        db.session.commit()

    @staticmethod
    def fail(user, team, challenge, request):
        data = request.form or request.get_json()
        submission = data["submission"].strip()
        wrong = Fails(user_id=user.id, team_id=team.id if team else None, challenge_id=challenge.id,
                      ip=get_ip(request), provided=submission)
        db.session.add(wrong)
        db.session.commit()

# --- Plugin Loading ---
	@active_docker_namespace.route("", methods=['GET'])
    class DockerStatus(Resource):
        @authed_only
        def get(self):
            # 1. Clear session and cache to force reality check
            db.session.expire_all()
            user_id = get_current_user().id
            docker = DockerConfig.query.filter_by(id=1).first()
            tracker = DockerChallengeTracker.query.filter_by(user_id=user_id).first()
            
            if not tracker:
                return jsonify({'success': True, 'status': 'no_instance', 'data': []})

            # 2. Check Expiry
            now = unix_time(datetime.utcnow())
            elapsed = now - int(tracker.timestamp)
            
            if elapsed >= 300:
                print(f"DEBUG: FORCING CLEANUP for {tracker.instance_id}")
                try:
                    delete_container(docker, tracker.instance_id)
                except Exception as e:
                    print(f"DEBUG: Machine B Delete Failed: {e}")
                
                db.session.delete(tracker)
                db.session.commit()
                # 3. CRITICAL: Return a status the JS understands to reset the button
                return jsonify({'success': True, 'status': 'no_instance', 'data': []})

            # 4. If still alive, return everything the JS might need
            return jsonify({
                'success': True,
                'status': 'already_running',
                'data': [{
                    'docker_image': tracker.docker_image,
                    'revert_time': tracker.timestamp + 300,
                    'ports': tracker.ports.split(','),
                    'host': tracker.host
                }],
                'ip': tracker.host,
                'port': tracker.ports
            })
