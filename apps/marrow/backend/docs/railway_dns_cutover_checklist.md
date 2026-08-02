# Cloudflare DNS cutover — marrow-health.com → Railway

Cloudflare API token in admin-ref is **invalid** (verify failed). Apply these in CF UI.
Set records to **DNS only (grey cloud)** until Railway cert shows ACTIVE, then proxy if desired.

| Type | Name | Target | Notes |
|------|------|--------|-------|
| CNAME | `api-dev` | `x79utexs.up.railway.app` | for api-dev.marrow-health.com |
| TXT | `_railway-verify.api-dev` | `railway-verify=3e8a68234641ad5ba722dd15aa721cb90f770ed56245e927cf37d56e4483a33e` | for api-dev.marrow-health.com |
| CNAME | `api` | `69u5iubr.up.railway.app` | for api.marrow-health.com |
| TXT | `_railway-verify.api` | `railway-verify=e31b23501e90467c421f25560465be8708ae5c20e3226b25e74f24c7b7e21546` | for api.marrow-health.com |
| CNAME | `app-dev` | `xyv9q3id.up.railway.app` | for app-dev.marrow-health.com |
| TXT | `_railway-verify.app-dev` | `railway-verify=817fc93383198d6087013ace7b5cb0ada25f0bd5fd86b7c382990979a3bbea83` | for app-dev.marrow-health.com |
| CNAME | `@` | `zzy6hb5h.up.railway.app` | for marrow-health.com |
| TXT | `_railway-verify` | `railway-verify=759e062a1f5f8d39e078c346e747d36204e683e49ccf45cd574ee9f5a660dcb7` | for marrow-health.com |
| CNAME | `mcp-dev` | `qznlqg5c.up.railway.app` | for mcp-dev.marrow-health.com |
| TXT | `_railway-verify.mcp-dev` | `railway-verify=3a6d882f856a964490a5cf1a9da7226c9446f6e62a60b0720c39212ec4f64af9` | for mcp-dev.marrow-health.com |
| CNAME | `mcp` | `ns86ixs7.up.railway.app` | for mcp.marrow-health.com |
| TXT | `_railway-verify.mcp` | `railway-verify=86c4fdba703dbd3fefcc9aad390d2b39ca685c87410554e9c26faf670ac598c7` | for mcp.marrow-health.com |
| CNAME | `www` | `myvmlozz.up.railway.app` | for www.marrow-health.com |
| TXT | `_railway-verify.www` | `railway-verify=623a2b5b9086ef65b91cd5fb01801f76e324ac2894dc9dd94930f056df4e25e7` | for www.marrow-health.com |

Replace existing Fly A/CNAME records for api/app-dev/apex/www.
Apex `@` may need Cloudflare CNAME flattening (supported).