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
