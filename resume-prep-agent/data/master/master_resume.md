# S. SENKATHIRSELVAN
**Python Backend Developer · Enterprise Mail Systems · Distributed & AI Multi-Agent Systems**  
senkathircomp@gmail.com • +91 9080903380 • [linkedin.com/in/senkathirselvan-python-developer](https://linkedin.com/in/senkathirselvan-python-developer) • [github.com/senkathirselvan](https://github.com/senkathirselvan) • Villupuram, Tamil Nadu, India

---

## PROFESSIONAL SUMMARY
Python Backend Developer with **2.5+ years of experience** architecting and maintaining production-grade backend systems, multi-tenant SaaS platforms, enterprise mail infrastructures, and autonomous AI multi-agent systems. Specialized in enterprise mail systems (Stalwart, Frappe Mail, JMAP/IMAP), distributed event streaming, and secure authentication (JWT, OAuth2, Authentik SSO, RFC 6238 TOTP 2FA). Proven track record in asynchronous job processing (Celery, Redis), RESTful API design, WebSockets, Docker containerization, and database performance optimization across MySQL/MariaDB and PostgreSQL. Architected an extensible, hierarchical multi-agent platform orchestrating autonomous job discovery, ATS resume optimization, and automated application workflows.

---

## TECHNICAL SKILLS

- **Languages:** Python, SQL, Bash
- **Backend Frameworks:** FastAPI, Frappe / ERPNext, Flask, Django
- **APIs & Protocols:** RESTful APIs, WebSockets, Server-Sent Events (SSE), JMAP, IMAP, SMTP, DNS (SPF, DKIM, DMARC)
- **AI & Multi-Agent Systems:** Multi-Agent Architecture, NVIDIA NIM / Cloud AI Models (Nemotron-3.5, Llama 3.3), Ollama, FastMCP (Model Context Protocol), Prompt Engineering
- **Auth & Security:** JWT, OAuth2, Authentik SSO, RFC 6238 TOTP 2FA, App Passwords, RBAC, OpenBao / Vault, API Security
- **Databases & Caching:** MySQL, MariaDB, PostgreSQL, SQLite, Redis (caching, event buffering, Redis Streams, pub/sub), Celery
- **Tools & Practices:** GitLab, Git, Swagger/OpenAPI, pytest, Postman, Docker, Docker Compose, Nginx, Linux Server Administration, Code Review, Agile/Scrum
- **Integrations:** Stalwart Mail Server, Frappe Mail API, OpenArchive, ResellerClub, Razorpay, Google Sheets API v4

---

## PROFESSIONAL EXPERIENCE

### **SagaSoft Technologies Pvt. Ltd.** — Villupuram, Tamil Nadu  
**Python Backend Developer (Internship → Full-Time)** | *Mar 2024 – Present*

Core backend developer on **SagaSuite & SagaMail**, an enterprise multi-tenant SaaS ecosystem spanning interconnected microservices for identity, mail administration, subscription billing, event ingestion, compliance archiving, and AI mail workflows. Responsible for end-to-end backend architecture, RESTful API design, database query optimization, and production-ready Linux deployments.

#### **1. Saga-Auth — Authentication & Authorization Module**
- Engineered the complete multi-tenant authentication and identity system covering signup, login, OTP verification, JWT session management, password reset, and strict tenant isolation.
- Integrated **Authentik SSO** and **OAuth2** for enterprise single sign-on.
- Implemented **RFC 6238 TOTP Two-Factor Authentication (2FA)** with QR code provisioning, authenticator app support, and recovery backup codes.
- Architected dedicated **SMTP/IMAP App Password provisioning** with secure hashing, enabling users to connect their custom domain directly into third-party clients (e.g., Gmail "Send Mail As") without paid Google Workspace accounts.
- Resolved a critical OTP race condition causing premature token invalidation, and rebuilt the global exception handler to prevent internal system error leakage across public APIs.

#### **2. Saga-Mail — Enterprise Mail Administration & Domain Platform**
- Developed backend services integrating Frappe Mail APIs with custom administration dashboards, covering mailbox provisioning, user/group/alias management, Forward-Only internal domains, temporary disposable aliases, and tenant-aware storage quotas.
- Implemented **Snooze, Schedule Send, Follow-up Reminders, and Undo Send** over JMAP in the `advance_saga_mail` Frappe app, and resolved a critical JMAP `accountId` resolution bug.
- Integrated **OpenArchive REST APIs** (tenant onboarding, compliance export, auditor management, message search) with per-tenant encryption secrets managed in OpenBao.
- Integrated **ResellerClub** domain purchase and registration with webhook callbacks; built DNS verification (MX, SPF, DKIM, DMARC) and WHOIS validation using Mail Principal Binding as the source of truth.
- Engineered a bulk user-creation pipeline with multi-step CSV validation and `frappe.enqueue` background job processing, supporting batches of **up to 1,000 users per upload**.

#### **3. Saga-Migration — IMAP Email Migration Engine**
- Architected a full-featured, multi-threaded email migration engine supporting Google Workspace (Gmail), Microsoft 365 (Outlook), and any standard IMAP server into the Stalwart Mail Server.
- Built configurable folder selection, date-range filtering, pre-flight IMAP connectivity validation, and mailbox size estimation.
- Delivered real-time migration progress tracking and status feeds via **WebSockets**, with background worker processing, audit logging, failure recovery queues, and complete migration history.

#### **4. Saga-Billing — Subscription & Invoicing Platform**
- Customized ERPNext/Frappe subscription billing to automate the full payment lifecycle — automated monthly recurring invoice generation, pro-rata billing calculations, payment reminder notifications, and penalty logic.
- Designed coupon and discount architecture for invoicing with row-level database locking (`SELECT FOR UPDATE`) to prevent double redemption under high concurrency.
- Co-engineered the `saga_billings` → `saga_auth` → `saga_mail` plan-update pipeline, and integrated the **Razorpay** payment gateway with automated webhook handling.

#### **5. Saga WebSocket Service & Performance Optimization**
- Developed real-time WebSocket backend services in Python for live mail arrival notifications and administrative dashboard updates, enabling concurrent event-driven communication across active tenant sessions.
- Designed and implemented a standalone RESTful API for a **Voice Sample Bank**, supporting multi-criteria filtering by language, gender, and dialect with targeted query indexing for high-performance search.
- Implemented Redis credential and response caching across platform modules, achieving an estimated **~40–60% latency reduction** on warm cache hits, with domain-lookup endpoints reaching **~95–99% latency reduction**.
- Optimized database performance through strategic SQL indexing, query refactoring, and schema tuning on MySQL and MariaDB.

#### **6. SagaMail AI Backend & Mail Event Ingestion Pipeline**
- Architected a distributed email intelligence microservice using **FastAPI, Celery, and Redis** to classify incoming emails and apply native **JMAP/IMAP tags** (e.g., Priority, Invoices, Marketing) directly into Stalwart Mail Server without blocking mail delivery.
- Built a standalone event ingestion service capturing Stalwart webhook streams, buffering events in Redis, and batch-persisting them to PostgreSQL.
- Implemented **distributed span context correlation** across multi-hop email lifecycles using `span_id`, `parent_queue_id`, and `child_queue_id` for accurate delivery tracking, bounce diagnostics, and transient retry monitoring.

---

## PROJECTS

### **Autonomous Hierarchical Multi-Agent Job Platform**
*React 18, Vite, Tailwind CSS, FastAPI, PostgreSQL, SQLite, Celery, Redis, Docker, NVIDIA NIM APIs (Nemotron-3.5, Llama 3.3), Playwright*
- **Modular Multi-Agent Architecture:** Architected a decoupled, extensible multi-agent system designed with a plug-and-play pattern, enabling dynamic registration and coordination of specialized worker agents through standardized event protocols.
- **Single Controlled UI (`agent-ui`):** Built a unified dashboard featuring real-time Server-Sent Events (SSE) token streaming, visual agent step badges (`Searching...`, `Scoring...`, `Tailoring...`), interactive job match scorecards (0–100%), matched/missing keyword chips, and one-click application actions.
- **Central Manager Agent (`manager-agent`):** Built the core FastAPI orchestrator managing session state, event routing, unified API gateways, and inter-agent task delegation.
- **Job-Find-Agent:** Autonomous discovery engine scraping LinkedIn, Indeed, and Naukri using Playwright, python-jobspy, and RESTful APIs; extracts role requirements and normalizes job records into PostgreSQL.
- **Resume-Prep-Agent:** ATS optimization engine powered by NVIDIA NIM API models (Nemotron-3.5, Llama 3.3 70B) that analyzes job descriptions against master profiles, computes compatibility scores, extracts keywords, and compiles tailored resumes into Markdown, DOCX, and PDF formats.
- **Job-Apply-Agent:** Automated application engine executing application workflows across job portals (Naukri, LinkedIn) with a human-in-the-loop review step before final submission.

### **Google Sheets MCP Server (`sheets-mcp`)**
*Python, FastMCP (Model Context Protocol), Google Sheets API v4, OAuth Service Account, Docker*
- Implemented a FastMCP Python server enabling AI agents and LLMs to securely query, write, append, and clear Google Sheets spreadsheet data via Google API v4 and Service Account OAuth.

---

## EDUCATION

**Bachelor of Engineering (B.E.) — Computer Science & Engineering**  
University College of Engineering, Villupuram | *Oct 2021 – Jul 2024*  
*Relevant Coursework:* Data Structures & Algorithms, Database Management Systems, Computer Networks, Operating Systems, Object-Oriented Programming, Software Engineering.

---

## COMMUNITY & OPEN SOURCE

- **VGLUG (Villupuram GNU/Linux Users Group) — Mentor & Contributor:** Organized technical workshops on Python, DevOps, Linux server administration, and FOSS for students and developers. Actively mentored junior developers in backend practices and system administration.
- **Hacktoberfest (2023) & Software Freedom Day (2023 & 2024):** Contributed to open-source GitHub repositories focused on backend APIs, bug fixes, and participated in community-driven Free & Open Source Software code sprints.
- **PyCon India 2023, Hyderabad — Participant:** Attended national Python developer conference, gaining insights into asynchronous Python, FastAPI, and scalable enterprise backend design.
