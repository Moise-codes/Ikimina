# Ikimina API SRS / Technical Proposal (v1, superseded - MongoDB draft)

> HISTORICAL ONLY. This is the earlier draft that proposed MongoDB. It has been
> superseded by `docs/ikimina-v2-design.md`, which specifies PostgreSQL. Kept for
> traceability of requirements evaluation and risk analysis.

---

Ikimina API: SRS, Technical Proposal, Architecture and Database Design




  Ikimina API: SRS, Technical Proposal,
  Architecture and Database Design
  Version 1.0 · Scope: Rwanda only · Currency: RWF · Stack: Python, FastAPI, MongoDB

  This document is the foundation of the project. It has five parts: (1) evaluation of the
  requirements and real-data risks, (2) Software Requirements Specification, (3) Technical
  Proposal, (4) Architecture Design, (5) Database Design with ERD and Data Dictionary.



  1. Evaluation of the Requirements and Real-Data Risks

  1.1 What we are building
  Ikimina API replaces the notebook and WhatsApp used by savings groups. It stores the
  group, its members and their roles, every contribution in Rwandan francs, loans and
  repayments, and reports. A frontend (web or mobile) will be added after the API is
  finished.


  1.2 Real data: what can and cannot be verified
  Because this system will hold real people and real money, every data field was examined
  for what we can truly verify.


     Data                                        Can we verify it?                Decision

     Phone number format                         Yes, by rule (Rwandan mobile     Normalize to E.164
                                                 prefixes 072, 073 Airtel; 078,   +2507XXXXXXXX , reject
                                                 079 MTN)                         everything else

     Phone number exists                         Only by sending an SMS           OTP verification
     and is active                                                                ( phone_verified )

     Phone owner's name                          No public source; only           Do not attempt. Member is
                                                 operators hold it, protected     confirmed in person by the group
                                                 by Law N° 058/2021               leaders

     Email                                       Format only, then ownership      Optional field, verified by link
                                                 by sending a link or code




                                                                                                                     Page 1 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     Data                                        Can we verify it?                Decision

     National ID (NIDA)                          Only licensed institutions can   Do not collect in version 1 (data
                                                 verify                           minimization)

     Full name                                   Cannot be verified               Stored as given, trimmed, length-
                                                                                  checked

     Money amounts                               Yes, by rules                    Integer RWF, positive, with upper
                                                                                  limits

     Dates                                       Yes                              Stored in UTC, shown in
                                                                                  Africa/Kigali, no future-dated
                                                                                  payments

     Group membership                            Social, not technical            Leaders add members; a member
     truth                                                                        must verify their own phone to
                                                                                  log in

     Who paid what                               Not provable by the system       Treasurer records it; entries are
                                                 alone                            append-only and audited;
                                                                                  members can see and dispute
                                                                                  their own entries



  1.3 Honest limits of the system
          The system records payments. It does not move money. Mobile money integration is a
          later phase.
          It can prove that the person logged in controls the phone number. It cannot prove the
          person's legal identity.
          Trust is protected by transparency: every member can see their own history, nothing
          is deleted, and every change is in the audit log.


  1.4 Legal and privacy considerations (Rwanda)
          Law N° 058/2021 on personal data protection applies. We collect only what is needed,
          record consent, protect data, and allow a member to request correction or deletion
          where the law allows.
          Financial records must be kept for accountability, so on account deletion we
          anonymize personal fields but keep ledger entries.




                                                                                                                   Page 2 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




          Anyone deploying this for real groups should confirm registration requirements with
          the National Cyber Security Authority (NCSA) before public launch. This is a legal
          check to do, not something this document can settle.


  1.5 Risks found during evaluation

     Risk                                                       Impact             Mitigation

     Treasurer records a false                                  Money disputes     Append-only ledger, reversal
     payment                                                                       entries, audit log, member can view
                                                                                   own entries, president can review

     Same person registered twice                               Duplicate data     Unique index on normalized phone

     SMS cost abuse                                             Money loss         Rate limit per phone and per IP, daily
                                                                                   SMS cap

     Lost phone or SIM swap                                     Account takeover   Short sessions, refresh token
                                                                                   rotation, re-verify phone for
                                                                                   sensitive actions

     Two requests change the same                               Wrong balances     Atomic updates and transactions,
     data at once                                                                  idempotency keys

     Float rounding                                             Wrong money        Integers only

     Leader leaves the group                                    Group has no       Transfer-leadership flow, rule:
                                                                president          exactly one president

     Personal data leak                                         Legal and trust    Hashing, encryption in transit,
                                                                damage             minimal data, access control, no
                                                                                   sensitive data in logs




  2. Software Requirements Specification (SRS)

  2.1 Purpose and scope
  Define the behaviour of the Ikimina API v1. In scope: users, authentication, groups,
  memberships, contributions, loans, repayments, reports, audit. Out of scope for v1: mobile
  money payments, national ID verification, multi-country support, multi-currency, the
  frontend.



                                                                                                                      Page 3 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




  2.2 Stakeholders and roles

     Role                         Kinyarwanda                            Description

     System                       Umuyobozi wa                           Platform operator; support and oversight only, no
     admin                        sisitemu                               editing of ledgers

     President                    Perezida                               One per group. Manages members and rules,
                                                                         approves loans

     Treasurer                    Umubitsi                               At most one per group. Records contributions
                                                                         and repayments

     Member                       Umunyamuryango                         Sees own history and group summary, requests
                                                                         loans


  Roles are per group, stored on the membership, not on the user.


  2.3 Functional requirements
  Authentication and accounts


     ID              Requirement

     FR-A1           A user registers with full name, phone number and
                     password. Email is optional.

     FR-A2           The system normalizes and validates Rwandan
                     phone numbers (see 2.5).

     FR-A3           The system sends a 6-digit OTP by SMS to verify
                     the phone.

     FR-A4           A user logs in with phone and password, only if the
                     phone is verified.

     FR-A5           The system issues a short-lived access token and a
                     rotating refresh token. Reuse of a used refresh
                     token revokes the session family.

     FR-A6           A user can log out and log out from all devices.

     FR-A7           A user can reset the password through an OTP
                     sent to the verified phone.




                                                                                                                      Page 4 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     ID              Requirement

     FR-A8           A user can view and update own profile. Changing
                     the phone requires OTP verification of the new
                     number.

     FR-A9           A user can add an email and verify it.


  Groups and memberships


     ID              Requirement

     FR-G1           A verified user can create an ikimina and
                     automatically becomes its president.

     FR-G2           A group has name, description, default
                     contribution amount (RWF), frequency (weekly,
                     biweekly, monthly), contribution day, loan interest
                     rate, and status.

     FR-G3           The president can add a member by phone number.
                     If the phone has no account, an invitation is
                     created and the member completes registration.

     FR-G4           Each membership has a role, an optional personal
                     suggested contribution, a join date and a status
                     (invited, active, suspended, left).

     FR-G5           The president can assign the treasurer role to one
                     member and transfer the presidency.

     FR-G6           The president can suspend or remove a member.
                     Financial history stays.

     FR-G7           A user can belong to many groups with a different
                     role in each.

     FR-G8           Changes to group rules apply to future periods
                     only, never to past entries.


  Contributions




                                                                           Page 5 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     ID              Requirement

     FR-C1           The treasurer records a contribution for a member:
                     amount, period, payment date, payment method
                     (cash, MTN MoMo, Airtel Money, bank), optional
                     reference.

     FR-C2           Contributions cannot be edited or deleted. A
                     correction is a reversal entry that links to the
                     original, plus a new entry.

     FR-C3           The system calculates expected versus paid per
                     member per period and flags late members.

     FR-C4           Members can view their own contributions.
                     Leaders can view all.

     FR-C5           A member can flag an entry as disputed; leaders
                     see disputes.

     FR-C6           Recording supports an Idempotency-Key so a retry
                     does not duplicate an entry.


  Loans and repayments


     ID              Requirement

     FR-L1           A member requests a loan with amount, purpose
                     and number of months.

     FR-L2           The system checks that the amount does not
                     exceed the available pot and the group's loan limit,
                     and that the member has no overdue loan.

     FR-L3           The president approves or rejects; the decision
                     and reason are recorded. The president cannot
                     approve own loan; another leader must (treasurer).

     FR-L4           On approval, a repayment schedule is generated
                     with principal and interest in whole RWF.

     FR-L5           The treasurer records repayments. Each reduces
                     the outstanding balance. Overpayment is rejected.




                                                                            Page 6 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     ID              Requirement

     FR-L6           A loan moves through the states requested,
                     approved, rejected, disbursed, repaid, overdue,
                     written_off.


  Reports


     ID              Requirement

     FR-R1           Group summary: total contributed, total loaned,
                     outstanding, available pot.

     FR-R2           Member statement: contributions, loans,
                     repayments, balance.

     FR-R3           Late members list per period.

     FR-R4           Export a statement as CSV or PDF (later phase).


  Audit and notifications


     ID              Requirement

     FR-U1           Every create, change and permission-relevant
                     action writes an audit log entry: who, what, when,
                     before and after, IP.

     FR-U2           SMS notifications for payment recorded, loan
                     decision, and reminder before due date (phase 2).



  2.4 Non-functional requirements

     ID                Category                           Requirement

     NFR-1             Security                           Passwords hashed with argon2id. OTPs stored
                                                          hashed. HTTPS only. Secrets from environment,
                                                          never in code.




                                                                                                          Page 7 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     ID                Category                           Requirement

     NFR-2             Security                           Role-based access checked on every request on
                                                          the server side. Users can reach only groups they
                                                          belong to.

     NFR-3             Integrity                          Money is stored as integer RWF. Ledgers are
                                                          append-only. Multi-document changes use
                                                          transactions.

     NFR-4             Performance                        95% of read requests under 300 ms at 1,000 groups
                                                          and 50,000 ledger entries. Indexes on all query
                                                          paths.

     NFR-5             Reliability                        Idempotent writes, graceful errors, health
                                                          endpoints, daily database backups.

     NFR-6             Privacy                            Minimal personal data, no personal data in logs,
                                                          anonymization on deletion, consent recorded.

     NFR-7             Usability of API                   One response envelope, machine-readable error
                                                          codes, OpenAPI docs, pagination on lists.

     NFR-8             Maintainability                    Layered code, type hints, linting, at least 80% test
                                                          coverage on services.

     NFR-9             Localization                       Times stored in UTC, shown in Africa/Kigali.
                                                          Messages ready for Kinyarwanda, English and
                                                          French.

     NFR-10            Observability                      Structured JSON logs with request id.

     NFR-11            Abuse protection                   Rate limits per IP and per user; stricter on login and
                                                          OTP.



  2.5 Data validation rules (the catalogue)

     Field                          Rule

     Phone                          Accepts 0788123456 , 788123456 ,
                                     +250788123456 , 250788123456 ; strips spaces and
                                    dashes; must match ^\+250(72|73|78|79)\d{7}$ ;
                                    stored as +250788123456




                                                                                                                   Page 8 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     Field                          Rule

     Email                          Valid format, lowercase, max 254 characters,
                                    unique when present

     Password                       8 to 128 characters, not equal to the phone number,
                                    not in a common-password list

     Full name                      2 to 100 characters, trimmed, letters, spaces,
                                    apostrophes, hyphens

     Amount (RWF)                   Integer, 100 to 100,000,000 for contributions;
                                    positive for loans within limits

     Interest rate                  Stored as basis points (integer), 0 to 5,000 (0% to
                                    50%) per month

     Loan term                      1 to 36 months

     Payment date                   Not in the future, not before the group's creation
                                    date

     Group name                     3 to 80 characters, unique per creator

     OTP                            6 digits, expires in 5 minutes, max 5 attempts,
                                    single use



  2.6 Business rules
          BR-1: Exactly one president per active group; at most one treasurer.
          BR-2: A user cannot hold two active memberships in the same group.
          BR-3: A treasurer cannot approve their own loan; a president cannot approve their
          own loan.
          BR-4: Ledger entries are immutable. Corrections use reversals.
          BR-5: Loan principal plus all outstanding loans cannot exceed the available pot.
          BR-6: A member with an overdue loan cannot request a new one.
          BR-7: Rule changes apply from the next period.
          BR-8: A removed member keeps their history; it cannot be deleted.
          BR-9: Interest is simple interest per month on the original principal, rounded to whole
          RWF using a fixed rule (round half up). The group can choose another method later.




                                                                                             Page 9 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




  2.7 Assumptions and constraints
          Users have a Rwandan mobile number and can receive SMS.
          An SMS provider with Rwanda coverage is available (to be chosen in the proposal).
          Version 1 is single-currency (RWF) and single-country.
          Group money physically stays with the group; the system only records it.


  2.8 Acceptance criteria (examples)
          AC-1: Registering with 0788123456 and with +250788123456 creates the same
          normalized phone, and the second attempt fails with PHONE_ALREADY_REGISTERED
          without revealing account details.
          AC-2: A login before OTP verification is refused with PHONE_NOT_VERIFIED .
          AC-3: Two simultaneous attempts to record the same Idempotency-Key create one
          entry.
          AC-4: A member cannot read another member's loan details unless they are a leader
          of the same group.
          AC-5: Attempting to edit a contribution returns 405 or IMMUTABLE_RECORD .



  3. Technical Proposal

  3.1 Goals
  Build a secure, tested, production-ready backend, and learn FastAPI deeply while doing it,
  with a clean path to a later frontend.


  3.2 Technology choices

     Layer                        Choice                                 Why                     Alternative
                                                                                                 considered

     Language                     Python 3.12                            Readable, strong
                                                                         ecosystem

     Framework                    FastAPI                                Async, type-driven      Django REST
                                                                         validation, automatic   (heavier)
                                                                         OpenAPI docs




                                                                                                               Page 10 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     Layer                        Choice                                 Why                          Alternative
                                                                                                      considered

     Validation                   Pydantic v2                            Built into FastAPI, strict
                                                                         models

     Database                     MongoDB 7                              Flexible documents,          PostgreSQL (strong
                                                                         aggregation for reports      for money; see note)

     Driver                       PyMongo async API                      Official driver, matches     Motor (older async
                                                                         your request                 wrapper)

     Auth                         PyJWT plus pwdlib                      Standard and maintained
                                  (argon2)

     Settings                     pydantic-settings                      Typed config from
                                                                         environment

     SMS                          Provider behind an                     Swap providers, fake         Africa's Talking,
                                  SmsSender interface                    sender for tests             Pindo, Twilio (to
                                                                                                      compare)

     Rate limiting                Custom limiter on                      Fewer moving parts to        slowapi
                                  MongoDB first, Redis                   start
                                  later

     Background                   APScheduler first                      Simple, enough for           Celery
     jobs                                                                reminders

     Testing                      pytest, pytest-asyncio,                Standard
                                  httpx

     Quality                      ruff, mypy, pre-commit                 Consistency

     Packaging                    Docker and docker-                     Same environment
                                  compose                                everywhere

     CI                           GitHub Actions                         Free for small projects


  Honest note on MongoDB: financial ledgers often fit relational databases well. MongoDB
  works here if we use integers, transactions on a replica set, and unique indexes. We
  choose it because you want to learn it, and we will design carefully so that it is safe.


  3.3 Key technical decisions
     1. Money as integer RWF everywhere, including the API.


                                                                                                                          Page 11 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     2. Append-only ledger for contributions and repayments; balances are computed, with
          a cached summary updated atomically.
     3. Replica set even in development, so transactions work.
     4. Feature-based modules with router, service, repository inside each.
     5. Roles on membership, checked through a reusable dependency.
     6. Single error envelope and stable error codes.
     7. Idempotency keys on all money-writing endpoints.
     8. Time in UTC, converted at the edge.


  3.4 Delivery phases

     Phase           Content                                             Learning focus

     0               Repo, config, MongoDB replica set, health           FastAPI basics, settings
                     check

     1               Users, phone validator, password hashing            Pydantic, validators,
                                                                         repositories

     2               OTP, SMS sender, login, JWT, refresh rotation       Security, Depends

     3               Groups and memberships, roles                       Authorization, indexes

     4               Contributions ledger, idempotency                   Atomic updates, transactions

     5               Loans and repayments                                State machines, business rules

     6               Reports                                             Aggregation pipelines

     7               Audit log, rate limits, error handling, logging     Cross-cutting concerns

     8               Tests, CI, Docker, deployment                       Quality and operations

     9               Frontend                                            Consuming the API



  3.5 Deliverables
  Working API, OpenAPI documentation, automated tests, Docker setup, CI pipeline, this
  documentation kept up to date, and a README.




                                                                                                    Page 12 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




  3.6 Technical risks

     Risk                                                      Mitigation

     Transactions need a replica set                           Use a single-node replica set locally; Atlas in
                                                               production

     SMS delivery unreliable                                   Provider fallback, resend limits, clear user
                                                               messages

     Scope growth                                              Phases above; anything extra goes to a backlog

     Learning curve                                            Small steps, review after each phase




  4. Architecture Design

  4.1 Style
  A modular monolith with layers. One deployable application, organized by feature, with
  strict boundaries between layers. It is simple to run, simple to learn, and can be split later
  if needed.


  4.2 System context

     [Mobile / Web frontend]                             --HTTPS-->         [Ikimina API (FastAPI)]       -->    [MongoDB]
                                                                                  |
                                                                                  +--> [SMS provider]
                                                                                  +--> [Email provider (optional)]
                                                                                  +--> [Mobile money APIs (future)]



  4.3 Layers

     Router (HTTP)                          parse request, call service, return response
        |
     Service (rules)                        business logic, permissions, transactions
           |
     Repository (data)                      all MongoDB queries; nothing else touches the database
        |
     MongoDB




                                                                                                                       Page 13 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




  Rules: routers never query the database; repositories contain no business rules; services
  never import FastAPI.


  4.4 Project structure

     ikimina/
     ├── app/
     │       ├── main.py
     │       ├── core/                                   config, database, security, errors, logging, deps
     │       ├── common/                                 money, phone, pagination, response envelope
     │       ├── auth/                                   router, service, schemas, otp, tokens
     │       ├── users/                                  router, service, repository, schemas
     │       ├── groups/                                 groups and memberships
     │       ├── contributions/
     │       ├── loans/                                  loans and repayments
     │       ├── reports/
     │       ├── audit/
     │       └── integrations/                           sms (interface, fake, provider)
     ├── tests/                                          unit/ and integration/
     ├── docker-compose.yml
     ├── Dockerfile
     └── pyproject.toml



  4.5 Request flow example: record a contribution
     1. Request arrives with a bearer token and an Idempotency-Key.
     2. Middleware adds a request id and logs it; the rate limiter runs.
     3. Dependency decodes the token and loads the current user.
     4. Dependency checks the user holds the treasurer role in this group.
     5. Pydantic validates the body (amount, period, date, method).
     6. Service checks the membership is active and the period is valid, then opens a
          transaction.
     7. Repository inserts the ledger entry, updates the cached group totals, writes the audit
        entry.
     8. Response envelope is returned; the idempotency record stores the result.




                                                                                                         Page 14 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




  4.6 Cross-cutting design

     Concern                      Design

     Response                     Success: { "data": ..., "pagination": ... } .
                                  Error: { "statusCode": 409, "error": {
                                  "code": "...", "message": "..." } }

     Authorization                Dependency require_role(group_id, roles)
                                  reads the membership

     Errors                       Custom exception classes mapped to error codes
                                  in one handler

     Logging                      JSON logs with request id; phone numbers masked
                                  as +250788***456

     Config                       Environment variables validated at startup

     Time                         UTC in the database; Africa/Kigali in reports

     Versioning                   Routes under /api/v1



  4.7 Security architecture
          Access token 15 minutes; refresh token 30 days, stored hashed, rotated on use, reuse
          detection.
          Argon2id for passwords; OTP hashed with HMAC and a server secret.
          Login and OTP routes have strict rate limits and lockouts.
          Generic error messages for account existence checks.
          CORS limited to known frontend origins; security headers set.
          Backups encrypted; secrets in environment or a secret manager.


  4.8 Deployment
  Docker image, MongoDB Atlas (replica set by default), environment-based configuration,
  GitHub Actions running lint, type check and tests, then deploying to a host such as
  Render, Fly.io, or a VPS. Health endpoints /health and /health/ready for monitoring.




                                                                                         Page 15 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




  5. Database Design

  5.1 Modeling decisions (SQL thinking versus MongoDB thinking)

     Decision                               Choice                                    Reason

     Users and groups                       Separate collections, linked by           Many-to-many with a role
                                             memberships

     Contributions                          Own collection, referenced                Grows without limit, so never
                                                                                      embedded

     Repayment                              Embedded in the loan                      Small, always read with the loan
     schedule

     Group summary                          Cached inside the group, updated          Fast dashboards
     totals                                 atomically

     Audit logs                             Own collection, append-only               Grows fast, separate retention

     IDs                                    MongoDB ObjectId internally               Standard



  5.2 Entity relationship diagram (ERD)

       users 1 ───────< memberships >─────── 1 groups
           |                                          |                       |
           |                                          |                       +───< loans
           |                                          |                       |
           |                                          +───< contributions >┘ (group_id)
           |                                          |
           |                                          +───< loans >───< repayments
           |
           +───< otp_codes
           +───< refresh_tokens
           +───< audit_logs (actor)
           +───< idempotency_keys


  Crow's-foot reading: 1 ───< N means one to many.


     Relationship                                         Cardinality             Notes

     users to memberships                                 1 to N                  A user can be in many groups




                                                                                                                 Page 16 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     Relationship                                        Cardinality           Notes

     groups to memberships                               1 to N                A group has many members

     users to groups                                     N to M through        Role stored on the membership
                                                         memberships

     memberships to                                      1 to N                Each entry belongs to one
     contributions                                                             membership and one period

     groups to contributions                             1 to N                Denormalized group_id for fast
                                                                               queries

     memberships to loans                                1 to N                A member can have many loans
                                                                               over time

     loans to repayments                                 1 to N                Repayments reduce the loan
                                                                               balance

     contributions to                                    1 to 0..1             A reversal links to the original
     contributions                                                             through reverses_id

     users to otp_codes,                                 1 to N                Security records
     refresh_tokens

     users to audit_logs                                 1 to N                The actor of each action



  5.3 Indexes

     Collection                            Index                                       Purpose

     users                                  phone unique                               No duplicate accounts, fast
                                                                                       login

     users                                  email unique, partial (only when           Optional unique email
                                           present)

     memberships                            (group_id, user_id) unique                 One membership per user
                                                                                       per group

     memberships                            (user_id, status)                          List my groups

     memberships                            (group_id) partial unique where role       Exactly one president
                                           = president and status = active




                                                                                                                  Page 17 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     Collection                            Index                                   Purpose

     memberships                            (group_id) partial unique where role   At most one treasurer
                                           = treasurer and status = active

     contributions                          (group_id, period, membership_id)      Expected versus paid

     contributions                          (membership_id, paid_at)               Member statement

     loans                                  (group_id, status)                     Pot and overdue checks

     loans                                  (membership_id, status)                Member loan checks

     repayments                             (loan_id, paid_at)                     Loan history

     otp_codes                              expires_at TTL                         Automatic cleanup

     otp_codes                              (phone, purpose)                       Lookup and rate checks

     refresh_tokens                         token_hash unique, expires_at TTL      Rotation and cleanup

     audit_logs                             (group_id, created_at) desc            Timeline

     idempotency_keys                       (user_id, key) unique, created_at      Safe retries
                                           TTL 24h



  5.4 Transaction and concurrency strategy
          Recording a contribution, a repayment or a loan decision runs inside a transaction that
          also updates cached totals and writes the audit entry.
          Loan approval checks the available pot with a conditional atomic update, so two
          approvals cannot both spend the same money.
          Idempotency keys make retries harmless.



  6. Data Dictionary
  Types: ObjectId , string , int (integers, RWF for money), bool , date (UTC datetime),
   object , array . R means required.




                                                                                                           Page 18 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




  6.1 users

     Field                                        Type                   R       Description and rules

     _id                                          ObjectId               R       Primary key

     full_name                                    string                 R       2 to 100 characters

     phone                                        string                 R       Normalized +2507XXXXXXXX , unique

     phone_verified                               bool                   R       Default false

     phone_verified_at                            date                           Set on OTP success

     email                                        string                         Lowercase, unique when present

     email_verified                               bool                   R       Default false

     password_hash                                string                 R       Argon2id hash, never returned by the API

     preferred_language                           string                 R       rw , en or fr ; default rw

     is_active                                    bool                   R       Default true

     is_platform_admin                            bool                   R       Default false

     consent                                      object                 R       { version, accepted_at } for the privacy
                                                                                 notice

     failed_login_count                           int                    R       For lockout, default 0

     locked_until                                 date                           Temporary lockout

     last_login_at                                date

     created_at,                                  date                   R       UTC
     updated_at

     deleted_at                                   date                           Set on anonymization



  6.2 groups

     Field                                            Type                   R     Description and rules

     _id                                              ObjectId               R

     name                                             string                 R     3 to 80 characters



                                                                                                                            Page 19 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     Field                                            Type               R       Description and rules

     description                                      string                     Up to 500 characters

     district, sector                                 string                     Rwandan administrative location (optional,
                                                                                 informational)

     default_contribution_rwf                         int                R       100 to 100,000,000

     frequency                                        string             R       weekly , biweekly , monthly

     contribution_day                                 int                R       Weekday 1 to 7 or day of month 1 to 28

     loan_interest_bp                                 int                R       Basis points per month, 0 to 5000

     max_loan_multiple                                int                        Loan limit as a multiple of a member's total
                                                                                 contributions

     status                                           string             R       active , suspended , closed

     totals                                           object             R       Cached: contributed_rwf ,
                                                                                 loaned_out_rwf , repaid_principal_rwf ,
                                                                                 interest_earned_rwf , available_rwf

     rules_version                                    int                R       Incremented on rule changes

     created_by                                       ObjectId           R       Founding user

     created_at, updated_at                           date               R



  6.3 memberships

     Field                                                  Type             R      Description and rules

     _id                                                    ObjectId         R

     group_id                                               ObjectId         R      Reference to groups

     user_id                                                ObjectId                Null while only invited and no account
                                                                                    exists

     invited_phone                                          string                  Normalized phone of the invitee

     role                                                   string           R       president , treasurer , member

     status                                                 string           R       invited , active , suspended , left




                                                                                                                           Page 20 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     Field                                                  Type             R      Description and rules

     suggested_contribution_rwf                             int                     Overrides the group default

     joined_at                                              date

     left_at                                                date

     added_by                                               ObjectId         R      Leader who added the member

     created_at, updated_at                                 date             R



  6.4 contributions (append-only ledger)

     Field                               Type                R           Description and rules

     _id                                 ObjectId            R

     group_id                            ObjectId            R

     membership_id                       ObjectId            R

     period                              string              R           Example 2027-03 (monthly) or 2027-W10
                                                                         (weekly)

     amount_rwf                          int                 R           Positive; negative only for reversal entries

     paid_at                             date                R           Not in the future

     method                              string              R           cash , mtn_momo , airtel_money , bank

     reference                           string                          Transaction id or receipt number, up to 64
                                                                         characters

     type                                string              R           payment or reversal

     reverses_id                         ObjectId                        Set when type = reversal

     recorded_by                         ObjectId            R           Treasurer user id

     disputed                            bool                R           Default false

     dispute_note                        string                          Member's note

     idempotency_key                     string                          Prevents duplicates




                                                                                                                        Page 21 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     Field                               Type                R           Description and rules

     created_at                          date                R           No updated_at : the record never changes (except
                                                                         dispute flag)



  6.5 loans

     Field                                          Type                 R     Description and rules

     _id                                            ObjectId             R

     group_id,                                      ObjectId             R
     membership_id

     principal_rwf                                  int                  R     Positive

     interest_bp                                    int                  R     Snapshot of the group rate at approval

     term_months                                    int                  R     1 to 36

     purpose                                        string                     Up to 300 characters

     status                                         string               R      requested , approved , rejected ,
                                                                                disbursed , repaid , overdue , written_off

     schedule                                       array                      Items: { due_date, principal_rwf,
                                                                               interest_rwf, paid_rwf }

     total_due_rwf                                  int                        Principal plus interest

     outstanding_rwf                                int                        Remaining balance

     decided_by                                     ObjectId                   Approver (must not be the borrower)

     decided_at                                     date

     decision_reason                                string                     Required on rejection

     disbursed_at                                   date

     requested_at,                                  date                 R
     updated_at




                                                                                                                        Page 22 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




  6.6 repayments (append-only)

     Field                                                      Type             R        Description and rules

     _id                                                        ObjectId         R

     loan_id, group_id,                                         ObjectId         R
     membership_id

     amount_rwf                                                 int              R        Positive; not above the
                                                                                          outstanding balance

     principal_part_rwf,                                        int              R        Split of the payment
     interest_part_rwf

     paid_at                                                    date             R

     method, reference                                          string                    As in contributions

     type, reverses_id                                          string,                   payment or reversal
                                                                ObjectId

     recorded_by                                                ObjectId         R

     idempotency_key                                            string

     created_at                                                 date             R



  6.7 otp_codes

     Field                       Type                 R           Description and rules

     _id                         ObjectId             R

     phone                       string               R           Normalized

     purpose                     string               R            verify_phone , reset_password , change_phone

     code_hash                   string               R           HMAC of the code

     attempts                    int                  R           Max 5

     expires_at                  date                 R           Now plus 5 minutes; TTL index

     consumed_at                 date                             Single use




                                                                                                                    Page 23 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     Field                       Type                 R           Description and rules

     request_ip                  string                           For abuse control

     created_at                  date                 R



  6.8 refresh_tokens

     Field                                   Type                R           Description and rules

     _id                                     ObjectId            R

     user_id                                 ObjectId            R

     token_hash                              string              R           Hash only; unique

     family_id                               string              R           Groups rotated tokens for reuse detection

     used_at, revoked_at                     date

     expires_at                              date                R           TTL index

     user_agent, ip                          string                          Session info

     created_at                              date                R



  6.9 audit_logs (append-only)

     Field                                  Type                         R        Description and rules

     _id                                    ObjectId                     R

     actor_user_id                          ObjectId                     R        Who acted

     group_id                               ObjectId                              Null for account-level actions

     action                                 string                       R        Example contribution.recorded ,
                                                                                  loan.approved

     entity_type,                           string,                      R        What was affected
     entity_id                              ObjectId

     before, after                          object                                Snapshots with sensitive fields removed

     ip, request_id                         string



                                                                                                                            Page 24 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     Field                                  Type                         R   Description and rules

     created_at                             date                         R



  6.10 idempotency_keys

     Field                        Type                R           Description and rules

     _id                          ObjectId            R

     user_id                      ObjectId            R

     key                          string              R           Client-supplied, unique per user

     request_hash                 string              R           Detects the same key used with a different body

     response                     object              R           Stored status and body

     created_at                   date                R           TTL 24 hours



  6.11 Enumerations

     Enum                                  Values

     role                                  president, treasurer, member

     membership status                     invited, active, suspended, left

     group status                          active, suspended, closed

     frequency                             weekly, biweekly, monthly

     payment method                        cash, mtn_momo, airtel_money, bank

     loan status                           requested, approved, rejected, disbursed, repaid,
                                           overdue, written_off

     otp purpose                           verify_phone, reset_password, change_phone




  7. Open Decisions (to settle before or during development)
     1. Which SMS provider (compare delivery on MTN and Airtel Rwanda, price, API quality).



                                                                                                                    Page 25 of 26
Ikimina API: SRS, Technical Proposal, Architecture and Database Design




     2. Whether loan interest is simple monthly (our default) or reducing balance.
     3. Whether a group may have a vice president or secretary role in a later version.
     4. Language for user-facing messages in v1 (English first, Kinyarwanda next).
     5. Hosting choice and legal registration check before public launch.


  8. Next Step
  Start Phase 0: repository, configuration, MongoDB replica set and the health endpoint.
  Then Phase 1: the Rwandan phone validator and the user model, written by you, reviewed
  by me.




                                                                                          Page 26 of 26
