# ISI Gestion Pédagogique — Changelog

Changes made to the project in this working session, grouped by feature.

---

## 1. Logo not showing on printed documents (bug fix)

**Problem:** the institute logo, uploaded via *Settings*, never appeared on any printed document in production.

**Cause:** `pedagogical/urls.py` only served `MEDIA_URL` when `DEBUG=True`. WhiteNoise (used for static files) does not serve `MEDIA_ROOT`, so in production the logo file returned a 404.

**Fix:** `MEDIA_URL` is now served in every environment.

- `pedagogical/urls.py`

---

## 2. Default PV (محضر مداولات) signatories

New settings-managed list of default committee members (e.g. institute directors) that get proposed — editable — every time a session's delegation committee is built. The trainer and the client's company representative are **never** pulled from this list; they're always entered fresh on each PV.

- **New model:** `core.PVDefaultSignatory` (الاسم و اللقب, الصفة, ordre, actif)
- **New admin registration:** `core/admin.py`
- **New Settings sub-pages:** list / add / edit / delete
  - `templates/core/pv_signatory_list.html`
  - `templates/core/pv_signatory_form.html`
  - `templates/core/pv_signatory_confirm_delete.html`
  - Linked from `templates/core/settings.html`
- **New views/urls:** `core/views.py`, `core/urls.py`, `core/forms.py` (`PVDefaultSignatoryForm`)
- **Migration:** `core/migrations/0003_pvdefaultsignatory.py`

---

## 3. Dynamic PV committee form

The committee (comité de délibération) form no longer uses a single free-text textarea. It's now a dynamic name + الصفة row list:

- Pre-filled with: active `PVDefaultSignatory` rows (Settings) + the session's trainer (live, never stored as a default) + one blank row for the client's company representative (always typed fresh).
- Add/remove rows client-side (JS), minimum 2 members enforced on save.

**Changed:**
- `documents/forms.py` — `CommitteeForm` rewritten to parse `member_name[]` / `member_role[]` pairs into `[{"name":..., "role":...}, ...]`
- `documents/views.py` — `set_committee_view` builds the pre-filled rows
- `templates/documents/committee_form.html` — rebuilt UI

---

## 4. محضر مداولات نهاية التكوين (Deliberation report / PV) — print template rebuilt

Rebuilt to match the reference EEMS paper form field-for-field:

- رقم, تاريخ, مستوى التأهيل, الاختصاص, الزبون, رمز التخصص
- تاريخ بداية/نهاية التكوين
- **عدد المتربصين — منهم بنات** (new, see §6)
- عدد الحضور, عدد الغياب, عدد الناجحين
- الوصي على التكوين السيد
- Committee table now renders each member's **name + الصفة** (previously name only)

**Changed:** `templates/documents/print/deliberation_report.html` (full rebuild)

---

## 5. الجدول الاسمي النهائي (Nominal list) — print template rebuilt

Rebuilt to match the second reference photo exactly:

- Header block: مجال التكوين, الاختصاص, الزبون, مدة التكوين (with dual-form "يومين" handling), تاريخ بداية/نهاية التكوين الحضوري, اسم ولقب الأستاذ المكون
- Table columns: م / اسم ولقب المتربص بالعربية (1) / بالفرنسية (2) / تاريخ الميلاد ومكان الميلاد (3) / علامة الامتحان / ملاحظة

**Changed:** `templates/documents/print/nominal_list.html` (full rebuild)

---

## 6. Gender field on participants (`منهم بنات` count)

- **New field:** `Participant.gender` (Homme/Femme, optional)
- **New property:** `Session.female_count` (feeds the PV's "منهم بنات" line) and `Session.passed_count`
- Wired into: participant form/template, admin fieldsets
- **Migration:** `formations/migrations/0006_participant_gender.py`

---

## 7. Exam scoring consolidated to once-per-formation

**Problem:** théorique/pratique marks could be entered separately on every day-session of a multi-day formation.

**Fix:**
- `session_scores` (théorique/pratique entry) is now restricted to the **primary session only** — visiting it on a child/day session redirects to the primary session with an explanatory message.
- `ExamScoreForm`'s exam mark now **defaults to the average** of théorique + pratique (when both are set), while staying fully editable/overridable.
- Explanatory note added to the exam-scores screen.

**Changed:** `formations/views.py`, `formations/forms.py`, `templates/formations/session_exam_scores.html`

---

## 8. Blank ("vierge") vs. auto-filled print mode

The candidate information list and the daily presence sheet can now each be printed two ways:

- **Auto-filled** (existing behaviour) — populated from registered participants.
- **Vierge** (new) — every row is blank, sized to the session's capacity (or 12 rows minimum), for on-site manual completion by the trainer/candidates. Available even before any participant is registered.

Triggered via `?mode=blank`; a "Vierge" button was added next to the existing "Générer" button on the documents dashboard.

**Changed:** `documents/views_print.py`, `documents/views.py`, `templates/documents/print/candidate_list.html`, `templates/documents/print/attendance_sheet.html`, `templates/documents/dashboard.html`

---

## 9. Attestation — dual-mode name display (French/Latin vs. Arabic)

**Problem:** the attestation always showed both a French/Latin name block and an Arabic name block, and French names were mandatory.

**Fix:**
- `Participant.first_name` / `last_name` are now optional (matching the already-optional Arabic pair).
- **Validation rule (enforced in `Participant.clean()`, applied by every form):** at least one *complete* name pair — French **or** Arabic — is required. Neither language is individually mandatory; a half-filled pair (e.g. only a prénom) doesn't count.
- New `Participant.has_fr_name` / `has_ar_name` properties; `full_name` now falls back to the Arabic name when no Latin name exists.
- The attestation print shows **only** the block(s) with actual data:
  - French only → French block only
  - Arabic only → Arabic block only
  - Both → both blocks (previous behaviour)
- Two other prints (`attendance_sheet.html`, `evaluation_list.html`) were fixed to fall back to the Arabic name instead of showing a blank name for Arabic-only participants.

**Changed:**
- `formations/models.py` — `Participant.first_name`/`last_name` → `blank=True`; new properties; `clean()` validation
- `formations/forms.py` — `ParticipantForm.clean()` updated (duplicate-name checks per language)
- `templates/formations/participant_form.html` — removed "required" markers, added explanatory note
- `documents/certificate_render.py` — added `HAS_FR` / `HAS_AR` flags to the template context
- `templates/documents/print/_certificate_body.html` — French/Arabic boxes now conditionally rendered
- `templates/documents/print/attendance_sheet.html`, `templates/documents/print/evaluation_list.html` — name fallback
- **Migration:** `formations/migrations/0007_alter_participant_first_name_and_more.py`

*Note: the unused box is simply hidden when only one language is provided — the layout doesn't reflow/widen the remaining box, since positioning is pixel-coordinate-based over a background image.*

---

## 10. Smart room / trainer / equipment double-booking warnings

**New:** when creating or editing a session, if the chosen room, trainer, or any selected equipment is already booked on another (non-cancelled/non-archived) session with overlapping dates, the form shows a **soft, non-blocking warning** instead of refusing to save:

- Lists each conflicting session (with a link to it)
- Offers a quick action to add another room / trainer / equipment (opens in a new tab)
- A **"Enregistrer quand même"** button lets the user save anyway

**New:** `Session.equipment` (ManyToMany to `resources.Equipment`) — equipment reservation per session didn't exist before; it was needed to detect equipment conflicts at all.

**Changed:**
- `formations/models.py` — new `Session.equipment` field
- `formations/utils.py` — new `check_scheduling_conflicts()` / `has_scheduling_conflicts()` helpers
- `formations/forms.py` — `SessionForm` includes the `equipment` field
- `formations/views.py` — `session_create` / `session_edit` implement the confirm-anyway flow
- `templates/formations/session_form.html` — warning banner, equipment checklist, confirm button
- **Migration:** `formations/migrations/0008_session_equipment.py`

*Verified end-to-end with a live request/response test: posting a conflicting session shows the banner and does not save; resubmitting with confirmation saves it correctly.*

---

## 11. Removed dead code

`documents/attestation_docx.py` and its orphaned template `documents/doc_templates/attestation_template.docx` were removed. This module (docx placeholder substitution → LibreOffice PDF conversion → QR stamping) was never imported or called anywhere — `documents/utils.py` already documented that attestations are generated through the HTML print pipeline (`certificate_render.py` + `certificate_layout.py` + `documents/print/attestation.html`) instead. No functional change; cleanup only.

---

## 12. Room ↔ equipment relationship, allocation history & guardrails

Room equipment was previously just free-text (`equipment_notes`). It's now a relational multi-select backed by the existing `Equipment.room` FK, with a full allocation history and cross-room usage guardrails.

- **New model:** `resources.EquipmentAllocation` — audit log of every time an equipment item is assigned to a room (home assignment, `session=None`) or checked into a session (`session=<Session>`), with `allocated_at`/`allocated_by` and `released_at`/`released_by`. `Equipment.active_allocation()` returns the current active **session-based** checkout (if any); a plain home-room assignment never counts as a lock — it's exactly what makes an item eligible to be borrowed elsewhere.
- **Guardrail:** `Equipment.is_locked_elsewhere()` / `formations.utils.equipment_is_blocked()` block attaching an equipment item to a session (or reassigning its home room) while it still has an *active, unreleased session checkout* elsewhere. It must be released (unchecked from that session, or that session archived/cancelled) first.
- **Room ↔ equipment multi-select:** `RoomForm.equipment` (checkbox multi-select) replaces relying on free-text for movable/trackable gear; `equipment_notes` is kept only for untracked fixed fittings (AC, outlets…). Saving a room applies the diff to `Equipment.room` and logs it to `EquipmentAllocation`; equipment already homed in another room isn't offered as a choice (must be released there first).
- **New page:** `resources:room_detail` — room's homed equipment + its allocation history table (session or home-room reassignment, allocated/released timestamps).
- **Auto-import on session creation:** picking a room now inherently pre-checks that room's homed equipment on the session form (AJAX `formations:room_equipment_api`, plus server-side prefill when a formation's last session is reused).
- **Session detail — check/uncheck usage:** new "Équipements" card lets managers toggle which of the room's equipment is actually used in that session (`formations:session_equipment_update`), and shows a soft-warning suggestion list of equipment **idle** in other rooms on the session's dates (i.e. not in any other active, overlapping session and not actively checked out) that could be added here — guardrail-checked on submit, so a race with another session can't silently steal it.

**New/changed:**
- `resources/models.py` — `EquipmentAllocation` model; `Room.available_equipment`; `Equipment.active_allocation()` / `is_locked_elsewhere()`
- `resources/forms.py` — `RoomForm.equipment` multi-select
- `resources/views.py` — `room_detail`; `room_create`/`room_edit` apply the diff via `_apply_room_equipment()`
- `resources/urls.py` — `rooms/<pk>/`
- `resources/admin.py` — `EquipmentAllocationAdmin`
- `formations/utils.py` — `equipment_is_blocked()`, `get_idle_equipment()`
- `formations/views.py` — `session_detail` (room/idle equipment context), `session_equipment_update`, `room_equipment_api`, `_log_equipment_allocations()` wired into `session_create`/`session_edit`
- `formations/urls.py` — `sessions/<pk>/equipment/`, `api/room/<pk>/equipment/`
- `templates/resources/room_form.html` — equipment multi-select section
- `templates/resources/room_detail.html` — new template
- `templates/resources/room_list.html` — room name now links to the detail page
- `templates/formations/session_form.html` — room→equipment auto-check JS
- `templates/formations/session_detail.html` — new "Équipements" card (toggle + idle suggestions)
- `core/management/commands/seed_db.py` — more equipment spread across rooms (idle-equipment demo data), seeded allocation history, one seeded session with reserved equipment
- **Migration:** `resources/migrations/0002_equipment_allocation.py`

*Verified end-to-end (Django test client, live DB): idle-equipment detection correctly excludes locally-assigned (non-room) equipment and equipment already booked/actively checked out elsewhere; the guardrail blocks adding an actively-checked-out item to a second overlapping session both from the session-detail toggle and from the room form, and releasing the original allocation makes it selectable/idle again; room equipment reassignment correctly releases the old allocation and logs the new one.*

---

## Migrations added this session

```
core/migrations/0003_pvdefaultsignatory.py
formations/migrations/0006_participant_gender.py
formations/migrations/0007_alter_participant_first_name_and_more.py
formations/migrations/0008_session_equipment.py
resources/migrations/0002_equipment_allocation.py
```

Run `python manage.py migrate` after deploying this version.

## Verification performed

- `python manage.py check` — 0 issues after every change
- Full `migrate` from a clean database — all migrations apply without error
- Live request/response tests (Django test client) for:
  - Session create/edit conflict-warning flow (warning shown → blocked → confirm → saved)
  - `ParticipantForm` validation (no name / Arabic-only / French-only)
  - Attestation dual-mode rendering (Arabic-only data → French block absent, Arabic block present)
  - Room ↔ equipment multi-select save, home-room reassignment, and allocation-history logging
  - Cross-room equipment guardrail (block/skip while actively checked out elsewhere; allowed again once released)
  - Idle-equipment suggestions on the session detail page
