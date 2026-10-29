# Sync ISI <-> site web

ISI (LAN) initiates every exchange; the website never calls ISI. Requests are signed
with HMAC-SHA256 (`X-Sync-Timestamp`, `X-Sync-Signature`, 5-minute window).

## Setup
1. Choose a long random secret. Set the SAME value on both servers:
   `SYNC_SHARED_SECRET=...` (if unset, `INSTITUTE_PING_SECRET` is used, so the
   existing secret already works). Empty = sync off (formations queue up meanwhile).
2. Deploy the website bridge app, then on **both** servers: `python manage.py migrate`
   and restart.
3. ISI cron (every 3 min):
   `*/3 * * * * cd /path/to/isi_pedagogical_webapp && venv/bin/python manage.py sync_main_site >> logs/sync.log 2>&1`
4. Optional settings (env vars)
   * ISI: `SYNC_PARTICULIERS_CLIENT_NAME` ("Particuliers"), `SYNC_SEED_STATUSES` ("accepted,confirmed"),
     `SYNC_INITIAL_BACKFILL` (0), `SYNC_AUTO_FULL_HOURS` (24, 0 = off), `SYNC_AUTOFLUSH` (1).
   * Website: `SYNC_DEFAULT_SESSION_SLUG` ("catalogue-eems"), `SYNC_NEW_OFFERINGS_ACTIVE` (0).

## What flows
* **Formation (ISI -> site)**: create/edit a Formation -> queued -> `Offering` created (or an
  existing one with same code+title adopted) with an auto "fiche technique". New offerings are
  **hidden** (support@ gets an email; filter "مزامنة ISI" in the offerings admin) until staff review them and publish (Admin > Liens formations ISI > "Publier";
  `SYNC_NEW_OFFERINGS_ACTIVE=1` publishes at once). Later ISI edits only update fields ISI
  changed; fiche text or visibility edited on the website is never overwritten.
  A formation without a specialty has no code: it is reported once as failed on `/sync/` and
  re-queued automatically when saved again.
* **Formation deleted (ISI -> site)**: the offering is hidden, never deleted (it may have
  enrollments). If ISI later recreates the same code+title, the hidden offering is re-adopted.
* **Clients (site -> ISI)**: active website clients only. Individuals -> shared "Particuliers"
  client; enterprises -> ISI client (matched by RC, NIF, then name before creating).
* **Participants (site -> ISI)**: company roster / individual enrollments become client-level
  "Participants inscrits via le site". Enrollments `accepted`/`confirmed` are added to the
  earliest *planned* session of that client + formation with free places — when the session is
  created, on each sync, or via the "Depuis le site (N)" button on the session page.
  Pending/contacted ones can be added by hand with "+ non validés (N)", or automatically by
  widening `SYNC_SEED_STATUSES`.
* Website edits update the linked ISI participant (only the fields the website changed).
  A person removed on the website is removed from ISI only if the session is still planned and
  they have no marks/certificate; otherwise they are kept and flagged "Retiré du site — à vérifier"
  on the client page and counted on `/sync/`.
* The website contact person stored by the web sign-up form is marked explicitly
  (`bridge.ContactPlaceholder`) and never sent as a trainee; existing ones were marked once by migration.

## Commands
`sync_main_site [--push-only|--pull-only] [--full] [--backfill]`
* first run starts "from now" and records a baseline: website clients that already existed are
  NOT imported. To import them: the "Importer les clients existants" button on `/sync/`,
  `--backfill`/`--full`, or `SYNC_INITIAL_BACKFILL=1` before the first run (matched to existing
  ISI clients by RC, NIF, then name).
* Missed changes repair themselves: every `SYNC_AUTO_FULL_HOURS` (24 h) the cron run also walks
  all clients ISI knows or created after the baseline (`--repair` does it on demand).

Status page: `/sync/` (sidebar "Synchro site web").
