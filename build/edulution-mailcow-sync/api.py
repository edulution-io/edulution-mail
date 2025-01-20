#!/usr/bin/env python3

from fastapi import FastAPI, Response, status
from pydantic import BaseModel

from modules import Keycloak, ConfigurationStorage

app = FastAPI()

class Login(BaseModel):
    username: str
    password: str

@app.post("/authenticate", status_code=status.HTTP_401_UNAUTHORIZED)
def authenticate(login: Login, response: Response):
    if keycloak.authenticate(login.username, login.password):
        response.status_code = status.HTTP_200_OK

@app.get("/token/{token}", status_code=status.HTTP_401_UNAUTHORIZED)
def authenticate(token: str, response: Response):
    result = keycloak.checkToken(token)
    if result:
        response.status_code = status.HTTP_200_OK
        return result

if __name__ == "__main__":
    config = ConfigurationStorage()
    config.importFromEnvironment()

    keycloak = Keycloak(server_url=config.KEYCLOAK_SERVER_URL, client_id=config.KEYCLOAK_CLIENT_ID, client_secret_key=config.KEYCLOAK_SECRET_KEY)
    keycloak.initKeycloakOpenID()

    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=5000)