

# Problem 1:
After running Part 3.2 in Dynamic Instance, I encountered an issue with restarting Docker.

## Solution #1: Fix systemd override
```
sudo systemctl stop docker
sudo systemctl stop docker.socket
sudo mkdir -p /etc/systemd/system/docker.service.d
sudo nano /etc/systemd/system/docker.service.d/docker-tls.conf
```

Write this inside the ```docker-tls.conf```
```
[Service]
ExecStart=
ExecStart=/usr/bin/dockerd \
  --tlsverify \
  --tlscacert=/home/ubun/ctfd_certs/ca.pem \
  --tlscert=/home/ubun/ctfd_certs/server-cert.pem \
  --tlskey=/home/ubun/ctfd_certs/server-key.pem \
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

# Problem #2: 
When I click Start Instance, it says `Internal Server Error`.
## Solution #2:
Just copy this container Python file out because it has read-only access. Make sure you are in the ~/CTFd/ directory: 
```
docker cp ctfd-ctfd-1:/opt/CTFd/CTFd/plugins/docker_challenges/__init__.py ./fixed_plugin.py
geany the fixed_plugin.py
```

# FIND THIS SECTION and replace it:
```
def get_unavailable_ports(docker):
    r = do_request(docker, '/containers/json?all=1')
    result = list()
    for i in r.json():
        if not i['Ports'] == []:
            for p in i['Ports']:
                # CHANGE THIS LINE:
                # result.append(p['PublicPort']) 
                
                # TO THIS:
                if 'PublicPort' in p:
                    result.append(p['PublicPort'])
    return result
```
Next: 
```
geany the docker-compose.yml:
```
Copy and paste this:
```
services:
  ctfd:
    # ... other settings ...
    volumes:
      - .data/CTFd/logs:/opt/CTFd/CTFd/logs
      - .data/CTFd/uploads:/opt/CTFd/CTFd/uploads
      # ADD THIS LINE (use the full path to your fixed_plugin.py):
      - ./fixed_plugin.py:/opt/CTFd/CTFd/plugins/docker_challenges/__init__.py:ro
```

Restart ctfd container:
```
docker compose up -d
```
# END 





