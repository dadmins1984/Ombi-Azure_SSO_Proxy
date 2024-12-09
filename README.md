# OMBI SSO bypass for OIDC Azure and others

## Preparation

### Azure Entra ID

- Go to Azure AD, then to the App registrations section. 
- Select **New registration**, set the application type to **Web**, and configure the **Redirect URI** to match the URL of the SSO container with the addition of `/callback`. 
- Next, create a secret for the application and copy the following details: **Tenant ID** and **Application ID**.

### Web Proxy (Cloudflare, Traefik, etc.)

- Create an account; in my case, it's Cloudflare.
- Next, connect the machine where you will set up the containers and configure the appropriate IP addresses. 
- In my case, I use a **Cloudflare tunnel** and set `sso-ombi.domain.com` to point to `machine_ip:5000` and `ombi.domain.com` to point to `machine_ip:3579`.

### Docker

#### Network

```bash
docker network create --subnet=172.18.0.0/16 ombi_network
```
- First, create a Docker container for Ombi and remove the value in the HTML file located in the

```bash
window.location.href = "https://sso-url";
```

- Why do we do this? Because it is an active redirection, and the first time you need to create an administrative account. 
- Additionally, you must copy the API key located in the settings. After creating the admin account and copying the API key. 
- Restore the value back to its original place. Remember to update it to the correct URL.

#### Ombi Docker

```bash
docker run -d \
  --name=ombi \
  --net ombi_network \
  --ip 172.18.0.10 \
  -e PUID=1000 \
  -e PGID=1000 \
  -e TZ=Etc/UTC \
  -p 3579:3579 \
  -v /patch/to/config:/config \
  -v /path/to_index/index.html:/app/ombi/ClientApp/dist/index.html \   #get index from this repo
  --restart unless-stopped \
  lscr.io/linuxserver/ombi:latest
```

#### SSO Docker

- Now, you can proceed to create the SSO bypass Docker container for Ombi. 
- Fill in the information you copied earlier and run Docker as shown below:
- Docker url: https://hub.docker.com/repository/docker/dadmins/ombi-sso/general

```bash
sudo docker run -d -p 5000:5000 \
  --name=sso_ombi \
  -e CLIENT_ID="Azure_Client_ID" \
  -e CLIENT_SECRET="Azure_Secret" \
  -e TENANT_ID="Azure_Tenant_ID" \
  -e REDIRECT_URI="https://sso-url/callback" \ #addres to sso container - sso-ombi.domain.com
  -e AUTHORIZATION_URL="https://login.microsoftonline.com/Azure_Tenant_ID/oauth2/v2.0/authorize" \
  -e TOKEN_URL="https://login.microsoftonline.com/Azure_Tenant_ID/oauth2/v2.0/token" \
  -e API_KEY="Ombi_API_Key" \
  -e OMBI_LOGIN_URL="https://ombi_url" \   #main ombi page - ombi.domain.com
  -e OMBI_DOCKER_IP="172.18.0.10" \
  -e OMBI_PORT="3579" \
  -e BASE_DOMAIN="base_domain" \  #main domain - domain.com
  --net ombi_network \
  --ip 172.18.0.11 \
  --restart unless-stopped \
 dadmins/ombi-sso
 ```
