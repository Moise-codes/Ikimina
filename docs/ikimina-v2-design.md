# Ikimina Platform - v2 Design Document (SRS, Technical Proposal, Architecture, Data Dictionary)

> This is the authoritative design document for the v2 backend. Where the build
> instructions and this document differ, the difference is recorded in `docs/adr/`.
> Original source: "Ikimina.pdf" (Nov 14, 2026).

---

Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




  Ikimina Platform: SRS, Technical Proposal,
  System Architecture and Database Design
    Nov 14, 2026         ·   ​@Moses

  Ikimina Platform is a production backend API that records savings-group (ikimina)
  members, roles, contributions in Rwandan francs (RWF), loans and repayments for groups
  in Rwanda, built on Python, FastAPI, PostgreSQL and SQLAlchemy.

  The document covers the requirements evaluation, the Software Requirements
  Specification, the technical proposal, the system architecture, and the database design
  with ERD and data dictionary.


  1. Requirements Evaluation and Real-Data Risks
  The system can prove that a person controls a phone number, but it cannot prove who
  that person legally is, so identity rests on SMS verification plus in-person confirmation by
  the group leaders.


  1.1 Problem and objective
  Ikimina groups in Rwanda track contributions and loans in notebooks and chat groups,
  which causes arithmetic errors, lost history and disputes. The platform replaces the
  notebook with a secure, auditable record: who belongs to the group, who holds which
  role, what each person contributed, who borrowed and what remains to be repaid.


  1.2 What can and cannot be verified

     Data                                       Verifiable?                          Decision

     Phone number format                        Yes, by rule: Rwandan mobile         Normalize to E.164
                                                prefixes 072, 073 (Airtel) and       +2507XXXXXXXX ; reject everything
                                                078, 079 (MTN)                       else

     Phone number exists                        Only by sending an SMS               One-time password (OTP)
     and is reachable                                                                verification; phone_verified_at
                                                                                     is set on success




                                                                                                                  Page 1 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Data                                       Verifiable?                          Decision

     Name of the phone's                        No public source; only               Not attempted. Leaders confirm
     owner                                      operators hold it, under Law         each member in person
                                                N° 058/2021

     Email                                      Format by rule; ownership by         Optional; verified by a link
                                                link or code

     National ID (NIDA)                         Only licensed institutions           Not collected in version 1 (data
                                                may verify                           minimization)

     Full name                                  Not verifiable                       Stored as given, trimmed and
                                                                                     length-checked

     Money amounts                              Yes, by rules                        Integer RWF with limits

     Payment dates                              Yes                                  Stored in UTC; not in the future

     Who actually paid                          Not provable by software             Treasurer records; ledger is
                                                                                     immutable; member can see and
                                                                                     dispute each entry; every action
                                                                                     audited



  1.3 Limits of the system
         The platform records payments; it does not move money. Mobile money integration is
         a later phase.
         It proves control of a SIM, not legal identity.
         Trust comes from transparency: members see their own history, nothing is deleted,
         and every change is in the audit log.


  1.4 Legal and privacy considerations
         Law N° 058/2021 on the protection of personal data and privacy applies: collect only
         what is needed, record consent, secure the data, honour correction and deletion
         requests where the law allows.
         Financial records must survive account deletion, so personal fields are anonymized
         while ledger rows stay.
         Cross-border transfer of personal data is restricted by the same law: hosting location
         and any foreign SMS or monitoring provider must be reviewed before launch.




                                                                                                                    Page 2 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




         Registration or notification duties with the National Cyber Security Authority (NCSA)
         must be confirmed with a Rwandan legal adviser before public launch. This document
         does not settle them.


  1.5 Risk register

     Risk                                                Impact                      Mitigation

     Treasurer records a false                           Money disputes              Immutable ledger, reversal entries,
     payment                                                                         member visibility, dispute flow, audit
                                                                                     log

     Same person registered                              Duplicate identities        Unique constraint on normalized
     twice                                                                           phone

     SMS cost abuse and OTP                              Financial loss,             Per-phone and per-IP rate limits, daily
     guessing                                            takeover                    SMS cap, hashed OTP, 5 attempts

     Lost phone or SIM swap                              Account takeover            Short-lived access tokens, rotating
                                                                                     refresh tokens, OTP re-verification for
                                                                                     sensitive actions

     Concurrent writes corrupt                           Wrong pot or loan           Row locks, transactions, idempotency
     balances                                            balance                     keys, database constraints

     Floating-point rounding                             Wrong money                 Integers only

     Leader leaves                                       Group without a             Leadership transfer flow; database
                                                         president                   rule of exactly one active president

     Personal data leak                                  Legal and trust             Encryption in transit and at rest,
                                                         damage                      minimal data, role checks, no personal
                                                                                     data in logs

     Provider outage (SMS,                               Users blocked               Outbox with retries, provider
     hosting)                                                                        interface, backups, health checks




  2. Software Requirements Specification (SRS)
  Version 1 delivers a JSON REST API for Rwandan savings groups covering accounts,
  groups, roles, contributions, loans, reports and audit; it excludes payments, ID
  verification, other countries and the user interface.



                                                                                                                         Page 3 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




  2.1 Purpose and scope
  In scope: users and authentication, groups and memberships, contributions ledger, loans
  and repayments, reports, audit log, SMS notifications.

  Out of scope for v1: mobile money payments, NIDA verification, multi-currency, multi-
  country, web and mobile frontends, PDF statements.


  2.2 Stakeholders and roles

     Role                          Kinyarwanda                                 Responsibility

     Platform                      Umuyobozi wa                                Operations and support only; cannot edit
     admin                         sisitemu                                    ledgers

     President                     Perezida                                    One per group. Manages members and rules,
                                                                               decides on loans

     Treasurer                     Umubitsi                                    At most one per group. Records contributions
                                                                               and repayments

     Member                        Umunyamuryango                              Views own history and group summary, requests
                                                                               loans


  Roles belong to the membership (user in a group), so one person can be president of one
  group and a member of another.


  2.3 Functional requirements
  Authentication and accounts


     ID               Requirement

     FR-A1            A user registers with full name, phone number and
                      password; email is optional.

     FR-A2            The system normalizes and validates Rwandan
                      phone numbers (section 2.5).

     FR-A3            The system sends a 6-digit OTP by SMS to verify
                      the phone.

     FR-A4            A user logs in with phone and password only after
                      the phone is verified.



                                                                                                                          Page 4 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     ID               Requirement

     FR-A5            Login issues a 15-minute access token and a
                      rotating refresh token; reuse of a spent refresh
                      token revokes the whole token family.

     FR-A6            A user can log out of one session or of all sessions.

     FR-A7            Password reset uses an OTP sent to the verified
                      phone and revokes all sessions.

     FR-A8            A user can update the profile; changing the phone
                      requires OTP verification of the new number.

     FR-A9            A user can add an email and verify it by link.

     FR-A10           Repeated failed logins lock the account
                      temporarily.


  Groups and memberships


     ID              Requirement

     FR-G1           A verified user creates a group and becomes its
                     president.

     FR-G2           A group has name, description, location (district,
                     sector), default contribution (RWF), frequency
                     (weekly, biweekly, monthly), contribution day, loan
                     interest rate and status.

     FR-G3           The president adds a member by phone. If no
                     account exists, an invitation is stored and linked
                     when the person registers.

     FR-G4           A membership has role, status (invited, active,
                     suspended, left), join date and an optional personal
                     suggested contribution.

     FR-G5           The president assigns the treasurer role and can
                     transfer the presidency.

     FR-G6           The president can suspend or remove a member;
                     financial history stays.




                                                                                     Page 5 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     ID              Requirement

     FR-G7           A user can belong to many groups with a different
                     role in each.

     FR-G8           Changing group rules affects future periods only.


  Contributions


     ID              Requirement

     FR-C1           The treasurer records a contribution: member,
                     period, amount, payment date, method (cash, MTN
                     MoMo, Airtel Money, bank) and optional reference.

     FR-C2           Contributions are immutable. A correction is a
                     reversal entry linked to the original, followed by a
                     new entry.

     FR-C3           The system computes expected versus paid per
                     member and period and lists late members.

     FR-C4           Members see their own entries; leaders see all
                     entries of their group.

     FR-C5           A member can dispute an entry; leaders see open
                     disputes and resolve them.

     FR-C6           Write endpoints accept an Idempotency-Key so
                     retries never duplicate an entry.


  Loans and repayments


     ID             Requirement

     FR-L1          A member requests a loan: amount, purpose,
                    number of months.

     FR-L2          The system checks the amount against the
                    available pot and the group's loan limit, and that
                    the member has no overdue loan.

     FR-L3          A leader other than the borrower approves or
                    rejects; decision, reason and time are recorded.



                                                                                     Page 6 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     ID             Requirement

     FR-L4          On approval a repayment schedule is generated
                    with principal and interest in whole RWF.

     FR-L5          The treasurer records repayments; each reduces
                    the outstanding balance; overpayment is rejected.

     FR-L6          Loan states: requested, approved, rejected,
                    disbursed, repaid, overdue, written_off, with only
                    valid transitions allowed.


  Reports, audit and notifications


     ID              Requirement

     FR-R1           Group summary: total contributed, loaned out,
                     repaid, interest earned, available pot.

     FR-R2           Member statement: contributions, loans,
                     repayments and balance for a date range.

     FR-R3           Late-members report per period.

     FR-R4           CSV export of statements (PDF in a later release).

     FR-U1           Every create, update and permission-relevant
                     action writes an audit entry: actor, action, entity,
                     before and after, IP, request id.

     FR-U2           SMS notifications for payment recorded, loan
                     decision and upcoming due date, sent through a
                     retrying outbox.



  2.4 Non-functional requirements

     ID               Category                           Requirement

     NFR-1            Security                           Passwords hashed with argon2id; OTPs and refresh
                                                         tokens stored only as hashes; HTTPS only; secrets
                                                         from environment or a secret manager.




                                                                                                             Page 7 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     ID               Category                           Requirement

     NFR-2            Authorization                      Role checks on every request, server side; a user
                                                         reaches only groups they belong to.

     NFR-3            Integrity                          Money is integer RWF; ledgers are immutable at
                                                         database level; multi-row changes run in
                                                         transactions with constraints as the last defence.

     NFR-4            Performance                        95% of read requests under 300 ms with 1,000
                                                         groups and 1,000,000 ledger rows; every query
                                                         path indexed.

     NFR-5            Availability                       Target 99.5% monthly; health and readiness
                                                         endpoints; graceful shutdown; zero-downtime
                                                         migrations.

     NFR-6            Recoverability                     Daily encrypted backups, point-in-time recovery,
                                                         restore tested quarterly; RPO 15 minutes, RTO 4
                                                         hours.

     NFR-7            Privacy                            Minimal personal data; no personal data in logs;
                                                         consent recorded; anonymization on deletion.

     NFR-8            API quality                        Versioned under /api/v1 ; one response envelope;
                                                         stable machine-readable error codes; pagination;
                                                         OpenAPI published.

     NFR-9            Maintainability                    Layered code, full type hints, lint and type checks
                                                         in CI, at least 85% coverage of services.

     NFR-10           Observability                      Structured JSON logs with request id, metrics,
                                                         error tracking, alerts.

     NFR-11           Abuse protection                   Rate limits per IP and per user; stricter on login and
                                                         OTP routes.

     NFR-12           Localization                       Times stored in UTC and presented in Africa/Kigali;
                                                         message catalogues for Kinyarwanda, English,
                                                         French.




                                                                                                                  Page 8 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




  2.5 Data validation rules

     Field                                    Rule

     Phone                                    Accepts 0788123456 , 788123456 , 250788123456 ,
                                              +250788123456 , ignoring spaces and dashes; must
                                              match ^\+250(72|73|78|79)\d{7}$ ; stored as
                                               +250788123456

     Email                                    Valid format, lowercase, maximum 254 characters,
                                              unique when present

     Password                                 8 to 128 characters, not the phone number, not on a
                                              common-password list

     Full name                                2 to 100 characters, trimmed, letters, spaces,
                                              apostrophes and hyphens

     Contribution amount                      Integer RWF, 100 to 100,000,000

     Loan principal                           Positive integer RWF within the pot and group loan
                                              limit

     Interest rate                            Basis points per month, 0 to 5,000

     Loan term                                1 to 36 months

     Payment date                             Not in the future; not before the group was created

     Group name                               3 to 80 characters, unique per creator

     OTP                                      6 digits, valid 5 minutes, maximum 5 attempts,
                                              single use



  2.6 Business rules
         BR-1: Each active group has exactly one active president and at most one active
         treasurer.
         BR-2: A user has at most one non-left membership per group.
         BR-3: A loan cannot be approved by its borrower.
         BR-4: Ledger rows are never updated or deleted; corrections are reversals.
         BR-5: Approved principal plus outstanding loans cannot exceed the available pot.
         BR-6: A member with an overdue loan cannot request another.



                                                                                                    Page 9 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




         BR-7: Rule changes apply from the next period.
         BR-8: Removed members keep their history.
         BR-9: Interest is simple interest per month on the original principal, rounded half up to
         whole RWF.


  2.7 Assumptions and constraints
         Users own a Rwandan mobile number and can receive SMS.
         Version 1 is single-currency (RWF) and single-country.
         Group money stays physically with the group; the system only records it.
         An SMS provider with MTN and Airtel Rwanda coverage will be contracted.


  2.8 Acceptance criteria (examples)
         AC-1: Registering with 0788123456 and then +250788123456 yields one normalized
         phone; the second attempt returns a generic conflict without revealing account
         details.
         AC-2: Login before OTP verification returns PHONE_NOT_VERIFIED .
         AC-3: Two simultaneous requests with the same Idempotency-Key create one ledger
         row.
         AC-4: A member cannot read another member's loan unless they lead the same group.
         AC-5: An attempt to update or delete a contribution row fails, including through direct
         SQL, because of the database trigger.
         AC-6: Two concurrent loan approvals cannot together exceed the available pot.



  3. Technical Proposal
  The platform is built as a modular monolith on FastAPI and PostgreSQL, with an
  asynchronous SQLAlchemy 2 data layer, Alembic migrations, a Redis-backed rate limiter
  and an outbox-driven worker, delivered in containers through a CI/CD pipeline.


  3.1 Goals
         Correct money handling: integers, immutable ledgers, constraints enforced by the
         database.
         Secure by default: hashed credentials, verified phones, role checks, audit trail.




                                                                                             Page 10 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




         Operable in production: health checks, metrics, structured logs, backups, repeatable
         deployments.
         Ready for a frontend: stable, versioned, documented API.


  3.2 Technology stack

     Concern                               Choice                                    Reason

     Language                              Python 3.12                               Mature ecosystem, strong
                                                                                     typing support

     API framework                         FastAPI                                   Async, type-driven validation,
                                                                                     generated OpenAPI

     Validation and                        Pydantic v2, pydantic-settings            Strict models; typed
     settings                                                                        configuration validated at
                                                                                     startup

     Database                              PostgreSQL 16                             ACID transactions, constraints,
                                                                                     partial unique indexes, row
                                                                                     locking, point-in-time recovery

     ORM and driver                        SQLAlchemy 2.x (async) with               Explicit unit of work, typed
                                           asyncpg                                   mappings, fast driver

     Migrations                            Alembic                                   Versioned, reviewable schema
                                                                                     changes

     Authentication                        PyJWT, argon2-cffi                        Signed short-lived tokens;
                                                                                     modern password hashing

     Cache and limits                      Redis                                     Atomic counters for rate limiting
                                                                                     and OTP throttling

     Background work                       Outbox table plus a worker                No message broker to run;
                                           process using FOR UPDATE SKIP             reliable retries; can move to
                                           LOCKED                                    Celery or ARQ later

     SMS                                   Provider adapter (Africa's Talking,       Provider chosen after delivery
                                           Pindo or Twilio)                          and price tests on MTN and
                                                                                     Airtel Rwanda




                                                                                                                     Page 11 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Concern                               Choice                                    Reason

     Server                                Gunicorn with Uvicorn workers             Process supervision, TLS
                                           behind a reverse proxy (Caddy or          termination
                                           Nginx)

     Packaging                             uv, Docker multi-stage images             Reproducible builds, small
                                                                                     images

     Quality                               ruff, mypy (strict), pre-commit           Style and type safety

     Testing                               pytest, pytest-asyncio, httpx,            Tests run against the real
                                           Testcontainers (real PostgreSQL),         database engine
                                           Hypothesis for money and phone
                                           logic

     Observability                         structlog, Prometheus metrics,            Diagnose production issues
                                           OpenTelemetry traces, Sentry

     CI/CD                                 GitHub Actions                            Lint, types, tests, image build,
                                                                                     deploy

     Hosting                               Containers on a cloud VM or               Location to be settled with the
                                           managed container service with            data-protection review in 1.4
                                           managed PostgreSQL



  3.3 Key technical decisions
     1. Money as BIGINT RWF in the database, int in Python, integer in JSON.
     2. Immutable ledgers enforced by triggers; balances computed from rows and
        reconciled by a nightly job.
     3. Layered modular monolith: router, service, repository per feature; one deployable
        unit.
     4. Roles on memberships, checked by one reusable authorization dependency.
     5. Constraints as the last defence: foreign keys, CHECK , unique and partial unique
         indexes.
     6. Serialized pot changes: loan approval and ledger writes lock the group row ( SELECT
         ... FOR UPDATE ).
     7. Idempotency keys on every money-writing endpoint.
     8. Transactional outbox for SMS: the message is stored in the same transaction as the
        business change.


                                                                                                                   Page 12 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     9. One error envelope with stable error codes.
   10. UTC everywhere, converted at the presentation edge.
   11. Expand-and-contract migrations so deployments need no downtime.


  3.4 Environments and delivery pipeline

     Environment                Purpose                                                 Data

     Local                      Development with Docker Compose                         Synthetic
                                (PostgreSQL, Redis, mail and SMS fakes)

     CI                         Every pull request: lint, type check, unit and          Ephemeral
                                integration tests, migration check, image build,
                                dependency and image vulnerability scan

     Staging                    Release candidate, load and security testing            Synthetic only

     Production                 Live groups                                             Real, encrypted, backed
                                                                                        up


  The pipeline runs on every merge: tests, build, scan, push image, run migrations, roll out
  with health-check gating and automatic rollback.


  3.5 Delivery phases (planning estimates for one full-time developer)

     Phase          Content                                                          Estimate

     0              Repository, configuration, Docker Compose, CI,                   1 week
                    health checks, logging, error envelope

     1              Users, phone normalization and validation,                       1 to 2 weeks
                    password hashing, first migrations

     2              OTP, SMS adapter and outbox, login, JWT, refresh                 2 weeks
                    rotation, rate limits

     3              Groups, memberships, roles, invitations                          1 to 2 weeks

     4              Contributions ledger, reversals, disputes,                       2 weeks
                    idempotency

     5              Loans, schedules, repayments, state machine                      2 weeks




                                                                                                            Page 13 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Phase          Content                                                                    Estimate

     6              Reports and CSV export                                                     1 week

     7              Audit log, notifications, reminders, hardening                             1 to 2 weeks

     8              Load test, security review, backups, production                            1 to 2 weeks
                    deployment

     9              Frontend                                                                   Separate plan



  3.6 Deliverables
  Source repository, versioned OpenAPI specification, Alembic migration history,
  automated test suite, Dockerfiles and Compose files, CI/CD pipeline, runbook (deploy,
  rollback, restore), and this document kept current.


  3.7 Technical risks

     Risk                                                            Mitigation

     SMS delivery gaps on one operator                               Provider adapter, resend limits, delivery reports,
                                                                     second provider option

     Concurrency bugs in money flows                                 Row locks, constraints, concurrent integration
                                                                     tests

     Schema change breaks production                                 Expand-and-contract migrations, migration check
                                                                     in CI, staging rehearsal

     Scope growth                                                    Phase plan; new ideas go to a backlog with a
                                                                     change process

     Single-region hosting outage                                    Backups with point-in-time recovery, documented
                                                                     restore, optional standby later




  4. System Architecture
  The system is one stateless API service backed by one PostgreSQL database, with a
  separate worker process for outbound SMS and scheduled jobs, so it is simple to operate
  and can scale horizontally.



                                                                                                                          Page 14 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




  4.1 Architectural style
  A modular monolith with strict layers. Features are separate packages with explicit
  boundaries, deployed as one unit. A feature can later be extracted into a service if load or
  team size requires it.


  4.2 System overview
  Clients reach the API through a reverse proxy that terminates TLS. The API holds all
  business rules and talks to PostgreSQL and Redis. The worker reads the outbox from
  PostgreSQL and calls the SMS provider.




  system architecture · 1 API service, 1 worker, 2 data stores

  Only the repositories touch SQL; the worker and the API never call each other directly and
  meet only through the database.




                                                                                         Page 15 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




  4.3 Layers and dependency rules

     Layer                   Responsibility                                                Must not

     Router                  Parse and validate input with Pydantic,                       Contain business rules or
                             authenticate, call a service, shape the response              SQL

     Service                 Business rules, permission checks, transaction                Import FastAPI or build SQL
                             boundaries, idempotency

     Repository              All SQLAlchemy queries for one aggregate                      Make business decisions

     Model                   SQLAlchemy table mappings and constraints                     Contain I/O


  Dependencies point downward only: router to service to repository to model.


  4.4 Project structure

     ikimina/
     ├── app/
     │       ├── main.py                                        application factory, middleware, routers
     │   ├── core/                                              config, database, security, errors, logging,
     dependencies
     │       ├── common/                                        money, phone, pagination, response envelope,
     clock
     │       ├── auth/                                          router, service, otp, tokens, schemas
     │       ├── users/                                         router, service, repository, models, schemas
     │       ├── groups/                                        groups and memberships
     │       ├── contributions/                                 ledger, reversals, disputes
     │       ├── loans/                                         loans, schedules, repayments
     │       ├── reports/                                       read-only queries
     │       ├── audit/                                         audit writer and queries
     │       ├── notifications/                                 outbox writer, templates
     │   └── integrations/sms/                                  interface, fake sender, provider adapter
     ├── worker/                                                outbox dispatcher, scheduled jobs
     ├── migrations/                                            Alembic revisions
     ├── tests/                                                 unit, integration, concurrency, contract
     ├── docker/                                                Dockerfile, compose files
     ├── pyproject.toml
     └── .github/workflows/




                                                                                                                 Page 16 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




  4.5 Request flow: recording a contribution
     1. The proxy forwards the request; middleware assigns a request id and starts a trace.
     2. The rate limiter checks Redis counters for the user and IP.
     3. The authentication dependency verifies the access token and loads the user.
     4. The authorization dependency confirms the user is the active treasurer of this group.
     5. Pydantic validates amount, period, date and method.
     6. The service opens a transaction, locks the group row, checks the idempotency key
        and membership status.
     7. The repository inserts the ledger row; the service writes the audit entry and an
         outbox message for the SMS.
     8. The transaction commits; the response envelope is returned and stored against the
        idempotency key.




                                                                                           Page 17 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




  4.6 Cross-cutting design

     Concern                               Design

     Response envelope                     Success: { "data": ..., "pagination": ... } .
                                           Error: { "statusCode": 409, "error": {
                                           "code": "...", "message": "..." } }

     Authorization                          require_role(group_id, roles) dependency
                                           reads the membership row

     Errors                                Domain exception classes mapped to error codes
                                           by one handler

     Logging                               JSON with request id and user id; phone numbers
                                           masked ( +250788***456 )

     Configuration                         Environment variables validated at startup; the app
                                           refuses to start on bad config

     Time                                   timestamptz in UTC; Africa/Kigali applied in
                                           reports and messages

     Versioning                            Routes under /api/v1 ; breaking changes go to
                                            /api/v2

     Transactions                          One database session per request; the service
                                           commits once



  4.7 Security architecture
         Access token lifetime 15 minutes; refresh token 30 days, stored hashed, rotated on
         every use, with reuse detection by token family.
         Argon2id for passwords; OTPs stored as HMAC with a server secret.
         Rate limits and lockouts on login and OTP routes; generic messages so account
         existence is not revealed.
         CORS limited to known frontend origins; security headers set; request size limits at
         the proxy.
         Database access through a least-privilege role; the application role cannot alter
         schema or disable triggers.
         Secrets from environment or a secret manager; encrypted backups; TLS to
         PostgreSQL and Redis.


                                                                                                 Page 18 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




         Dependency and container image scanning in CI.


  4.8 Background processing
  SMS messages and other side effects are written to an outbox_messages table inside the
  business transaction. The worker claims rows with FOR UPDATE SKIP LOCKED , sends
  through the provider adapter, records the outcome and retries with backoff. Scheduled
  jobs handle due-date reminders, expired OTP and token cleanup, overdue loan marking
  and the nightly ledger reconciliation.


  4.9 Deployment and operations
         Docker images built in CI and deployed with health-gated rollout; /health for
         liveness and /health/ready for readiness (database and Redis reachable).
         Migrations run as a separate release step before the new version takes traffic.
         Metrics for request rate, latency, errors, database pool use and outbox backlog, with
         alerts on error rate, latency, failed SMS and backup failures.
         Automated daily backups with point-in-time recovery and a documented, rehearsed
         restore.



  5. Database Design
  The relational schema has 14 tables in PostgreSQL 16, with every business rule that can be
  enforced by the database (keys, checks, unique and partial unique indexes, triggers)
  enforced there, not only in application code.


  5.1 Design principles

     Principle                    Rule

     Identifiers                   uuid primary keys, generated by the application
                                  (UUIDv7, time-ordered)

     Money                         bigint whole RWF; CHECK constraints on sign
                                  and range

     Time                          timestamptz , stored in UTC; date only for
                                  calendar dates such as due dates




                                                                                           Page 19 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Principle                    Rule

     Enumerations                  text with CHECK (... IN (...)) , which migrate
                                  more easily than native enum types

     Naming                        snake_case , plural table names, <table>_id
                                  foreign keys, created_at and updated_at on
                                  mutable tables

     Ledgers                       contributions and repayments are append-only,
                                  protected by triggers that reject UPDATE and
                                   DELETE

     Deletion                     No hard deletes of business rows; users are
                                  anonymized, memberships are marked left

     Foreign keys                  ON DELETE RESTRICT for business tables, so
                                  history can never be orphaned

     Migrations                   Alembic, reviewed in pull requests, expand-and-
                                  contract



  5.2 Entity relationship diagram
  The diagram shows the core business tables; the rule history table (group_rule_versions)
  hangs off groups. Contributions, loans and repayments also store group_id to keep
  reports fast. The five platform tables (OTP challenges, refresh tokens, audit logs,
  idempotency keys, outbox messages) support security and reliability.




                                                                                        Page 20 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




  entity relationship diagram · 8 core tables and the platform band

  Read each line as one-to-many (1 to N). Contributions, loans and repayments hang off a
  membership, so history survives when a member leaves the group.


  5.3 Relationships

     Relationship                                              Cardinality           Notes

     users to memberships                                      1 to N                A user can be in many groups

     groups to memberships                                     1 to N                A group has many members

     users to groups                                           N to M through        The role lives on the membership
                                                               memberships




                                                                                                                Page 21 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Relationship                                              Cardinality           Notes

     memberships to contributions                              1 to N                Each entry belongs to one
                                                                                     member and one period

     contributions to contributions                            1 to 0..1             A reversal points to the original
                                                                                     through reverses_id

     contributions to                                          1 to N                A member can raise a dispute;
     contribution_disputes                                                           leaders resolve it

     memberships to loans                                      1 to N                A member can borrow many
                                                                                     times over time

     loans to loan_schedule_items                              1 to N                One installment per row

     loans to repayments                                       1 to N                Repayments reduce the
                                                                                     outstanding balance

     users to platform tables                                  1 to N                Security and audit records

     groups to group_rule_versions                             1 to N                One row per rule change;
                                                                                     expected amounts for a period
                                                                                     use the version in force



  5.4 Integrity rules enforced in the database
         One membership per user per group while not left : partial unique index.
         Exactly one active president and at most one active treasurer per group: two partial
         unique indexes.
         Ledger sign rule: payment rows have a positive amount; reversal rows have a
         negative amount and a reverses_id ; one reversal per original (unique on
          reverses_id ).

         Immutable ledgers: BEFORE UPDATE OR DELETE triggers on contributions ,
          repayments and audit_logs raise an error.
         A loan's borrower cannot be its approver: CHECK (decided_by_membership_id <>
         membership_id) .
         Principal, interest and amounts: range CHECK constraints matching the SRS validation
         rules.
         Phone format: CHECK (phone ~ '^\+250(72|73|78|79)[0-9]{7}$') .
         The application database role has no permission to alter schema or disable triggers.



                                                                                                                   Page 22 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




  5.5 Indexes

     Table                                    Index                                  Purpose

     users                                    unique phone ; unique lower(email)     No duplicates; login
                                              where email is not null                lookup

     memberships                              unique (group_id, user_id) where       One live membership per
                                              status <> 'left'                       group

     memberships                              unique (group_id) where role =         One president
                                              'president' and status = 'active'

     memberships                              unique (group_id) where role =         One treasurer
                                              'treasurer' and status = 'active'

     memberships                               (user_id, status) ; unique            My groups; no duplicate
                                               (group_id, invited_phone) where       invites
                                              status = 'invited'

     contributions                             (group_id, period,                    Expected versus paid;
                                              membership_id) ; (membership_id,       statements
                                              paid_at desc)

     contributions                            unique (group_id,                      Safe retries; one reversal
                                              idempotency_key) where key is not
                                              null; unique (reverses_id) where not
                                              null

     loans                                     (group_id, status) ;                  Pot and overdue checks
                                               (membership_id, status)

     loan_schedule_items                      unique (loan_id, installment_no) ;     Schedule; reminder job
                                               (due_date) where paid_rwf <
                                              total_rwf

     repayments                                (loan_id, paid_at)                    Loan history

     otp_challenges                            (phone, purpose, created_at           Throttling; cleanup
                                              desc) ; (expires_at)

     refresh_tokens                           unique (token_hash) ; (user_id) ;      Rotation; revocation;
                                              (family_id) ; (expires_at)             cleanup




                                                                                                             Page 23 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Table                                    Index                                        Purpose

     audit_logs                                (group_id, created_at desc) ;               Timelines
                                               (actor_user_id, created_at desc) ;
                                               (entity_type, entity_id)

     idempotency_keys                         unique (user_id, key) ;                      Retries; cleanup
                                               (created_at)

     outbox_messages                           (status, next_attempt_at) where             Worker polling
                                              status in ('pending','failed')



  5.6 Transactions and concurrency
         Each request runs in one transaction. Money-writing services first lock the group row
         with SELECT ... FOR UPDATE , which serializes anything that changes the pot.
         Loan approval recomputes the available pot after taking the lock, so two approvals
         cannot spend the same money.
         Idempotency: the unique (user_id, key) row is inserted first; a duplicate returns
         the stored response.
         The outbox row is written in the same transaction as the business change, so an SMS
         is never sent for a change that rolled back.
         Default isolation READ COMMITTED ; SERIALIZABLE is reserved for the nightly
         reconciliation if needed.


  5.7 Backup, retention and reconciliation

     Data                                            Retention

     Ledgers, loans, audit logs                      Kept for the life of the group plus the legally
                                                     required period (to be confirmed with legal advice)

     OTP challenges                                  Deleted after 24 hours

     Refresh tokens                                  Deleted 7 days after expiry

     Idempotency keys                                Deleted after 24 hours

     Outbox messages                                 Sent rows archived after 90 days




                                                                                                              Page 24 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Data                                            Retention

     Backups                                         Daily base backup plus continuous WAL archiving;
                                                     30-day point-in-time recovery


  A nightly job recomputes each group's totals from the ledger and alerts if any cached
  figure differs.



  6. Data Dictionary
  This dictionary defines every table and column. All tables are in the public schema.
  Every uuid primary key is named id ; every created_at and updated_at is
   timestamptz in UTC. "Null?" says whether the column accepts NULL.


  6.1 users

     Column                                       Type                       Null?   Description and constraints

     id                                           uuid                       No      Primary key

     full_name                                    varchar(100)               No      2 to 100 characters, trimmed

     phone                                        varchar(13)                Yes     Normalized +2507XXXXXXXX , unique,
                                                                                     format CHECK . Null only when status =
                                                                                     'anonymized'

     phone_verified_at                            timestamptz                Yes     Set when an OTP succeeds

     email                                        varchar(254)               Yes     Lowercase; unique when present

     email_verified_at                            timestamptz                Yes     Set when the link is confirmed

     password_hash                                text                       Yes     Argon2id hash; never returned by the API.
                                                                                     Null when anonymized

     preferred_language                           varchar(2)                 No      rw , en or fr ; default rw

     status                                       text                       No      active , locked , deactivated ,
                                                                                     anonymized ; default active

     is_platform_admin                            boolean                    No      Default false

     privacy_notice_version                       varchar(16)                No      Version of the privacy notice accepted




                                                                                                                         Page 25 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Column                                       Type                       Null?      Description and constraints

     privacy_accepted_at                          timestamptz                No         Consent time

     failed_login_count                           smallint                   No         Default 0; reset on success

     locked_until                                 timestamptz                Yes        Temporary lockout

     last_login_at                                timestamptz                Yes

     anonymized_at                                timestamptz                Yes        Set by the anonymization routine

     created_at,                                  timestamptz                No
     updated_at



  6.2 groups

     Column                                          Type                       Null?     Description and constraints

     id                                              uuid                       No        Primary key

     name                                            varchar(80)                No        3 to 80 characters; unique per creator,
                                                                                          case-insensitive

     description                                     varchar(500)               Yes

     district, sector                                varchar(50)                Yes       Rwandan administrative location,
                                                                                          informational

     default_contribution_rwf                        bigint                     No        100 to 100,000,000

     frequency                                       text                       No        weekly , biweekly , monthly

     contribution_day                                smallint                   No        1 to 7 (weekday) for weekly and
                                                                                          biweekly; 1 to 28 (day of month) for
                                                                                          monthly

     loan_interest_bp                                integer                    No        Basis points per month, 0 to 5000;
                                                                                          default 0

     max_loan_multiple                               smallint                   Yes       Loan cap as a multiple of the member's
                                                                                          total contributions

     status                                          text                       No        active , suspended , closed




                                                                                                                                 Page 26 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Column                                          Type                       Null?      Description and constraints

     rules_version                                   integer                    No         Current version in
                                                                                             group_rule_versions ; starts at 1

     created_by                                      uuid                       No         FK to users

     created_at, updated_at                          timestamptz                No



  6.3 group_rule_versions
  History of a group's rules, so that rule changes affect future periods only. Unique on
   (group_id, version) .


     Column                                                              Type                  Null?     Description and constraints

     id                                                                  uuid                  No        Primary key

     group_id                                                            uuid                  No        FK to groups

     version                                                             integer               No        1, 2, 3 ... per group

     default_contribution_rwf, frequency,                                as in groups                    Snapshot of the rules for
     contribution_day, loan_interest_bp,                                                                 this version
     max_loan_multiple

     effective_from_period                                               varchar(8)            No        First period the version
                                                                                                         applies to, e.g. 2027-04

     changed_by                                                          uuid                  No        FK to users

     created_at                                                          timestamptz           No



  6.4 memberships

     Column                                                Type                      Null?     Description and constraints

     id                                                    uuid                      No        Primary key

     group_id                                              uuid                      No        FK to groups

     user_id                                               uuid                      Yes       FK to users; null while an invitee has
                                                                                               no account




                                                                                                                                    Page 27 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Column                                                Type                      Null?   Description and constraints

     invited_phone                                         varchar(13)               Yes     Normalized phone of the invitee;
                                                                                             CHECK (user_id IS NOT NULL OR
                                                                                             invited_phone IS NOT NULL)

     role                                                  text                      No      president , treasurer , member

     status                                                text                      No      invited , active , suspended ,
                                                                                             left

     suggested_contribution_rwf                            bigint                    Yes     Overrides the group default for this
                                                                                             member

     joined_at, left_at                                    timestamptz               Yes

     added_by_user_id                                      uuid                      No      FK to users: the leader who added
                                                                                             the member

     created_at, updated_at                                timestamptz               No



  6.5 contributions (immutable ledger)

     Column                                   Type                       Null?       Description and constraints

     id                                       uuid                       No          Primary key

     group_id                                 uuid                       No          FK to groups (denormalized for reporting)

     membership_id                            uuid                       No          FK to memberships

     period                                   varchar(8)                 No           2027-03 (monthly) or 2027-W10 (weekly,
                                                                                     biweekly); format CHECK

     type                                     text                       No           payment or reversal

     amount_rwf                               bigint                     No          Positive for payment, negative for reversal;
                                                                                     never 0

     reverses_id                              uuid                       Yes         FK to contributions; required when type =
                                                                                     'reversal' ; unique

     paid_at                                  timestamptz                No           CHECK (paid_at <= created_at)

     method                                   text                       No           cash , mtn_momo , airtel_money , bank




                                                                                                                              Page 28 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Column                                   Type                       Null?       Description and constraints

     reference                                varchar(64)                Yes         Transaction id or receipt number

     recorded_by_user_id                      uuid                       No          FK to users: the treasurer

     idempotency_key                          varchar(64)                Yes         Unique per group when present

     created_at                               timestamptz                No          There is no updated_at : rows never change



  6.6 contribution_disputes

     Column                                                Type                      Null?   Description and constraints

     id                                                    uuid                      No      Primary key

     contribution_id                                       uuid                      No      FK to contributions

     raised_by_membership_id                               uuid                      No      FK to memberships

     reason                                                varchar(500)              No

     status                                                text                      No       open , upheld , rejected ; default
                                                                                              open

     resolved_by_membership_id                             uuid                      Yes     FK to memberships

     resolution_note                                       varchar(500)              Yes

     created_at                                            timestamptz               No

     resolved_at                                           timestamptz               Yes



  6.7 loans

     Column                                               Type                       Null?   Description and constraints

     id                                                   uuid                       No      Primary key

     group_id                                             uuid                       No      FK to groups

     membership_id                                        uuid                       No      FK to memberships: the borrower

     principal_rwf                                        bigint                     No      Greater than 0




                                                                                                                             Page 29 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Column                                               Type                       Null?       Description and constraints

     interest_bp                                          integer                    No          Snapshot of the group rate at
                                                                                                 approval; 0 to 5000

     term_months                                          smallint                   No          1 to 36

     purpose                                              varchar(300)               Yes

     status                                               text                       No          requested , approved , rejected ,
                                                                                                 disbursed , repaid , overdue ,
                                                                                                 written_off

     total_due_rwf                                        bigint                     Yes         Principal plus interest, set at
                                                                                                 approval

     outstanding_rwf                                      bigint                     Yes         Remaining balance, at least 0;
                                                                                                 reconciled nightly against
                                                                                                 repayments

     decided_by_membership_id                             uuid                       Yes         FK to memberships; CHECK
                                                                                                 (decided_by_membership_id <>
                                                                                                 membership_id)

     decided_at                                           timestamptz                Yes

     decision_reason                                      varchar(300)               Yes         Required on rejection

     disbursed_at                                         timestamptz                Yes

     requested_at, updated_at                             timestamptz                No



  6.8 loan_schedule_items

     Column                                         Type              Null?          Description and constraints

     id                                             uuid              No             Primary key

     loan_id                                        uuid              No             FK to loans; unique with installment_no

     installment_no                                 smallint          No             1 to term

     due_date                                       date              No             In Africa/Kigali calendar

     principal_rwf,                                 bigint            No             Zero or more
     interest_rwf



                                                                                                                                   Page 30 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Column                                         Type              Null?          Description and constraints

     total_rwf                                      bigint            No             CHECK (total_rwf = principal_rwf +
                                                                                     interest_rwf)

     paid_rwf                                       bigint            No             Default 0; CHECK (paid_rwf BETWEEN 0 AND
                                                                                     total_rwf)



  6.9 repayments (immutable ledger)

     Column                                               Type                         Null?   Description and constraints

     id                                                   uuid                         No      Primary key

     loan_id                                              uuid                         No      FK to loans

     group_id, membership_id                              uuid                         No      FKs (denormalized for reporting)

     type                                                 text                         No      payment or reversal

     amount_rwf                                           bigint                       No      Positive for payment, negative for
                                                                                               reversal; CHECK (amount_rwf =
                                                                                               principal_part_rwf +
                                                                                               interest_part_rwf)

     principal_part_rwf,                                  bigint                       No      Split of the amount; same sign as
     interest_part_rwf                                                                         the amount

     reverses_id                                          uuid                         Yes     FK to repayments; required for
                                                                                               reversals; unique

     paid_at                                              timestamptz                  No

     method, reference                                    text,                                As in contributions
                                                          varchar(64)

     recorded_by_user_id                                  uuid                         No      FK to users

     idempotency_key                                      varchar(64)                  Yes     Unique per group when present

     created_at                                           timestamptz                  No      No updated_at




                                                                                                                             Page 31 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




  6.10 otp_challenges

     Column                      Type                       Null?         Description and constraints

     id                          uuid                       No            Primary key

     phone                       varchar(13)                No            Normalized phone the code was sent to

     purpose                     text                       No             verify_phone , reset_password , change_phone

     user_id                     uuid                       Yes           FK to users; null during registration before the user
                                                                          row is confirmed

     code_hmac                   text                       No            HMAC-SHA256 of the 6-digit code with a server
                                                                          secret; the code itself is never stored

     attempts                    smallint                   No            Default 0; CHECK (attempts <= 5)

     expires_at                  timestamptz                No            Creation time plus 5 minutes

     consumed_at                 timestamptz                Yes           Set once on success; single use

     request_ip                  inet                       Yes           For abuse control

     created_at                  timestamptz                No



  6.11 refresh_tokens

     Column                   Type                       Null?         Description and constraints

     id                       uuid                       No            Primary key

     user_id                  uuid                       No            FK to users

     family_id                uuid                       No            Links tokens rotated from one login, for reuse
                                                                       detection

     token_hash               char(64)                   No            SHA-256 of the token; unique

     used_at                  timestamptz                Yes           Set when rotated; presenting it again revokes the
                                                                       family

     revoked_at               timestamptz                Yes

     expires_at               timestamptz                No            Creation time plus 30 days




                                                                                                                           Page 32 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Column                   Type                       Null?         Description and constraints

     user_agent               varchar(255)               Yes

     ip                       inet                       Yes

     created_at               timestamptz                No



  6.12 audit_logs (immutable)

     Column                                   Type                      Null?        Description and constraints

     id                                       uuid                      No           Primary key

     actor_user_id                            uuid                      Yes          FK to users; null for system actions

     group_id                                 uuid                      Yes          FK to groups; null for account-level actions

     action                                   varchar(64)               No           For example contribution.recorded ,
                                                                                     loan.approved

     entity_type                              varchar(32)               No           For example contribution , loan ,
                                                                                     membership

     entity_id                                uuid                      No

     before_data,                             jsonb                     Yes          Snapshots with sensitive fields removed
     after_data

     ip                                       inet                      Yes

     request_id                               varchar(64)               Yes          Correlates with logs and traces

     created_at                               timestamptz               No



  6.13 idempotency_keys

     Column                          Type                      Null?         Description and constraints

     id                              uuid                      No            Primary key

     user_id                         uuid                      No            FK to users; unique with key

     key                             varchar(64)               No            Client-supplied




                                                                                                                              Page 33 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     Column                         Type                       Null?         Description and constraints

     request_hash                   char(64)                   No            Detects the same key reused with a different
                                                                             body

     status_code                    smallint                   Yes           Null while the first request is still running

     response_body                  jsonb                      Yes           Stored response returned on replay

     created_at                     timestamptz                No            Rows older than 24 hours are deleted

     completed_at                   timestamptz                Yes



  6.14 outbox_messages

     Column                                    Type                       Null?      Description and constraints

     id                                        uuid                       No         Primary key

     channel                                   text                       No         sms or email

     recipient                                 varchar(254)               No         Normalized phone or email address

     template                                  varchar(64)                No         Message template name

     payload                                   jsonb                      No         Template parameters; no secrets

     status                                    text                       No         pending , sent , failed , dead ; default
                                                                                     pending

     attempts                                  smallint                   No         Default 0; moves to dead after the retry
                                                                                     limit

     next_attempt_at                           timestamptz                No         Worker picks rows due now

     provider_message_id                       varchar(64)                Yes        Provider reference for delivery reports

     last_error                                varchar(500)               Yes

     created_at                                timestamptz                No

     sent_at                                   timestamptz                Yes




                                                                                                                               Page 34 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




  6.15 Enumerations

     Name                                  Values

     role                                  president, treasurer, member

     membership status                     invited, active, suspended, left

     group status                          active, suspended, closed

     user status                           active, locked, deactivated, anonymized

     frequency                             weekly, biweekly, monthly

     ledger type                           payment, reversal

     payment method                        cash, mtn_momo, airtel_money, bank

     dispute status                        open, upheld, rejected

     loan status                           requested, approved, rejected, disbursed, repaid,
                                           overdue, written_off

     OTP purpose                           verify_phone, reset_password, change_phone

     outbox status                         pending, sent, failed, dead

     outbox channel                        sms, email

     language                              rw, en, fr




  7. Open Decisions
  Five decisions must be settled before or during delivery; none blocks the start of Phase 0.


     #           Decision                                                            Needed by

     1           SMS provider: compare delivery on MTN and Airtel                    Phase 2
                 Rwanda, price and API quality

     2           Loan interest method: simple monthly (default in                    Phase 5
                 this document) or reducing balance

     3           Hosting location and managed services, based on                     Phase 8
                 the data-protection review in 1.4



                                                                                                 Page 35 of 36
Ikimina Platform: SRS, Technical Proposal, System Architecture and Database Design




     #           Decision                                                            Needed by

     4           Retention period for financial records, confirmed                   Phase 8
                 by legal advice

     5           Additional group roles (vice president, secretary)                  After v1
                 in a later version




  8. Starting Point
  Phase 0 produces the repository, configuration, Docker Compose environment, CI
  pipeline, health endpoints, logging and the error envelope. Phase 1 then adds the user
  model, phone normalization and validation, and the first Alembic migration.




                                                                                                 Page 36 of 36
