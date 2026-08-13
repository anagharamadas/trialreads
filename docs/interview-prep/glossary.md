# Concepts Glossary (beginner-friendly)

Plain-English explanations with analogies. Where a concept is delivered by **tools or
frameworks**, the options and their key differences are listed so you understand *why* a
developer picks one over another. Each term also notes how it shows up in **TrialReads**.

> This is a **living document** — new terms get appended over time. Each term is its own
> `##` section, so it stays easy to scan and extend.

---

## Stateless vs. Stateful services

**Plain meaning.** A *stateless* service remembers **nothing** about you between requests —
every request must carry everything the server needs. A *stateful* service **remembers**
things about you (your session, your progress) between requests.

**Analogy.** A **vending machine** is stateless: each purchase is self-contained — insert
money, press a button, get a snack; it doesn't remember you next time. A **bartender running
a tab** is stateful: they remember what you've ordered all night, so you *must* go back to the
same bartender.

**Why it matters.** Stateless services are easy to scale: since no server holds "your" data,
*any* copy of the service can handle *any* request. Stateful services are harder — the request
must be routed back to the server that has your state ("sticky sessions"), and if that server
dies, your state is gone.

**In TrialReads.** The backend is deliberately **stateless**: there's no server-side login
session (a self-contained JWT is verified on each request), and the chat history lives in the
browser and is sent with every message. The one piece of memory — the daily rate-limit count —
is pushed into the *database*, not held in a server's memory, precisely so the service stays
stateless. That's what would let it run many identical copies behind a load balancer.

---

## Horizontal vs. Vertical scaling

**Plain meaning.** Two ways to handle more load. *Vertical* scaling ("scaling up") = make
**one machine bigger** (more CPU/RAM). *Horizontal* scaling ("scaling out") = add **more
machines** and split the work among them.

**Analogy.** A busy restaurant. *Vertical* = replace your one chef with a superhuman chef and
buy a bigger stove. *Horizontal* = open more identical kitchens and send orders to whichever is
free. Vertical hits a ceiling (there's a biggest possible stove); horizontal keeps going by
adding more kitchens.

**Key differences / trade-offs.**
- **Vertical:** simplest (no code changes), but has a hard upper limit and a single point of
  failure (one machine — if it dies, you're down). Often more expensive per unit at the top end.
- **Horizontal:** near-unlimited scale and fault tolerance (one machine dying just removes one
  of many), but **requires the service to be stateless** (see above) and adds complexity — you
  need a **load balancer** and shared data stores.

**In TrialReads.** The backend is *built* for horizontal scaling (it's stateless), even though
it runs one instance today. Vertical scaling here would be paying Render for a bigger instance;
horizontal would be running several instances behind a load balancer.

---

## Synchronous vs. Asynchronous work

**Plain meaning.** *Synchronous* = you ask for something and **wait, blocked**, until it's
done before doing anything else. *Asynchronous* = you kick it off and **carry on**; you're
told (or you check) when it's finished.

**Analogy.** Ordering food. *Synchronous* = you order at the counter and **stand there** until
the food is ready — you can't do anything else. *Asynchronous* = you order, take a **buzzer**,
and go sit down; the buzzer goes off when it's ready, so you were free the whole time.

**Why it matters.** Waiting (blocking) wastes resources. If a web server *synchronously* waits
10 seconds for an AI response, that worker can't help anyone else during those 10 seconds.
Asynchronous designs let one worker juggle many in-flight tasks, and let slow work happen in the
background so the user isn't stuck staring at a spinner.

**In TrialReads.** The AI features are currently **synchronous** — the browser waits 10–60s for
the curation agent (that's why there's a "Thinking…" indicator). The "industry upgrade" noted
throughout the docs is to make it **asynchronous**: the request returns immediately with a job
id, a background worker does the slow AI work, and the result is pushed to the browser when
ready. (Separately, *inside* the agent, the book-grounding lookups already run
**concurrently** — a related idea: doing independent waits at the same time instead of one
after another.)

---

## Coupling

**Plain meaning.** How **dependent** two pieces of code are on each other's internal details.
*Tight* (high) coupling = change one, you're forced to change the other. *Loose* coupling = they
interact through a stable, minimal interface, so each can change freely.

**Analogy.** **Cheap Christmas lights wired in series** — one bulb burns out and the *whole*
string goes dark (tight coupling: everything depends on everything). Compare **Lego bricks** —
they connect through a standard stud interface, so you can swap any brick without touching the
others (loose coupling).

**Why it matters.** Loose coupling makes systems easier to change, test, and reason about. Tight
coupling makes them fragile: a small change ripples everywhere ("I changed one function and three
unrelated features broke").

**In TrialReads.** The frontend and backend are **loosely coupled** — they talk only through a
defined HTTP/JSON API, so either side can be rewritten as long as the contract holds. A place
that's **tightly coupled** (a known weak spot): the old recommendation *parser* depends on the
exact text format the prompt produces — change the prompt and the parser breaks. That fragility
is exactly why the curation agent switched to structured output instead.

---

## Cohesion

**Plain meaning.** How **focused** a single module/class/function is on **one job**. *High*
cohesion = it does one thing and everything in it relates to that thing. *Low* cohesion = it's a
grab-bag of unrelated responsibilities.

**Analogy.** A **well-organized toolbox** where each drawer holds one kind of tool (all
screwdrivers together) = high cohesion. A **kitchen junk drawer** with batteries, tape, receipts,
and a spatula = low cohesion — technically it holds stuff, but nothing belongs together.

**Coupling vs. cohesion (they pair up).** The goal is **low coupling, high cohesion**: modules
that are each focused (high cohesion) and depend minimally on each other (low coupling). They're
different axes — cohesion is *within* a module ("is this one thing?"); coupling is *between*
modules ("how tangled are they?").

**In TrialReads.** High-cohesion examples: `google_books.py` does only Google Books lookups;
`auth.py` does only token verification; `telemetry.py` holds *all* observability setup in one
place. A low-cohesion smell would be a "utils" file that does auth, database, and formatting —
avoided here by splitting responsibilities into focused modules.

---

## Load balancing

**Plain meaning.** A **load balancer** sits in front of several identical server copies and
spreads incoming requests across them, so no single server is overwhelmed — and if one dies,
traffic just goes to the others.

**Analogy.** The **host at a busy restaurant** who greets each party and sends them to whichever
waiter has capacity, instead of every table piling onto one waiter. If a waiter goes on break,
the host simply stops sending them tables.

**How it decides where to send traffic (algorithms):** *round-robin* (take turns), *least
connections* (send to the least-busy server), *IP hash* (same user → same server, useful for
sticky sessions), and *weighted* variants (bigger servers get more).

**Tool/framework options & differences.**

| Option | What it is | When you'd choose it |
|---|---|---|
| **Nginx** | Software reverse proxy + LB, extremely common | Self-managed, want a proven, fast, cheap LB (also serves static files, TLS) |
| **HAProxy** | Software LB focused purely on load balancing | Very high performance / fine-grained control at the connection level |
| **Envoy** | Modern proxy, the data plane behind service meshes | Microservices, need advanced routing, observability, gRPC, retries |
| **Cloud LBs** (AWS ELB/ALB/NLB, GCP Cloud LB) | Managed by the cloud provider | You want zero ops, autoscaling, health checks, HTTPS handled for you |
| **Traefik** | Auto-configuring proxy popular with containers/Kubernetes | Dynamic environments where services come and go (Docker/K8s) |

**Key differences that drive the choice:** *managed vs. self-hosted* (ops burden), *Layer 4 vs.
Layer 7* (raw TCP speed vs. HTTP-aware routing by path/header), and *ecosystem fit* (Envoy/Traefik
for Kubernetes, Nginx/HAProxy for classic servers, cloud LBs for cloud-native).

**In TrialReads.** There's no explicit load balancer today (one backend instance). Render/Vercel
provide the managed-LB layer implicitly; if you scaled the backend to multiple instances, you'd
put one of the above in front — and it works *because* the backend is stateless.

---

## API Gateway

**Plain meaning.** A single **front door** for all your APIs. Every client request goes through
the gateway, which handles cross-cutting concerns — authentication, rate limiting, routing to the
right backend service, logging — so each backend service doesn't have to reimplement them.

**Analogy.** A **hotel front desk**. Guests don't wander into the kitchen or housekeeping
directly; they go to the front desk, which checks their key (auth), enforces rules (rate
limiting), and directs their request to the right department (routing). One controlled entry
point for everything.

**Gateway vs. load balancer (commonly confused).** A load balancer asks "*which copy* of this
service should handle this?" (spreading load). A gateway asks "*what should happen to* this
request — is it allowed, where does it go, should it be throttled?" (policy + routing across
*different* services). They're often used together; a gateway usually *includes* load balancing.

**Tool/framework options & differences.**

| Option | What it is | When you'd choose it |
|---|---|---|
| **Kong** | Popular open-source gateway (plugins for auth, rate-limit, etc.) | Self-hosted, want a rich plugin ecosystem |
| **AWS API Gateway** | Fully-managed gateway | AWS shop, want serverless/managed, pay-per-request |
| **Apigee** (Google) | Enterprise gateway + API management/analytics | Large orgs monetizing/managing many public APIs |
| **NGINX / Traefik** | Proxies that can act as lightweight gateways | You want gateway-ish routing without a heavy platform |
| **Cloud-native (Envoy, Istio ingress)** | Gateway layer for Kubernetes/mesh | Microservices on Kubernetes |

**Key differences that drive the choice:** *managed vs. self-hosted*, *simple routing vs. full
API management* (analytics, developer portals, monetization), and *ecosystem* (AWS Gateway if
you're on AWS Lambda, Kong/Envoy if you run your own infra).

**In TrialReads.** There's **no gateway** — the browser calls the FastAPI backend directly, and
the backend itself handles auth and rate limiting (via FastAPI dependencies). That's fine for one
service. A gateway earns its place once you have *many* backend services and want auth/rate-limit/
routing enforced in one shared place instead of in every service.

---

## RLS (Row-Level Security)

**Plain meaning.** A database feature where the **database itself** decides which **rows** each
user is allowed to see or change — based on rules ("policies") you write. Even if the application
code forgets to filter, the database won't hand over rows you're not allowed to see.

**Analogy.** A **shared filing cabinet with a smart lock on every drawer**. Everyone's files are
in the same cabinet, but your key only opens *your* drawers — and the *cabinet* enforces that, not
the clerk. So even a careless clerk can't accidentally give you someone else's file.

**Why it matters.** In a **multi-tenant** app (many users sharing one database), the nightmare is
user A seeing user B's data. Enforcing that only in application code is risky — one forgotten
`WHERE user_id = ...` and you leak data. RLS is a **second, deeper line of defense** inside the
database that holds even if the app has a bug ("defense in depth").

**Options for tenant isolation (RLS is one of several):**

| Approach | How it isolates | Trade-offs |
|---|---|---|
| **App-level filtering only** | Every query manually adds `WHERE user_id = …` | Simple, fast; but one forgotten filter = a leak. No safety net. |
| **Row-Level Security (RLS)** | The DB enforces per-row rules automatically | Strong safety net; needs a DB that supports it (Postgres does); slight per-query cost |
| **Schema-per-tenant** | Each tenant gets their own set of tables | Strong isolation; heavy to manage at thousands of tenants |
| **Database-per-tenant** | Each tenant gets a whole separate database | Strongest isolation (and easy per-tenant backup/delete); most expensive/complex to run |

The choice trades **strength of isolation** against **operational cost**: shared-table + RLS is
the sweet spot for many SaaS apps; separate DBs are for high-compliance or very large tenants.

**In TrialReads.** RLS is a **core security feature**. Every user table (`library`, `shelves`,
`shelf_books`) has RLS policies so a user can only touch their own rows. It's especially important
for the **text-to-SQL** feature: since an AI writes the SQL, the app can't fully trust that SQL —
so it runs on a database connection where RLS physically restricts results to the current user.
(Full detail: interview-prep section 05.)

---

## CAP theorem

**Plain meaning.** For a distributed system (data spread across multiple machines), when the
network between machines breaks (a "partition"), you can only guarantee **two of these three**:
**C**onsistency (everyone sees the same latest data), **A**vailability (every request gets a
response), **P**artition tolerance (the system keeps working despite network splits). Since network
partitions *will* happen, you're really choosing between **C and A** *during* a partition.

**Analogy.** Two shop branches in different towns share one inventory count, kept in sync by phone.
One day **the phone line goes down** (partition). A customer wants the last item at branch B. Two
choices:
- **Choose Consistency (give up Availability):** branch B refuses to sell until it can confirm with
  branch A — no risk of overselling, but the customer is turned away (system "unavailable" for that
  request).
- **Choose Availability (give up Consistency):** branch B sells it now and they'll reconcile later —
  the customer is served, but for a while the two branches disagree on the count (they might oversell).

**Why it matters.** It forces an honest design decision: **during a network failure, do you prefer
to stay correct or stay up?** Banks lean **CP** (correctness first — better to decline than
double-spend). Social feeds lean **AP** (availability first — better to show a slightly stale feed
than an error). "Eventual consistency" is the AP promise that the copies will agree *eventually*.

**Common misunderstanding.** CAP is only about behavior **during a partition**. When the network is
healthy, you can have both strong consistency *and* availability — the trade-off only bites when
things break.

**In TrialReads.** The database is a **single primary Postgres** (Supabase), so it isn't a
partition-tolerant multi-node system — it leans toward **consistency** (one source of truth). CAP
becomes a real decision only if you scale out with **read replicas** (copies of the data): then a
replica might be slightly behind the primary, and you'd choose whether to serve possibly-stale reads
(favor availability) or force reads to the up-to-date primary (favor consistency). That's the classic
trade-off the theorem describes.

---

*More terms will be appended below as you send them.*
