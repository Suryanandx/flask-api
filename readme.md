command for creating mongo admin

db.createUser({ user: "llmadmin", pwd: passwordPrompt(), roles: [ { role: "userAdminAnyDatabase", db: "admin" }, "readWriteAnyDatabase" ] } )

https://gist.github.com/royz/46397fe4ee25dc14418b41821ee45335

to run the app in background
sudo nohup python3 app.py > log.txt 2>&1 &
