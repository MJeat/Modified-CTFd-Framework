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
(Check [Setting-Up-CTFd](https://github.com/MJeat/Modified-CTFd-Framework/blob/main/Setting-Up-CTFd.md)) 
*Note: You have to be inside CTFd/ to use the Docker Compose command*

## 2. Install CTFd Docker Plugin
(Outside the CTFd/ directory after its installation above)
```
git clone https://github.com/offsecginger/CTFd-Docker-Challenges
```
Then, move ```docker-challenges/``` from this directory into ```CTFd/CTFd/plugins```
Next, go inside ```CTFd/``` from ```~/``` directory, and type: 
```
docker compose down 
docker compose up -d
```
Open CTFd web UI > login > At the top, you will see the Plugins option

# Step 3: For Docker Instance Host (Setting Up HTTPS Connection) (Machine B)
Official Document: [Link](https://docs.docker.com/engine/security/protect-access/#use-tls-https-to-protect-the-docker-daemon-socket)
This is about Securing Docker Daemon Access with TLS (HTTPS). 

## Part 1: TLS Certificate Generation (Docker Instance Host)
⚠️ _*Important*_:
- All files generated in this section are confidential and must be stored securely.
- Do not expose or share these files publicly.
- Create a new directory anywhere on the Docker Instance Host to store the certificates, then proceed with the following steps.

### 0. Initially, make a directory called ctfd-certs/ then enter.

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
echo subjectAltName = DNS:$HOST,IP:10.10.10.20,IP:127.0.0.1 >> extfile.cnf
echo extendedKeyUsage = serverAuth >> extfile.cnf
```

If you don’t have a DNS name, you can use this as a one-for-all:
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
If configured correctly, the page will refresh and display Docker images available on the Docker Instance Host.
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
