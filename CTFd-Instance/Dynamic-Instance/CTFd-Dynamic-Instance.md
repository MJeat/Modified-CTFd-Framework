# Dynamic Instance 
It also includes the Start Instance Button* after you create the “docker”challenge type. 

# Requirements:
Need 2 Ubuntu machines
- CTFd Host – For hosting database and web UI only (Example IP: 192.168.100.81) - Machine A
- Docker Instance Host – For hosting the challenges (Example IP: 192.168.100.59) - Machine B

# Step 0: Prepare
- You need to be able to ping both machines. 
- Change both machines’ networks to Bridge Adapter
- Use the Docker Instance Host VM to ping the CTFd Host (make sure it’s on)
```
ping {ctfd_host_IP}
```
Next, use the Docker Instance Host VM to ping the CTFd Host web UI (make sure it’s on)
```
curl -I {ctfd_host_IP}:8000
```
If you see *HTTP/1.1 200 OK*, good. Both VMs can now communicate with one another. 

# Step 1: Docker Installation
Both machines must install Docker.
(Check the [Docker Installation](https://github.com/MJeat/Modified-CTFd-Framework/blob/main/Docker-Installation.md))

# Step 2: For CTFd Host Machine (Machine A)
## 1. Install CTFd
```
git clone https://github.com/CTFd/CTFd
```
(Check [Setting-Up-CTFd](https://github.com/MJeat/Modified-CTFd-Framework/blob/main/Setting-Up-CTFd.md)) <br/>
*Note: You have to be inside CTFd/ to use the Docker Compose command*

## 2. Install CTFd Docker Plugin
(Outside the CTFd/ directory after its installation above)
```
git clone https://github.com/offsecginger/CTFd-Docker-Challenges
```
Then, move ```docker-challenges/``` from this directory into ```CTFd/CTFd/plugins``` <br/>
Next, go inside ```CTFd/``` from ```~/``` directory, and type: 
```
docker compose down 
docker compose up -d
```
Open CTFd web UI > login > At the top, you will see the Plugins option

# Step 3: For Docker Instance Host (Setting Up HTTPS Connection) (Machine B)
Official Document: [Link](https://docs.docker.com/engine/security/protect-access/#use-tls-https-to-protect-the-docker-daemon-socket) <br/>
This is about Securing Docker Daemon Access with TLS (HTTPS). 

## Part 1: TLS Certificate Generation (Docker Instance Host)
⚠️ _*Important*_:
- All files generated in this section are confidential and must be stored securely.
- Do not expose or share these files publicly.
- Create a new directory anywhere on the Docker Instance Host to store the certificates, then proceed with the following steps.

### 0. Initial
Make a directory called ```ctfd-certs/``` in the ```~/``` directory, then enter ```ctfd-certs/``` .

### 1. Certificate Authority (CA) – Generate
Generate a private RSA key for the CA (you will be prompted to set a secure passphrase):
```
openssl genrsa -aes256 -out ca-key.pem 4096
```
*Note: My default passphrase is ubun*

Generate the CA certificate (the certificate details are not critical):
```
openssl req -new -x509 -days 365 -key ca-key.pem -sha256 -out ca.pem
```
You will be prompted to input some info. You can tag along or leave it blank by typing "." > Enter

### 2. Server Certificate – Generate
Generate the server private key:
```
openssl genrsa -out server-key.pem 4096
```
Create a Certificate Signing Request (CSR).
Replace $HOST with the CTFd Host IP address or DNS name:
```
openssl req -subj "/CN=$HOST" -sha256 -new -key server-key.pem -out server.csr
```

If $HOST is a DNS name, add both the DNS name and the IP addresses it resolves to:
```
echo subjectAltName = DNS:$HOST,IP:192.168.100.59,IP:127.0.0.1 >> extfile.cnf
echo extendedKeyUsage = serverAuth >> extfile.cnf
```

If you don’t have a DNS name, you can use this as a one-for-all:
```
cat > extfile.cnf <<EOF
subjectAltName = IP:{Machine-B-IP},IP:127.0.0.1
extendedKeyUsage = serverAuth
EOF
```
Example:
```
cat > extfile.cnf <<EOF
subjectAltName = IP:192.168.100.59,IP:127.0.0.1
extendedKeyUsage = serverAuth
EOF
```

Generate the signed server certificate:
```
openssl x509 -req -days 365 -sha256 -in server.csr -CA ca.pem -CAkey ca-key.pem \
-CAcreateserial -out server-cert.pem -extfile extfile.cnf
```
By now,  you should have these 7 files in the ctfd_certificates/:
```
ca-key.pem
ca.pem
server-key.pem
server.csr
server-cert.pem
ca.srl
extfile.cnf
```

### 3. Client Certificate – Generate
Generate the client private key:
```
openssl genrsa -out key.pem 4096
```
Create the client CSR:
```
openssl req -subj '/CN=client' -new -key key.pem -out client.csr
```
Specify client authentication usage:
```
echo extendedKeyUsage = clientAuth > extfile-client.cnf
```
Generate the signed client certificate:
```
openssl x509 -req -days 365 -sha256 -in client.csr -CA ca.pem -CAkey ca-key.pem \
-CAcreateserial -out cert.pem -extfile extfile-client.cnf
```

### 4. Cleanup and Permissions
Remove temporary files:
```
rm -v client.csr server.csr extfile.cnf extfile-client.cnf
```
By now, you should have these 7 files: 
```
ca-key.pem  
ca.pem  
ca.srl  
cert.pem  
key.pem  
server-cert.pem  
server-key.pem
```
Set secure file permissions:
```
chmod -v 0400 ca-key.pem key.pem server-key.pem
chmod -v 0444 ca.pem server-cert.pem cert.pem
```

## Part 2: Preparing Certificates for the CTFd Host
Copy the following files from the Docker Instance Host to the CTFd Host, and store them securely in a dedicated folder:
```
ca-key.pem  
ca.pem  
ca.srl  
cert.pem  
key.pem  
server-cert.pem  
server-key.pem
```
You should follow [SSH-Communication](https://github.com/MJeat/Modified-CTFd-Framework/blob/main/SSH-Communication.md) for this step. <br/>
3 of these files are required for the CTFd host to securely communicate with the Docker Instance Host.

## Part 3: Enabling TLS on the Docker Daemon (Docker Instance Host)
### 1. Stop the Docker Socket and Service
```
sudo systemctl stop docker.socket
sudo systemctl stop docker
```

### 2. Start Docker with TLS Enabled
Run Docker manually with TLS verification enabled:
```
sudo systemctl stop docker
sudo systemctl stop docker.socket
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo nano /etc/systemd/system/docker.service.d/docker-tls.conf
```
Write this inside the docker-tls.conf
```
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd \
  --tlsverify \
  --tlscacert=/home/ubun/ctfd-certs/ca.pem \
  --tlscert=/home/ubun/ctfd-certs/cert.pem \
  --tlskey=/home/ubun/ctfd-certs/key.pem \
  -H=unix:///var/run/docker.sock \
  -H=tcp://0.0.0.0:2376
```

Reload systemd:
```
sudo systemctl daemon-reload
sudo systemctl daemon-reexec
sudo systemctl start docker
sudo systemctl status docker --no-pager
```
Docker will now listen securely on TCP port 2376 using TLS. 
*Note: This will allow the TLS connection to continue. Check with: ```sudo ss -tulpn | grep 2376```*

In the CTFd Host machine > make sure all .pem files are in one folder and go into that folder, confirm TLS handshake: 
```
docker -H tcp://{Docker_Instance_Host_IP}:2376 --tlsverify --tlscacert=ca.pem --tlscert=cert.pem --tlskey=key.pem info
```

### 3. Reverting Back to Default Docker Socket
To disable TLS mode and restore the default Docker socket:
Terminate the dockerd process using Ctrl + C
Restart Docker services:
```
sudo systemctl start docker.socket
sudo systemctl start docker
```
*Note: You don’t need to start Docker again. Let the Docker Instance Host machine operate TLS connection only.*

Check if TLS handshake is successful: (From Machine A)
```
openssl s_client -connect {Machine-B-IP}:2376 \
  -CAfile ca.pem \
  -cert cert.pem \
  -key key.pem
```
If there's no error, you are all good.

## Part 4: Connecting from the CTFd Host
While the Docker Instance Host is running in TLS mode:
- Log in to the CTFd Admin Panel
- Navigate to:
```
Admin → Plugins → Docker Config
```
- Enter:
```
Docker Docker Instance Host IP (IP: 192.168.100.59)
Port: 2376
Upload the following TLS files:
ca.pem
key.pem (If error, try Server-key.pem)
cert.pem (If error, try Server-cert.pem)
```
- Click Submit
If configured correctly, the page will refresh and display Docker images available on the Docker Instance Host. <br/>
*Note: You might encounter an issue with key.pem and cert.pem. You should check Part 3.2: Start Docker with TLS Enabled*

## Part 5: Adding Instance-Based Challenges
### 1. Preparing the Challenge
- Obtain an instance-based challenge (e.g., from Hack The Box) or create your own
- The challenge must include a Dockerfile
- Ensure the real flag is correctly placed inside the challenge container
- Place the challenge files anywhere on the Docker Instance Host.

### 2. Building the Challenge Image
From the directory containing the Dockerfile, run:
```
sudo docker build -t <challenge-name> .
```
Verify the image was built successfully:
```
sudo docker images
```

## Part 6: Make Start-Instance Running
After you setup CTFd *Step 2.2 Install CTFd Docker Plugin* and host a docker challenge type, you should see a *Start Instance* button once you start the challenge. However, you will most likely face an issue with "Internal Server Error". 

To fix this, in the CTFd Host machine or Machine A, you have to create 1 file and modify 5 files.

### 1. fixed_plugins.py
Create a file called ```~/CTFd/fixed_plugins.py``` and modify it:
For full code, check [fixed_plugins.py](https://github.com/MJeat/Modified-CTFd-Framework/blob/main/CTFd-Instance/Dynamic-Instance/Modifed-Files/fixed_plugins.py) <br/>
Just copy this container Python file out because it has read-only access. Make sure you are in the ```~/CTFd/``` directory:
``` 
docker cp ctfd-ctfd-1:/opt/CTFd/CTFd/plugins/docker_challenges/__init__.py ./fixed_plugin.py
geany the fixed_plugin.py
```
FIND THIS SECTION Line 284:
```
def get_unavailable_ports(docker):
    r = do_request(docker, '/containers/json?all=1')
    result = list()
    # Ensure r is a valid response object and has json
    if not hasattr(r, 'json'):
        return result
        
    for i in r.json():
        if i.get('Ports'):
            for p in i['Ports']:
                # Use .get() to avoid KeyError if PublicPort is missing
                public_port = p.get('PublicPort')
                if public_port:
                    result.append(public_port)
    return result

def get_required_ports(docker, image):
    r = do_request(docker, f'/images/{image}/json?all=1')
    try:
        data = r.json()
        # Use .get() with an empty dict fallback
        exposed_ports = data.get('Config', {}).get('ExposedPorts', {})
        return exposed_ports.keys()
    except Exception:
        traceback.print_exc()
        return []
```

Line 556:
```
@container_namespace.route("", methods=['POST', 'GET'])
class ContainerAPI(Resource):
    @authed_only
    def get(self):
        container = request.args.get('name')
        challenge = request.args.get('challenge')
        
        if not container or not challenge:
            return abort(403, "Missing parameters")
        
        docker = DockerConfig.query.filter_by(id=1).first()
        
        # 1. Determine Identity (Team vs User)
        if is_teams_mode():
            session = get_current_team()
            tracker_filter = {"team_id": session.id}
        else:
            session = get_current_user()
            tracker_filter = {"user_id": session.id}

        # 2. Cleanup expired containers (Changed from 7200s to 600s/10m for efficiency)
        # You can adjust '600' to your preferred maximum lifetime
        all_trackers = DockerChallengeTracker.query.filter_by(**tracker_filter).all()
        for i in all_trackers:
            if (unix_time(datetime.utcnow()) - int(i.timestamp)) >= 600:
                delete_container(docker, i.instance_id)
                db.session.delete(i)
        db.session.commit()

        # 3. Handle logic for EXISTING container for THIS challenge
        check = DockerChallengeTracker.query.filter_by(**tracker_filter).filter_by(docker_image=container).first()
        
        if check:
            # Check if 5 minutes (300s) have passed
            time_since_creation = unix_time(datetime.utcnow()) - int(check.timestamp)
            if time_since_creation < 300:
                return abort(403, "To prevent abuse, dockers can be reverted and stopped after 5 minutes.")

            # Stop Request
            if request.args.get('stopcontainer'):
                delete_container(docker, check.instance_id)
                db.session.delete(check)
                db.session.commit()
                return {"result": "Container stopped"}
            
            # Revert Request (Implicitly happens if we reach here)
            delete_container(docker, check.instance_id)
            db.session.delete(check)
            db.session.commit()

        # 4. Global Limit: Check if they have ANY other container running
        # This prevents running 2 different challenges at once
        active_other = DockerChallengeTracker.query.filter_by(**tracker_filter).first()
        if active_other:
            return abort(403, f"Another container is already running for: <b>{active_other.challenge}</b>. Stop it first.")

        # 5. Create New Container
        portsbl = get_unavailable_ports(docker)
        create = create_container(docker, container, session.name, portsbl)
        
        # Determine the next Revert Time (+5 minutes = 300s)
        # Adjust this number to change how long they must wait to revert again
        REVERT_COOLDOWN = 300 

        ports = json.loads(create[1])['HostConfig']['PortBindings'].values()
        entry = DockerChallengeTracker(
            team_id=session.id if is_teams_mode() else None,
            user_id=session.id if not is_teams_mode() else None,
            docker_image=container,
            timestamp=unix_time(datetime.utcnow()),
            revert_time=unix_time(datetime.utcnow()) + REVERT_COOLDOWN, 
            instance_id=create[0]['Id'],
            ports=','.join([p[0]['HostPort'] for p in ports]),
            host=str(docker.hostname).split(':')[0],
            challenge=challenge
        )
        db.session.add(entry)
        db.session.commit()
        
        return {
            "success": True,
            "data": {
                "host": entry.host,
                "ports": entry.ports.split(',')
            }
        }

import threading
import time

def monitor_containers(app):
    with app.app_context():
        while True:
            try:
                # 1. Force the database session to refresh
                db.session.expire_all()
                db.session.commit() # Calling commit helps clear stale transaction states
                
                docker = DockerConfig.query.filter_by(id=1).first()
                if docker:
                    # 2. Use a slightly padded 'now' to account for sync drift
                    # We add 2 seconds to 'now' to ensure we catch everything the JS sees
                    now = unix_time(datetime.utcnow()) + 2
                    
                    all_instances = DockerChallengeTracker.query.all()
                    
                    for instance in all_instances:
                        # 3. Add debug logging to see why it's skipping
                        # print(f"Checking {instance.instance_id}: Now({now}) vs Expiry({instance.revert_time})")
                        
                        if now >= int(instance.revert_time):
                            print(f"[Monitor] Killing expired instance {instance.instance_id}")
                            delete_container(docker, instance.instance_id)
                            db.session.delete(instance)
                            db.session.commit()
            except Exception as e:
                print(f"[Docker Monitor Error]: {e}")
                db.session.rollback()
            
            time.sleep(3)
```

Line 747:

```
def load(app):
    app.db.create_all()
    CHALLENGE_CLASSES['docker'] = DockerChallengeType
    
    @app.template_filter('datetimeformat')
    def datetimeformat(value, format='%Y-%m-%d %H:%M:%S'):
        return datetime.fromtimestamp(value).strftime(format)
        
    register_plugin_assets_directory(app, base_path='/plugins/docker_challenges/assets')
    
    define_docker_admin(app)
    define_docker_status(app)
    
    # Register your API namespaces
    CTFd_API_v1.add_namespace(docker_namespace, '/docker')
    CTFd_API_v1.add_namespace(container_namespace, '/container')
    CTFd_API_v1.add_namespace(active_docker_namespace, '/docker_status')
    CTFd_API_v1.add_namespace(kill_container, '/nuke')
    
    # START THE AUTO-KILLER THREAD   | This is related to function called: monitor_containers
    thread = threading.Thread(target=monitor_containers, args=(app,))
    thread.daemon = True
    thread.start()

```

### 2. docker-compose.yml
Second file, ```~/CTFd/docker-compose.yml```:

Navigate to ~/CTFd/

```
geany docker-compose.yml
```
And paste this code (Changes only in services class). Full code is at [docker-compose.yml](https://github.com/MJeat/Modified-CTFd-Framework/blob/main/CTFd-Instance/Dynamic-Instance/Modifed-Files/docker-compose.yml): 
```
services:
  ctfd:
    build: .
    user: root
    restart: always
    ports:
      - "8000:8000"
    environment:
      - UPLOAD_FOLDER=/var/uploads
      - DATABASE_URL=mysql+pymysql://ctfd:ctfd@db/ctfd
      - REDIS_URL=redis://cache:6379
      - WORKERS=1
      - LOG_FOLDER=/var/log/CTFd
      - ACCESS_LOG=-
      - ERROR_LOG=-
      - REVERSE_PROXY=true
    volumes:
      - .data/CTFd/logs:/var/log/CTFd
      - .data/CTFd/uploads:/var/uploads
      - .:/opt/CTFd:ro
      # ADD THIS LINE (use the full path to your fixed_plugin.py):
      - ./fixed_plugins.py:/opt/CTFd/CTFd/plugins/docker_challenges/__init__.py:ro
    depends_on:
      - db
    networks:
        default:
        internal:
```

### 3. \__init__.py\

Since the code is too long, check [__init__.py](https://github.com/MJeat/Modified-CTFd-Framework/blob/main/CTFd-Instance/Dynamic-Instance/Modifed-Files/__init__.py).

The location of the file is: ```~/CTFd/CTFd/plugins/docker_challenges/```


### 4. view.js

You ONLY need to change the ```function get_docker_status``` 

Check [view.js](https://github.com/MJeat/Modified-CTFd-Framework/blob/main/CTFd-Instance/Dynamic-Instance/Modifed-Files/view.js).

The location of the file is: ```~/CTFd/CTFd/plugins/docker_challenges/assets```

```
function get_docker_status(container) {
    const containerDiv = CTFd.lib.$('#docker_container');
    const NormalStartButtonHTML = `
        <span>
            <a onclick="start_container('${container}');" class='btn btn-dark'>
                <small style='color:white;'><i class="fas fa-play"></i> <b>START INSTANCE</b></small>
            </a>
        </span>`;

    CTFd.fetch("/api/v1/docker_status")
    .then(response => response.json())
    .then(result => {
        if (!result.success || !result.data || result.data.length === 0) {
            containerDiv.html(NormalStartButtonHTML);
            return;
        }

        let matchFound = false;
        result.data.forEach(item => {
            if (item.docker_image == container) {
                matchFound = true;
                const ports = String(item.ports).split(',');
                let data = '';
                
                ports.forEach(port => {
                    const cleanPort = port.split('/')[0];
                    const fullAddress = `${item.host}:${cleanPort}`;
                    // Added the href Link format you requested
                    data += `Link: <a href="http://${fullAddress}" target="_blank" style="color: #00bc8c; text-decoration: underline;">${fullAddress}</a><br />`;
                });

                const instance_short_id = String(item.instance_id).substring(0, 10);
                
                containerDiv.html(`
                    <pre style="color:inherit;">Docker Container Information:<br />${data}</pre>
                    <div class="mb-2">
                        <a onclick="start_container('${item.docker_image}');" class="btn btn-warning btn-sm mr-2">
                            <small style="color:black;"><i class="fas fa-sync-alt"></i> <b>RESTART INSTANCE</b></small>
                        </a>
                    </div>
                    <div id="${instance_short_id}_expiry_timer"></div>
                `);

                const countDownDate = new Date(parseInt(item.revert_time) * 1000).getTime();
                if (window.dockerInterval) clearInterval(window.dockerInterval);

                window.dockerInterval = setInterval(function() {
                    const now = new Date().getTime();
                    const distance = countDownDate - now;

                    if (distance <= 0) {
                        clearInterval(window.dockerInterval);
                        containerDiv.html('<small class="text-info">Instance expired. Resetting UI...</small>');
                        
                        // Increased to 7 seconds to ensure the Python thread (which sleeps 3s) has run
                        setTimeout(() => {
                            get_docker_status(container);
                        }, 7000);
                        return;
                    }

                    const minutes = Math.floor((distance % (1000 * 60 * 60)) / (1000 * 60));
                    const seconds = Math.floor((distance % (1000 * 60)) / 1000).toString().padStart(2, '0');

                    CTFd.lib.$(`#${instance_short_id}_expiry_timer`).html(
                        `<small class="text-muted">Instance expires in: <b>${minutes}:${seconds}</b></small>`
                    );
                }, 1000);
            }
        });

        if (!matchFound) containerDiv.html(NormalStartButtonHTML);
    });
}
```

### 5. view.html

Fourth file location: (CTFd/CTFd/plugins/docker_challenges/assets), view.html file:
The original has the word saying, “Start an instance for a challenge”. I changed it to “LAUNCH INSTANCE”. 

```
{% extends "challenge.html" %}
{% block description %}
{{ challenge.html }}
<div class='mb-3 text-center' id='docker_container' name='{{ challenge.docker_image | safe }}'>
    <span>
        <a onclick="start_container('{{ challenge.docker_image | safe }}');" class='btn btn-dark'>
            <small style='color:white;'><i class="fas fa-play"></i>  LAUNCH INSTANCE </small>
        </a>
    </span>
</div>
{% endblock %}
{% block input %}
<input id="challenge-id" class="challenge-id" type="hidden" value="{{ challenge.id }}">
<input id="challenge-input" class="challenge-input form-control" type="text" name="submission" @keyup.enter="submitChallenge()" placeholder="Flag" x-model="submission">
{% endblock %}
{% block submit %}
<button id="challenge-submit" class="challenge-submit btn btn-outline-secondary w-100 h-100" type="submit" @click.debounce.500ms="submitChallenge()">
    Submit
</button>
{% endblock %}
```

