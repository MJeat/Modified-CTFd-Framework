# Static Instance
This is a static instance. Meaning everyone can only access this one port. This has no start instances. Just running instances from one container. It is vulnerable cuz players can attack each other and can DOS this one container.
This has no “Start Instance” button. It’s just running in the background as you open the Ubuntu server. In this case, we’ll create a basic website.

*Note: This requires 1 machine.*

# Step 1:
```
mkdir -p ~/ctf-challenges/web-static-instance
cd ~/ctf-challenges/web-static-instance
```
This is not inside the CTFd directory. Challenge files should be in a different folder. 

# Step 2:
Create *app.py*, then write the code below inside *app.py*:

```
from flask import Flask, request
app = Flask(__name__)
FLAG = "breadCTF{static_web_instance}"
@app.route("/")
def index():
    return "Try harder 😉"
@app.route("/admin")
def admin():
    key = request.args.get("key")
    if key == "letmein":
        return FLAG
    return "Access denied"
app.run(host="0.0.0.0", port=5000)
```
# Step 3:
Create *Dockerfile*. No extension. This is the file that the docker is gonna communicate with. Just ```nano Dockerfile``` and paste the code below:

```
FROM python:3.12-alpine
WORKDIR /app
COPY app.py .
RUN pip install flask
EXPOSE 5000
CMD ["python", "app.py"]
```
# Step 4: 
Build the image:
```
docker build -t web-basic .
```
Then, check its location:
```
docker images | grep web-basic
```
# Step 5:
Run the static instance:
```
docker run -d  --name web-basic-instance -p 5001:5000 web-basic
```

# Step 6:
Test with the CTFd IP with port:
```
http://<CTFd_VM_IP>:5001
```
# Step 7:
Register in CTFd Challenge Type as *Standard Challenge*
Description (No “Start Instance” button):
- Target: http://127.0.0.1:5001
Find the admin access and retrieve the flag.


# Checklist:
- You should check if the container is running or not: ```docker ps```
- Look for ```web-basic-instance```
- If you see it says "Up...", everything is good. If "Restarting..." or something else besides "Up...", something is wrong. Check with AI.

# Verdict
- Good for testing containers and the internal instance. However, this approach only uses 1 port and IP. It is vulnerable to a DoS attack or server overflow.
- Not good for hosting dynamic ports and instances. 
