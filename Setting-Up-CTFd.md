Official Documentation: [Link](https://docs.ctfd.io/tutorials/getting-started)

# Requirements
- Docker
- Docker compose
- Ubuntu or any Linux distro to run as a server

# Installation
You need Composer, so check:
```
docker compose version
```
Followed by
```
git clone https://github.com/CTFd/CTFd.git
cd CTFd
docker compose up -d (it took almost an hour to compose and build everything)
```
# Check Local CTFd:
```
http://localhost:8000
```
# Check what containers are running:
```
docker ps
```
# Stop/Start/ShutDown (need to be in CTFd/):
```
docker compose stop
docker compose start
docker compose down
```
# Result
When you check the list of containers, you can see these two. Moreover, by default, I receive a database called MariaDB. Redis is the preferred and highly recommended caching server for CTFd to store configuration values, user sessions, and page content, which significantly improves the platform's performance.
To access the CTFd website, use localhost:8000

======================
Account Setup
Admin account: breadAdmin
Password: 123456789
Description: 
This is a testing ground for the CTFd framework, not instance buttons. Starting from 12/27/2025 - Ends 1/10/2026 (Success)

# To-do Next
```
How to get another VM to sign up as a regular user while my Ubuntu is running as admin and server?
```
> To get another VM to register, both machines have to be on the same network, preferably, Bridge Network. Both machines must be able to ping each other. On the client machine's browser, type this:
```
{CTFd-Host-IP:CTFd-Port}
```
Example: 192.168.100.84:8000

*Note: CTFd process is usually on port 8000*

