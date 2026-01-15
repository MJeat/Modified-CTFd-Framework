
# Logs
For ctfd/ctfd or if there’s something wrong with the web UI:
This assumes you are running CTFd via Docker Compose
```
docker logs -f ctfd-ctfd-1
```
# Checking worker table and timestamp:
```
docker exec -it ctfd-db-1 mysql -u root -pctfd -e "USE ctfd; SELECT * FROM docker_challenge_tracker;"
```
# Use this to remove the tracker to get the start instance back:
```
docker exec -it ctfd-db-1 mysql -u root -pctfd -e "USE ctfd; DELETE FROM docker_challenge_tracker;"
```
# Check ctfd-worker logs:
```
docker logs -f ctfd-worker-1
```
# Watch live (-n 1 means every second):
```
watch -n 1 docker ps
```





