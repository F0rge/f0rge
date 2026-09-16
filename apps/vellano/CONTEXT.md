# Vellano / Stockroom

Furniture retailer back office, sold as **Stockroom** (placeholder product name). The Gauteng shop **Vellano** is the first Company on that product.

## Language

### Tenancy

**Stockroom**:
The product a stranger signs up for. Placeholder name until a rename.
_Avoid_: Vellano (that is the first tenant, not the product), platform (control-plane jargon)

**Company**:
The organisation a stranger creates from the public landing. One Company, one workspace, one database.
_Avoid_: Team, shop, account, org, tenant (in UI copy)

**Tenant**:
The control-plane record for a Company (slug, hostnames, database URL, status). Not shown on the landing.
_Avoid_: Team, Company (in registry/code comments prefer Tenant)

**Team**:
The single organisation row inside a Company database (`teams`). Staff users belong to it. Not what the landing creates.
_Avoid_: Company, tenant

**Workspace**:
The Company’s running back office at `{slug}.{base-domain}` (login, catalogue, books).
_Avoid_: App, portal (portal is the trade customer surface)

**Landing**:
The public Stockroom site (its own Next app) where a stranger creates a Company and is sent to a Workspace login. Not the back office.
_Avoid_: Marketing homepage of Vellano, `/` on the Workspace app

**Owner**:
The first staff user created for a Company; they verified the signup email.
_Avoid_: Admin (roles are a permission catalog), seed user

**Vellano**:
The existing Gauteng furniture retailer; first Company (`vellano`). Not a second product.
_Avoid_: Using Vellano as the public product name on the landing

### Already in the back office (unchanged)

**User**:
A staff back-office login. Email is unique inside a Company database, not across Stockroom.
_Avoid_: Account, member

**Customer**:
A CRM/trade buyer. Not a Company and not staff.
_Avoid_: Client, tenant
