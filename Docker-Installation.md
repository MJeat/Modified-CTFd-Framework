Hello this will be a tutorial on how to set up CTFd as well as to modify it to make it look "Good Enough"

==========================================
# Docker Installation
Platform: Ubuntu 25.04
(Use lsb_release -a to know the Ubuntu OS version)
Documentation Installation on Ubuntu: [Link](https://docs.docker.com/engine/install/ubuntu/)

## Installation
### Add Docker's official GPG key:
```
sudo apt update
sudo apt install ca-certificates curl
sudo install -m 0755 -d /etc/apt/keyrings
sudo curl -fsSL https://download.docker.com/linux/ubuntu/gpg -o /etc/apt/keyrings/docker.asc
sudo chmod a+r /etc/apt/keyrings/docker.asc
```

# Add the repository to Apt sources:
```
sudo tee /etc/apt/sources.list.d/docker.sources <<EOF
Types: deb
URIs: https://download.docker.com/linux/ubuntu
Suites: $(. /etc/os-release && echo "${UBUNTU_CODENAME:-$VERSION_CODENAME}")
Components: stable
Signed-By: /etc/apt/keyrings/docker.asc
EOF
sudo apt update
```

### Download Docker packages:
```
sudo apt install docker-ce docker-ce-cli containerd.io docker-buildx-plugin docker-compose-plugin
```

### Status Check
```
sudo systemctl status docker
sudo systemctl start docker
sudo systemctl stop docker
```
### Confirmation:
```
sudo docker run hello-world
```
Note: The hello-world container has a summary of how Docker works once you run it. 

### Remove Sudo
Don’t wanna type sudo in every time you run Docker? Use:
```
sudo usermod -aG docker $USER
newgrp docker
```


Key CLI

- ```docker ps``` will only show the running containers
- ```docker ps -a``` will show every container and its status
- ```exit``` will exit a container if you are inside a container
- ```docker``` will show you a list of commands to use for containers and general commands
- ```docker images``` will show you a list of commands for dealing with images only
====================================
## Create image & container
To create a container, you need an image. You can pull an image from the internet. In this example, I will pull Alpine, a lightweight Linux distro. 
```
docker pull alpine
```
### Creating the container:
```
docker run --name {docker_name} -it {image_name} {shell}
-i means interactive
-t means allocate TTY in the container. It makes sure you can use your Linux terminal in the container. 
```
Example: ```docker run --name container1 -it alpine /bin/sh```

### Remove image & container
To remove a Docker container:
```
docker rm {container_name or ID}
```
To remove a Docker image:
```
docker rmi {image_name or ID}
```
Note: rmi = remove image

